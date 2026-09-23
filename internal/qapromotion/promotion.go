// Package qapromotion owns a resumable DEV/QA-only runtime promotion flow.
// It is not part of the Execution Node protocol or normal project lifecycle.
package qapromotion

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"platform-installer/internal/executionbundle"
	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
)

const (
	stageBuilt     = "BUILT"
	stagePublished = "PUBLISHED"
	stageActivated = "ACTIVATED"
)

// Request deliberately requires the current lock pair.  The tool never
// selects a runtime or silently changes a project to a newer bundle.
type Request struct {
	CheckpointRoot         string
	CacheRoot              string
	ProjectRoot            string
	ExpectedArtifactDigest string
	ExpectedCatalogDigest  string
	PublishedDigest        string
	RuntimeInput           string
	BundleVersion          string
	Node                   executionnode.Node
}

// Result is safe to print in QA logs. It contains immutable identities only.
type Result struct {
	Resumed            bool
	ArtifactDigest     string
	CatalogDigest      string
	ProjectRevision    string
	PreparationChanged bool
}

type checkpoint struct {
	ProjectRoot            string `json:"projectRoot"`
	ExpectedArtifactDigest string `json:"expectedArtifactDigest"`
	ExpectedCatalogDigest  string `json:"expectedCatalogDigest"`
	NewArtifactDigest      string `json:"newArtifactDigest"`
	NewCatalogDigest       string `json:"newCatalogDigest"`
	Stage                  string `json:"stage"`
}

// Dependencies isolate the external acquisition/activation boundaries. They
// are intentionally small so the state machine can be tested without SSH.
type Dependencies struct {
	Build        func(context.Context, executionnode.Node, string, string) (executionbundle.Verified, error)
	Publish      func(context.Context, executionbundle.Verified) (executionbundle.Verified, error)
	CleanupBuild func(executionbundle.Verified)
	Prepare      func(context.Context, executionnode.Node, executionbundle.Verified) (executionnode.Result, error)
	UpdateLocks  func(context.Context, installer.RuntimeLockSetUpdateRequest) (installer.RuntimeLockSetUpdateResult, error)
	ReadLocks    func(context.Context, string, executionbundle.Verified) (artifactDigest, catalogDigest string, err error)
}

// Promote builds and publishes at most once per checkpoint, then safely
// retries activation and lock rebinding. A published bundle is sufficient to
// resume after the old cache entry has been pruned by immutable publication.
func Promote(ctx context.Context, request Request, dependencies Dependencies) (Result, error) {
	if err := validateRequest(request, dependencies); err != nil {
		return Result{}, err
	}
	path, err := checkpointPath(request.CheckpointRoot, request.ProjectRoot)
	if err != nil {
		return Result{}, err
	}
	state, found, err := readCheckpoint(path)
	if err != nil {
		return Result{}, err
	}
	resumed := found
	var bundle executionbundle.Verified
	if !found {
		if request.PublishedDigest != "" {
			bundle, err = resolvePublishedBundle(request.CacheRoot, request.PublishedDigest)
			if err != nil {
				return Result{}, err
			}
		} else {
			bundle, err = dependencies.Build(ctx, request.Node, request.RuntimeInput, request.BundleVersion)
			if err != nil {
				return Result{}, fmt.Errorf("QA_RUNTIME_PROMOTION_BUILD_FAILED: %w", err)
			}
			state = checkpoint{ProjectRoot: request.ProjectRoot, ExpectedArtifactDigest: request.ExpectedArtifactDigest, ExpectedCatalogDigest: request.ExpectedCatalogDigest, NewArtifactDigest: bundle.Digest, NewCatalogDigest: bundle.Manifest.CatalogDigest, Stage: stageBuilt}
			if err := writeCheckpoint(path, state); err != nil {
				cleanupBuild(dependencies, bundle)
				return Result{}, err
			}
			bundle, err = publishBuilt(ctx, dependencies, bundle)
			if err != nil {
				return Result{}, err
			}
		}
		state = checkpoint{ProjectRoot: request.ProjectRoot, ExpectedArtifactDigest: request.ExpectedArtifactDigest, ExpectedCatalogDigest: request.ExpectedCatalogDigest, NewArtifactDigest: bundle.Digest, NewCatalogDigest: bundle.Manifest.CatalogDigest, Stage: stagePublished}
		if err := writeCheckpoint(path, state); err != nil {
			return Result{}, err
		}
	} else {
		if !sameRequest(state, request) {
			return Result{}, errors.New("QA_RUNTIME_PROMOTION_CHECKPOINT_MISMATCH")
		}
		bundle, err = resolvePublishedBundle(request.CacheRoot, state.NewArtifactDigest)
		if err != nil && state.Stage == stageBuilt {
			bundle, err = dependencies.Build(ctx, request.Node, request.RuntimeInput, request.BundleVersion)
			if err != nil || bundle.Digest != state.NewArtifactDigest || bundle.Manifest.CatalogDigest != state.NewCatalogDigest {
				cleanupBuild(dependencies, bundle)
				return Result{}, errors.New("QA_RUNTIME_PROMOTION_REBUILD_MISMATCH")
			}
			bundle, err = publishBuilt(ctx, dependencies, bundle)
			if err != nil {
				return Result{}, err
			}
			state.Stage = stagePublished
			if err := writeCheckpoint(path, state); err != nil {
				return Result{}, err
			}
		}
		if err != nil {
			return Result{}, err
		}
		if bundle.Manifest.CatalogDigest != state.NewCatalogDigest {
			return Result{}, errors.New("QA_RUNTIME_PROMOTION_PUBLISHED_BUNDLE_MISMATCH")
		}
	}

	prepared, err := dependencies.Prepare(ctx, request.Node, bundle)
	if err != nil {
		return Result{}, fmt.Errorf("QA_RUNTIME_PROMOTION_PREPARE_FAILED: %w", err)
	}
	if prepared.State != executionnode.Ready || prepared.Runtime.BundleDigest != bundle.Digest {
		return Result{}, errors.New("QA_RUNTIME_PROMOTION_PREPARE_UNVERIFIED")
	}
	state.Stage = stageActivated
	if err := writeCheckpoint(path, state); err != nil {
		return Result{}, err
	}

	artifactDigest, catalogDigest, err := dependencies.ReadLocks(ctx, request.ProjectRoot, bundle)
	if err != nil {
		return Result{}, err
	}
	var revision string
	if artifactDigest == bundle.Digest && catalogDigest == bundle.Manifest.CatalogDigest {
		revision, err = installer.ProjectRevision(request.ProjectRoot)
		if err != nil {
			return Result{}, err
		}
	} else if artifactDigest == request.ExpectedArtifactDigest && catalogDigest == request.ExpectedCatalogDigest {
		baseRevision, revisionErr := installer.ProjectRevision(request.ProjectRoot)
		if revisionErr != nil {
			return Result{}, revisionErr
		}
		updated, updateErr := dependencies.UpdateLocks(ctx, installer.RuntimeLockSetUpdateRequest{ProjectRoot: request.ProjectRoot, ExpectedProjectRevision: baseRevision, ExpectedOldArtifactDigest: request.ExpectedArtifactDigest, ExpectedOldCatalogDigest: request.ExpectedCatalogDigest, NewDigest: bundle.Digest, NewBundleRoot: bundle.Root})
		if updateErr != nil {
			return Result{}, fmt.Errorf("QA_RUNTIME_PROMOTION_LOCK_UPDATE_FAILED: %w", updateErr)
		}
		revision = updated.NewProjectRevision
	} else {
		return Result{}, errors.New("QA_RUNTIME_PROMOTION_PROJECT_LOCKS_UNEXPECTED")
	}

	artifactDigest, catalogDigest, err = dependencies.ReadLocks(ctx, request.ProjectRoot, bundle)
	if err != nil || artifactDigest != bundle.Digest || catalogDigest != bundle.Manifest.CatalogDigest {
		return Result{}, errors.New("QA_RUNTIME_PROMOTION_REOPEN_FAILED")
	}
	if err := os.Remove(path); err != nil && !errors.Is(err, os.ErrNotExist) {
		return Result{}, fmt.Errorf("QA_RUNTIME_PROMOTION_CHECKPOINT_REMOVE_FAILED: %w", err)
	}
	return Result{Resumed: resumed, ArtifactDigest: bundle.Digest, CatalogDigest: bundle.Manifest.CatalogDigest, ProjectRevision: revision, PreparationChanged: prepared.Changed}, nil
}

func validateRequest(request Request, dependencies Dependencies) error {
	if request.CheckpointRoot == "" || request.CacheRoot == "" || request.ProjectRoot == "" || request.ExpectedArtifactDigest == "" || request.ExpectedCatalogDigest == "" || dependencies.Build == nil || dependencies.Publish == nil || dependencies.Prepare == nil || dependencies.UpdateLocks == nil || dependencies.ReadLocks == nil || (request.PublishedDigest == "" && (request.RuntimeInput == "" || request.BundleVersion == "")) {
		return errors.New("QA_RUNTIME_PROMOTION_INPUT_INVALID")
	}
	return nil
}

func sameRequest(state checkpoint, request Request) bool {
	return state.ProjectRoot == request.ProjectRoot && state.ExpectedArtifactDigest == request.ExpectedArtifactDigest && state.ExpectedCatalogDigest == request.ExpectedCatalogDigest && (state.Stage == stageBuilt || state.Stage == stagePublished || state.Stage == stageActivated)
}

func checkpointPath(root, projectRoot string) (string, error) {
	abs, err := filepath.Abs(projectRoot)
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256([]byte(filepath.Clean(abs)))
	return filepath.Join(root, "runtime-promotions", hex.EncodeToString(sum[:])+".json"), nil
}

func readCheckpoint(path string) (checkpoint, bool, error) {
	content, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return checkpoint{}, false, nil
	}
	if err != nil || len(content) > 4096 {
		return checkpoint{}, false, errors.New("QA_RUNTIME_PROMOTION_CHECKPOINT_INVALID")
	}
	var value checkpoint
	if json.Unmarshal(content, &value) != nil || value.ProjectRoot == "" || value.NewArtifactDigest == "" || value.NewCatalogDigest == "" || (value.Stage != stageBuilt && value.Stage != stagePublished && value.Stage != stageActivated) {
		return checkpoint{}, false, errors.New("QA_RUNTIME_PROMOTION_CHECKPOINT_INVALID")
	}
	return value, true, nil
}

func publishBuilt(ctx context.Context, dependencies Dependencies, bundle executionbundle.Verified) (executionbundle.Verified, error) {
	published, err := dependencies.Publish(ctx, bundle)
	cleanupBuild(dependencies, bundle)
	if err != nil {
		return executionbundle.Verified{}, fmt.Errorf("QA_RUNTIME_PROMOTION_PUBLISH_FAILED: %w", err)
	}
	if published.Digest != bundle.Digest || published.Manifest.CatalogDigest != bundle.Manifest.CatalogDigest {
		return executionbundle.Verified{}, errors.New("QA_RUNTIME_PROMOTION_PUBLICATION_MISMATCH")
	}
	return published, nil
}

func cleanupBuild(dependencies Dependencies, bundle executionbundle.Verified) {
	if dependencies.CleanupBuild != nil && bundle.Root != "" {
		dependencies.CleanupBuild(bundle)
	}
}

func writeCheckpoint(path string, value checkpoint) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return fmt.Errorf("QA_RUNTIME_PROMOTION_CHECKPOINT_WRITE_FAILED: %w", err)
	}
	content, err := json.Marshal(value)
	if err != nil {
		return err
	}
	temporary, err := os.CreateTemp(filepath.Dir(path), ".promotion-")
	if err != nil {
		return err
	}
	name := temporary.Name()
	if _, err := temporary.Write(append(content, '\n')); err != nil || temporary.Sync() != nil || temporary.Close() != nil {
		_ = temporary.Close()
		_ = os.Remove(name)
		return errors.New("QA_RUNTIME_PROMOTION_CHECKPOINT_WRITE_FAILED")
	}
	if err := os.Chmod(name, 0o600); err != nil {
		_ = os.Remove(name)
		return err
	}
	// Rename has atomic replacement semantics on the supported QA Linux and
	// Windows filesystems. A failure leaves the prior checkpoint intact.
	if err := os.Rename(name, path); err != nil {
		_ = os.Remove(name)
		return fmt.Errorf("QA_RUNTIME_PROMOTION_CHECKPOINT_WRITE_FAILED: %w", err)
	}
	return nil
}

func resolvePublishedBundle(cacheRoot, digest string) (executionbundle.Verified, error) {
	if !strings.HasPrefix(digest, "sha256:") || len(digest) != len("sha256:")+64 {
		return executionbundle.Verified{}, errors.New("QA_RUNTIME_PROMOTION_CHECKPOINT_INVALID")
	}
	root := filepath.Join(cacheRoot, strings.TrimPrefix(digest, "sha256:"))
	verified, err := executionbundle.ValidateRoot(root)
	if err != nil || verified.Digest != digest {
		return executionbundle.Verified{}, errors.New("QA_RUNTIME_PROMOTION_PUBLISHED_BUNDLE_MISSING")
	}
	return verified, nil
}

// ReadLocks uses the existing managed-project reader and never parses or
// mutates canonical Ansible files locally.
func ReadLocks(ctx context.Context, projectRoot string, _ executionbundle.Verified) (string, string, error) {
	if err := ctx.Err(); err != nil {
		return "", "", err
	}
	locks, err := installer.ReadRuntimeLockSet(projectRoot)
	if err != nil {
		return "", "", errors.New("QA_RUNTIME_PROMOTION_PROJECT_OPEN_FAILED")
	}
	return locks.ArtifactDigest, locks.CatalogDigest, nil
}

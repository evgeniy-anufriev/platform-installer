package qapromotion

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"platform-installer/internal/executionbundle"
	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
)

func TestPromoteResumesFromPublishedCheckpointWithoutRebuild(t *testing.T) {
	root := t.TempDir()
	project := filepath.Join(root, "project")
	if err := os.MkdirAll(project, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(project, "project.yml"), []byte("metadata: test\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	cache := filepath.Join(root, "bundle")
	bundle := testBundle(t, cache, "new-catalog")
	request := testRequest(root, project, cache)
	builds, prepares, updates := 0, 0, 0
	currentArtifact, currentCatalog := request.ExpectedArtifactDigest, request.ExpectedCatalogDigest
	dependencies := Dependencies{
		Build: func(context.Context, executionnode.Node, string, string) (executionbundle.Verified, error) {
			builds++
			return bundle, nil
		},
		Publish: func(context.Context, executionbundle.Verified) (executionbundle.Verified, error) { return bundle, nil },
		Prepare: func(context.Context, executionnode.Node, executionbundle.Verified) (executionnode.Result, error) {
			prepares++
			if prepares == 1 {
				return executionnode.Result{}, fmt.Errorf("injected prepare failure")
			}
			return readyResult(bundle), nil
		},
		UpdateLocks: func(_ context.Context, update installer.RuntimeLockSetUpdateRequest) (installer.RuntimeLockSetUpdateResult, error) {
			updates++
			if update.NewDigest != bundle.Digest {
				t.Fatalf("unexpected digest %s", update.NewDigest)
			}
			currentArtifact, currentCatalog = bundle.Digest, bundle.Manifest.CatalogDigest
			return installer.RuntimeLockSetUpdateResult{NewProjectRevision: "sha256:" + strings.Repeat("c", 64)}, nil
		},
		ReadLocks: func(context.Context, string, executionbundle.Verified) (string, string, error) {
			return currentArtifact, currentCatalog, nil
		},
	}
	if _, err := Promote(t.Context(), request, dependencies); err == nil || !strings.Contains(err.Error(), "PREPARE_FAILED") {
		t.Fatalf("first err=%v", err)
	}
	path, err := checkpointPath(request.CheckpointRoot, request.ProjectRoot)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(path); err != nil {
		t.Fatalf("checkpoint missing: %v", err)
	}
	result, err := Promote(t.Context(), request, dependencies)
	if err != nil {
		t.Fatal(err)
	}
	if !result.Resumed || builds != 1 || updates != 1 || result.ArtifactDigest != bundle.Digest {
		t.Fatalf("result=%+v builds=%d updates=%d", result, builds, updates)
	}
	if _, err := os.Stat(path); !os.IsNotExist(err) {
		t.Fatalf("checkpoint remains: %v", err)
	}
}

func TestPromoteRejectsUnexpectedProjectLocksWithoutMutation(t *testing.T) {
	root := t.TempDir()
	project := filepath.Join(root, "project")
	if err := os.MkdirAll(project, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(project, "project.yml"), []byte("metadata: test\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	bundle := testBundle(t, filepath.Join(root, "bundle"), "new-catalog")
	request := testRequest(root, project, filepath.Join(root, "bundle"))
	updates := 0
	_, err := Promote(t.Context(), request, Dependencies{
		Build: func(context.Context, executionnode.Node, string, string) (executionbundle.Verified, error) {
			return bundle, nil
		},
		Publish: func(context.Context, executionbundle.Verified) (executionbundle.Verified, error) { return bundle, nil },
		Prepare: func(context.Context, executionnode.Node, executionbundle.Verified) (executionnode.Result, error) {
			return readyResult(bundle), nil
		},
		UpdateLocks: func(context.Context, installer.RuntimeLockSetUpdateRequest) (installer.RuntimeLockSetUpdateResult, error) {
			updates++
			return installer.RuntimeLockSetUpdateResult{}, nil
		},
		ReadLocks: func(context.Context, string, executionbundle.Verified) (string, string, error) {
			return "sha256:" + strings.Repeat("9", 64), request.ExpectedCatalogDigest, nil
		},
	})
	if err == nil || err.Error() != "QA_RUNTIME_PROMOTION_PROJECT_LOCKS_UNEXPECTED" || updates != 0 {
		t.Fatalf("err=%v updates=%d", err, updates)
	}
}

func TestPromoteFailsClosedWhenPublishedCheckpointBundleWasPruned(t *testing.T) {
	root := t.TempDir()
	project := filepath.Join(root, "project")
	if err := os.MkdirAll(project, 0o700); err != nil {
		t.Fatal(err)
	}
	request := testRequest(root, project, filepath.Join(root, "bundle"))
	path, err := checkpointPath(request.CheckpointRoot, request.ProjectRoot)
	if err != nil {
		t.Fatal(err)
	}
	state := checkpoint{ProjectRoot: request.ProjectRoot, ExpectedArtifactDigest: request.ExpectedArtifactDigest, ExpectedCatalogDigest: request.ExpectedCatalogDigest, NewArtifactDigest: "sha256:" + strings.Repeat("a", 64), NewCatalogDigest: "sha256:" + strings.Repeat("b", 64), Stage: stagePublished}
	if err := writeCheckpoint(path, state); err != nil {
		t.Fatal(err)
	}
	builds := 0
	_, err = Promote(t.Context(), request, Dependencies{
		Build: func(context.Context, executionnode.Node, string, string) (executionbundle.Verified, error) {
			builds++
			return executionbundle.Verified{}, nil
		},
		Publish: func(context.Context, executionbundle.Verified) (executionbundle.Verified, error) {
			return executionbundle.Verified{}, nil
		},
		Prepare: func(context.Context, executionnode.Node, executionbundle.Verified) (executionnode.Result, error) {
			return executionnode.Result{}, nil
		},
		UpdateLocks: func(context.Context, installer.RuntimeLockSetUpdateRequest) (installer.RuntimeLockSetUpdateResult, error) {
			return installer.RuntimeLockSetUpdateResult{}, nil
		},
		ReadLocks: func(context.Context, string, executionbundle.Verified) (string, string, error) { return "", "", nil },
	})
	if err == nil || err.Error() != "QA_RUNTIME_PROMOTION_PUBLISHED_BUNDLE_MISSING" || builds != 0 {
		t.Fatalf("err=%v builds=%d", err, builds)
	}
}

func TestPromoteExplicitPublishedDigestBootstrapsSafeRecoveryWithoutBuild(t *testing.T) {
	root := t.TempDir()
	project := filepath.Join(root, "project")
	if err := os.MkdirAll(project, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(project, "project.yml"), []byte("metadata: test\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	cache := filepath.Join(root, "bundle")
	bundle := testBundle(t, cache, "recovered-catalog")
	request := testRequest(root, project, cache)
	request.PublishedDigest = bundle.Digest
	builds := 0
	artifact, catalog := request.ExpectedArtifactDigest, request.ExpectedCatalogDigest
	result, err := Promote(t.Context(), request, Dependencies{
		Build: func(context.Context, executionnode.Node, string, string) (executionbundle.Verified, error) {
			builds++
			return executionbundle.Verified{}, nil
		},
		Publish: func(context.Context, executionbundle.Verified) (executionbundle.Verified, error) { return bundle, nil },
		Prepare: func(context.Context, executionnode.Node, executionbundle.Verified) (executionnode.Result, error) {
			return readyResult(bundle), nil
		},
		UpdateLocks: func(context.Context, installer.RuntimeLockSetUpdateRequest) (installer.RuntimeLockSetUpdateResult, error) {
			artifact, catalog = bundle.Digest, bundle.Manifest.CatalogDigest
			return installer.RuntimeLockSetUpdateResult{NewProjectRevision: "sha256:" + strings.Repeat("d", 64)}, nil
		},
		ReadLocks: func(context.Context, string, executionbundle.Verified) (string, string, error) {
			return artifact, catalog, nil
		},
	})
	if err != nil || builds != 0 || result.ArtifactDigest != bundle.Digest {
		t.Fatalf("result=%+v err=%v builds=%d", result, err, builds)
	}
}

func TestPromoteResumesFromPrePublishCheckpointWhenPublicationCompletedBeforeInterruption(t *testing.T) {
	root := t.TempDir()
	project := filepath.Join(root, "project")
	if err := os.MkdirAll(project, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(project, "project.yml"), []byte("metadata: test\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	cache := filepath.Join(root, "bundle")
	bundle := testBundle(t, cache, "pre-publish")
	request := testRequest(root, project, cache)
	builds := 0
	first := Dependencies{
		Build: func(context.Context, executionnode.Node, string, string) (executionbundle.Verified, error) {
			builds++
			return bundle, nil
		},
		Publish: func(context.Context, executionbundle.Verified) (executionbundle.Verified, error) {
			return executionbundle.Verified{}, fmt.Errorf("injected interruption after cache publication")
		},
		Prepare: func(context.Context, executionnode.Node, executionbundle.Verified) (executionnode.Result, error) {
			return readyResult(bundle), nil
		},
		UpdateLocks: func(context.Context, installer.RuntimeLockSetUpdateRequest) (installer.RuntimeLockSetUpdateResult, error) {
			return installer.RuntimeLockSetUpdateResult{}, nil
		},
		ReadLocks: func(context.Context, string, executionbundle.Verified) (string, string, error) {
			return request.ExpectedArtifactDigest, request.ExpectedCatalogDigest, nil
		},
	}
	if _, err := Promote(t.Context(), request, first); err == nil || !strings.Contains(err.Error(), "PUBLISH_FAILED") {
		t.Fatalf("err=%v", err)
	}
	path, err := checkpointPath(request.CheckpointRoot, request.ProjectRoot)
	if err != nil {
		t.Fatal(err)
	}
	state, found, err := readCheckpoint(path)
	if err != nil || !found || state.Stage != stageBuilt {
		t.Fatalf("state=%+v found=%v err=%v", state, found, err)
	}
	artifact, catalog := request.ExpectedArtifactDigest, request.ExpectedCatalogDigest
	second := first
	second.Build = func(context.Context, executionnode.Node, string, string) (executionbundle.Verified, error) {
		builds++
		return executionbundle.Verified{}, fmt.Errorf("must not rebuild")
	}
	second.Publish = func(context.Context, executionbundle.Verified) (executionbundle.Verified, error) {
		return executionbundle.Verified{}, fmt.Errorf("must not republish")
	}
	second.UpdateLocks = func(context.Context, installer.RuntimeLockSetUpdateRequest) (installer.RuntimeLockSetUpdateResult, error) {
		artifact, catalog = bundle.Digest, bundle.Manifest.CatalogDigest
		return installer.RuntimeLockSetUpdateResult{NewProjectRevision: "sha256:" + strings.Repeat("e", 64)}, nil
	}
	second.ReadLocks = func(context.Context, string, executionbundle.Verified) (string, string, error) {
		return artifact, catalog, nil
	}
	result, err := Promote(t.Context(), request, second)
	if err != nil || !result.Resumed || builds != 1 {
		t.Fatalf("result=%+v err=%v builds=%d", result, err, builds)
	}
}

func testRequest(root, project, cache string) Request {
	return Request{CheckpointRoot: filepath.Join(root, "runtime"), CacheRoot: cache, ProjectRoot: project, ExpectedArtifactDigest: "sha256:" + strings.Repeat("a", 64), ExpectedCatalogDigest: "sha256:" + strings.Repeat("b", 64), RuntimeInput: filepath.Join(root, "input"), BundleVersion: "qa-test", Node: executionnode.Node{ID: "node", Address: "127.0.0.1", User: "qa", Port: 22, CredentialRef: "runtime:ssh", HostKey: executionnode.HostKeyPolicy{State: "TRUSTED", KnownHosts: "known-hosts", Fingerprint: "fingerprint"}}}
}

func testBundle(t *testing.T, cache, catalogSeed string) executionbundle.Verified {
	t.Helper()
	component := []byte("capability")
	sum := sha256.Sum256(component)
	catalogSum := sha256.Sum256([]byte(catalogSeed))
	root := filepath.Join(cache, "candidate")
	if err := os.MkdirAll(filepath.Join(root, "core"), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "core", "capabilities.yml"), component, 0o600); err != nil {
		t.Fatal(err)
	}
	manifest := fmt.Sprintf("apiVersion: platform.installer/execution-bundle/v1alpha1\nkind: ExecutionRuntimeBundle\nbundleVersion: qa-test\nbootstrapProtocol: v1alpha1\ncoreVersion: 0.1.0\ncatalogDigest: sha256:%s\nschemaDigest: sha256:%s\nplatforms:\n  - os: redos\n    version: '8'\n    architecture: x86_64\ncomponents:\n  - path: core/capabilities.yml\n    sha256: sha256:%s\n    size: %d\n", hex.EncodeToString(catalogSum[:]), strings.Repeat("c", 64), hex.EncodeToString(sum[:]), len(component))
	if err := os.WriteFile(filepath.Join(root, "manifest.yaml"), []byte(manifest), 0o600); err != nil {
		t.Fatal(err)
	}
	verified, err := executionbundle.ValidateRoot(root)
	if err != nil {
		t.Fatal(err)
	}
	published, err := (executionbundle.Cache{Root: cache}).Publish(verified.Root)
	if err != nil {
		t.Fatal(err)
	}
	return published
}

func readyResult(bundle executionbundle.Verified) executionnode.Result {
	return executionnode.Result{State: executionnode.Ready, Runtime: executionnode.Runtime{BundleDigest: bundle.Digest}}
}

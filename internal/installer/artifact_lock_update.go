package installer

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"os"
	"strings"

	"gopkg.in/yaml.v3"

	"platform-installer/internal/projectlifecycle"
)

// ArtifactLockUpdateRequest is the intentionally narrow, explicit authority
// for rebinding a managed project to an already verified immutable bundle.
// It is not an EditCommand and is never used by the ordinary ProjectWriter.
type ArtifactLockUpdateRequest struct {
	ProjectRoot       string
	ExpectedOldDigest string
	NewDigest         string
	NewBundleRoot     string
}

type ArtifactLockUpdateResult struct {
	PreviousDigest     string
	NewDigest          string
	NewProjectRevision string
}

// RuntimeLockSetUpdateRequest is the deliberately narrow, explicit authority
// for an immutable runtime release whose catalog lock also changed. Normal
// project writers never receive this authority.
type RuntimeLockSetUpdateRequest struct {
	ProjectRoot               string
	ExpectedProjectRevision   string
	ExpectedOldArtifactDigest string
	ExpectedOldCatalogDigest  string
	NewDigest                 string
	NewBundleRoot             string
}

type RuntimeLockSetUpdateResult struct {
	PreviousArtifactDigest string
	PreviousCatalogDigest  string
	NewArtifactDigest      string
	NewCatalogDigest       string
	NewProjectRevision     string
}

// RuntimeLockSet is the narrow read-only view required by controlled runtime
// promotion. It exposes neither desired topology nor catalog content.
type RuntimeLockSet struct {
	ArtifactDigest string
	CatalogDigest  string
}

// ReadRuntimeLockSet reads only the two immutable compatibility locks from a
// managed project. It does not require the old runtime to remain in the local
// cache, which is essential after immutable cache publication prunes it.
func ReadRuntimeLockSet(projectRoot string) (RuntimeLockSet, error) {
	root, err := cleanRoot(projectRoot)
	if err != nil {
		return RuntimeLockSet{}, err
	}
	path, err := safeProjectPath(root, "project.yml", false)
	if err != nil {
		return RuntimeLockSet{}, err
	}
	content, err := os.ReadFile(path)
	if err != nil {
		return RuntimeLockSet{}, err
	}
	return readRuntimeLockSet(content)
}

// UpdateRuntimeLockSet atomically moves both lock fields to the complete pair
// derived from a verified immutable bundle. The expected raw project revision
// makes this a compare-and-swap for the whole canonical project, not merely a
// digest replacement.
func (b *Backend) UpdateRuntimeLockSet(ctx context.Context, request RuntimeLockSetUpdateRequest) (RuntimeLockSetUpdateResult, error) {
	if err := ctx.Err(); err != nil {
		return RuntimeLockSetUpdateResult{}, err
	}
	if !validDigest(request.ExpectedProjectRevision) || !validDigest(request.ExpectedOldArtifactDigest) || !validDigest(request.ExpectedOldCatalogDigest) || !validDigest(request.NewDigest) || request.NewBundleRoot == "" || request.ExpectedOldArtifactDigest == request.NewDigest {
		return RuntimeLockSetUpdateResult{}, blocked("RUNTIME_LOCK_SET_UPDATE_INVALID", "Runtime lock-set update input is invalid", "project.yml")
	}
	root, err := cleanRoot(request.ProjectRoot)
	if err != nil {
		return RuntimeLockSetUpdateResult{}, err
	}
	release, err := acquireWriterLock(ctx, root, b.lockWait)
	if err != nil {
		return RuntimeLockSetUpdateResult{}, err
	}
	defer release()
	if err := recoverTransactions(root); err != nil {
		return RuntimeLockSetUpdateResult{}, err
	}
	currentRevision, err := ProjectRevision(root)
	if err != nil {
		return RuntimeLockSetUpdateResult{}, err
	}
	if currentRevision != request.ExpectedProjectRevision {
		return RuntimeLockSetUpdateResult{}, blocked("PROJECT_CHANGED", "Project changed before runtime lock update", "project.yml")
	}
	candidate, err := projectlifecycle.ResolveRuntimeLockUpgradeCandidate(ctx, root, request.NewBundleRoot, request.NewDigest)
	if err != nil {
		return RuntimeLockSetUpdateResult{}, err
	}
	path, err := safeProjectPath(root, "project.yml", false)
	if err != nil {
		return RuntimeLockSetUpdateResult{}, err
	}
	before, err := os.ReadFile(path)
	if err != nil {
		return RuntimeLockSetUpdateResult{}, err
	}
	after, err := replaceRuntimeLockSet(before, request.ExpectedOldArtifactDigest, request.ExpectedOldCatalogDigest, candidate)
	if err != nil {
		return RuntimeLockSetUpdateResult{}, err
	}
	identifier, err := artifactLockTransactionID()
	if err != nil {
		return RuntimeLockSetUpdateResult{}, err
	}
	if err := b.commitDocuments(root, identifier, []storedDocument{{LogicalPath: "project.yml", Before: before, After: after, Existed: true}}); err != nil {
		return RuntimeLockSetUpdateResult{}, err
	}
	reopened, err := projectlifecycle.NewService(map[string]string{"runtime-lock-set-update": request.NewBundleRoot}).OpenProject(ctx, root)
	if err != nil || reopened.Project == nil || reopened.Project.Source.BundleDigest != candidate.ArtifactDigest || reopened.Catalog == nil || reopened.Catalog.Status != "READY" {
		return RuntimeLockSetUpdateResult{}, errors.New("RUNTIME_LOCK_SET_UPDATE_REOPEN_FAILED")
	}
	revision, err := ProjectRevision(root)
	if err != nil {
		return RuntimeLockSetUpdateResult{}, err
	}
	return RuntimeLockSetUpdateResult{PreviousArtifactDigest: request.ExpectedOldArtifactDigest, PreviousCatalogDigest: request.ExpectedOldCatalogDigest, NewArtifactDigest: candidate.ArtifactDigest, NewCatalogDigest: candidate.CatalogDigest, NewProjectRevision: revision}, nil
}

// UpdateArtifactLock validates a compatible immutable bundle, then changes
// only artifactLock.digest through the existing guarded writer transaction.
func (b *Backend) UpdateArtifactLock(ctx context.Context, request ArtifactLockUpdateRequest) (ArtifactLockUpdateResult, error) {
	if err := ctx.Err(); err != nil {
		return ArtifactLockUpdateResult{}, err
	}
	if !validDigest(request.ExpectedOldDigest) || !validDigest(request.NewDigest) || request.ExpectedOldDigest == request.NewDigest || request.NewBundleRoot == "" {
		return ArtifactLockUpdateResult{}, blocked("ARTIFACT_LOCK_UPDATE_INVALID", "Artifact lock update input is invalid", "artifactLock")
	}
	root, err := cleanRoot(request.ProjectRoot)
	if err != nil {
		return ArtifactLockUpdateResult{}, err
	}
	release, err := acquireWriterLock(ctx, root, b.lockWait)
	if err != nil {
		return ArtifactLockUpdateResult{}, err
	}
	defer release()
	if err := recoverTransactions(root); err != nil {
		return ArtifactLockUpdateResult{}, err
	}
	if err := projectlifecycle.ValidateArtifactLockCandidate(ctx, root, request.NewBundleRoot, request.NewDigest); err != nil {
		return ArtifactLockUpdateResult{}, err
	}
	path, err := safeProjectPath(root, "project.yml", false)
	if err != nil {
		return ArtifactLockUpdateResult{}, err
	}
	before, err := os.ReadFile(path)
	if err != nil {
		return ArtifactLockUpdateResult{}, err
	}
	after, err := replaceArtifactLockDigest(before, request.ExpectedOldDigest, request.NewDigest)
	if err != nil {
		return ArtifactLockUpdateResult{}, err
	}
	identifier, err := artifactLockTransactionID()
	if err != nil {
		return ArtifactLockUpdateResult{}, err
	}
	if err := b.commitDocuments(root, identifier, []storedDocument{{LogicalPath: "project.yml", Before: before, After: after, Existed: true}}); err != nil {
		return ArtifactLockUpdateResult{}, err
	}
	reopened, err := projectlifecycle.NewService(map[string]string{"artifact-lock-update": request.NewBundleRoot}).OpenProject(ctx, root)
	if err != nil || reopened.Project == nil || reopened.Project.Source.BundleDigest != request.NewDigest || reopened.Catalog == nil || reopened.Catalog.Status != "READY" {
		return ArtifactLockUpdateResult{}, errors.New("ARTIFACT_LOCK_UPDATE_REOPEN_FAILED")
	}
	revision, err := ProjectRevision(root)
	if err != nil {
		return ArtifactLockUpdateResult{}, err
	}
	return ArtifactLockUpdateResult{PreviousDigest: request.ExpectedOldDigest, NewDigest: request.NewDigest, NewProjectRevision: revision}, nil
}

func artifactLockTransactionID() (string, error) {
	value := make([]byte, 16)
	if _, err := rand.Read(value); err != nil {
		return "", err
	}
	return hex.EncodeToString(value), nil
}

// replaceArtifactLockDigest accepts only the canonical scalar form emitted for
// managed projects. It validates the YAML shape first, then replaces that one
// scalar in-place so all unrelated project.yml bytes remain untouched.
func replaceArtifactLockDigest(before []byte, expectedOldDigest, newDigest string) ([]byte, error) {
	var document yaml.Node
	if err := yaml.Unmarshal(before, &document); err != nil || len(document.Content) != 1 || document.Content[0].Kind != yaml.MappingNode {
		return nil, blocked("ARTIFACT_LOCK_UPDATE_INVALID", "Managed project manifest cannot be safely updated", "artifactLock")
	}
	artifactLock, found, duplicate := yamlMappingValue(document.Content[0], "artifactLock")
	if !found || duplicate || artifactLock.Kind != yaml.MappingNode {
		return nil, blocked("ARTIFACT_LOCK_UPDATE_INVALID", "Managed project artifact lock is invalid", "artifactLock")
	}
	digest, found, duplicate := yamlMappingValue(artifactLock, "digest")
	if !found || duplicate || digest.Kind != yaml.ScalarNode || digest.Tag != "!!str" || digest.Value != expectedOldDigest {
		return nil, blocked("ARTIFACT_LOCK_CHANGED", "Artifact lock changed before update", "artifactLock.digest")
	}
	start, end, ok := yamlSourceLine(before, digest.Line)
	if !ok {
		return nil, blocked("ARTIFACT_LOCK_UPDATE_INVALID", "Managed project artifact lock is not in canonical form", "artifactLock.digest")
	}
	line := string(before[start:end])
	trimmed := strings.TrimSpace(strings.TrimSuffix(line, "\r"))
	if trimmed != "digest: "+expectedOldDigest || strings.Count(line, expectedOldDigest) != 1 {
		return nil, blocked("ARTIFACT_LOCK_UPDATE_INVALID", "Managed project artifact lock is not in canonical form", "artifactLock.digest")
	}
	offset := bytes.Index(before[start:end], []byte(expectedOldDigest))
	if offset < 0 {
		return nil, blocked("ARTIFACT_LOCK_UPDATE_INVALID", "Managed project artifact lock is not in canonical form", "artifactLock.digest")
	}
	position := start + offset
	after := make([]byte, 0, len(before)-len(expectedOldDigest)+len(newDigest))
	after = append(after, before[:position]...)
	after = append(after, newDigest...)
	after = append(after, before[position+len(expectedOldDigest):]...)
	return after, nil
}

type runtimeCatalogLock struct {
	APIVersion string                                                `yaml:"apiVersion"`
	Digest     string                                                `yaml:"digest"`
	Services   map[string]projectlifecycle.RuntimeCatalogServiceLock `yaml:"services"`
}

func replaceRuntimeLockSet(before []byte, expectedArtifactDigest, expectedCatalogDigest string, candidate projectlifecycle.RuntimeLockUpgradeCandidate) ([]byte, error) {
	locks, err := readRuntimeLockSet(before)
	if err != nil {
		return nil, err
	}
	if locks.CatalogDigest != expectedCatalogDigest || locks.ArtifactDigest != expectedArtifactDigest {
		return nil, blocked("RUNTIME_LOCK_CHANGED", "Runtime lock changed before update", "project.yml")
	}
	var document yaml.Node
	if err := yaml.Unmarshal(before, &document); err != nil || len(document.Content) != 1 || document.Content[0].Kind != yaml.MappingNode {
		return nil, blocked("RUNTIME_LOCK_SET_UPDATE_INVALID", "Managed project manifest cannot be safely updated", "project.yml")
	}
	mapping := document.Content[0]
	catalogKey, catalogLock, catalogFound, catalogDuplicate := yamlMappingPair(mapping, "catalogLock")
	artifactKey, artifactLock, artifactFound, artifactDuplicate := yamlMappingPair(mapping, "artifactLock")
	if !catalogFound || catalogDuplicate || !artifactFound || artifactDuplicate || catalogLock.Kind != yaml.MappingNode || artifactLock.Kind != yaml.MappingNode || catalogKey.Line < 1 || artifactKey.Line <= catalogKey.Line {
		return nil, blocked("RUNTIME_LOCK_SET_UPDATE_INVALID", "Managed project lock layout is invalid", "project.yml")
	}
	catalogStart, _, ok := yamlSourceLine(before, catalogKey.Line)
	artifactStart, _, okArtifact := yamlSourceLine(before, artifactKey.Line)
	if !ok || !okArtifact || catalogStart >= artifactStart {
		return nil, blocked("RUNTIME_LOCK_SET_UPDATE_INVALID", "Managed project lock layout is not canonical", "project.yml")
	}
	encoded, err := yaml.Marshal(runtimeCatalogLock{APIVersion: "platform.installer/catalog/v1alpha1", Digest: candidate.CatalogDigest, Services: candidate.CatalogServices})
	if err != nil {
		return nil, err
	}
	block := "catalogLock:\n" + indentYAML(encoded, "    ")
	withCatalog := append(append(append([]byte{}, before[:catalogStart]...), []byte(block)...), before[artifactStart:]...)
	return replaceArtifactLockDigest(withCatalog, expectedArtifactDigest, candidate.ArtifactDigest)
}

func readRuntimeLockSet(content []byte) (RuntimeLockSet, error) {
	var document yaml.Node
	if err := yaml.Unmarshal(content, &document); err != nil || len(document.Content) != 1 || document.Content[0].Kind != yaml.MappingNode {
		return RuntimeLockSet{}, blocked("RUNTIME_LOCK_SET_UPDATE_INVALID", "Managed project manifest cannot be safely read", "project.yml")
	}
	mapping := document.Content[0]
	_, catalogLock, catalogFound, catalogDuplicate := yamlMappingPair(mapping, "catalogLock")
	_, artifactLock, artifactFound, artifactDuplicate := yamlMappingPair(mapping, "artifactLock")
	if !catalogFound || catalogDuplicate || !artifactFound || artifactDuplicate || catalogLock.Kind != yaml.MappingNode || artifactLock.Kind != yaml.MappingNode {
		return RuntimeLockSet{}, blocked("RUNTIME_LOCK_SET_UPDATE_INVALID", "Managed project lock layout is invalid", "project.yml")
	}
	catalogDigest, catalogFound, catalogDuplicate := yamlMappingValue(catalogLock, "digest")
	artifactDigest, artifactFound, artifactDuplicate := yamlMappingValue(artifactLock, "digest")
	if !catalogFound || catalogDuplicate || catalogDigest.Kind != yaml.ScalarNode || catalogDigest.Tag != "!!str" || !validDigest(catalogDigest.Value) || !artifactFound || artifactDuplicate || artifactDigest.Kind != yaml.ScalarNode || artifactDigest.Tag != "!!str" || !validDigest(artifactDigest.Value) {
		return RuntimeLockSet{}, blocked("RUNTIME_LOCK_SET_UPDATE_INVALID", "Managed project lock layout is invalid", "project.yml")
	}
	return RuntimeLockSet{ArtifactDigest: artifactDigest.Value, CatalogDigest: catalogDigest.Value}, nil
}

func yamlMappingPair(mapping *yaml.Node, name string) (*yaml.Node, *yaml.Node, bool, bool) {
	var key, value *yaml.Node
	for index := 0; index+1 < len(mapping.Content); index += 2 {
		candidateKey := mapping.Content[index]
		if candidateKey.Kind != yaml.ScalarNode || candidateKey.Value != name {
			continue
		}
		if value != nil {
			return nil, nil, true, true
		}
		key, value = candidateKey, mapping.Content[index+1]
	}
	return key, value, value != nil, false
}

func indentYAML(value []byte, prefix string) string {
	trimmed := strings.TrimSuffix(string(value), "\n")
	if trimmed == "" {
		return ""
	}
	return prefix + strings.ReplaceAll(trimmed, "\n", "\n"+prefix) + "\n"
}

func yamlMappingValue(mapping *yaml.Node, name string) (*yaml.Node, bool, bool) {
	var value *yaml.Node
	for index := 0; index+1 < len(mapping.Content); index += 2 {
		key := mapping.Content[index]
		if key.Kind != yaml.ScalarNode || key.Value != name {
			continue
		}
		if value != nil {
			return nil, true, true
		}
		value = mapping.Content[index+1]
	}
	return value, value != nil, false
}

func yamlSourceLine(content []byte, lineNumber int) (int, int, bool) {
	if lineNumber < 1 {
		return 0, 0, false
	}
	start := 0
	for line := 1; line < lineNumber; line++ {
		next := bytes.IndexByte(content[start:], '\n')
		if next < 0 {
			return 0, 0, false
		}
		start += next + 1
	}
	end := len(content)
	if next := bytes.IndexByte(content[start:], '\n'); next >= 0 {
		end = start + next
	}
	return start, end, true
}

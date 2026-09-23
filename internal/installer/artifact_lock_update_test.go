package installer

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"

	"platform-installer/internal/executionbundle"
	"platform-installer/internal/projectlifecycle"
)

func artifactLockTestBundle(t *testing.T, version string) string {
	return artifactLockTestBundleWithCatalogDigest(t, version, "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
}

func artifactLockTestBundleWithCatalogDigest(t *testing.T, version, catalogDigest string) string {
	t.Helper()
	root := t.TempDir()
	if err := os.MkdirAll(filepath.Join(root, "catalog"), 0o755); err != nil {
		t.Fatal(err)
	}
	catalog := "apiVersion: platform.installer/catalog/v1alpha1\nkind: ServiceCatalog\ndigest: " + catalogDigest + "\ndefinitions:\n  kafka:\n    metadata:\n      id: kafka\n      version: 1.0.0\n      displayName: Kafka\n    modes:\n      single:\n        displayName: Single\n        memberRoles: [broker]\n        placement:\n          minMembers: 1\n          distinctHosts: false\n    x-definitionDigest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n"
	catalogPath := filepath.Join(root, "catalog", "service-catalog.yml")
	if err := os.WriteFile(catalogPath, []byte(catalog), 0o644); err != nil {
		t.Fatal(err)
	}
	sum := sha256.Sum256([]byte(catalog))
	manifest := "apiVersion: platform.installer/execution-bundle/v1alpha1\nkind: ExecutionRuntimeBundle\nbundleVersion: " + version + "\nbootstrapProtocol: v1alpha1\ncoreVersion: 0.1.0\ncatalogDigest: " + catalogDigest + "\nschemaDigest: sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc\nplatforms:\n  - os: redos\n    version: '8'\n    architecture: x86_64\ncomponents:\n  - path: catalog/service-catalog.yml\n    sha256: sha256:" + hex.EncodeToString(sum[:]) + "\n    size: " + strconv.Itoa(len(catalog)) + "\n"
	if err := os.WriteFile(filepath.Join(root, "manifest.yaml"), []byte(manifest), 0o644); err != nil {
		t.Fatal(err)
	}
	return root
}

func artifactLockTestProject(t *testing.T, bundle string) (string, string) {
	t.Helper()
	verified, err := executionbundle.ValidateRoot(bundle)
	if err != nil {
		t.Fatal(err)
	}
	parent := t.TempDir()
	result, err := projectlifecycle.NewService(map[string]string{"old": bundle}).CreateProject(t.Context(), projectlifecycle.CreateProjectRequest{
		ProjectRoot: filepath.Join(parent, "project"), DisplayName: "Artifact lock test", CompatibilitySourceID: "old",
	})
	if err != nil {
		t.Fatal(err)
	}
	return result.Root, verified.Digest
}

func TestUpdateArtifactLockChangesOnlyDigestAndReopensCompatibleProject(t *testing.T) {
	oldBundle := artifactLockTestBundle(t, "old")
	newBundle := artifactLockTestBundle(t, "new")
	root, oldDigest := artifactLockTestProject(t, oldBundle)
	newDigest := mustBundleDigest(t, newBundle)
	projectPath := filepath.Join(root, "project.yml")
	before, err := os.ReadFile(projectPath)
	if err != nil {
		t.Fatal(err)
	}
	result, err := NewBackend(nil).UpdateArtifactLock(context.Background(), ArtifactLockUpdateRequest{ProjectRoot: root, ExpectedOldDigest: oldDigest, NewDigest: newDigest, NewBundleRoot: newBundle})
	if err != nil {
		t.Fatal(err)
	}
	if result.PreviousDigest != oldDigest || result.NewDigest != newDigest || result.NewProjectRevision == "" {
		t.Fatalf("result=%+v", result)
	}
	after, err := os.ReadFile(projectPath)
	if err != nil {
		t.Fatal(err)
	}
	want := []byte(strings.Replace(string(before), oldDigest, newDigest, 1))
	if string(after) != string(want) {
		t.Fatalf("project.yml changed outside artifactLock.digest\nwant:\n%s\ngot:\n%s", want, after)
	}
	reopened, err := projectlifecycle.NewService(map[string]string{"new": newBundle}).OpenProject(t.Context(), root)
	if err != nil || reopened.Project == nil || reopened.Project.Source.BundleDigest != newDigest || reopened.Catalog == nil || reopened.Catalog.Status != "READY" {
		t.Fatalf("reopened=%+v err=%v", reopened, err)
	}
}

func TestUpdateArtifactLockRejectsCASAndBundleFailuresWithoutMutation(t *testing.T) {
	oldBundle := artifactLockTestBundle(t, "old")
	newBundle := artifactLockTestBundle(t, "new")
	root, oldDigest := artifactLockTestProject(t, oldBundle)
	newDigest := mustBundleDigest(t, newBundle)
	invalidBundle := artifactLockTestBundle(t, "invalid")
	invalidDigest := mustBundleDigest(t, invalidBundle)
	if err := os.WriteFile(filepath.Join(invalidBundle, "manifest.yaml"), []byte("invalid\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	projectPath := filepath.Join(root, "project.yml")
	before, err := os.ReadFile(projectPath)
	if err != nil {
		t.Fatal(err)
	}
	wrongDigest := "sha256:" + strings.Repeat("d", 64)
	incompatibleBundle := artifactLockTestBundleWithCatalogDigest(t, "incompatible", "sha256:"+strings.Repeat("e", 64))
	incompatibleDigest := mustBundleDigest(t, incompatibleBundle)
	for _, test := range []struct {
		name    string
		request ArtifactLockUpdateRequest
	}{
		{name: "compare-and-swap mismatch", request: ArtifactLockUpdateRequest{ProjectRoot: root, ExpectedOldDigest: wrongDigest, NewDigest: newDigest, NewBundleRoot: newBundle}},
		{name: "bundle missing", request: ArtifactLockUpdateRequest{ProjectRoot: root, ExpectedOldDigest: oldDigest, NewDigest: newDigest, NewBundleRoot: filepath.Join(root, "missing-bundle")}},
		{name: "bundle invalid", request: ArtifactLockUpdateRequest{ProjectRoot: root, ExpectedOldDigest: oldDigest, NewDigest: invalidDigest, NewBundleRoot: invalidBundle}},
		{name: "bundle digest mismatch", request: ArtifactLockUpdateRequest{ProjectRoot: root, ExpectedOldDigest: oldDigest, NewDigest: wrongDigest, NewBundleRoot: newBundle}},
		{name: "bundle catalog incompatible", request: ArtifactLockUpdateRequest{ProjectRoot: root, ExpectedOldDigest: oldDigest, NewDigest: incompatibleDigest, NewBundleRoot: incompatibleBundle}},
	} {
		t.Run(test.name, func(t *testing.T) {
			if _, err := NewBackend(nil).UpdateArtifactLock(context.Background(), test.request); err == nil {
				t.Fatal("expected update failure")
			}
			after, err := os.ReadFile(projectPath)
			if err != nil {
				t.Fatal(err)
			}
			if string(after) != string(before) {
				t.Fatal("project changed after rejected update")
			}
		})
	}
}

func TestUpdateRuntimeLockSetAtomicallyUpgradesVerifiedCatalogPair(t *testing.T) {
	oldBundle := artifactLockTestBundle(t, "old")
	newCatalogDigest := "sha256:" + strings.Repeat("e", 64)
	newBundle := artifactLockTestBundleWithCatalogDigest(t, "new", newCatalogDigest)
	root, oldArtifactDigest := artifactLockTestProject(t, oldBundle)
	projectPath := filepath.Join(root, "project.yml")
	before, err := os.ReadFile(projectPath)
	if err != nil {
		t.Fatal(err)
	}
	beforeRevision, err := ProjectRevision(root)
	if err != nil {
		t.Fatal(err)
	}
	newArtifactDigest := mustBundleDigest(t, newBundle)
	result, err := NewBackend(nil).UpdateRuntimeLockSet(t.Context(), RuntimeLockSetUpdateRequest{
		ProjectRoot: root, ExpectedProjectRevision: beforeRevision, ExpectedOldArtifactDigest: oldArtifactDigest,
		ExpectedOldCatalogDigest: "sha256:" + strings.Repeat("a", 64), NewDigest: newArtifactDigest, NewBundleRoot: newBundle,
	})
	if err != nil {
		t.Fatal(err)
	}
	if result.PreviousArtifactDigest != oldArtifactDigest || result.PreviousCatalogDigest != "sha256:"+strings.Repeat("a", 64) || result.NewArtifactDigest != newArtifactDigest || result.NewCatalogDigest != newCatalogDigest || result.NewProjectRevision == "" {
		t.Fatalf("result=%+v", result)
	}
	after, err := os.ReadFile(projectPath)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(after), "catalogLock:\n    apiVersion: platform.installer/catalog/v1alpha1\n    digest: "+newCatalogDigest) || !strings.Contains(string(after), "artifactLock:\n    apiVersion: platform.installer/artifacts/v1alpha1\n    digest: "+newArtifactDigest) {
		t.Fatalf("updated locks missing:\n%s", after)
	}
	beforeCatalog, afterCatalog := strings.Index(string(before), "catalogLock:"), strings.Index(string(after), "catalogLock:")
	if beforeCatalog < 0 || afterCatalog < 0 || string(before)[:beforeCatalog] != string(after)[:afterCatalog] {
		t.Fatal("project bytes before lock blocks changed")
	}
	reopened, err := projectlifecycle.NewService(map[string]string{"new": newBundle}).OpenProject(t.Context(), root)
	if err != nil || reopened.Project == nil || reopened.Project.Source.BundleDigest != newArtifactDigest || reopened.Catalog == nil || reopened.Catalog.Status != "READY" {
		t.Fatalf("reopened=%+v err=%v", reopened, err)
	}
}

func TestReadRuntimeLockSetReadsOnlyValidatedLockPair(t *testing.T) {
	bundle := artifactLockTestBundle(t, "old")
	root, oldArtifactDigest := artifactLockTestProject(t, bundle)
	locks, err := ReadRuntimeLockSet(root)
	if err != nil || locks.ArtifactDigest != oldArtifactDigest || locks.CatalogDigest == "" {
		t.Fatalf("locks=%+v err=%v", locks, err)
	}
	if err := os.WriteFile(filepath.Join(root, "project.yml"), []byte("artifactLock:\n  digest: invalid\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := ReadRuntimeLockSet(root); err == nil {
		t.Fatal("invalid lock layout was accepted")
	}
}

func TestUpdateRuntimeLockSetRejectsWholeProjectCASAndInvalidBundleWithoutMutation(t *testing.T) {
	oldBundle := artifactLockTestBundle(t, "old")
	newBundle := artifactLockTestBundleWithCatalogDigest(t, "new", "sha256:"+strings.Repeat("e", 64))
	root, oldArtifactDigest := artifactLockTestProject(t, oldBundle)
	projectPath := filepath.Join(root, "project.yml")
	before, err := os.ReadFile(projectPath)
	if err != nil {
		t.Fatal(err)
	}
	revision, err := ProjectRevision(root)
	if err != nil {
		t.Fatal(err)
	}
	newDigest := mustBundleDigest(t, newBundle)
	base := RuntimeLockSetUpdateRequest{ProjectRoot: root, ExpectedProjectRevision: revision, ExpectedOldArtifactDigest: oldArtifactDigest, ExpectedOldCatalogDigest: "sha256:" + strings.Repeat("a", 64), NewDigest: newDigest, NewBundleRoot: newBundle}
	wrongRevision := base
	wrongRevision.ExpectedProjectRevision = "sha256:" + strings.Repeat("d", 64)
	missingBundle := base
	missingBundle.NewBundleRoot = filepath.Join(root, "missing")
	for _, request := range []RuntimeLockSetUpdateRequest{wrongRevision, missingBundle} {
		if _, err := NewBackend(nil).UpdateRuntimeLockSet(t.Context(), request); err == nil {
			t.Fatal("expected rejected runtime lock update")
		}
		after, err := os.ReadFile(projectPath)
		if err != nil {
			t.Fatal(err)
		}
		if string(after) != string(before) {
			t.Fatal("project changed after rejected runtime lock update")
		}
	}
}

func TestOrdinaryProjectWriterDoesNotPlanArtifactLockMutation(t *testing.T) {
	bundle := artifactLockTestBundle(t, "old")
	root, _ := artifactLockTestProject(t, bundle)
	before, err := os.ReadFile(filepath.Join(root, "project.yml"))
	if err != nil {
		t.Fatal(err)
	}
	revision, err := ProjectRevision(root)
	if err != nil {
		t.Fatal(err)
	}
	backend := NewBackend(&firstWriteAdapter{}, WithServerTypes([]string{"infra"}))
	plan, err := backend.PlanStructuralSave(t.Context(), root, projectlifecycle.ClassificationEmpty, revision, []EditCommand{{
		APIVersion: EditCommandAPIVersionV4, Kind: "EditCommand", BaseProjectRevision: revision,
		Operation: "CreateServer", HostID: "node1", ServerType: "infra", DesiredHostname: "node1.example.test", Address: "192.0.2.10",
	}})
	if err != nil || plan.Status != "READY" {
		t.Fatalf("plan=%+v err=%v", plan, err)
	}
	for _, document := range plan.AffectedDocuments {
		if document.LogicalPath == "project.yml" {
			t.Fatal("ordinary writer planned project.yml mutation")
		}
	}
	result := backend.CommitStructuralSave(t.Context(), plan.PlanID)
	if result.Status != "COMMITTED" {
		t.Fatalf("result=%+v", result)
	}
	after, err := os.ReadFile(filepath.Join(root, "project.yml"))
	if err != nil {
		t.Fatal(err)
	}
	if string(after) != string(before) {
		t.Fatal("ordinary writer changed artifact lock manifest")
	}
}

func mustBundleDigest(t *testing.T, root string) string {
	t.Helper()
	verified, err := executionbundle.ValidateRoot(root)
	if err != nil {
		t.Fatal(err)
	}
	return verified.Digest
}

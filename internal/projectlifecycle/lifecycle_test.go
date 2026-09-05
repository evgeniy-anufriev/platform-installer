package projectlifecycle

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
)

func testBundle(t *testing.T) string {
	t.Helper()
	root := t.TempDir()
	if err := os.MkdirAll(filepath.Join(root, "catalog"), 0o755); err != nil {
		t.Fatal(err)
	}
	catalog := "apiVersion: platform.installer/catalog/v1alpha1\nkind: ServiceCatalog\ndigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\ndefinitions:\n  kafka:\n    metadata:\n      id: kafka\n      version: 1.0.0\n    x-definitionDigest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n"
	catalogPath := filepath.Join(root, "catalog", "service-catalog.yml")
	if err := os.WriteFile(catalogPath, []byte(catalog), 0o644); err != nil {
		t.Fatal(err)
	}
	sum := sha256.Sum256([]byte(catalog))
	manifest := "apiVersion: platform.installer/execution-bundle/v1alpha1\nkind: ExecutionRuntimeBundle\nbundleVersion: test\nbootstrapProtocol: v1alpha1\ncoreVersion: 0.1.0\ncatalogDigest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\nschemaDigest: sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc\nplatforms:\n  - os: redos\n    version: '8'\n    architecture: x86_64\ncomponents:\n  - path: catalog/service-catalog.yml\n    sha256: sha256:" + hex.EncodeToString(sum[:]) + "\n    size: " + strconv.Itoa(len(catalog)) + "\n"
	if err := os.WriteFile(filepath.Join(root, "manifest.yaml"), []byte(manifest), 0o644); err != nil {
		t.Fatal(err)
	}
	return root
}

func TestCreateProjectPublishesOneManagedManifest(t *testing.T) {
	bundle := testBundle(t)
	parent := t.TempDir()
	service := NewService(map[string]string{DefaultCompatibilitySourceID: bundle})
	result, err := service.CreateProject(t.Context(), CreateProjectRequest{ProjectRoot: filepath.Join(parent, "new-project"), DisplayName: "Production", CompatibilitySourceID: DefaultCompatibilitySourceID})
	if err != nil {
		t.Fatal(err)
	}
	if result.Classification != classificationEmpty || result.Project == nil || !validProjectID(result.Project.ID) {
		t.Fatalf("result=%+v", result)
	}
	entries, err := os.ReadDir(result.Root)
	if err != nil || len(entries) != 1 || entries[0].Name() != "project.yml" {
		t.Fatalf("entries=%v err=%v", entries, err)
	}
	data, err := os.ReadFile(filepath.Join(result.Root, "project.yml"))
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(data), "desiredState:") || !strings.Contains(string(data), managedProjectLabel) || !strings.Contains(string(data), "catalogLock:") || !strings.Contains(string(data), "artifactLock:") {
		t.Fatalf("unexpected manifest: %s", data)
	}
	reopened, err := service.OpenProject(t.Context(), result.Root)
	if err != nil || reopened.Classification != classificationEmpty || reopened.Project.ID != result.Project.ID || reopened.Project.Name != "Production" {
		t.Fatalf("reopened=%+v err=%v", reopened, err)
	}
}

func TestCreateProjectFailsClosedForSourceAndDestination(t *testing.T) {
	parent := t.TempDir()
	root := filepath.Join(parent, "new-project")
	service := NewService(map[string]string{})
	if _, err := service.CreateProject(t.Context(), CreateProjectRequest{ProjectRoot: root, DisplayName: "Project", CompatibilitySourceID: DefaultCompatibilitySourceID}); err == nil || err.Error() != "PROJECT_COMPATIBILITY_SOURCE_UNAVAILABLE" {
		t.Fatalf("err=%v", err)
	}
	if _, err := os.Stat(root); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("unexpected root: %v", err)
	}
	if err := os.Mkdir(root, 0o755); err != nil {
		t.Fatal(err)
	}
	service = NewService(map[string]string{DefaultCompatibilitySourceID: testBundle(t)})
	if _, err := service.CreateProject(t.Context(), CreateProjectRequest{ProjectRoot: root, DisplayName: "Project", CompatibilitySourceID: DefaultCompatibilitySourceID}); err == nil || err.Error() != "PROJECT_DESTINATION_EXISTS" {
		t.Fatalf("err=%v", err)
	}
}

func TestCreateProjectReverifiesCompatibilitySourceOnEveryCall(t *testing.T) {
	bundle := testBundle(t)
	service := NewService(map[string]string{DefaultCompatibilitySourceID: bundle})
	if _, err := service.CreateProject(t.Context(), CreateProjectRequest{ProjectRoot: filepath.Join(t.TempDir(), "first"), DisplayName: "First", CompatibilitySourceID: DefaultCompatibilitySourceID}); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(bundle, "catalog", "service-catalog.yml"), []byte("modified"), 0o644); err != nil {
		t.Fatal(err)
	}
	root := filepath.Join(t.TempDir(), "second")
	if _, err := service.CreateProject(t.Context(), CreateProjectRequest{ProjectRoot: root, DisplayName: "Second", CompatibilitySourceID: DefaultCompatibilitySourceID}); err == nil || err.Error() != "PROJECT_COMPATIBILITY_SOURCE_UNAVAILABLE" {
		t.Fatalf("err=%v", err)
	}
	if _, err := os.Stat(root); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("source failure wrote project: %v", err)
	}
}

func TestCreateProjectRaceAndPublishFailureNeverReplaceDestination(t *testing.T) {
	parent := t.TempDir()
	root := filepath.Join(parent, "new-project")
	service := NewService(map[string]string{DefaultCompatibilitySourceID: testBundle(t)})
	service.beforePublish = func(destination string) error { return os.Mkdir(destination, 0o755) }
	if _, err := service.CreateProject(t.Context(), CreateProjectRequest{ProjectRoot: root, DisplayName: "Project", CompatibilitySourceID: DefaultCompatibilitySourceID}); err == nil {
		t.Fatal("race accepted")
	}
	if _, err := os.Stat(root); err != nil {
		t.Fatal(err)
	}
	root = filepath.Join(parent, "publish-failure")
	service = NewService(map[string]string{DefaultCompatibilitySourceID: testBundle(t)})
	service.publish = func(string, string) error { return errors.New("simulated") }
	if _, err := service.CreateProject(t.Context(), CreateProjectRequest{ProjectRoot: root, DisplayName: "Project", CompatibilitySourceID: DefaultCompatibilitySourceID}); err == nil || err.Error() != "PROJECT_PUBLISH_FAILED" {
		t.Fatalf("err=%v", err)
	}
	if _, err := os.Stat(root); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("published after failure: %v", err)
	}
}

func TestCreateProjectSurfacesOwnStagingCleanupFailure(t *testing.T) {
	parent := t.TempDir()
	service := NewService(map[string]string{DefaultCompatibilitySourceID: testBundle(t)})
	service.publish = func(string, string) error { return errors.New("simulated") }
	service.removeAll = func(string) error { return errors.New("simulated cleanup failure") }
	if _, err := service.CreateProject(t.Context(), CreateProjectRequest{ProjectRoot: filepath.Join(parent, "new-project"), DisplayName: "Project", CompatibilitySourceID: DefaultCompatibilitySourceID}); err == nil || err.Error() != "PROJECT_CREATE_CLEANUP_FAILED" {
		t.Fatalf("err=%v", err)
	}
}

func TestOpenNeverAdoptsExternalIncompleteOrMalformedManagedProject(t *testing.T) {
	service := NewService(nil)
	for _, test := range []struct{ name, content, want string }{
		{name: "external", content: "apiVersion: platform.installer/v2alpha1\nkind: PlatformProject\nmetadata:\n  id: external\n", want: classificationIncomplete},
		{name: "malformed", content: "apiVersion: platform.installer/v2alpha1\nkind: PlatformProject\nmetadata:\n  id: project-aaaaaaaaaaaaaaaa\n  labels:\n    platform.installer/managed-project: v1alpha1\n", want: classificationInvalid},
		{name: "desired-state", content: "apiVersion: platform.installer/v2alpha1\nkind: PlatformProject\nmetadata:\n  id: project-aaaaaaaaaaaaaaaa\n  name: Incorrect empty project\n  labels:\n    platform.installer/managed-project: v1alpha1\ndesiredStateContract: platform.installer/project-desired-state/v2alpha1\ndesiredState: {}\ncatalogLock:\n  apiVersion: platform.installer/catalog/v1alpha1\n  digest: sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n  services:\n    kafka:\n      definitionVersion: 1.0.0\n      digest: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\nartifactLock:\n  apiVersion: platform.installer/artifacts/v1alpha1\n  digest: sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc\n", want: classificationInvalid},
	} {
		root := filepath.Join(t.TempDir(), test.name)
		if err := os.Mkdir(root, 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(root, "project.yml"), []byte(test.content), 0o644); err != nil {
			t.Fatal(err)
		}
		result, _ := service.OpenProject(t.Context(), root)
		if result.Classification != test.want || result.Classification == classificationEmpty {
			t.Fatalf("%s: %+v", test.name, result)
		}
	}
}

func TestOpenClassifiesExternalCanonicalProjectWithoutAdoption(t *testing.T) {
	root := t.TempDir()
	if err := os.WriteFile(filepath.Join(root, "project.yml"), []byte("apiVersion: external/v1\nkind: External\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.Mkdir(filepath.Join(root, "inventory"), 0o755); err != nil {
		t.Fatal(err)
	}
	result, err := NewService(nil).OpenProject(t.Context(), root)
	if err != nil || result.Classification != classificationExternal || result.Project != nil {
		t.Fatalf("result=%+v err=%v", result, err)
	}
}

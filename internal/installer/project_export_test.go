package installer

import (
	"os"
	"path/filepath"
	"runtime"
	"testing"
)

func TestProjectExportCopiesOnlyPortableDocuments(t *testing.T) {
	root := t.TempDir()
	writeExportFixture(t, root, "project.yml", "apiVersion: platform.installer/v2alpha1\nmetadata:\n  id: project-test\n")
	writeExportFixture(t, root, "ansible.cfg", "[defaults]\nhost_key_checking = true\n")
	writeExportFixture(t, root, "inventory/hosts.yml", "all:\n  hosts: {}\n")
	writeExportFixture(t, root, "inventory/group_vars/all/platform-installer.yml", "# preserved\nplatform_project: {}\n")
	writeExportFixture(t, root, "inventory/group_vars/all/platform-state.yml", "generated: true\n")
	writeExportFixture(t, root, "inventory/host_vars/node1/extra.yaml", "extension: preserved\n")
	writeExportFixture(t, root, ".runtime/secret.txt", "must not copy\n")
	parent := filepath.Join(filepath.Dir(root), "exports")
	if err := os.Mkdir(parent, 0o755); err != nil {
		t.Fatal(err)
	}
	if directory, err := openExportDestinationDirectory(parent); err != nil {
		t.Fatalf("open destination: %v", err)
	} else {
		directory.close()
	}
	export, plan, err := PlanProjectExport(root, parent, "portable-copy")
	if err != nil {
		t.Fatal(err)
	}
	defer export.Close()
	if plan.SourceProjectRevision == "" || len(plan.Documents) != 5 {
		t.Fatalf("unexpected plan: %#v", plan)
	}
	for _, document := range plan.Documents {
		if document.LogicalPath == generatedDocument {
			t.Fatalf("generated document was included: %#v", plan.Documents)
		}
	}
	result := export.Commit(plan.PlanDigest)
	if result.Status != "EXPORTED" {
		t.Fatalf("Commit() = %#v", result)
	}
	copyRoot := filepath.Join(parent, "portable-copy")
	for _, logical := range []string{"project.yml", "ansible.cfg", "inventory/hosts.yml", "inventory/group_vars/all/platform-installer.yml", "inventory/host_vars/node1/extra.yaml"} {
		original, originalErr := os.ReadFile(filepath.Join(root, filepath.FromSlash(logical)))
		copied, copiedErr := os.ReadFile(filepath.Join(copyRoot, filepath.FromSlash(logical)))
		if logical == "project.yml" && originalErr == nil {
			original, originalErr = exportManifestName(original, "portable-copy")
		}
		if originalErr != nil || copiedErr != nil || string(original) != string(copied) {
			t.Fatalf("portable document %q was not copied exactly", logical)
		}
	}
	for _, logical := range []string{generatedDocument, ".runtime/secret.txt"} {
		if _, err := os.Stat(filepath.Join(copyRoot, filepath.FromSlash(logical))); !os.IsNotExist(err) {
			t.Fatalf("excluded document %q exists or has unexpected error %v", logical, err)
		}
	}
}

func TestProjectExportAllowsSiblingUnderSourceParent(t *testing.T) {
	parent := t.TempDir()
	source := filepath.Join(parent, "source-project")
	if err := os.Mkdir(source, 0o755); err != nil {
		t.Fatal(err)
	}
	writeExportFixture(t, source, "project.yml", "apiVersion: platform.installer/v2alpha1\n")
	export, plan, err := PlanProjectExport(source, parent, "full-service-install")
	if err != nil {
		t.Fatal(err)
	}
	defer export.Close()
	if result := export.Commit(plan.PlanDigest); result.Status != "EXPORTED" {
		t.Fatalf("sibling export: %+v", result)
	}
	if _, err := os.Stat(filepath.Join(parent, "full-service-install", "project.yml")); err != nil {
		t.Fatal(err)
	}
	for _, destination := range []struct{ parent, name string }{
		{parent, "source-project"},
		{source, "nested-export"},
	} {
		if _, _, err := PlanProjectExport(source, destination.parent, destination.name); err == nil || err.Error() != "EXPORT_DESTINATION_INVALID" {
			t.Fatalf("overlapping destination accepted: %v", err)
		}
	}
}

func TestProjectExportRejectsStalePlanAndExistingDestination(t *testing.T) {
	root := t.TempDir()
	writeExportFixture(t, root, "project.yml", "apiVersion: platform.installer/v2alpha1\n")
	parent := filepath.Join(filepath.Dir(root), "exports")
	if err := os.Mkdir(parent, 0o755); err != nil {
		t.Fatal(err)
	}
	export, plan, err := PlanProjectExport(root, parent, "portable-copy")
	if err != nil {
		t.Fatal(err)
	}
	if actual := export.Commit("sha256:not-the-plan"); actual.ErrorCode != "EXPORT_PLAN_STALE" {
		t.Fatalf("stale Commit() = %#v", actual)
	}
	export, _, err = PlanProjectExport(root, parent, "portable-copy")
	if err != nil {
		t.Fatal(err)
	}
	writeExportFixture(t, root, "project.yml", "apiVersion: platform.installer/v2alpha1\nchanged: true\n")
	if actual := export.Commit(export.Plan().PlanDigest); actual.ErrorCode != "PROJECT_CHANGED" && actual.ErrorCode != "EXPORT_PLAN_STALE" {
		t.Fatalf("changed Commit() = %#v", actual)
	}
	export.Close()
	if err := os.Mkdir(filepath.Join(parent, "already-exists"), 0o755); err != nil {
		t.Fatal(err)
	}
	if _, _, err := PlanProjectExport(root, parent, "already-exists"); err == nil || err.Error() != "EXPORT_DESTINATION_EXISTS" {
		t.Fatalf("existing destination error = %v", err)
	}
	_ = plan
}

func TestProjectExportPlatformPublish(t *testing.T) {
	parent := t.TempDir()
	destination, err := openExportDestinationDirectory(parent)
	if err != nil {
		t.Fatal(err)
	}
	defer destination.close()
	staging, name, err := destination.createStaging("export")
	if err != nil {
		t.Fatal(err)
	}
	defer staging.close()
	if err := destination.publish(staging, name, "published"); err != nil {
		t.Fatalf("publish: %v", err)
	}
}

func TestProjectExportRejectsLinkedPortableDocument(t *testing.T) {
	root, parent, outside := t.TempDir(), t.TempDir(), t.TempDir()
	writeExportFixture(t, root, "project.yml", "apiVersion: platform.installer/v2alpha1\n")
	writeExportFixture(t, outside, "hosts.yml", "all:\n  hosts: {}\n")
	if err := os.MkdirAll(filepath.Join(root, "inventory"), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(filepath.Join(outside, "hosts.yml"), filepath.Join(root, "inventory", "hosts.yml")); err != nil {
		if runtime.GOOS == "windows" {
			t.Skipf("symlink creation unavailable: %v", err)
		}
		t.Fatal(err)
	}
	if _, _, err := PlanProjectExport(root, parent, "portable-copy"); err == nil || err.Error() != "EXPORT_SOURCE_UNSAFE" {
		t.Fatalf("linked source err=%v", err)
	}
}

func TestProjectExportBoundsAreFailClosed(t *testing.T) {
	root, parent := t.TempDir(), t.TempDir()
	writeExportFixture(t, root, "project.yml", "apiVersion: platform.installer/v2alpha1\n")
	oversized := make([]byte, maxExportFileBytes+1)
	if err := os.WriteFile(filepath.Join(root, "ansible.cfg"), oversized, 0o600); err != nil {
		t.Fatal(err)
	}
	if _, _, err := PlanProjectExport(root, parent, "portable-copy"); err == nil || err.Error() != "EXPORT_LIMIT_EXCEEDED" {
		t.Fatalf("oversized source err=%v", err)
	}
}

func writeExportFixture(t *testing.T, root, logical, content string) {
	t.Helper()
	path := filepath.Join(root, filepath.FromSlash(logical))
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
}

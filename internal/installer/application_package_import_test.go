package installer

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func b2Package(t *testing.T) (string, string) {
	t.Helper()
	root := t.TempDir()
	files := map[string]string{
		"application.yml": "apiVersion: platform.installer/application-package/v1alpha1\nkind: ApplicationPackage\nname: gateway\nversion: 1.0.0\nfiles:\n  - roles/application_gateway/defaults/main.yml\n  - roles/application_gateway/templates/compose.yml.j2\nrender:\n  compose_template: roles/application_gateway/templates/compose.yml.j2\n",
		"roles/application_gateway/defaults/main.yml":        "platform_application_definition:\n  name: gateway\n  version: 1.0.0\n  defaults: {image: probe, command: ['/bin/probe']}\n",
		"roles/application_gateway/templates/compose.yml.j2": "services:\n  gateway:\n    image: '{{ image }}'\n    environment:\n      PASSWORD: 'password=synthetic-user-value'\n",
	}
	records := []exportRecord{}
	for name, content := range files {
		writeExportFixture(t, root, name, content)
		records = append(records, exportRecord{ProjectExportDocument: ProjectExportDocument{LogicalPath: "application-packages/gateway/1.0.0/" + name}, content: []byte(content)})
	}
	digest, err := checkPackageManifest(records, "application", "gateway", "1.0.0")
	if err != nil {
		t.Fatal(err)
	}
	return root, digest
}

func TestB2PackageRollbackAndConcurrentRevisionGuard(t *testing.T) {
	root, b, revision := b2Project(t)
	source, digest := b2Package(t)
	plan, _ := b.PlanApplicationPackageImport(context.Background(), root, source, revision, "application", "gateway", "1.0.0", digest)
	if plan.Status != "READY" {
		t.Fatalf("%+v", plan)
	}
	calls := 0
	b.replace = func(from, to string) error {
		calls++
		if calls == 2 {
			return errors.New("injected publication failure")
		}
		return atomicReplace(from, to)
	}
	result := b.CommitStructuralSave(context.Background(), plan.PlanID)
	if result.Status == "COMMITTED" {
		t.Fatal("injected write failure ignored")
	}
	if after, err := ProjectRevision(root); err != nil || after != revision {
		t.Fatalf("package transaction not rolled back: %s %v", after, err)
	}
	b.replace = atomicReplace
	plan, _ = b.PlanApplicationPackageImport(context.Background(), root, source, revision, "application", "gateway", "1.0.0", digest)
	if plan.Status != "READY" {
		t.Fatalf("retry=%+v", plan)
	}
	writeExportFixture(t, root, "inventory/group_vars/all/concurrent.yml", "external: true\n")
	if result := b.CommitStructuralSave(context.Background(), plan.PlanID); result.Changed {
		t.Fatal("stale package plan published")
	}
}

func TestB2PackageImportRevisionExportAndImmutableVersion(t *testing.T) {
	root, b, revision := b2Project(t)
	source, digest := b2Package(t)
	plan, err := b.PlanApplicationPackageImport(context.Background(), root, source, revision, "application", "gateway", "1.0.0", digest)
	if err != nil || plan.Status != "READY" {
		t.Fatalf("plan=%+v err=%v", plan, err)
	}
	if current, _ := ProjectRevision(root); current != revision {
		t.Fatal("package review changed project")
	}
	result := b.CommitStructuralSave(context.Background(), plan.PlanID)
	if result.Status != "COMMITTED" || result.NewProjectRevision == revision {
		t.Fatalf("%+v", result)
	}
	retry, _ := b.PlanApplicationPackageImport(context.Background(), root, source, result.NewProjectRevision, "application", "gateway", "1.0.0", digest)
	if retry.Status != "BLOCKED" {
		t.Fatal("package version replaced")
	}
	writeExportFixture(t, root, ".runtime/infrastructure-verification/cache.json", "must-not-export")
	export, _, err := PlanProjectExport(root, t.TempDir(), "copy")
	if err != nil {
		t.Fatal(err)
	}
	defer export.Close()
	templates := 0
	for _, d := range export.Plan().Documents {
		if strings.HasSuffix(d.LogicalPath, ".j2") {
			templates++
		}
		if strings.Contains(d.LogicalPath, ".runtime") {
			t.Fatal("cache exported")
		}
	}
	if templates != 1 {
		t.Fatal("template closure missing")
	}
}

func TestB2PackageRejectsDigestHookTraversalAndSymlink(t *testing.T) {
	root, b, revision := b2Project(t)
	source, digest := b2Package(t)
	for _, item := range []struct{ version, digest string }{{"../1.0.0", digest}, {"1.0.0", "sha256:" + strings.Repeat("a", 64)}} {
		p, _ := b.PlanApplicationPackageImport(context.Background(), root, source, revision, "application", "gateway", item.version, item.digest)
		if p.Status != "BLOCKED" {
			t.Fatal("unsafe package accepted")
		}
	}
	writeExportFixture(t, source, "roles/application_gateway/tasks/main.yml", "- shell: unsafe\n")
	p, _ := b.PlanApplicationPackageImport(context.Background(), root, source, revision, "application", "gateway", "1.0.0", digest)
	if p.Status != "BLOCKED" {
		t.Fatal("executable hook accepted")
	}
	if err := os.Remove(filepath.Join(source, "roles/application_gateway/tasks/main.yml")); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(t.TempDir(), filepath.Join(source, "escape")); err == nil {
		p, _ := b.PlanApplicationPackageImport(context.Background(), root, source, revision, "application", "gateway", "1.0.0", digest)
		if p.Status != "BLOCKED" {
			t.Fatal("symlink accepted")
		}
	}
}

func TestB2LibraryEnvAllowsUserPasswordName(t *testing.T) {
	prefix := "library-packages/demo/1.0.0/"
	records := []exportRecord{}
	for path, content := range map[string]string{
		"library.yml":                          "apiVersion: platform.installer/application-package/v1alpha1\nkind: LibraryPackage\nname: demo\nversion: 1.0.0\nfiles:\n  - roles/library_demo/defaults/main.yml\n  - files/.env\n",
		"roles/library_demo/defaults/main.yml": "platform_library_definition:\n  name: demo\n  version: 1.0.0\n",
		"files/.env":                           "PASSWORD=password=synthetic-user-value\nTOKEN=user-defined\n",
	} {
		records = append(records, exportRecord{ProjectExportDocument: ProjectExportDocument{LogicalPath: prefix + path}, content: []byte(content)})
	}
	if _, err := checkPackageManifest(records, "library", "demo", "1.0.0"); err != nil {
		t.Fatal(err)
	}
}

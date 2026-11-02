package installer

import (
	"bytes"
	"context"
	"errors"
	"os"
	"path/filepath"
	"platform-installer/internal/projectlifecycle"
	"reflect"
	"strings"
	"testing"
)

func TestApplicationDirectoryImportPreservesLargeAssetsAndLimits(t *testing.T) {
	root, b, revision := b2Project(t)
	source, _ := b2Package(t)
	manifest := filepath.Join(source, "application.yml")
	data, err := os.ReadFile(manifest)
	if err != nil {
		t.Fatal(err)
	}
	data = bytes.Replace(data, []byte("files:\n"), []byte("files:\n  - assets/providers/\n  - assets/themes.tar.gz\n"), 1)
	if err = os.WriteFile(manifest, data, 0600); err != nil {
		t.Fatal(err)
	}
	payload := bytes.Repeat([]byte{0, 255, 80, 75}, 16*1024*1024/4)
	if err = os.MkdirAll(filepath.Join(source, "assets/providers"), 0700); err != nil {
		t.Fatal(err)
	}
	if err = os.WriteFile(filepath.Join(source, "assets/providers/mock.jar"), payload, 0600); err != nil {
		t.Fatal(err)
	}
	archive := bytes.Repeat([]byte{0, 255, 80, 75}, 9*1024*1024/4)
	if err = os.WriteFile(filepath.Join(source, "assets/themes.tar.gz"), archive, 0600); err != nil {
		t.Fatal(err)
	}
	directory, err := openExportSourceDirectory(source)
	if err != nil {
		t.Fatal(err)
	}
	defer directory.close()
	observation := exportObservation{}
	if err = collectExportDirectory(directory, "application-packages/gateway/1.0.0", &observation, map[string]bool{}, map[string]bool{}); err != nil {
		t.Fatal(err)
	}
	digest, err := checkPackageManifest(observation.documents, "application", "gateway", "1.0.0")
	if err != nil {
		t.Fatal(err)
	}
	plan, err := b.PlanApplicationPackageImport(context.Background(), root, source, revision, "application", "gateway", "1.0.0", digest)
	if err != nil || plan.Status != "READY" {
		t.Fatalf("%v %+v", err, plan)
	}
	if result := b.CommitStructuralSave(context.Background(), plan.PlanID); !result.Changed {
		t.Fatalf("%+v", result)
	}
	actual, err := os.ReadFile(filepath.Join(root, "application-packages/gateway/1.0.0/assets/providers/mock.jar"))
	if err != nil || !bytes.Equal(payload, actual) {
		t.Fatal("binary bytes changed", err)
	}
	actualArchive, err := os.ReadFile(filepath.Join(root, "application-packages/gateway/1.0.0/assets/themes.tar.gz"))
	if err != nil || !bytes.Equal(archive, actualArchive) {
		t.Fatal("archive bytes changed", err)
	}
	export, _, err := PlanProjectExport(root, t.TempDir(), "szi-copy")
	if err != nil {
		t.Fatal("large package export failed", err)
	}
	export.Close()
	if err = os.WriteFile(filepath.Join(source, "assets/providers/new.jar"), []byte("new"), 0600); err != nil {
		t.Fatal(err)
	}
	updated := exportObservation{}
	if err = collectExportDirectory(directory, "application-packages/gateway/1.0.0", &updated, map[string]bool{}, map[string]bool{}); err != nil {
		t.Fatal(err)
	}
	updatedDigest, err := checkPackageManifest(updated.documents, "application", "gateway", "1.0.0")
	if err != nil || updatedDigest == digest {
		t.Fatalf("directory member did not change package digest: %v", err)
	}
	for _, ext := range []string{"jar", "java", "csv", "dat", "sh", "exe", "unknown"} {
		if !safeApplicationPackagePath("application-packages/gateway/1.0.0/assets/input." + ext) {
			t.Fatal(ext)
		}
	}
	if !safeApplicationPackagePath("application-packages/gateway/1.0.0/assets/noextension") {
		t.Fatal("file without extension rejected")
	}
	if safeApplicationPackagePath("application-packages/gateway/1.0.0/roles/application_gateway/tasks/hook.sh") {
		t.Fatal("controller task path accepted")
	}
	oversized, err := os.OpenFile(filepath.Join(source, "assets/providers/mock.jar"), os.O_RDWR, 0600)
	if err != nil {
		t.Fatal(err)
	}
	if err = oversized.Truncate(maxApplicationPackageFileBytes + 1); err != nil {
		t.Fatal(err)
	}
	if err = oversized.Close(); err != nil {
		t.Fatal(err)
	}
	if err = collectExportDirectory(directory, "application-packages/gateway/1.0.0", &exportObservation{}, map[string]bool{}, map[string]bool{}); err == nil {
		t.Fatal("oversized source accepted")
	}
}

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

func TestApplicationPackageManifestAcceptsGenericScripts(t *testing.T) {
	source, _ := b2Package(t)
	manifest := filepath.Join(source, "application.yml")
	data, err := os.ReadFile(manifest)
	if err != nil {
		t.Fatal(err)
	}
	data = bytes.Replace(data, []byte("files:\n"), []byte("files:\n  - assets/scripts/setup.sh\n"), 1)
	data = append(data, []byte("scripts:\n  - id: setup\n    source: assets/scripts/setup.sh\n    phase: after_ready\n    execution: once\n    argv: [--instance, {valueFrom: applicationId}]\n")...)
	if err := os.WriteFile(manifest, data, 0600); err != nil {
		t.Fatal(err)
	}
	writeExportFixture(t, source, "assets/scripts/setup.sh", "#!/bin/sh\nexit 0\n")
	directory, err := openExportSourceDirectory(source)
	if err != nil {
		t.Fatal(err)
	}
	defer directory.close()
	observation := exportObservation{}
	if err := collectExportDirectory(directory, "application-packages/gateway/1.0.0", &observation, map[string]bool{}, map[string]bool{}); err != nil {
		t.Fatal(err)
	}
	if _, err := checkPackageManifest(observation.documents, "application", "gateway", "1.0.0"); err != nil {
		t.Fatalf("generic script manifest rejected: %v", err)
	}
}

func TestApplicationPackageImportAcceptsManifestV2(t *testing.T) {
	source, _ := b2Package(t)
	manifest := filepath.Join(source, "application.yml")
	data, err := os.ReadFile(manifest)
	if err != nil {
		t.Fatal(err)
	}
	data = bytes.ReplaceAll(data, []byte("application-package/v1alpha1"), []byte("application-package/v1alpha2"))
	if err := os.WriteFile(manifest, data, 0600); err != nil {
		t.Fatal(err)
	}
	directory, err := openExportSourceDirectory(source)
	if err != nil {
		t.Fatal(err)
	}
	defer directory.close()
	observation := exportObservation{}
	if err := collectExportDirectory(directory, "application-packages/gateway/1.0.0", &observation, map[string]bool{}, map[string]bool{}); err != nil {
		t.Fatal(err)
	}
	if _, err := checkPackageManifest(observation.documents, "application", "gateway", "1.0.0"); err != nil {
		t.Fatal(err)
	}
}

func TestApplicationPackageImportAcceptsManifestV4(t *testing.T) {
	source, _ := b2Package(t)
	manifest := filepath.Join(source, "application.yml")
	data, err := os.ReadFile(manifest)
	if err != nil {
		t.Fatal(err)
	}
	data = bytes.ReplaceAll(data, []byte("application-package/v1alpha1"), []byte("application-package/v1alpha4"))
	if err := os.WriteFile(manifest, data, 0600); err != nil {
		t.Fatal(err)
	}
	directory, err := openExportSourceDirectory(source)
	if err != nil {
		t.Fatal(err)
	}
	defer directory.close()
	observation := exportObservation{}
	if err := collectExportDirectory(directory, "application-packages/gateway/1.0.0", &observation, map[string]bool{}, map[string]bool{}); err != nil {
		t.Fatal(err)
	}
	if _, err := checkPackageManifest(observation.documents, "application", "gateway", "1.0.0"); err != nil {
		t.Fatal(err)
	}
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

func TestB2PackageImportRevisionExportAndIdenticalReimport(t *testing.T) {
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
	if retry.Status != "NO_CHANGE" {
		t.Fatal("identical reimport was not a no-op")
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

func TestB2PackageRejectsHookTraversalAndSymlink(t *testing.T) {
	root, b, revision := b2Project(t)
	source, digest := b2Package(t)
	for _, item := range []struct{ version, digest string }{{"../1.0.0", digest}} {
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

func TestApplicationPackageImportReadsVersionWithoutExpectedSHA(t *testing.T) {
	for _, suppliedSHA := range []string{"", "sha256:" + strings.Repeat("a", 64)} {
		t.Run(suppliedSHA, func(t *testing.T) {
			root, b, revision := b2Project(t)
			source, _ := b2Package(t)
			plan, err := b.PlanApplicationPackageImport(context.Background(), root, source, revision, "application", "gateway", "", suppliedSHA)
			if err != nil || plan.Status != "READY" {
				t.Fatalf("import without manual version/SHA: %v %+v", err, plan)
			}
			if result := b.CommitStructuralSave(context.Background(), plan.PlanID); !result.Changed {
				t.Fatalf("%+v", result)
			}
			if _, err := os.Stat(filepath.Join(root, "application-packages/gateway/1.0.0/application.yml")); err != nil {
				t.Fatal(err)
			}
		})
	}
}

func TestLibraryPackageImportReadsManifestVersion(t *testing.T) {
	root, b, revision := b2Project(t)
	source := t.TempDir()
	writeExportFixture(t, source, "library.yml", "apiVersion: platform.installer/application-package/v1alpha1\nkind: LibraryPackage\nname: demo\nversion: 2.1.0\nfiles:\n  - roles/library_demo/defaults/main.yml\n")
	writeExportFixture(t, source, "roles/library_demo/defaults/main.yml", "platform_library_definition:\n  name: demo\n  version: 2.1.0\n")
	plan, err := b.PlanApplicationPackageImport(context.Background(), root, source, revision, "library", "demo", "", "")
	if err != nil || plan.Status != "READY" {
		t.Fatalf("%v %+v", err, plan)
	}
	if result := b.CommitStructuralSave(context.Background(), plan.PlanID); !result.Changed {
		t.Fatalf("%+v", result)
	}
	if _, err := os.Stat(filepath.Join(root, "library-packages/demo/2.1.0/library.yml")); err != nil {
		t.Fatal(err)
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

func TestApplicationPackagesBatchImport(t *testing.T) {
	for _, failure := range []string{"", "invalid", "existing", "empty"} {
		t.Run(failure, func(t *testing.T) {
			root, b, revision := b2Project(t)
			source := t.TempDir()
			if failure != "empty" {
				for _, version := range []string{"1.0.0", "2.0.0"} {
					pkg, _ := b2Package(t)
					err := filepath.WalkDir(pkg, func(path string, entry os.DirEntry, err error) error {
						if err != nil || entry.IsDir() {
							return err
						}
						data, err := os.ReadFile(path)
						if err != nil {
							return err
						}
						rel, err := filepath.Rel(pkg, path)
						if err != nil {
							return err
						}
						writeExportFixture(t, source, filepath.Join("gateway", version, rel), strings.ReplaceAll(string(data), "1.0.0", version))
						return nil
					})
					if err != nil {
						t.Fatal(err)
					}
				}
			}
			if failure == "invalid" {
				writeExportFixture(t, source, "gateway/2.0.0/unlisted.yml", "invalid: true\n")
			}
			if failure == "existing" {
				if err := os.MkdirAll(filepath.Join(root, "application-packages/gateway/2.0.0"), 0700); err != nil {
					t.Fatal(err)
				}
			}
			plan, err := b.PlanApplicationPackageImport(context.Background(), root, source, revision, "application", "", "", "")
			if err != nil {
				t.Fatal(err)
			}
			if failure != "" && failure != "existing" {
				if plan.Status != "BLOCKED" {
					t.Fatalf("invalid batch accepted: %+v", plan)
				}
				if _, err := os.Stat(filepath.Join(root, "application-packages/gateway/1.0.0")); !os.IsNotExist(err) {
					t.Fatal("partial import written")
				}
				return
			}
			if plan.Status != "READY" {
				t.Fatalf("%+v", plan)
			}
			if _, err := os.Stat(filepath.Join(root, "application-packages/gateway/1.0.0")); !os.IsNotExist(err) {
				t.Fatal("preview wrote project")
			}
			writeExportFixture(t, source, "gateway/1.0.0/application.yml", "changed after review")
			if result := b.CommitStructuralSave(context.Background(), plan.PlanID); !result.Changed {
				t.Fatalf("%+v", result)
			}
			for _, version := range []string{"1.0.0", "2.0.0"} {
				data, err := os.ReadFile(filepath.Join(root, "application-packages/gateway", version, "application.yml"))
				if err != nil || !strings.Contains(string(data), "version: "+version) {
					t.Fatalf("reviewed bytes not saved: %v", err)
				}
			}
		})
	}
}

func TestApplicationImportRepositoryLibraries(t *testing.T) {
	for _, item := range []struct{ library, example string }{{"szi", "szi"}, {"sdku", "sdku"}, {"cspa", "sdku"}} {
		t.Run(item.library, func(t *testing.T) {
			root, b, revision := b2Project(t)
			exampleRoot, err := filepath.Abs(filepath.Join("..", "..", "examples", item.example))
			if err != nil {
				t.Fatal(err)
			}
			source := filepath.Join(exampleRoot, "library-packages", item.library, "1.0.0")
			plan, err := b.PlanApplicationPackageImport(context.Background(), root, source, revision, "library", item.library, "", "")
			if err != nil || plan.Status != "READY" {
				t.Fatalf("library import: %v %+v", err, plan)
			}
			result := b.CommitStructuralSave(context.Background(), plan.PlanID)
			if !result.Changed {
				t.Fatalf("library commit: %+v", result)
			}
			revision, err = ProjectRevision(root)
			if err != nil {
				t.Fatal(err)
			}
			plan, err = b.PlanApplicationPackageImport(context.Background(), root, filepath.Join(exampleRoot, "application-packages"), revision, "application", "", "", "")
			if err != nil || plan.Status != "READY" {
				t.Fatalf("application batch: %v %+v", err, plan)
			}
			if result := b.CommitStructuralSave(context.Background(), plan.PlanID); !result.Changed {
				t.Fatalf("batch commit: %+v", result)
			}
		})
	}
}

func TestApplicationPackageImportDiagnostics(t *testing.T) {
	for _, tc := range []struct {
		name, path, message string
		mutate              func(*testing.T, string)
	}{
		{"missing", "application-packages/gateway/1.0.0/roles/application_gateway/templates/compose.yml.j2", "отсутствует", func(t *testing.T, source string) {
			if err := os.Remove(filepath.Join(source, "roles/application_gateway/templates/compose.yml.j2")); err != nil {
				t.Fatal(err)
			}
		}},
		{"unlisted", "application-packages/gateway/1.0.0/assets/extra.txt", "не объявлен", func(t *testing.T, source string) {
			writeExportFixture(t, source, "assets/extra.txt", "private-content-never-in-diagnostic")
		}},
		{"unsafe-path", "application-packages/gateway/1.0.0/roles/application_gateway/tasks/main.yml", "не разрешён", func(t *testing.T, source string) {
			writeExportFixture(t, source, "roles/application_gateway/tasks/main.yml", "private-content-never-in-diagnostic")
		}},
		{"defaults-version", "application-packages/gateway/1.0.0/roles/application_gateway/defaults/main.yml", "Версия в defaults", func(t *testing.T, source string) {
			writeExportFixture(t, source, "roles/application_gateway/defaults/main.yml", "platform_application_definition:\n  name: gateway\n  version: 2.0.0\n")
		}},
	} {
		t.Run(tc.name, func(t *testing.T) {
			root, b, revision := b2Project(t)
			source, _ := b2Package(t)
			tc.mutate(t, source)
			plan, err := b.PlanApplicationPackageImport(context.Background(), root, source, revision, "application", "gateway", "", "")
			if err != nil || plan.Status != "BLOCKED" || plan.Finding == nil {
				t.Fatalf("%v %+v", err, plan)
			}
			if plan.Finding.Field != tc.path || !strings.Contains(plan.Finding.SafeMessage, tc.path) || !strings.Contains(plan.Finding.SafeMessage, tc.message) {
				t.Fatalf("%+v", plan.Finding)
			}
			if strings.Contains(plan.Finding.SafeMessage, "private-content-never-in-diagnostic") {
				t.Fatal("file contents exposed")
			}
			if after, err := ProjectRevision(root); err != nil || after != revision {
				t.Fatal("blocked import changed project", err)
			}
		})
	}
}

func TestImportedApplicationsEnrollAllMatchingLibrariesAtomically(t *testing.T) {
	for _, stale := range []bool{false, true} {
		t.Run(map[bool]string{false: "commit", true: "stale-plan"}[stale], func(t *testing.T) {
			root, backend, _ := b2Project(t)
			for _, pkg := range []struct{ name, version string }{{"demo", "1.0.0"}, {"other", "2.0.0"}} {
				prefix := "library-packages/" + pkg.name + "/1.0.0/"
				writeExportFixture(t, root, prefix+"library.yml", "apiVersion: platform.installer/application-package/v1alpha1\nkind: LibraryPackage\nname: "+pkg.name+"\nversion: 1.0.0\nfiles: [roles/library_"+pkg.name+"/defaults/main.yml]\n")
				writeExportFixture(t, root, prefix+"roles/library_"+pkg.name+"/defaults/main.yml", "platform_library_definition:\n  name: "+pkg.name+"\n  version: 1.0.0\n  slots:\n    gateway:\n      applicationRef: gateway@"+pkg.version+"\n      required: false\n")
			}
			retained := map[string]any{"overrides": map[string]any{"image": "retained/image", "environment": map[string]any{"KEEP": "value"}}}
			for _, id := range []string{"one", "two", "other"} {
				revision, err := ProjectRevision(root)
				if err != nil {
					t.Fatal(err)
				}
				command := b2Command(revision, "CreateApplicationLibraryDeployment")
				command.DeploymentID = id
				ref := "demo@1.0.0"
				if id == "other" {
					ref = "other@1.0.0"
				}
				command.Entity = map[string]any{"libraryRef": ref, "runtimeRef": "kafka-main", "applications": map[string]any{}}
				if id == "one" {
					command.Entity["applications"] = map[string]any{"gateway": retained}
				}
				commitStructuralForTest(t, backend, root, projectlifecycle.ClassificationManaged, revision, []EditCommand{command})
			}
			revision, err := ProjectRevision(root)
			if err != nil {
				t.Fatal(err)
			}
			source, _ := b2Package(t)
			plan, err := backend.PlanApplicationPackageImport(context.Background(), root, source, revision, "application", "gateway", "", "")
			if err != nil || plan.Status != "READY" {
				t.Fatalf("%v %+v", err, plan)
			}
			view, err := ReadManagedProjectView(root)
			if err != nil {
				t.Fatal(err)
			}
			if len(asMap(view.ApplicationLibraries["two"]["applications"])) != 0 {
				t.Fatal("review modified library")
			}
			found := false
			for _, change := range plan.SemanticChanges {
				if change.EntityID == "two/gateway" {
					found = true
				}
			}
			if !found {
				t.Fatal("review omits automatic enrollment")
			}
			if stale {
				file := filepath.Join(root, filepath.FromSlash(desiredDocument))
				data, err := os.ReadFile(file)
				if err != nil {
					t.Fatal(err)
				}
				if err = os.WriteFile(file, append(data, []byte("\n# concurrent change\n")...), 0600); err != nil {
					t.Fatal(err)
				}
			}
			result := backend.CommitStructuralSave(context.Background(), plan.PlanID)
			view, err = ReadManagedProjectView(root)
			if err != nil {
				t.Fatal(err)
			}
			if stale {
				if result.Changed || len(asMap(view.ApplicationLibraries["two"]["applications"])) != 0 {
					t.Fatal("stale import published library changes")
				}
				if _, err := os.Stat(filepath.Join(root, "application-packages/gateway/1.0.0")); !os.IsNotExist(err) {
					t.Fatal("stale import published package")
				}
				return
			}
			if !result.Changed {
				t.Fatalf("%+v", result)
			}
			if _, ok := asMap(view.ApplicationLibraries["two"]["applications"])["gateway"]; !ok {
				t.Fatal("optional matching slot not enrolled")
			}
			if !reflect.DeepEqual(asMap(view.ApplicationLibraries["one"]["applications"])["gateway"], retained) {
				t.Fatal("existing settings overwritten")
			}
			if len(asMap(view.ApplicationLibraries["other"]["applications"])) != 0 {
				t.Fatal("different version enrolled")
			}
			if _, err := os.Stat(filepath.Join(root, "application-packages/gateway/1.0.0/application.yml")); err != nil {
				t.Fatal(err)
			}
		})
	}
}

func TestApplicationPackageReimportReplacesClosureAndRollsBack(t *testing.T) {
	for _, fail := range []bool{false, true} {
		t.Run(map[bool]string{false: "commit", true: "rollback"}[fail], func(t *testing.T) {
			root, b, revision := b2Project(t)
			source, _ := b2Package(t)
			manifest := filepath.Join(source, "application.yml")
			original := mustRead(t, manifest)
			if err := os.WriteFile(manifest, bytes.Replace(original, []byte("files:\n"), []byte("files:\n  - assets/old.bin\n"), 1), 0600); err != nil {
				t.Fatal(err)
			}
			writeExportFixture(t, source, "assets/old.bin", "old binary")
			first, _ := b.PlanApplicationPackageImport(context.Background(), root, source, revision, "application", "gateway", "", "")
			saved := b.CommitStructuralSave(context.Background(), first.PlanID)
			if saved.Status != "COMMITTED" {
				t.Fatalf("initial: %+v", saved)
			}
			before := saved.NewProjectRevision
			if err := os.Remove(filepath.Join(source, "assets/old.bin")); err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(manifest, bytes.Replace(original, []byte("files:\n"), []byte("files:\n  - assets/new.bin\n"), 1), 0600); err != nil {
				t.Fatal(err)
			}
			writeExportFixture(t, source, "assets/new.bin", "new binary")
			plan, err := b.PlanApplicationPackageImport(context.Background(), root, source, before, "application", "gateway", "", "")
			if err != nil || plan.Status != "READY" {
				t.Fatalf("replacement: %+v %v", plan, err)
			}
			foundDelete := false
			for _, d := range plan.AffectedDocuments {
				if strings.HasSuffix(d.LogicalPath, "old.bin") {
					foundDelete = d.After.State == "ABSENT"
				}
			}
			if !foundDelete {
				t.Fatal("obsolete file deletion not disclosed")
			}
			if current, _ := ProjectRevision(root); current != before {
				t.Fatal("review mutated project")
			}
			if fail {
				b.replace = func(string, string) error { return errors.New("injected replacement failure") }
			}
			result := b.CommitStructuralSave(context.Background(), plan.PlanID)
			prefix := filepath.Join(root, "application-packages/gateway/1.0.0/assets")
			if fail {
				if result.Status == "COMMITTED" {
					t.Fatal("failure ignored")
				}
				if got := string(mustRead(t, filepath.Join(prefix, "old.bin"))); got != "old binary" {
					t.Fatal("deleted file not restored")
				}
				if current, err := ProjectRevision(root); err != nil || current != before {
					t.Fatalf("rollback revision: %v", err)
				}
			} else {
				if result.Status != "COMMITTED" {
					t.Fatalf("replacement failed: %+v", result)
				}
				if _, err := os.Stat(filepath.Join(prefix, "old.bin")); !os.IsNotExist(err) {
					t.Fatal("obsolete file retained")
				}
				if string(mustRead(t, filepath.Join(prefix, "new.bin"))) != "new binary" {
					t.Fatal("new file missing")
				}
				retry, _ := b.PlanApplicationPackageImport(context.Background(), root, source, result.NewProjectRevision, "application", "gateway", "", "")
				if retry.Status != "NO_CHANGE" {
					t.Fatalf("identical retry: %+v", retry)
				}
			}
		})
	}
}

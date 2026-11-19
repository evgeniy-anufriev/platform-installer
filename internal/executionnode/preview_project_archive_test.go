package executionnode

import (
	"archive/tar"
	"bytes"
	"io"
	"os"
	"path/filepath"
	"testing"

	"platform-installer/internal/installer"
)

func writePreviewProjectFile(t *testing.T, root, name, value string) {
	t.Helper()
	path := filepath.Join(root, filepath.FromSlash(name))
	if err := os.MkdirAll(filepath.Dir(path), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(value), 0600); err != nil {
		t.Fatal(err)
	}
}

func TestServicePreviewProjectsOnlyRequiredPackageAssets(t *testing.T) {
	root := t.TempDir()
	const pkg = "library-packages/example/1.0.0/"
	const app = "application-packages/example/1.0.0/"
	writePreviewProjectFile(t, root, "inventory/hosts.yml", "all: {}\n")
	writePreviewProjectFile(t, root, "inventory/group_vars/all/settings.yml",
		"value: \"{{ lookup('ansible.builtin.template', 'assets/settings.j2') }}\"\n")
	writePreviewProjectFile(t, root, pkg+"assets/settings.j2", "{{ query('file', 'assets/example.txt') }}")
	writePreviewProjectFile(t, root, pkg+"assets/example.txt", "included")
	writePreviewProjectFile(t, root, pkg+"assets/database.dump", "omitted")
	writePreviewProjectFile(t, root, app+"assets/large.bin", "omitted")
	writePreviewProjectFile(t, root, pkg+"roles/library_example/defaults/main.yml",
		"value: \"{{ lookup('template', platform_project_root ~ '/assets/groups.j2') }}\"\n")
	writePreviewProjectFile(t, root, app+"roles/application_example/defaults/main.yml",
		"value: \"{{ lookup('file', application_path) }}\"\n")
	writePreviewProjectFile(t, root, app+"roles/application_example/templates/compose.yml.j2",
		"{{ lookup('file', application_path) }}")
	files, err := previewAssetFiles(root)
	if err != nil || files == nil {
		t.Fatalf("expected a reduced archive, got %v", err)
	}
	if len(files.omitted) != 2 || !files.omitted[pkg+"assets/database.dump"] || !files.omitted[app+"assets/large.bin"] {
		t.Fatalf("unexpected file selection: %v", files.omitted)
	}
	var archive bytes.Buffer
	writer := tar.NewWriter(&archive)
	if err := files.writeArchive(root, writer); err != nil {
		t.Fatal(err)
	}
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
	extracted := t.TempDir()
	reader := tar.NewReader(&archive)
	for {
		entry, err := reader.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			t.Fatal(err)
		}
		if entry.Typeflag == tar.TypeDir {
			continue
		}
		data, err := io.ReadAll(reader)
		if err != nil {
			t.Fatal(err)
		}
		if files.omitted[entry.Name] {
			t.Fatalf("unexpected entry: %s", entry.Name)
		}
		writePreviewProjectFile(t, extracted, entry.Name, string(data))
	}
	full, projected, err := installer.PreviewProjectRevisions(root, files.omitted)
	if err != nil {
		t.Fatal(err)
	}
	actual, err := installer.ProjectRevision(extracted)
	if err != nil || actual != projected || full == projected {
		t.Fatalf("preview revisions do not match staged inputs: %v", err)
	}
}

func TestServicePreviewUsesFullArchiveForUnprovedInputs(t *testing.T) {
	for _, tc := range []struct{ name, source, content string }{
		{"dynamic lookup", "inventory/group_vars/all.yml", "value: \"{{ lookup('file', filename) }}\"\n"},
		{"encoded dynamic lookup", "inventory/group_vars/all.yml", `value: "\u007b\u007b lookup('file', filename) }}"`},
		{"template include", "inventory/group_vars/all.yml", "value: \"{% include filename %}\"\n"},
		{"unknown template", "inventory/group_vars/all.yml", "value: \"{{ lookup('template', 'elsewhere.j2') }}\"\n"},
		{"custom inventory plugin", "inventory/hosts.yml", "plugin: custom\n"},
		{"encrypted inputs", "inventory/group_vars/all.yml", "value: !vault |\n  opaque\n"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			root := t.TempDir()
			writePreviewProjectFile(t, root, "inventory/hosts.yml", "all: {}\n")
			writePreviewProjectFile(t, root, tc.source, tc.content)
			writePreviewProjectFile(t, root, "library-packages/example/1.0.0/assets/database.dump", "full fallback")
			files, err := previewAssetFiles(root)
			if err != nil || files != nil {
				t.Fatalf("expected full archive fallback, got selection=%v error=%v", files != nil, err)
			}
		})
	}
}

func TestServicePreviewFollowsReferenceIntoPackageDefaults(t *testing.T) {
	root := t.TempDir()
	const defaults = "library-packages/example/1.0.0/roles/library_example/defaults/main.yml"
	writePreviewProjectFile(t, root, "inventory/hosts.yml", "all: {}\n")
	writePreviewProjectFile(t, root, "inventory/group_vars/all.yml",
		"value: \"{{ lookup('template', '"+defaults+"') }}\"\n")
	writePreviewProjectFile(t, root, defaults, "value: \"{{ query('file', filename) }}\"\n")
	writePreviewProjectFile(t, root, "library-packages/example/1.0.0/assets/database.dump", "full fallback")
	files, err := previewAssetFiles(root)
	if err != nil || files != nil {
		t.Fatalf("expected full archive for a referenced dynamic dependency, got selection=%v error=%v", files != nil, err)
	}
}

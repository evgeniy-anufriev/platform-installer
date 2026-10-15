package executionnode

import (
	"archive/tar"
	"io"
	"os"
	"path/filepath"
	"testing"

	"platform-installer/internal/installer"
)

func TestProjectArchivePreservesApplicationPackageRevision(t *testing.T) {
	root := t.TempDir()
	files := map[string]string{
		"ansible.cfg":         managedCandidateAnsibleConfig,
		"project.yml":         "metadata: {id: package-transfer}\n",
		"inventory/hosts.yml": "all: {hosts: {node1: {}}}\n",
		"library-packages/demo/1.0.0/library.yml":                                               "name: demo\n",
		"library-packages/demo/1.0.0/files/.env":                                                "USER_PARAMETER=kept\n",
		"application-packages/gateway/1.0.0/application.yml":                                    "name: gateway\n",
		"application-packages/gateway/1.0.0/roles/application_gateway/templates/compose.yml.j2": "services: {{ applications }}\n",
	}
	for logical, content := range files {
		file := filepath.Join(root, filepath.FromSlash(logical))
		if err := os.MkdirAll(filepath.Dir(file), 0700); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(file, []byte(content), 0600); err != nil {
			t.Fatal(err)
		}
	}
	want, err := installer.ProjectRevision(root)
	if err != nil {
		t.Fatal(err)
	}
	for _, factory := range []struct {
		name   string
		create func(string) (string, error)
	}{{"plan", createProjectArchive}, {"candidate", createCandidateProjectArchive}} {
		t.Run(factory.name, func(t *testing.T) {
			archive, err := factory.create(root)
			if err != nil {
				t.Fatal(err)
			}
			defer os.Remove(archive)
			input, err := os.Open(archive)
			if err != nil {
				t.Fatal(err)
			}
			defer input.Close()
			extracted := t.TempDir()
			reader := tar.NewReader(input)
			for {
				header, err := reader.Next()
				if err == io.EOF {
					break
				}
				if err != nil {
					t.Fatal(err)
				}
				file := filepath.Join(extracted, filepath.FromSlash(header.Name))
				if header.Typeflag == tar.TypeDir {
					if err := os.MkdirAll(file, 0700); err != nil {
						t.Fatal(err)
					}
					continue
				}
				content, err := io.ReadAll(reader)
				if err != nil {
					t.Fatal(err)
				}
				if string(content) != files[header.Name] {
					t.Fatalf("unexpected or changed document %s", header.Name)
				}
				if err := os.MkdirAll(filepath.Dir(file), 0700); err != nil {
					t.Fatal(err)
				}
				if err := os.WriteFile(file, content, 0600); err != nil {
					t.Fatal(err)
				}
			}
			got, err := installer.ProjectRevision(extracted)
			if err != nil {
				t.Fatal(err)
			}
			if got != want {
				t.Fatalf("transferred revision %s differs from %s", got, want)
			}
		})
	}
}

func TestCandidatePackagePathsRemainDataOnly(t *testing.T) {
	for _, logical := range []string{"library-packages/demo/1.0.0/roles/library_demo/tasks/main.yml", "application-packages/gateway/1.0.0/plugins/action/test.py", "library-packages/demo/1.0.0/secrets/admin-token", "library-packages/demo/1.0.0/assets/../../secret.txt", "library-packages/demo/latest/library.yml"} {
		if candidateArchiveLogicalPathAllowed(logical) {
			t.Fatalf("unsafe package path accepted: %s", logical)
		}
	}
}

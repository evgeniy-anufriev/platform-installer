package main

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"testing"

	"platform-installer/internal/installer"
	"platform-installer/internal/projectlifecycle"
)

func secretFileTestApp(t *testing.T) *App {
	t.Helper()
	a := NewApp(unavailableProjectReader{}, lifecycleStub{})
	a.ctx = context.Background()
	a.current = ProjectOpenResult{Status: "OPEN", Root: t.TempDir(), Project: &projectlifecycle.Project{ID: "project-aaaaaaaaaaaaaaaa"},
		Managed: &installer.ManagedProjectView{Deployments: map[string]installer.ManagedDeployment{"vault-main": {DeploymentID: "vault-main", ServiceType: "vault", Mode: "standalone"}}},
		Catalog: &projectlifecycle.ProjectCatalogView{Status: "READY", Services: []projectlifecycle.ProjectCatalogService{{ID: "vault", Modes: []projectlifecycle.ProjectCatalogMode{{ID: "standalone"}}, SecretInputs: []projectlifecycle.ProjectCatalogSecretInput{{RequirementRef: "admin-token", Purpose: "SERVICE_ADMIN_TOKEN", DisplayLabel: "Admin", RequiredWhen: "INITIALIZED", Operations: []string{"SERVICE_APPLY"}}}}}}}
	return a
}

func TestSecretFileSelectionSeamRetainsImportGuards(t *testing.T) {
	for _, scenario := range []string{"valid", "cancel", "picker-error", "missing-file", "invalid-file", "token-line-ending", "wrong-purpose", "project-changed"} {
		t.Run(scenario, func(t *testing.T) {
			a := secretFileTestApp(t)
			path := filepath.Join(t.TempDir(), "token.json")
			contents := []byte(`{"root_token":"synthetic-token"}`)
			if scenario == "invalid-file" {
				contents = []byte(`{"root_token":7}`)
			}
			if scenario == "token-line-ending" {
				contents = []byte("synthetic-token\n")
			}
			if err := os.WriteFile(path, contents, 0600); err != nil {
				t.Fatal(err)
			}
			called := false
			a.chooseSecretFile = func(context.Context, DialogOptions) (string, error) {
				called = true
				switch scenario {
				case "cancel":
					return "", nil
				case "picker-error":
					return "", errors.New("PRIVATE_DETAIL")
				case "missing-file":
					return path + ".absent", nil
				case "project-changed":
					a.current.Project = &projectlifecycle.Project{ID: "project-bbbbbbbbbbbbbbbb"}
				}
				return path, nil
			}
			input := PendingRuntimeSecretFileInput{ServiceDeployment: "vault-main", Purpose: "SERVICE_ADMIN_TOKEN"}
			if scenario == "wrong-purpose" {
				input.Purpose = "UNSUPPORTED"
			}
			status, err := a.ChoosePendingDeploymentRuntimeSecretFile(input)
			if scenario == "valid" {
				if err != nil || status != "STORED" {
					t.Fatal("valid file not imported")
				}
			} else if scenario == "cancel" {
				if err != nil || status != "CANCELLED" {
					t.Fatal("cancel not preserved")
				}
			} else {
				expected := map[string]string{"picker-error": "SECRET_FILE_SELECTION_FAILED", "missing-file": "SECRET_FILE_INVALID", "invalid-file": "SECRET_FILE_INVALID", "token-line-ending": "SECRET_FILE_INVALID", "wrong-purpose": "RUNTIME_SECRET_DESCRIPTOR_NOT_FOUND", "project-changed": "PROJECT_CHANGED"}[scenario]
				if err == nil || err.Error() != expected {
					t.Fatal("safe guard failed")
				}
			}
			if scenario == "wrong-purpose" && called {
				t.Fatal("unauthorized picker invoked")
			}
			after, readErr := os.ReadFile(path)
			if readErr != nil || string(after) != string(contents) {
				t.Fatal("selected source file mutated")
			}
		})
	}
}

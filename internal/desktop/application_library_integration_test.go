package desktop

import (
	"os"
	"path/filepath"
	"platform-installer/internal/installer"
	"platform-installer/internal/projectlifecycle"
	"testing"
)

func TestB4LibraryEditsUseProductionSessionAllowlist(t *testing.T) {
	for _, op := range []string{"CreateApplicationLibraryDeployment", "UpdateApplicationLibraryDeployment", "DeleteApplicationLibraryDeployment", "SetApplicationLibrarySlot", "RemoveApplicationLibrarySlot", "SetApplicationLibraryPlacement", "RemoveApplicationLibraryPlacement", "SetApplicationLibraryOverride", "RemoveApplicationLibraryOverride"} {
		t.Run(op, func(t *testing.T) {
			root := t.TempDir()
			if err := os.WriteFile(filepath.Join(root, "project.yml"), []byte("metadata: {id: project-aaaaaaaaaaaaaaaa}\n"), 0600); err != nil {
				t.Fatal(err)
			}
			app := NewApp(editorReaderStub{}, lifecycleStub{})
			app.current = ProjectOpenResult{Status: "OPEN", Root: root, Classification: projectlifecycle.ClassificationEmpty, Project: &projectlifecycle.Project{ID: "project-aaaaaaaaaaaaaaaa"}}
			started := app.StartEditSession()
			if started.Session == nil {
				t.Fatal(started.Error)
			}
			cmd := installer.EditCommand{Operation: op, DeploymentID: "sdku"}
			switch op {
			case "CreateApplicationLibraryDeployment", "UpdateApplicationLibraryDeployment":
				cmd.Entity = map[string]any{"libraryRef": "sdku@1.0.0", "runtimeRef": "docker-main"}
			case "SetApplicationLibrarySlot":
				cmd.EntityID = "gateway"
				cmd.Entity = map[string]any{"overrides": map[string]any{"environment": map[string]any{"PASSWORD": "synthetic-user-parameter"}}}
			case "RemoveApplicationLibrarySlot":
				cmd.EntityID = "gateway"
			case "SetApplicationLibraryPlacement":
				cmd.HostID = "node1"
				cmd.Placement = map[string]any{}
			case "RemoveApplicationLibraryPlacement":
				cmd.HostID = "node1"
			case "SetApplicationLibraryOverride":
				cmd.EntityID = "gateway"
				cmd.Property = "environment"
				cmd.Setting = "PASSWORD"
				cmd.Value = "synthetic-user-parameter"
			case "RemoveApplicationLibraryOverride":
				cmd.EntityID = "gateway"
				cmd.Property = "environment"
				cmd.Setting = "PASSWORD"
			}
			result := app.AppendEditCommand(started.Session.SessionID, cmd)
			if result.Error != nil || result.Session == nil || result.Session.CommandCount != 1 {
				t.Fatalf("%+v", result)
			}
			before, _ := os.ReadFile(filepath.Join(root, "project.yml"))
			if len(before) == 0 {
				t.Fatal("canonical project lost")
			}
			if got := app.DiscardEditSession(started.Session.SessionID); got.Error != nil {
				t.Fatal(got.Error)
			}
		})
	}
}

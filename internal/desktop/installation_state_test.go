package desktop

import (
	"os"
	"path/filepath"
	"testing"

	"platform-installer/internal/installer"
	"platform-installer/internal/projectlifecycle"
)

func TestInstallationStateIsLocalReadOnlyAndBlocksMissingPrerequisites(t *testing.T) {
	root := t.TempDir()
	writeInstallationProject(t, root)
	app := NewApp(snapshotReaderStub{}, lifecycleStub{})
	app.current = ProjectOpenResult{Status: "OPEN", Root: root, Project: &projectlifecycle.Project{ID: "project-aaaaaaaaaaaaaaaa"}, Verification: ProjectVerification{Status: "VERIFIED"}}

	state := app.GetInstallationState()
	if state.Status != installationStatePrerequisitesRequired || state.Project == nil || state.Project.Revision == "" {
		t.Fatalf("state=%#v", state)
	}
	if state.Plan.Status != installationPlanNotCreated || len(state.Prerequisites) != 1 || state.Prerequisites[0].Code != "EXECUTION_NODE_READY_REQUIRED" {
		t.Fatalf("state=%#v", state)
	}
	if state.Project.VerificationStatus != "VERIFIED" || state.ExecutionNode.Status != executionNodeNotConfigured {
		t.Fatalf("state=%#v", state)
	}
}

func TestInstallationStateRequiresSaveBeforeReadyNode(t *testing.T) {
	root := t.TempDir()
	writeInstallationProject(t, root)
	app := NewApp(snapshotReaderStub{}, lifecycleStub{})
	app.current = ProjectOpenResult{Status: "OPEN", Root: root, Project: &projectlifecycle.Project{ID: "project-aaaaaaaaaaaaaaaa"}}
	revision, err := installer.ProjectRevision(root)
	if err != nil {
		t.Fatal(err)
	}
	session, err := app.sessions.Start("project-aaaaaaaaaaaaaaaa", root, projectlifecycle.ClassificationManaged, revision)
	if err != nil {
		t.Fatal(err)
	}
	app.activeSession = session.SessionID
	app.execution.context = ExecutionNodeContext{Status: "READY", SelectionKind: "EXPLICIT_EXTERNAL"}

	state := app.GetInstallationState()
	if state.Status != installationStatePrerequisitesRequired || state.Project == nil || !state.Project.HasUnsavedChanges || len(state.Prerequisites) != 1 || state.Prerequisites[0].Code != "PROJECT_CHANGES_UNSAVED" {
		t.Fatalf("state=%#v", state)
	}
}

func TestInstallationStateRequiresTrustedBindingBeforePlan(t *testing.T) {
	root := t.TempDir()
	writeInstallationProject(t, root)
	app := NewApp(snapshotReaderStub{}, lifecycleStub{})
	app.current = ProjectOpenResult{Status: "OPEN", Root: root, Project: &projectlifecycle.Project{ID: "project-aaaaaaaaaaaaaaaa"}}
	app.execution.context = ExecutionNodeContext{Status: "READY", SelectionKind: "EXPLICIT_EXTERNAL"}

	state := app.GetInstallationState()
	if state.Status != installationStatePrerequisitesRequired || len(state.Prerequisites) != 1 || state.Prerequisites[0].Code != "EXECUTION_NODE_BINDING_REQUIRED" {
		t.Fatalf("state=%#v", state)
	}
}

func TestInstallationStateFailsSafelyWhenRevisionCannotBeRead(t *testing.T) {
	app := NewApp(snapshotReaderStub{}, lifecycleStub{})
	app.current = ProjectOpenResult{Status: "OPEN", Root: filepath.Join(t.TempDir(), "missing"), Project: &projectlifecycle.Project{ID: "project-aaaaaaaaaaaaaaaa"}}

	state := app.GetInstallationState()
	if state.Status != installationStatePrerequisitesRequired || state.Project != nil || len(state.Prerequisites) != 1 || state.Prerequisites[0].Code != "PROJECT_REVISION_UNAVAILABLE" {
		t.Fatalf("state=%#v", state)
	}
}

func writeInstallationProject(t *testing.T, root string) {
	t.Helper()
	content := "apiVersion: platform.installer/v2alpha1\nkind: PlatformProject\nmetadata:\n  id: project-aaaaaaaaaaaaaaaa\n  name: Test\n"
	if err := os.WriteFile(filepath.Join(root, "project.yml"), []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
}

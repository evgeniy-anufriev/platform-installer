package main

import (
	"os"
	"path/filepath"
	"testing"

	"platform-installer/internal/installer"
	"platform-installer/internal/projectlifecycle"
)

// This opt-in fixture prepares only local disposable files for the real Wails
// bridge check. It neither contacts an Execution Node nor invokes rebind.
func TestPrepareRuntimeBundleRebindWailsFixture(t *testing.T) {
	root := os.Getenv("PLATFORM_QA_REBIND_FIXTURE_ROOT")
	if root == "" {
		t.Skip("set PLATFORM_QA_REBIND_FIXTURE_ROOT for disposable Wails acceptance")
	}
	if !filepath.IsAbs(root) {
		t.Fatal("fixture path must be absolute")
	}
	if _, err := os.Lstat(root); !os.IsNotExist(err) {
		t.Fatalf("fixture path must not exist: %v", err)
	}
	if err := os.Mkdir(root, 0o700); err != nil {
		t.Fatal(err)
	}
	oldBundle := rebindTestBundle(t, "wails-old")
	oldRoot := filepath.Join(root, "old-runtime")
	if err := os.Rename(oldBundle, oldRoot); err != nil {
		t.Fatal(err)
	}
	service := projectlifecycle.NewService(map[string]string{projectlifecycle.DefaultCompatibilitySourceID: oldRoot})
	app := NewApp(unavailableProjectReader{}, service, testApplicationConfig(), WithAvailableExecutionBundle(oldRoot), WithBundleCacheRoot(filepath.Join(root, "cache")), WithLocalRunRecordRoot(filepath.Join(root, "run-records")))
	projectRoot := filepath.Join(root, "project")
	created := app.CreateProject(projectlifecycle.CreateProjectRequest{ProjectRoot: projectRoot, DisplayName: "Bundle rebind Wails QA", CompatibilitySourceID: projectlifecycle.DefaultCompatibilitySourceID})
	if created.Status != "OPEN" {
		t.Fatalf("create=%+v", created)
	}
	started := app.StartEditSession()
	if started.Session == nil {
		t.Fatalf("edit=%+v", started)
	}
	appended := app.AppendEditCommand(started.Session.SessionID, installer.EditCommand{Operation: "CreateServer", HostID: "node1", ServerType: "infra", DesiredHostname: "node1.example.internal", Address: "192.0.2.10", SSHPort: 22})
	if appended.Session == nil || appended.Session.CommandCount != 1 {
		t.Fatalf("append=%+v", appended)
	}
	reviewed := app.ReviewStructuralEditSession(started.Session.SessionID)
	if reviewed.Plan == nil || !reviewed.Plan.SaveAllowed {
		t.Fatalf("review=%+v", reviewed)
	}
	committed := app.CommitStructuralEditPlan(started.Session.SessionID, reviewed.Plan.PlanID)
	if committed.Commit == nil || committed.Status != "COMMITTED" {
		t.Fatalf("commit=%+v", committed)
	}
	newBundle := rebindTestBundle(t, "wails-new")
	if err := os.Rename(newBundle, filepath.Join(projectRoot, "bundle")); err != nil {
		t.Fatal(err)
	}
	t.Logf("fixture prepared: project=%s oldRuntime=%s", projectRoot, oldRoot)
}

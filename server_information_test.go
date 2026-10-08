package main

import (
	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
	"platform-installer/internal/projectlifecycle"
	"testing"
)

// The informational pin must pass through the existing installation boundary
// unchanged, and cannot authorize another endpoint or project revision.
func TestInformationPinInstallationBinding(t *testing.T) {
	app := NewApp(unavailableProjectReader{}, lifecycleStub{})
	app.current = ProjectOpenResult{Status: "OPEN", Root: "project", Project: &projectlifecycle.Project{ID: "one"}, Managed: &installer.ManagedProjectView{ProjectRevision: "revision", Servers: map[string]installer.ManagedServer{"node1": {HostID: "node1", Address: "192.0.2.10"}}}}
	app.projectRevision = func(string) (string, error) { return "revision", nil }
	app.approvedTargetHostKeys = map[string]approvedTargetHostKey{"node1": {root: "project", projectID: "one", revision: "revision", hostID: "node1", address: "192.0.2.10", port: 22, keyType: "ssh-ed25519", publicKey: "exact-confirmed-key"}}
	plan := executionnode.DeploymentPlan{ProjectIdentity: "one", ProjectRevision: "revision", Phases: []executionnode.DeploymentPlanPhase{{Actions: []executionnode.DeploymentPlanAction{{Targets: []string{"node1"}}}}}}
	pins, err := app.approvedTargetKeysForPlan(plan)
	if err != nil || len(pins) != 1 || pins[0].PublicKey != "exact-confirmed-key" {
		t.Fatalf("confirmed pin not preserved: %v", err)
	}
	app.current.Managed.Servers["node1"] = installer.ManagedServer{HostID: "node1", Address: "192.0.2.11"}
	if _, err = app.approvedTargetKeysForPlan(plan); err == nil {
		t.Fatal("changed endpoint accepted")
	}
	app.current.Managed.Servers["node1"] = installer.ManagedServer{HostID: "node1", Address: "192.0.2.10"}
	plan.ProjectRevision = "other"
	if _, err = app.approvedTargetKeysForPlan(plan); err == nil {
		t.Fatal("changed revision accepted")
	}
	plan.ProjectRevision = "revision"
	plan.ProjectIdentity = "other"
	if _, err = app.approvedTargetKeysForPlan(plan); err == nil {
		t.Fatal("changed project accepted")
	}
}

func TestInformationApprovalRequiresCurrentOneShotToken(t *testing.T) {
	app := NewApp(unavailableProjectReader{}, lifecycleStub{})
	app.pendingServerInformation = &serverInformationProbe{id: "expected", hostID: "node1"}
	if got := app.CheckServerInformation("different"); got.Status == "CHECKED" {
		t.Fatal("wrong token accepted")
	}
	if app.pendingServerInformation != nil || len(app.approvedTargetHostKeys) != 0 {
		t.Fatal("invalid token retained or granted trust")
	}
	if got := app.CheckServerInformation("expected"); got.Status == "CHECKED" {
		t.Fatal("consumed token reused")
	}
}

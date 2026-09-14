package installer

import (
	"context"
	"path/filepath"
	"testing"

	"gopkg.in/yaml.v3"
)

func savedServerProject(t *testing.T, adapter *firstWriteAdapter) (string, *Backend) {
	t.Helper()
	root, revision := emptyManagedProject(t)
	backend := NewBackend(adapter, WithServerTypes([]string{"infra", "app"}))
	plan, err := backend.planFirstWrite(context.Background(), root, revision, []EditCommand{{
		APIVersion: EditCommandAPIVersionV4, Kind: "EditCommand", BaseProjectRevision: revision,
		Operation: "CreateServer", HostID: "node1", ServerType: "infra", DesiredHostname: "node1.example.internal", Address: "192.0.2.10",
	}})
	if err != nil || !plan.CommitAllowed {
		t.Fatalf("first plan=%#v err=%v", plan, err)
	}
	if result := backend.CommitEditPlan(context.Background(), plan.PlanID); result.Status != "COMMITTED" {
		t.Fatalf("first commit=%#v", result)
	}
	return root, backend
}

func currentRevision(t *testing.T, root string) string {
	t.Helper()
	_, revision, err := collectProjectDocuments(root)
	if err != nil {
		t.Fatal(err)
	}
	return revision
}

func serverCommand(revision, operation, host string) EditCommand {
	return EditCommand{APIVersion: EditCommandAPIVersionV4, Kind: "EditCommand", BaseProjectRevision: revision, Operation: operation, HostID: host}
}

func TestServerCRUDUsesFinalStateAndExplicitPortIntent(t *testing.T) {
	adapter := &firstWriteAdapter{}
	root, backend := savedServerProject(t, adapter)
	revision := currentRevision(t, root)
	create := serverCommand(revision, "CreateServer", "node2")
	create.ServerType, create.DesiredHostname, create.Address = "app", "node2.example.internal", "192.0.2.11"
	update := serverCommand(revision, "UpdateServer", "node2")
	update.Address, update.SSHPort = "192.0.2.12", 22
	plan, err := backend.planCommands(context.Background(), root, "MANAGED_PROJECT", revision, []EditCommand{create, update})
	if err != nil || !plan.CommitAllowed || len(plan.ExpectedEffectiveState) != 1 {
		t.Fatalf("plan=%#v err=%v", plan, err)
	}
	if result := backend.CommitEditPlan(context.Background(), plan.PlanID); result.Status != "COMMITTED" {
		t.Fatalf("commit=%#v", result)
	}
	var inventory map[string]any
	if err := yaml.Unmarshal(mustRead(t, filepath.Join(root, "inventory", "hosts.yml")), &inventory); err != nil {
		t.Fatal(err)
	}
	node2 := asMap(asMap(asMap(inventory["all"])["hosts"])["node2"])
	if node2["ansible_port"] != 22 || asMap(node2["platform_host"])["desiredHostname"] != "node2.example.internal" {
		t.Fatalf("node2=%#v", node2)
	}

	revision = currentRevision(t, root)
	clear := serverCommand(revision, "UpdateServer", "node2")
	clear.ClearSSHPort = true
	plan, err = backend.planCommands(context.Background(), root, "MANAGED_PROJECT", revision, []EditCommand{clear})
	if err != nil || !plan.CommitAllowed {
		t.Fatalf("clear plan=%#v err=%v", plan, err)
	}
	if result := backend.CommitEditPlan(context.Background(), plan.PlanID); result.Status != "COMMITTED" {
		t.Fatalf("clear commit=%#v", result)
	}
	if err := yaml.Unmarshal(mustRead(t, filepath.Join(root, "inventory", "hosts.yml")), &inventory); err != nil {
		t.Fatal(err)
	}
	node2 = asMap(asMap(asMap(inventory["all"])["hosts"])["node2"])
	if _, found := node2["ansible_port"]; found {
		t.Fatalf("clearSSHPort retained override: %#v", node2)
	}
}

func TestServerCreateThenDeleteIsNoChangeAndRecreateIsBlocked(t *testing.T) {
	root, backend := savedServerProject(t, &firstWriteAdapter{})
	revision := currentRevision(t, root)
	create := serverCommand(revision, "CreateServer", "node2")
	create.ServerType, create.DesiredHostname, create.Address = "app", "node2.example.internal", "192.0.2.11"
	deleteCommand := serverCommand(revision, "DeleteServer", "node2")
	plan, err := backend.planCommands(context.Background(), root, "MANAGED_PROJECT", revision, []EditCommand{create, deleteCommand})
	if err != nil || plan.Status != "NO_CHANGE" {
		t.Fatalf("net-zero plan=%#v err=%v", plan, err)
	}
	deleteNode1 := serverCommand(revision, "DeleteServer", "node1")
	createNode1 := serverCommand(revision, "CreateServer", "node1")
	createNode1.ServerType, createNode1.DesiredHostname, createNode1.Address = "infra", "node1.example.internal", "192.0.2.10"
	plan, err = backend.planCommands(context.Background(), root, "MANAGED_PROJECT", revision, []EditCommand{deleteNode1, createNode1})
	if err != nil || plan.Validation.Findings[0].Code != "SERVER_RECREATE_IN_SESSION_UNSUPPORTED" {
		t.Fatalf("recreate plan=%#v err=%v", plan, err)
	}
}

func TestServerDeleteConsumesGenericCoreReferences(t *testing.T) {
	adapter := &firstWriteAdapter{references: map[string]map[string][]map[string]any{
		"hosts": {"node1": []map[string]any{{"kind": "placement", "sourceId": "kafka-main", "field": "safe"}}},
	}}
	root, backend := savedServerProject(t, adapter)
	revision := currentRevision(t, root)
	deleteCommand := serverCommand(revision, "DeleteServer", "node1")
	plan, err := backend.planCommands(context.Background(), root, "MANAGED_PROJECT", revision, []EditCommand{deleteCommand})
	if err != nil || plan.Validation.Findings[0].Code != "REFERENCE_IN_USE" {
		t.Fatalf("delete plan=%#v err=%v", plan, err)
	}
}

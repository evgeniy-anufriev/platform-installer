package installer

import (
	"context"
	"os"
	"path/filepath"
	"testing"
	"time"

	"platform-installer/internal/coreadapter"
)

// This test is enabled explicitly on the RED OS QA controller. It proves the
// real Go writer -> normal UI-BE-02 Ansible/Core snapshot path.
func TestAuthoritativeCoreAdapterRoundTrip(t *testing.T) {
	repository := os.Getenv("PLATFORM_INSTALLER_REPOSITORY")
	if repository == "" {
		t.Skip("authoritative Core adapter environment is not configured")
	}
	source := filepath.Join(repository, "examples", "valid", "ui-project-snapshot")
	root, cleanup, err := copyProject(source)
	if err != nil {
		t.Fatal(err)
	}
	defer cleanup()
	adapter := &coreadapter.CommandAdapter{
		Executable: "ansible-playbook",
		WorkingDir: filepath.Join(repository, "ansible-core"),
		Playbook:   filepath.Join(repository, "ansible-core", "playbooks", "project-snapshot-machine.yml"),
		Catalog:    filepath.Join(repository, "examples", "catalog", "service-catalog.yml"),
		Env:        []string{"ANSIBLE_CONFIG=" + filepath.Join(repository, "ansible-core", "ansible.cfg")},
	}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	owned, err := discoverOwnedPaths(root)
	if err != nil {
		t.Fatal(err)
	}
	initial, err := adapter.BuildSnapshot(ctx, root, owned)
	if err != nil || initial.Status != "PASS" {
		t.Fatalf("initial authoritative snapshot failed: %#v, %v", initial, err)
	}
	path := filepath.Join(root, filepath.FromSlash(desiredDocument))
	before, _ := os.ReadFile(path)
	set := command(initial.ProjectRevision, "SetServiceConfigurationValue")
	set.DeploymentID, set.Setting, set.Value = "postgres-ha", "port", 55432
	backend := NewBackend(adapter)
	plan, err := backend.PlanEdit(ctx, root, set)
	if err != nil || plan.Status != "READY" || plan.Validation.Status != "PASS" {
		t.Fatalf("authoritative staged plan failed: %#v, %v", plan, err)
	}
	afterPlan, _ := os.ReadFile(path)
	if string(before) != string(afterPlan) {
		t.Fatal("authoritative planning changed canonical bytes")
	}
	committed := backend.CommitEditPlan(ctx, plan.PlanID)
	if committed.Status != "COMMITTED" || committed.NewProjectRevision == initial.ProjectRevision {
		t.Fatalf("authoritative commit failed: %#v", committed)
	}
	t.Logf("performance planApplication=%s initialSnapshot=%s stagedSnapshot=%s commitTransaction=%s postCommitSnapshot=%s",
		plan.Timing.Application, plan.Timing.InitialSnapshot, plan.Timing.StagedSnapshot,
		committed.Timing.Transaction, committed.Timing.Snapshot)
	refreshed, ok := committed.Snapshot.(*coreadapter.Snapshot)
	if !ok {
		t.Fatalf("post-commit snapshot has unexpected type: %T", committed.Snapshot)
	}
	port := asMap(snapshotValue(refreshed, "effectiveConfiguration", "services", "postgres-ha", "configuration", "port"))
	if !semanticEqual(port["value"], 55432) || port["source"] != "DEPLOYMENT_OVERRIDE" {
		t.Fatalf("authoritative effective port mismatch: %#v", port)
	}
	remove := command(refreshed.ProjectRevision, "RemoveServiceConfigurationOverride")
	remove.DeploymentID, remove.Setting = "postgres-ha", "port"
	removePlan, _ := backend.PlanEdit(ctx, root, remove)
	removed := backend.CommitEditPlan(ctx, removePlan.PlanID)
	if removed.Status != "COMMITTED" {
		t.Fatalf("authoritative remove failed: %#v", removed)
	}
	removedSnapshot := removed.Snapshot.(*coreadapter.Snapshot)
	port = asMap(snapshotValue(removedSnapshot, "effectiveConfiguration", "services", "postgres-ha", "configuration", "port"))
	if !semanticEqual(port["value"], 5432) || port["source"] != "ROLE_DEFAULT" {
		t.Fatalf("role-default fallback mismatch: %#v", port)
	}
	commit := func(edit EditCommand) *coreadapter.Snapshot {
		currentOwned, ownedErr := discoverOwnedPaths(root)
		if ownedErr != nil {
			t.Fatal(ownedErr)
		}
		current, snapshotErr := adapter.BuildSnapshot(ctx, root, currentOwned)
		if snapshotErr != nil {
			t.Fatal(snapshotErr)
		}
		edit.APIVersion, edit.Kind, edit.BaseProjectRevision = EditCommandAPIVersion, "EditCommand", current.ProjectRevision
		editPlan, planErr := backend.PlanEdit(ctx, root, edit)
		if planErr != nil || editPlan.Status != "READY" {
			t.Fatalf("authoritative generic plan failed: %#v, %v", editPlan, planErr)
		}
		editResult := backend.CommitEditPlan(ctx, editPlan.PlanID)
		if editResult.Status != "COMMITTED" {
			t.Fatalf("authoritative generic commit failed: %#v", editResult)
		}
		return editResult.Snapshot.(*coreadapter.Snapshot)
	}
	placementSnapshot := commit(EditCommand{Operation: "SetPlacementProperty", HostID: "node1",
		DeploymentID: "keepalived-a", Property: "priority", Value: 140})
	placements := asMap(placementSnapshot.Hosts["node1"]["platformDeployments"])
	if !semanticEqual(asMap(placements["keepalived-a"])["priority"], 140) {
		t.Fatal("authoritative placement edit was not effective")
	}
	commit(EditCommand{Operation: "CreateEndpointGroup", EndpointGroupID: "unused",
		EndpointGroup: map[string]any{"address": map[string]any{"domain": "unused.scada.local", "wildcard": false}}})
	commit(EditCommand{Operation: "UpdateEndpointGroup", EndpointGroupID: "unused",
		EndpointGroup: map[string]any{"address": map[string]any{"domain": "changed.scada.local", "wildcard": false}}})
	commit(EditCommand{Operation: "ClearHAProxyIntegration", DeploymentID: "postgres-ha"})
	endpointSnapshot := commit(EditCommand{Operation: "ClearServiceEndpointGroup", DeploymentID: "postgres-ha"})
	if endpointSnapshot.ServiceDeployments["postgres-ha"]["endpointGroup"] != nil {
		t.Fatal("authoritative endpoint relation clear was not effective")
	}
	endpointSnapshot = commit(EditCommand{Operation: "SetServiceEndpointGroup", DeploymentID: "postgres-ha", EndpointGroupID: "asutp-a"})
	if endpointSnapshot.ServiceDeployments["postgres-ha"]["endpointGroup"] != "asutp-a" {
		t.Fatal("authoritative endpoint relation set was not effective")
	}
	commit(EditCommand{Operation: "SetHAProxyIntegration", DeploymentID: "postgres-ha",
		HAProxyDeploymentID: "haproxy-a", Backend: map[string]any{"balance": "leastconn", "check": true,
			"fall": 3, "rise": 2, "ssl": true, "sslVerify": "required"}})
	commit(EditCommand{Operation: "DeleteEndpointGroup", EndpointGroupID: "unused"})
	created := commit(EditCommand{Operation: "Batch", Commands: []EditCommand{
		{Operation: "CreateServiceDeployment", DeploymentID: "dns-client-extra",
			Deployment: map[string]any{"serviceType": "dns-client", "mode": "host-resolver",
				"configuration": map[string]any{"dnsServerRef": "bind-main"}}},
		{Operation: "AssignServiceToHost", HostID: "node1", DeploymentID: "dns-client-extra", Placement: map[string]any{}},
	}})
	if created.ServiceDeployments["dns-client-extra"] == nil {
		t.Fatal("authoritative deployment create was not effective")
	}
	deleted := commit(EditCommand{Operation: "Batch", Commands: []EditCommand{
		{Operation: "RemoveServiceFromHost", HostID: "node1", DeploymentID: "dns-client-extra"},
		{Operation: "DeleteServiceDeployment", DeploymentID: "dns-client-extra"},
	}})
	if deleted.ServiceDeployments["dns-client-extra"] != nil {
		t.Fatal("authoritative deployment delete was not effective")
	}
}

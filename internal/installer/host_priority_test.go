package installer

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"

	"platform-installer/internal/projectlifecycle"
)

func v9HostPriorityCommand(revision string, priorities ...int) EditCommand {
	hosts := make([]PlacementHost, len(priorities))
	for index, priority := range priorities {
		hosts[index] = PlacementHost{HostID: "node" + strconv.Itoa(index+1), Priority: priority}
	}
	return EditCommand{APIVersion: EditCommandAPIVersionV9, Kind: "EditCommand", BaseProjectRevision: revision,
		Operation: "ReconcileHostScopedDeploymentPlacement", DeploymentID: "keepalived-main", Hosts: hosts}
}

func TestV9HostPlacementPriorityValidation(t *testing.T) {
	revision := "sha256:" + strings.Repeat("a", 64)
	valid := v9HostPriorityCommand(revision, 150)
	if err := validateCommand(valid); err != nil {
		t.Fatalf("valid command rejected: %v", err)
	}
	for name, priority := range map[string]int{"absent": 0, "below": 0, "above": 255} {
		t.Run(name, func(t *testing.T) {
			if err := validateCommand(v9HostPriorityCommand(revision, priority)); err == nil {
				t.Fatal("invalid priority accepted")
			}
		})
	}
	for _, content := range []string{
		`{"apiVersion":"platform.installer/edit-command/v1alpha9","kind":"EditCommand","baseProjectRevision":"` + revision + `","operation":"ReconcileHostScopedDeploymentPlacement","deploymentId":"keepalived-main","hosts":[{"hostId":"node1","priority":null}]}`,
		`{"apiVersion":"platform.installer/edit-command/v1alpha9","kind":"EditCommand","baseProjectRevision":"` + revision + `","operation":"ReconcileHostScopedDeploymentPlacement","deploymentId":"keepalived-main","hosts":[{"hostId":"node1","priority":150,"rawYaml":"unsafe"}]}`,
	} {
		var command EditCommand
		if err := json.Unmarshal([]byte(content), &command); err != nil {
			t.Fatal(err)
		}
		if err := validateCommand(command); err == nil {
			t.Fatal("invalid decoded priority command accepted")
		}
	}
	var fractional EditCommand
	if err := json.Unmarshal([]byte(`{"apiVersion":"platform.installer/edit-command/v1alpha9","kind":"EditCommand","baseProjectRevision":"`+revision+`","operation":"ReconcileHostScopedDeploymentPlacement","deploymentId":"keepalived-main","hosts":[{"hostId":"node1","priority":1.5}]}`), &fractional); err == nil {
		t.Fatal("fractional priority decoded into integer command")
	}
}

func TestV9HostPlacementPrioritySaveReopenAndExactReplacement(t *testing.T) {
	root, revision := emptyManagedProject(t)
	commands := []EditCommand{
		{APIVersion: EditCommandAPIVersionV9, Kind: "EditCommand", BaseProjectRevision: revision, Operation: "CreateServer", HostID: "node1", ServerType: "infra", DesiredHostname: "node1.example.test", Address: "192.0.2.10"},
		{APIVersion: EditCommandAPIVersionV9, Kind: "EditCommand", BaseProjectRevision: revision, Operation: "CreateServer", HostID: "node2", ServerType: "infra", DesiredHostname: "node2.example.test", Address: "192.0.2.11"},
		{APIVersion: EditCommandAPIVersionV9, Kind: "EditCommand", BaseProjectRevision: revision, Operation: "CreateServiceDeployment", DeploymentID: "keepalived-main", ServiceType: "keepalived", Mode: "vrrp"},
		v9HostPriorityCommand(revision, 150, 120),
	}
	first := commitStructuralForTest(t, f2Backend(f2Catalog()), root, projectlifecycle.ClassificationEmpty, revision, commands)
	if len(first.Managed.HostPlacements) != 2 || first.Managed.HostPlacements[0].Priority == nil || *first.Managed.HostPlacements[0].Priority != 150 || first.Managed.HostPlacements[1].Priority == nil || *first.Managed.HostPlacements[1].Priority != 120 {
		t.Fatalf("first managed placements=%#v", first.Managed.HostPlacements)
	}
	second := commitStructuralForTest(t, f2Backend(f2Catalog()), root, projectlifecycle.ClassificationManaged, first.NewProjectRevision, []EditCommand{v9HostPriorityCommand(first.NewProjectRevision, 154, 119)})
	if got := *second.Managed.HostPlacements[0].Priority; got != 154 {
		t.Fatalf("node1 priority=%d, want 154", got)
	}
	reopened, err := ReadManagedProjectView(root)
	if err != nil || reopened.HostPlacements[0].Priority == nil || *reopened.HostPlacements[0].Priority != 154 {
		t.Fatalf("reopen=%#v err=%v", reopened, err)
	}
	content, err := os.ReadFile(filepath.Join(root, "inventory", "host_vars", "node1", "platform-installer.yml"))
	if err != nil || !strings.Contains(string(content), "priority: 154") || strings.Contains(string(content), "priority: 150") {
		t.Fatalf("node1 host document was not exactly replaced: %q err=%v", content, err)
	}
}

func TestManagedHostPlacementRejectsMalformedPriority(t *testing.T) {
	root := managedReadProject(t)
	path := filepath.Join(root, "inventory", "host_vars", "node1", "platform-installer.yml")
	content := string(managedHeader) + "platform_deployments:\n  keepalived-main:\n    priority: 0\n"
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := ReadManagedProjectView(root); err == nil {
		t.Fatal("malformed persisted priority accepted")
	}
}

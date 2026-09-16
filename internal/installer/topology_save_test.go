package installer

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"platform-installer/internal/coreadapter"
	"platform-installer/internal/projectlifecycle"
)

func f2Catalog() *projectlifecycle.ProjectCatalogView {
	return &projectlifecycle.ProjectCatalogView{Status: "READY", Services: []projectlifecycle.ProjectCatalogService{
		{ID: "kafka", EndpointConsumer: true, Modes: []projectlifecycle.ProjectCatalogMode{{ID: "kraft", PlacementKind: "MEMBER_SCOPED", Roles: []string{"broker", "controller"}}}},
		{ID: "haproxy", Modes: []projectlifecycle.ProjectCatalogMode{{ID: "edge", PlacementKind: "HOST_SCOPED", Roles: []string{}}}},
	}}
}

func f2Backend(catalog *projectlifecycle.ProjectCatalogView) *Backend {
	options := []Option{WithServerTypes([]string{"infra"})}
	if catalog != nil {
		options = append(options, WithProjectCatalogResolver(func(context.Context, string) (*projectlifecycle.ProjectCatalogView, error) { return catalog, nil }))
	}
	return NewBackend(nil, options...)
}

func f2Command(revision, operation string) EditCommand {
	return EditCommand{APIVersion: EditCommandAPIVersionV5, Kind: "EditCommand", BaseProjectRevision: revision, Operation: operation}
}

func commitStructuralForTest(t *testing.T, backend *Backend, root, classification, revision string, commands []EditCommand) StructuralSaveResult {
	t.Helper()
	plan, err := backend.PlanStructuralSave(context.Background(), root, classification, revision, commands)
	if err != nil || plan == nil || plan.Status != "READY" || !plan.SaveAllowed {
		var finding *Finding
		if plan != nil {
			finding = plan.Finding
		}
		t.Fatalf("plan=%#v finding=%#v err=%v", plan, finding, err)
	}
	result := backend.CommitStructuralSave(context.Background(), plan.PlanID)
	if result.Status != "COMMITTED" || !result.Changed || result.Managed == nil {
		t.Fatalf("result=%#v", result)
	}
	return result
}

func TestF2FirstSaveMemberTopologyAndReopen(t *testing.T) {
	root, revision := emptyManagedProject(t)
	commands := []EditCommand{
		func() EditCommand {
			c := f2Command(revision, "CreateServer")
			c.HostID, c.ServerType, c.DesiredHostname, c.Address = "node1", "infra", "node1.example.test", "192.0.2.10"
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "CreateServiceDeployment")
			c.DeploymentID, c.ServiceType, c.Mode = "kafka-main", "kafka", "kraft"
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "CreateEndpointGroup")
			c.EndpointGroupID = "edge"
			c.EndpointGroup = map[string]any{"address": map[string]any{"domain": "edge.example.test", "wildcard": false}}
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "SetServiceEndpointGroup")
			c.DeploymentID, c.EndpointGroupID = "kafka-main", "edge"
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "ReconcileDeploymentPlacement")
			c.DeploymentID = "kafka-main"
			c.Members = []PlacementMember{{MemberID: "kafka-1", HostID: "node1", Roles: []string{"broker", "controller"}}}
			return c
		}(),
	}
	result := commitStructuralForTest(t, f2Backend(f2Catalog()), root, projectlifecycle.ClassificationEmpty, revision, commands)
	view := result.Managed
	if view.Deployments["kafka-main"].EndpointGroup != "edge" || view.EndpointGroups["edge"].Domain != "edge.example.test" || len(view.MemberPlacements) != 1 || view.MemberPlacements[0].MemberID != "kafka-1" {
		t.Fatalf("view=%#v", view)
	}
	reopened, err := ReadManagedProjectView(root)
	if err != nil || reopened.ProjectRevision != result.NewProjectRevision || len(reopened.MemberPlacements) != 1 {
		t.Fatalf("reopened=%#v err=%v", reopened, err)
	}
}

func TestF2HostScopedPlacementHasNoSyntheticMember(t *testing.T) {
	root, revision := emptyManagedProject(t)
	commands := []EditCommand{
		func() EditCommand {
			c := f2Command(revision, "CreateServer")
			c.HostID, c.ServerType, c.DesiredHostname, c.Address = "node1", "infra", "node1.example.test", "192.0.2.10"
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "CreateServiceDeployment")
			c.DeploymentID, c.ServiceType, c.Mode = "proxy-main", "haproxy", "edge"
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "ReconcileHostScopedDeploymentPlacement")
			c.DeploymentID = "proxy-main"
			c.Hosts = []PlacementHost{{HostID: "node1"}}
			return c
		}(),
	}
	result := commitStructuralForTest(t, f2Backend(f2Catalog()), root, projectlifecycle.ClassificationEmpty, revision, commands)
	if len(result.Managed.HostPlacements) != 1 || len(result.Managed.MemberPlacements) != 0 {
		t.Fatalf("managed=%#v", result.Managed)
	}
	content := string(mustRead(t, filepath.Join(root, "inventory", "host_vars", "node1", "platform-installer.yml")))
	if strings.Contains(content, "members:") {
		t.Fatalf("synthetic member form persisted: %s", content)
	}
}

func TestF2DeleteAndMoveTraversesSourceUnion(t *testing.T) {
	root, revision := emptyManagedProject(t)
	initial := []EditCommand{
		func() EditCommand {
			c := f2Command(revision, "CreateServer")
			c.HostID, c.ServerType, c.DesiredHostname, c.Address = "node1", "infra", "node1.example.test", "192.0.2.10"
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "CreateServer")
			c.HostID, c.ServerType, c.DesiredHostname, c.Address = "node2", "infra", "node2.example.test", "192.0.2.11"
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "CreateServiceDeployment")
			c.DeploymentID, c.ServiceType, c.Mode = "kafka-main", "kafka", "kraft"
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "ReconcileDeploymentPlacement")
			c.DeploymentID = "kafka-main"
			c.Members = []PlacementMember{{MemberID: "kafka-1", HostID: "node1", Roles: []string{"broker"}}}
			return c
		}(),
	}
	first := commitStructuralForTest(t, f2Backend(f2Catalog()), root, projectlifecycle.ClassificationEmpty, revision, initial)
	revision = first.NewProjectRevision
	move := []EditCommand{
		func() EditCommand { c := f2Command(revision, "DeleteServer"); c.HostID = "node1"; return c }(),
		func() EditCommand {
			c := f2Command(revision, "ReconcileDeploymentPlacement")
			c.DeploymentID = "kafka-main"
			c.Members = []PlacementMember{{MemberID: "kafka-1", HostID: "node2", Roles: []string{"broker"}}}
			return c
		}(),
	}
	second := commitStructuralForTest(t, f2Backend(f2Catalog()), root, projectlifecycle.ClassificationManaged, revision, move)
	if len(second.Managed.Servers) != 1 || second.Managed.MemberPlacements[0].HostID != "node2" {
		t.Fatalf("managed=%#v", second.Managed)
	}
	orphan := string(mustRead(t, filepath.Join(root, "inventory", "host_vars", "node1", "platform-installer.yml")))
	if strings.Contains(orphan, "kafka-main") || !strings.Contains(orphan, "platform_deployments: {}") {
		t.Fatalf("stale orphan placement survived: %s", orphan)
	}
}

func TestF2MemberMovePreservesUnownedMemberFields(t *testing.T) {
	root, revision := emptyManagedProject(t)
	initial := []EditCommand{
		func() EditCommand {
			c := f2Command(revision, "CreateServer")
			c.HostID, c.ServerType, c.DesiredHostname, c.Address = "node1", "infra", "node1.example.test", "192.0.2.10"
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "CreateServer")
			c.HostID, c.ServerType, c.DesiredHostname, c.Address = "node2", "infra", "node2.example.test", "192.0.2.11"
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "CreateServiceDeployment")
			c.DeploymentID, c.ServiceType, c.Mode = "kafka-main", "kafka", "kraft"
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "ReconcileDeploymentPlacement")
			c.DeploymentID = "kafka-main"
			c.Members = []PlacementMember{{MemberID: "member-1", HostID: "node1", Roles: []string{"broker"}}}
			return c
		}(),
	}
	commitStructuralForTest(t, f2Backend(f2Catalog()), root, projectlifecycle.ClassificationEmpty, revision, initial)
	logical := managedHostDocument("node1")
	document, _, err := (&managedReadBudget{}).ownedDocument(root, logical)
	if err != nil {
		t.Fatal(err)
	}
	members := asMap(asMap(asMap(document["platform_deployments"])["kafka-main"])["members"])
	member := asMap(members["member-1"])
	member["configuration"] = map[string]any{"retention.ms": 1000}
	member["x-owner"] = "preserve"
	content, _ := deterministicYAML(document)
	if err := os.WriteFile(filepath.Join(root, filepath.FromSlash(logical)), content, 0o600); err != nil {
		t.Fatal(err)
	}
	revision, _ = ProjectRevision(root)
	move := f2Command(revision, "ReconcileDeploymentPlacement")
	move.DeploymentID = "kafka-main"
	move.Members = []PlacementMember{{MemberID: "member-1", HostID: "node2", Roles: []string{"controller"}}}
	commitStructuralForTest(t, f2Backend(f2Catalog()), root, projectlifecycle.ClassificationManaged, revision, []EditCommand{move})
	moved, _, err := (&managedReadBudget{}).ownedDocument(root, managedHostDocument("node2"))
	if err != nil {
		t.Fatal(err)
	}
	movedMember := asMap(asMap(asMap(moved["platform_deployments"])["kafka-main"])["members"])["member-1"]
	value := asMap(movedMember)
	if asMap(value["configuration"])["retention.ms"] != 1000 || value["x-owner"] != "preserve" {
		t.Fatalf("unowned member fields were lost: %#v", value)
	}
}

func TestF2CertificateScopeCompositeMemberBlocksRemoval(t *testing.T) {
	root, revision := emptyManagedProject(t)
	initial := []EditCommand{
		func() EditCommand {
			c := f2Command(revision, "CreateServer")
			c.HostID, c.ServerType, c.DesiredHostname, c.Address = "node1", "infra", "node1.example.test", "192.0.2.10"
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "CreateServiceDeployment")
			c.DeploymentID, c.ServiceType, c.Mode = "kafka-main", "kafka", "kraft"
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "ReconcileDeploymentPlacement")
			c.DeploymentID = "kafka-main"
			c.Members = []PlacementMember{{MemberID: "member-1", HostID: "node1", Roles: []string{"broker"}}}
			return c
		}(),
	}
	first := commitStructuralForTest(t, f2Backend(f2Catalog()), root, projectlifecycle.ClassificationEmpty, revision, initial)
	path := filepath.Join(root, filepath.FromSlash(desiredDocument))
	document, _, err := (&managedReadBudget{}).ownedDocument(root, desiredDocument)
	if err != nil {
		t.Fatal(err)
	}
	state := asMap(document["platform_desired_state"])
	state["certificateScopes"] = map[string]any{"kafka-tls": map[string]any{"profile": "server", "sources": map[string]any{"members": []any{map[string]any{"deploymentId": "kafka-main", "memberId": "member-1"}}}}}
	content, err := deterministicYAML(document)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, content, 0o600); err != nil {
		t.Fatal(err)
	}
	revision, _ = ProjectRevision(root)
	clear := f2Command(revision, "ReconcileDeploymentPlacement")
	clear.DeploymentID = "kafka-main"
	plan, err := f2Backend(nil).PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationManaged, revision, []EditCommand{clear})
	if err != nil || plan.Status != "BLOCKED" || plan.Finding == nil || plan.Finding.Code != "REFERENCE_IN_USE" {
		t.Fatalf("plan=%#v err=%v first=%s", plan, err, first.NewProjectRevision)
	}
}

func TestF2CertificateScopeReferencesBlockMatchingRemoval(t *testing.T) {
	tests := []struct {
		name      string
		sources   map[string]any
		commands  func(string) []EditCommand
		wantField string
	}{
		{
			name:    "host",
			sources: map[string]any{"hosts": []any{"node1"}},
			commands: func(revision string) []EditCommand {
				clear := f2Command(revision, "ReconcileDeploymentPlacement")
				clear.DeploymentID = "kafka-main"
				remove := f2Command(revision, "DeleteServer")
				remove.HostID = "node1"
				return []EditCommand{clear, remove}
			},
			wantField: "sources.hosts",
		},
		{
			name:    "deployment",
			sources: map[string]any{"serviceDeployments": []any{"kafka-main"}},
			commands: func(revision string) []EditCommand {
				clear := f2Command(revision, "ReconcileDeploymentPlacement")
				clear.DeploymentID = "kafka-main"
				remove := f2Command(revision, "DeleteServiceDeployment")
				remove.DeploymentID = "kafka-main"
				return []EditCommand{clear, remove}
			},
			wantField: "sources.serviceDeployments",
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			root, revision := emptyManagedProject(t)
			initial := []EditCommand{
				func() EditCommand {
					c := f2Command(revision, "CreateServer")
					c.HostID, c.ServerType, c.DesiredHostname, c.Address = "node1", "infra", "node1.example.test", "192.0.2.10"
					return c
				}(),
				func() EditCommand {
					c := f2Command(revision, "CreateServiceDeployment")
					c.DeploymentID, c.ServiceType, c.Mode = "kafka-main", "kafka", "kraft"
					return c
				}(),
				func() EditCommand {
					c := f2Command(revision, "ReconcileDeploymentPlacement")
					c.DeploymentID = "kafka-main"
					c.Members = []PlacementMember{{MemberID: "member-1", HostID: "node1", Roles: []string{"broker"}}}
					return c
				}(),
			}
			first := commitStructuralForTest(t, f2Backend(f2Catalog()), root, projectlifecycle.ClassificationEmpty, revision, initial)
			document, _, err := (&managedReadBudget{}).ownedDocument(root, desiredDocument)
			if err != nil {
				t.Fatal(err)
			}
			state := asMap(document["platform_desired_state"])
			state["certificateScopes"] = map[string]any{"scope": map[string]any{"profile": "server", "sources": test.sources}}
			content, err := deterministicYAML(document)
			if err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(filepath.Join(root, filepath.FromSlash(desiredDocument)), content, 0o600); err != nil {
				t.Fatal(err)
			}
			revision, _ = ProjectRevision(root)
			plan, err := f2Backend(nil).PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationManaged, revision, test.commands(revision))
			if err != nil || plan.Status != "BLOCKED" || plan.Finding == nil || plan.Finding.Code != "REFERENCE_IN_USE" || plan.Finding.Field != test.wantField {
				t.Fatalf("plan=%#v err=%v initial=%s", plan, err, first.NewProjectRevision)
			}
		})
	}
}

func TestF2CertificateScopeMemberIdentityIsDeploymentScoped(t *testing.T) {
	root, revision := emptyManagedProject(t)
	initial := []EditCommand{
		func() EditCommand {
			c := f2Command(revision, "CreateServer")
			c.HostID, c.ServerType, c.DesiredHostname, c.Address = "node1", "infra", "node1.example.test", "192.0.2.10"
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "CreateServiceDeployment")
			c.DeploymentID, c.ServiceType, c.Mode = "kafka-a", "kafka", "kraft"
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "CreateServiceDeployment")
			c.DeploymentID, c.ServiceType, c.Mode = "kafka-b", "kafka", "kraft"
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "ReconcileDeploymentPlacement")
			c.DeploymentID = "kafka-a"
			c.Members = []PlacementMember{{MemberID: "member-1", HostID: "node1", Roles: []string{"broker"}}}
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "ReconcileDeploymentPlacement")
			c.DeploymentID = "kafka-b"
			c.Members = []PlacementMember{{MemberID: "member-1", HostID: "node1", Roles: []string{"broker"}}}
			return c
		}(),
	}
	commitStructuralForTest(t, f2Backend(f2Catalog()), root, projectlifecycle.ClassificationEmpty, revision, initial)
	document, _, err := (&managedReadBudget{}).ownedDocument(root, desiredDocument)
	if err != nil {
		t.Fatal(err)
	}
	state := asMap(document["platform_desired_state"])
	state["certificateScopes"] = map[string]any{"scope": map[string]any{"profile": "server", "sources": map[string]any{"members": []any{map[string]any{"deploymentId": "kafka-a", "memberId": "member-1"}}}}}
	content, _ := deterministicYAML(document)
	if err := os.WriteFile(filepath.Join(root, filepath.FromSlash(desiredDocument)), content, 0o600); err != nil {
		t.Fatal(err)
	}
	revision, _ = ProjectRevision(root)
	clear := f2Command(revision, "ReconcileDeploymentPlacement")
	clear.DeploymentID = "kafka-b"
	plan, err := f2Backend(nil).PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationManaged, revision, []EditCommand{clear})
	if err != nil || plan.Status != "READY" {
		t.Fatalf("same memberId in another deployment was treated as referenced: plan=%#v err=%v", plan, err)
	}
}

func TestF2MalformedCertificateScopeReferenceFailsClosed(t *testing.T) {
	root, revision := emptyManagedProject(t)
	initial := []EditCommand{
		func() EditCommand {
			c := f2Command(revision, "CreateServer")
			c.HostID, c.ServerType, c.DesiredHostname, c.Address = "node1", "infra", "node1.example.test", "192.0.2.10"
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "CreateServiceDeployment")
			c.DeploymentID, c.ServiceType, c.Mode = "kafka-main", "kafka", "kraft"
			return c
		}(),
	}
	commitStructuralForTest(t, f2Backend(f2Catalog()), root, projectlifecycle.ClassificationEmpty, revision, initial)
	document, _, err := (&managedReadBudget{}).ownedDocument(root, desiredDocument)
	if err != nil {
		t.Fatal(err)
	}
	state := asMap(document["platform_desired_state"])
	state["certificateScopes"] = map[string]any{"scope": map[string]any{"profile": "server", "sources": map[string]any{"hosts": []any{"node1", "node1"}}}}
	content, _ := deterministicYAML(document)
	if err := os.WriteFile(filepath.Join(root, filepath.FromSlash(desiredDocument)), content, 0o600); err != nil {
		t.Fatal(err)
	}
	revision, _ = ProjectRevision(root)
	command := f2Command(revision, "UpdateServer")
	command.HostID, command.Address = "node1", "192.0.2.11"
	plan, err := f2Backend(nil).PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationManaged, revision, []EditCommand{command})
	if err != nil || plan.Status != "BLOCKED" || plan.Finding == nil || plan.Finding.Code != "MANAGED_DOCUMENT_INVALID" {
		t.Fatalf("plan=%#v finding=%+v err=%v", plan, plan.Finding, err)
	}
}

func TestF2CatalogIndependentCleanupAndReviewLimit(t *testing.T) {
	root, revision := emptyManagedProject(t)
	commands := make([]EditCommand, 17)
	for index := range commands {
		commands[index] = f2Command(revision, "ClearServiceEndpointGroup")
		commands[index].DeploymentID = "deployment-" + string(rune('a'+index))
	}
	plan, err := f2Backend(nil).PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationEmpty, revision, commands)
	if err != nil || plan.Status != "BLOCKED" || plan.Finding == nil || plan.Finding.Code != "EDIT_SESSION_COMMANDS_UNSUPPORTED" {
		t.Fatalf("plan=%#v err=%v", plan, err)
	}
	create := f2Command(revision, "CreateServiceDeployment")
	create.DeploymentID, create.ServiceType, create.Mode = "kafka-main", "kafka", "kraft"
	plan, err = f2Backend(nil).PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationEmpty, revision, []EditCommand{create})
	if err != nil || plan.Status != "BLOCKED" || plan.Finding == nil || plan.Finding.Code != "PROJECT_CATALOG_UNAVAILABLE" {
		t.Fatalf("catalog plan=%#v err=%v", plan, err)
	}
}

func TestF2CatalogIndependentCleanupSucceeds(t *testing.T) {
	root, revision := emptyManagedProject(t)
	initial := []EditCommand{
		func() EditCommand {
			c := f2Command(revision, "CreateServer")
			c.HostID, c.ServerType, c.DesiredHostname, c.Address = "node1", "infra", "node1.example.test", "192.0.2.10"
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "CreateServiceDeployment")
			c.DeploymentID, c.ServiceType, c.Mode = "kafka-main", "kafka", "kraft"
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "CreateEndpointGroup")
			c.EndpointGroupID = "edge"
			c.EndpointGroup = map[string]any{"address": map[string]any{"domain": "edge.example.test", "wildcard": false}}
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "SetServiceEndpointGroup")
			c.DeploymentID, c.EndpointGroupID = "kafka-main", "edge"
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "ReconcileDeploymentPlacement")
			c.DeploymentID = "kafka-main"
			c.Members = []PlacementMember{{MemberID: "member-1", HostID: "node1", Roles: []string{"broker"}}}
			return c
		}(),
	}
	first := commitStructuralForTest(t, f2Backend(f2Catalog()), root, projectlifecycle.ClassificationEmpty, revision, initial)
	revision = first.NewProjectRevision
	commands := []EditCommand{
		func() EditCommand {
			c := f2Command(revision, "ClearServiceEndpointGroup")
			c.DeploymentID = "kafka-main"
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "DeleteEndpointGroup")
			c.EndpointGroupID = "edge"
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "ReconcileDeploymentPlacement")
			c.DeploymentID = "kafka-main"
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "DeleteServiceDeployment")
			c.DeploymentID = "kafka-main"
			return c
		}(),
	}
	result := commitStructuralForTest(t, f2Backend(nil), root, projectlifecycle.ClassificationManaged, revision, commands)
	if len(result.Managed.Deployments) != 0 || len(result.Managed.EndpointGroups) != 0 || len(result.Managed.MemberPlacements) != 0 {
		t.Fatalf("cleanup result=%#v", result.Managed)
	}
}

func TestF2CatalogAdmissionIsGenericAndOperationSpecific(t *testing.T) {
	tests := []struct {
		name    string
		command func(string) EditCommand
		want    string
	}{
		{
			name: "unknown service",
			command: func(revision string) EditCommand {
				c := f2Command(revision, "CreateServiceDeployment")
				c.DeploymentID, c.ServiceType, c.Mode = "unknown-main", "unknown", "mode"
				return c
			},
			want: "CATALOG_VALUE_UNKNOWN",
		},
		{
			name: "wrong placement kind",
			command: func(revision string) EditCommand {
				c := f2Command(revision, "ReconcileHostScopedDeploymentPlacement")
				c.DeploymentID, c.Hosts = "kafka-main", []PlacementHost{{HostID: "node1"}}
				return c
			},
			want: "PLACEMENT_KIND_MISMATCH",
		},
		{
			name: "unknown role",
			command: func(revision string) EditCommand {
				c := f2Command(revision, "ReconcileDeploymentPlacement")
				c.DeploymentID, c.Members = "kafka-main", []PlacementMember{{MemberID: "member-1", HostID: "node1", Roles: []string{"unknown"}}}
				return c
			},
			want: "CATALOG_VALUE_UNKNOWN",
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			root, revision := emptyManagedProject(t)
			initial := []EditCommand{
				func() EditCommand {
					c := f2Command(revision, "CreateServer")
					c.HostID, c.ServerType, c.DesiredHostname, c.Address = "node1", "infra", "node1.example.test", "192.0.2.10"
					return c
				}(),
				func() EditCommand {
					c := f2Command(revision, "CreateServiceDeployment")
					c.DeploymentID, c.ServiceType, c.Mode = "kafka-main", "kafka", "kraft"
					return c
				}(),
			}
			first := commitStructuralForTest(t, f2Backend(f2Catalog()), root, projectlifecycle.ClassificationEmpty, revision, initial)
			command := test.command(first.NewProjectRevision)
			plan, err := f2Backend(f2Catalog()).PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationManaged, first.NewProjectRevision, []EditCommand{command})
			if err != nil || plan.Status != "BLOCKED" || plan.Finding == nil || plan.Finding.Code != test.want {
				t.Fatalf("plan=%#v finding=%+v err=%v", plan, plan.Finding, err)
			}
		})
	}

	root, revision := emptyManagedProject(t)
	create := f2Command(revision, "CreateServiceDeployment")
	create.DeploymentID, create.ServiceType, create.Mode = "kafka-main", "kafka", "kraft"
	incompatible := &projectlifecycle.ProjectCatalogView{Status: "INCOMPATIBLE"}
	plan, err := f2Backend(incompatible).PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationEmpty, revision, []EditCommand{create})
	if err != nil || plan.Status != "BLOCKED" || plan.Finding == nil || plan.Finding.Code != "PROJECT_CATALOG_INCOMPATIBLE" {
		t.Fatalf("incompatible plan=%#v err=%v", plan, err)
	}
}

func TestF2EndpointAssignmentRequiresConsumerCapability(t *testing.T) {
	root, revision := emptyManagedProject(t)
	initial := []EditCommand{
		func() EditCommand {
			c := f2Command(revision, "CreateServiceDeployment")
			c.DeploymentID, c.ServiceType, c.Mode = "proxy-main", "haproxy", "edge"
			return c
		}(),
		func() EditCommand {
			c := f2Command(revision, "CreateEndpointGroup")
			c.EndpointGroupID = "edge"
			c.EndpointGroup = map[string]any{"address": map[string]any{"domain": "edge.example.test", "wildcard": false}}
			return c
		}(),
	}
	first := commitStructuralForTest(t, f2Backend(f2Catalog()), root, projectlifecycle.ClassificationEmpty, revision, initial)
	set := f2Command(first.NewProjectRevision, "SetServiceEndpointGroup")
	set.DeploymentID, set.EndpointGroupID = "proxy-main", "edge"
	plan, err := f2Backend(f2Catalog()).PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationManaged, first.NewProjectRevision, []EditCommand{set})
	if err != nil || plan.Status != "BLOCKED" || plan.Finding == nil || plan.Finding.Code != "CAPABILITY_NOT_SUPPORTED" {
		t.Fatalf("plan=%#v finding=%+v err=%v", plan, plan.Finding, err)
	}
}

func TestF2EndpointUpdatePreservesExtensions(t *testing.T) {
	root, revision := emptyManagedProject(t)
	create := f2Command(revision, "CreateEndpointGroup")
	create.EndpointGroupID = "edge"
	create.EndpointGroup = map[string]any{"address": map[string]any{"domain": "old.example.test", "wildcard": false}, "x-owner": "preserve"}
	first := commitStructuralForTest(t, f2Backend(nil), root, projectlifecycle.ClassificationEmpty, revision, []EditCommand{create})
	update := f2Command(first.NewProjectRevision, "UpdateEndpointGroup")
	update.EndpointGroupID = "edge"
	update.EndpointGroup = map[string]any{"address": map[string]any{"domain": "new.example.test", "wildcard": true}}
	commitStructuralForTest(t, f2Backend(nil), root, projectlifecycle.ClassificationManaged, first.NewProjectRevision, []EditCommand{update})
	document, _, err := (&managedReadBudget{}).ownedDocument(root, desiredDocument)
	if err != nil {
		t.Fatal(err)
	}
	group := asMap(asMap(asMap(document["platform_desired_state"])["endpointGroups"])["edge"])
	if group["x-owner"] != "preserve" || asMap(group["address"])["domain"] != "new.example.test" {
		t.Fatalf("endpoint group=%#v", group)
	}
}

func TestF2PreservedProviderAndDependencyReferencesBlockDeletion(t *testing.T) {
	tests := []struct {
		name      string
		configure func(map[string]any)
		command   func(string) EditCommand
		field     string
	}{
		{
			name: "provider endpoint group reference",
			configure: func(state map[string]any) {
				asMap(asMap(state["serviceDeployments"])["provider"])["endpointGroupRef"] = "edge"
			},
			command: func(revision string) EditCommand {
				c := f2Command(revision, "DeleteEndpointGroup")
				c.EndpointGroupID = "edge"
				return c
			},
			field: "endpointGroupRef",
		},
		{
			name: "dependency reference",
			configure: func(state map[string]any) {
				asMap(asMap(state["serviceDeployments"])["consumer"])["dependencies"] = map[string]any{"primary": map[string]any{"serviceDeployment": "provider", "capability": "endpoint"}}
			},
			command: func(revision string) EditCommand {
				c := f2Command(revision, "DeleteServiceDeployment")
				c.DeploymentID = "provider"
				return c
			},
			field: "serviceDeployment",
		},
		{
			name: "haproxy deployment reference",
			configure: func(state map[string]any) {
				asMap(asMap(state["serviceDeployments"])["consumer"])["haproxy"] = map[string]any{"deploymentRef": "provider"}
			},
			command: func(revision string) EditCommand {
				c := f2Command(revision, "DeleteServiceDeployment")
				c.DeploymentID = "provider"
				return c
			},
			field: "deploymentRef",
		},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			root, revision := emptyManagedProject(t)
			create := f2Command(revision, "CreateServer")
			create.HostID, create.ServerType, create.DesiredHostname, create.Address = "node1", "infra", "node1.example.test", "192.0.2.10"
			commitStructuralForTest(t, f2Backend(nil), root, projectlifecycle.ClassificationEmpty, revision, []EditCommand{create})
			document, _, err := (&managedReadBudget{}).ownedDocument(root, desiredDocument)
			if err != nil {
				t.Fatal(err)
			}
			state := asMap(document["platform_desired_state"])
			state["endpointGroups"] = map[string]any{"edge": map[string]any{"address": map[string]any{"domain": "edge.example.test", "wildcard": false}}}
			state["serviceDeployments"] = map[string]any{
				"provider": map[string]any{"serviceType": "provider", "mode": "default"},
				"consumer": map[string]any{"serviceType": "consumer", "mode": "default"},
			}
			test.configure(state)
			content, _ := deterministicYAML(document)
			if err := os.WriteFile(filepath.Join(root, filepath.FromSlash(desiredDocument)), content, 0o600); err != nil {
				t.Fatal(err)
			}
			revision, _ = ProjectRevision(root)
			plan, err := f2Backend(nil).PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationManaged, revision, []EditCommand{test.command(revision)})
			if err != nil || plan.Status != "BLOCKED" || plan.Finding == nil || plan.Finding.Code != "REFERENCE_IN_USE" || plan.Finding.Field != test.field {
				t.Fatalf("plan=%#v finding=%+v err=%v", plan, plan.Finding, err)
			}
		})
	}
}

func TestF2DanglingFinalReferenceFailsClosed(t *testing.T) {
	root, revision := emptyManagedProject(t)
	create := f2Command(revision, "CreateServer")
	create.HostID, create.ServerType, create.DesiredHostname, create.Address = "node1", "infra", "node1.example.test", "192.0.2.10"
	first := commitStructuralForTest(t, f2Backend(nil), root, projectlifecycle.ClassificationEmpty, revision, []EditCommand{create})
	document, _, err := (&managedReadBudget{}).ownedDocument(root, desiredDocument)
	if err != nil {
		t.Fatal(err)
	}
	state := asMap(document["platform_desired_state"])
	state["serviceDeployments"] = map[string]any{"consumer": map[string]any{"serviceType": "consumer", "mode": "default", "dependencies": map[string]any{"missing": map[string]any{"serviceDeployment": "absent", "capability": "endpoint"}}}}
	content, _ := deterministicYAML(document)
	if err := os.WriteFile(filepath.Join(root, filepath.FromSlash(desiredDocument)), content, 0o600); err != nil {
		t.Fatal(err)
	}
	revision, _ = ProjectRevision(root)
	update := f2Command(revision, "UpdateServer")
	update.HostID, update.Address = "node1", "192.0.2.11"
	plan, err := f2Backend(nil).PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationManaged, revision, []EditCommand{update})
	if err != nil || plan.Status != "BLOCKED" || plan.Finding == nil || plan.Finding.Code != "REFERENCE_NOT_FOUND" {
		t.Fatalf("plan=%#v finding=%+v err=%v first=%s", plan, plan.Finding, err, first.NewProjectRevision)
	}
}

func TestF2ConflictingIntentsFailClosed(t *testing.T) {
	root, revision := emptyManagedProject(t)
	commands := make([]EditCommand, 2)
	for index := range commands {
		commands[index] = f2Command(revision, "CreateEndpointGroup")
		commands[index].EndpointGroupID = "edge"
		commands[index].EndpointGroup = map[string]any{"address": map[string]any{"domain": "edge.example.test", "wildcard": false}}
	}
	plan, err := f2Backend(nil).PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationEmpty, revision, commands)
	if err != nil || plan.Status != "BLOCKED" || plan.Finding == nil || plan.Finding.Code != "EDIT_COMMAND_CONFLICT" {
		t.Fatalf("plan=%#v finding=%+v err=%v", plan, plan.Finding, err)
	}
}

func TestF2ReviewDetectsRevisionChangeAfterCatalogAdmission(t *testing.T) {
	root, revision := emptyManagedProject(t)
	backend := NewBackend(nil, WithProjectCatalogResolver(func(context.Context, string) (*projectlifecycle.ProjectCatalogView, error) {
		path := filepath.Join(root, "project.yml")
		content, err := os.ReadFile(path)
		if err != nil {
			return nil, err
		}
		if err := os.WriteFile(path, append(content, []byte("# concurrent change\n")...), 0o600); err != nil {
			return nil, err
		}
		return f2Catalog(), nil
	}))
	create := f2Command(revision, "CreateServiceDeployment")
	create.DeploymentID, create.ServiceType, create.Mode = "kafka-main", "kafka", "kraft"
	plan, err := backend.PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationEmpty, revision, []EditCommand{create})
	if err != nil || plan.Status != "BLOCKED" || plan.Finding == nil || plan.Finding.Code != "PROJECT_CHANGED" {
		t.Fatalf("plan=%#v finding=%+v err=%v", plan, plan.Finding, err)
	}
	if _, err := os.Stat(filepath.Join(root, "inventory", "hosts.yml")); !os.IsNotExist(err) {
		t.Fatalf("review wrote candidate files after revision race: %v", err)
	}
}

type countingCoreAdapter struct{ calls int }

func (adapter *countingCoreAdapter) BuildSnapshot(context.Context, string, []string) (*coreadapter.Snapshot, error) {
	adapter.calls++
	return nil, errors.New("core must not be contacted")
}

func TestF2StructuralSaveDoesNotContactCore(t *testing.T) {
	root, revision := emptyManagedProject(t)
	core := &countingCoreAdapter{}
	backend := NewBackend(core)
	create := f2Command(revision, "CreateEndpointGroup")
	create.EndpointGroupID = "edge"
	create.EndpointGroup = map[string]any{"address": map[string]any{"domain": "edge.example.test", "wildcard": false}}
	commitStructuralForTest(t, backend, root, projectlifecycle.ClassificationEmpty, revision, []EditCommand{create})
	if core.calls != 0 {
		t.Fatalf("local topology Save contacted Core %d times", core.calls)
	}
}

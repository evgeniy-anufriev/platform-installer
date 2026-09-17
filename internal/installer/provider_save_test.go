package installer

import (
	"context"
	"os"
	"path/filepath"
	"testing"

	"platform-installer/internal/projectlifecycle"
)

func providerCommand(revision, operation string) EditCommand {
	return EditCommand{APIVersion: EditCommandAPIVersionV7, Kind: "EditCommand", BaseProjectRevision: revision, Operation: operation}
}

func providerProject(t *testing.T, configured bool) (string, string) {
	t.Helper()
	root := managedReadProject(t)
	// The generic managed-read fixture intentionally carries unrelated placement
	// examples. Provider save tests require a reference-consistent project so the
	// final-state reference guard exercises provider edges only.
	hostPath := filepath.Join(root, "inventory", "host_vars", "node1", "platform-installer.yml")
	if err := os.WriteFile(hostPath, []byte(string(managedHeader)+"platform_deployments: {}\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	document, _, err := (&managedReadBudget{}).ownedDocument(root, desiredDocument)
	if err != nil {
		t.Fatal(err)
	}
	deployments := asMap(asMap(document["platform_desired_state"])["serviceDeployments"])
	provider := map[string]any{"serviceType": "keepalived", "mode": "vrrp", "x-owner": "preserve"}
	if configured {
		provider["endpointGroupRef"] = "edge"
		provider["virtualRouterId"] = 42
		provider["virtualAddresses"] = []any{map[string]any{"address": "192.0.2.42", "interface": "eth0"}}
	}
	deployments["provider"] = provider
	content, err := deterministicYAML(document)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, filepath.FromSlash(desiredDocument)), content, 0o600); err != nil {
		t.Fatal(err)
	}
	revision, err := ProjectRevision(root)
	if err != nil {
		t.Fatal(err)
	}
	return root, revision
}

func TestProviderReconcileSaveReopenPreservesDeploymentFields(t *testing.T) {
	root, revision := providerProject(t, false)
	command := providerCommand(revision, "ReconcileEndpointProvider")
	command.DeploymentID, command.EndpointGroupID, command.VirtualRouterID = "provider", "edge", 42
	command.VirtualAddresses = []VirtualAddress{{Address: "192.0.2.42", Interface: "eth0"}, {Address: "192.0.2.43", Interface: "eth1"}}
	result := commitStructuralForTest(t, f2Backend(f2Catalog()), root, projectlifecycle.ClassificationManaged, revision, []EditCommand{command})
	provider := result.Managed.Deployments["provider"]
	if provider.ProviderEditState != "EDITABLE" || provider.EndpointGroupRef != "edge" || provider.VirtualRouterID == nil || *provider.VirtualRouterID != 42 || len(provider.VirtualAddresses) != 2 {
		t.Fatalf("managed provider=%#v", provider)
	}
	document, _, err := (&managedReadBudget{}).ownedDocument(root, desiredDocument)
	if err != nil {
		t.Fatal(err)
	}
	if asMap(asMap(asMap(document["platform_desired_state"])["serviceDeployments"])["provider"])["x-owner"] != "preserve" {
		t.Fatal("unrelated provider field was not preserved")
	}
}

func TestProviderClearIsCatalogIndependentAndSupportsFinalStateGroupDelete(t *testing.T) {
	root, revision := providerProject(t, true)
	clear := providerCommand(revision, "ClearEndpointProvider")
	clear.DeploymentID = "provider"
	clearConsumer := providerCommand(revision, "ClearServiceEndpointGroup")
	clearConsumer.DeploymentID = "kafka-main"
	deleteGroup := providerCommand(revision, "DeleteEndpointGroup")
	deleteGroup.EndpointGroupID = "edge"
	// The delete intentionally comes first: final-state reduction must not make
	// safe clear/delete recovery depend on command order.
	result := commitStructuralForTest(t, f2Backend(nil), root, projectlifecycle.ClassificationManaged, revision, []EditCommand{deleteGroup, clear, clearConsumer})
	provider := result.Managed.Deployments["provider"]
	if provider.ProviderEditState != "NONE" || provider.EndpointGroupRef != "" || provider.VirtualRouterID != nil || len(provider.VirtualAddresses) != 0 {
		t.Fatalf("managed provider=%#v", provider)
	}
	if result.Managed.EndpointGroups["edge"].EndpointGroupID != "" {
		t.Fatalf("endpoint group was not deleted: %#v", result.Managed.EndpointGroups)
	}
}

func TestProviderReconcileRequiresReadyProviderCatalog(t *testing.T) {
	root, revision := providerProject(t, false)
	command := providerCommand(revision, "ReconcileEndpointProvider")
	command.DeploymentID, command.EndpointGroupID, command.VirtualRouterID = "provider", "edge", 42
	command.VirtualAddresses = []VirtualAddress{{Address: "192.0.2.42", Interface: "eth0"}}
	for name, backend := range map[string]*Backend{
		"unavailable": f2Backend(nil),
		"not provider": NewBackend(nil, WithProjectCatalogResolver(func(context.Context, string) (*projectlifecycle.ProjectCatalogView, error) {
			return &projectlifecycle.ProjectCatalogView{Status: "READY", Services: []projectlifecycle.ProjectCatalogService{{ID: "keepalived"}}}, nil
		})),
	} {
		t.Run(name, func(t *testing.T) {
			plan, err := backend.PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationManaged, revision, []EditCommand{command})
			if err != nil || plan.Status != "BLOCKED" || plan.Finding == nil {
				t.Fatalf("plan=%#v err=%v", plan, err)
			}
			if name == "unavailable" && plan.Finding.Code != "PROJECT_CATALOG_UNAVAILABLE" {
				t.Fatalf("finding=%#v", plan.Finding)
			}
			if name == "not provider" && plan.Finding.Code != "CAPABILITY_NOT_SUPPORTED" {
				t.Fatalf("finding=%#v", plan.Finding)
			}
		})
	}
}

func TestProviderIntentsConflict(t *testing.T) {
	root, revision := providerProject(t, true)
	reconcile := providerCommand(revision, "ReconcileEndpointProvider")
	reconcile.DeploymentID, reconcile.EndpointGroupID, reconcile.VirtualRouterID = "provider", "edge", 43
	reconcile.VirtualAddresses = []VirtualAddress{{Address: "192.0.2.43", Interface: "eth0"}}
	clear := providerCommand(revision, "ClearEndpointProvider")
	clear.DeploymentID = "provider"
	plan, err := f2Backend(f2Catalog()).PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationManaged, revision, []EditCommand{reconcile, clear})
	if err != nil || plan.Status != "BLOCKED" || plan.Finding == nil || plan.Finding.Code != "EDIT_COMMAND_CONFLICT" {
		t.Fatalf("plan=%#v err=%v", plan, err)
	}
}

func TestProviderClearMissingDeploymentFailsClosedWithoutCatalog(t *testing.T) {
	root, revision := providerProject(t, false)
	command := providerCommand(revision, "ClearEndpointProvider")
	command.DeploymentID = "missing"
	plan, err := f2Backend(nil).PlanStructuralSave(context.Background(), root, projectlifecycle.ClassificationManaged, revision, []EditCommand{command})
	if err != nil || plan.Status != "BLOCKED" || plan.Finding == nil || plan.Finding.Code != "REFERENCE_NOT_FOUND" || plan.Finding.Field != "command.deploymentId" {
		t.Fatalf("plan=%#v err=%v", plan, err)
	}
}

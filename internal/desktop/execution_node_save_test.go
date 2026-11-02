package desktop

import (
	"strings"
	"testing"

	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
	"platform-installer/internal/projectlifecycle"
	"platform-installer/internal/runtimesecret"
)

func TestSavePreservesOnlyUnchangedExecutionBinding(t *testing.T) {
	for _, change := range []string{"placement", "other-server", "address", "port", "removed", "bundle", "catalog", "project", "root"} {
		t.Run(change, func(t *testing.T) {
			bundle, catalog := "sha256:"+strings.Repeat("a", 64), "sha256:"+strings.Repeat("b", 64)
			project := &projectlifecycle.Project{ID: "project-one", Source: projectlifecycle.CompatibilitySourceSummary{BundleDigest: bundle, CatalogDigest: catalog}}
			app := NewApp(unavailableProjectReader{}, lifecycleStub{})
			root := t.TempDir()
			servers := map[string]installer.ManagedServer{"node2": {HostID: "node2", Address: "192.0.2.2"}}
			app.current = ProjectOpenResult{Status: "OPEN", Root: root, Project: project, Managed: &installer.ManagedProjectView{Servers: servers}}
			app.execution.bind(root, project.ID, managedSnapshotHosts(app.current.Managed))
			app.execution.context.SelectionSource = "EXPLICIT"
			app.execution.setStatus("READY")
			app.execution.context.RuntimeDigest = bundle
			binding := &executionNodeBinding{dynamic: true, node: executionnode.Node{ID: "node2", Address: "192.0.2.2", Port: 22}, reader: projectReader{runtimeRelease: map[string]any{"bundleDigest": bundle, "catalogDigest": catalog, "coreVersion": "1", "planningProtocol": "1"}}}
			app.binding = binding
			app.installationPlanID = "old-plan"
			app.installationGeneration = 10
			switch change {
			case "other-server":
				servers["node1"] = installer.ManagedServer{HostID: "node1", Address: "192.0.2.1"}
			case "address":
				servers["node2"] = installer.ManagedServer{HostID: "node2", Address: "192.0.2.3"}
			case "port":
				port := 2222
				servers["node2"] = installer.ManagedServer{HostID: "node2", Address: "192.0.2.2", SSHPort: &port}
			case "removed":
				delete(servers, "node2")
			case "bundle":
				project.Source.BundleDigest = "sha256:" + strings.Repeat("c", 64)
			case "catalog":
				project.Source.CatalogDigest = "sha256:" + strings.Repeat("c", 64)
			case "project":
				project.ID = "project-two"
			case "root":
				root = t.TempDir()
			}
			app.refreshExecutionAfterSaveLocked(root, project, managedSnapshotHosts(app.current.Managed))
			preserved := change == "placement" || change == "other-server"
			if preserved {
				if app.binding != binding || app.execution.context.Status != "READY" || app.execution.context.RuntimeDigest != bundle || app.execution.context.SelectedHostID != "node2" || app.execution.context.SelectionSource != "EXPLICIT" {
					t.Fatalf("unchanged prepared node lost: %+v", app.execution.context)
				}
			} else if app.binding != nil || app.execution.context.Status == "READY" {
				t.Fatalf("changed authority retained: %+v", app.execution.context)
			}
			if app.installationPlanID != "" || app.installationGeneration <= 10 {
				t.Fatal("save retained execution approval")
			}
		})
	}
}

func TestExternalExecutionSaveRetainsPendingSecretsAndReadiness(t *testing.T) {
	app := preparedDraftApp(t)
	app.binding.dynamic = false
	app.execution.context.SelectionKind = "EXPLICIT_EXTERNAL"
	app.execution.context.SelectedHostID = ""
	binding := app.binding
	credential := runtimesecret.Binding{Root: app.current.Root, ID: app.current.Project.ID}
	if err := app.secrets.SetPendingServiceSecretInput(credential, "kafka", "SERVICE_PASSWORD", []byte("synthetic-password"), nil); err != nil {
		t.Fatal(err)
	}
	if _, err := app.secrets.SetPKIStorePassword(credential, "synthetic-pki-password"); err != nil {
		t.Fatal(err)
	}
	if err := app.secrets.SetPendingRuntimeSecretValuesForRequirements(credential, []string{"keycloak-password"}, map[string]string{"keycloak-password": "synthetic-application-password"}); err != nil {
		t.Fatal(err)
	}
	app.clearRuntimeSecretDescriptorEvidenceLocked(true)
	app.refreshExecutionAfterSaveLocked(app.current.Root, app.current.Project, managedSnapshotHosts(app.current.Managed))
	if app.binding != binding || app.execution.context.Status != "READY" ||
		!app.secrets.ServiceSecretsPresent(credential, []runtimesecret.RuntimeSecretInput{{ServiceDeployment: "kafka", Purpose: "SERVICE_PASSWORD"}}) {
		t.Fatal("unchanged startup connection Save lost readiness or pending service password")
	}
	if status := app.secrets.Status(credential); status.PKIStorePasswordStatus != runtimesecret.PKIStorePasswordPresent {
		t.Fatal("Save lost PKCS password")
	}
	if err := app.secrets.PromotePendingRuntimeSecretValues(credential, []string{"keycloak-password"}); err != nil {
		t.Fatal(err)
	}
	if missing := app.secrets.MissingRequiredSecrets(credential, []string{"keycloak-password"}, true, true); len(missing) != 0 {
		t.Fatal("Save lost a pending application password")
	}
}

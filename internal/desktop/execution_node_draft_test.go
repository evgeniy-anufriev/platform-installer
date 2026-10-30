package desktop

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"testing"

	"platform-installer/internal/executionbundle"
	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
	"platform-installer/internal/projectlifecycle"
	"platform-installer/internal/runtimesecret"
)

type draftPreviewTransport struct {
	verificationTransportStub
	build func() (executionnode.ServiceConfigurationPreview, error)
}

func (s draftPreviewTransport) BuildServiceConfigurationPreview(context.Context, executionnode.Node, string, map[string]any) (executionnode.ServiceConfigurationPreview, error) {
	return s.build()
}

func preparedDraftApp(t *testing.T) *App {
	t.Helper()
	bundle := v02TestBundle(t)
	root := t.TempDir()
	if err := os.WriteFile(filepath.Join(root, "project.yml"), []byte("name: saved\n"), 0600); err != nil {
		t.Fatal(err)
	}
	revision, err := installer.ProjectRevision(root)
	if err != nil {
		t.Fatal(err)
	}
	app := NewApp(unavailableProjectReader{}, lifecycleStub{}, WithAvailableExecutionBundle(bundle.Root))
	t.Cleanup(app.secrets.Close)
	credential := runtimesecret.Binding{Root: root, ID: "one"}
	if _, err := app.secrets.Set(credential, runtimesecret.Input{Username: "installer", SSHMode: runtimesecret.SSHPassword, SSHPassword: "synthetic-test-only"}); err != nil {
		t.Fatal(err)
	}
	identity, err := app.secrets.CurrentExecutionIdentity(credential)
	if err != nil {
		t.Fatal(err)
	}
	app.current = ProjectOpenResult{Status: "OPEN", Root: root,
		Project: &projectlifecycle.Project{ID: "one", Source: projectlifecycle.CompatibilitySourceSummary{BundleDigest: bundle.Digest, CatalogDigest: bundle.Manifest.CatalogDigest}},
		Managed: &installer.ManagedProjectView{ProjectRevision: revision, Servers: map[string]installer.ManagedServer{"node1": {HostID: "node1", Address: "192.0.2.10"}}},
		Catalog: &projectlifecycle.ProjectCatalogView{Status: "READY"}}
	app.execution.bind(root, "one", managedSnapshotHosts(app.current.Managed))
	app.execution.setStatus("READY")
	app.binding = &executionNodeBinding{dynamic: true, node: executionnode.Node{ID: "node1", Address: "192.0.2.10", Port: 22, User: identity.Username},
		reader:     projectReader{transport: verificationTransportStub{}, runtimeRelease: map[string]any{"bundleDigest": bundle.Digest, "catalogDigest": bundle.Manifest.CatalogDigest, "coreVersion": bundle.Manifest.CoreVersion, "planningProtocol": executionbundle.ProtocolVersion}},
		bundleRoot: bundle.Root, service: &executionLifecycleStub{}, credentialGeneration: identity.Generation, hostKeyPin: &approvedExecutionHostKey{}, commandGuard: func() (func(), error) { return func() {}, nil }}
	return app
}

func TestDraftBlocksOperationsWithoutRevokingPreparedNode(t *testing.T) {
	app := preparedDraftApp(t)
	binding := app.binding
	app.activeSession = "draft"
	if _, err := app.resolveSelectedExecutionNodeBindingLocked(); err == nil {
		t.Fatal("draft authorized an operation")
	}
	if err := app.revalidateBindingBeforePublicationLocked(binding); err == nil {
		t.Fatal("draft authorized publication of an execution result")
	}
	if app.binding != binding || app.execution.context.Status != "READY" {
		t.Fatal("draft revoked prepared binding")
	}
	// A live edit session is not required to test the saved presentation helper.
	if err := app.revalidateSavedPreviewBindingLocked(binding); err != nil {
		t.Fatal(err)
	}
}

func TestDraftContextRetainsSavedRuntimeDigest(t *testing.T) {
	app := preparedDraftApp(t)
	binding := app.binding
	session, err := app.sessions.Start(app.current.Project.ID, app.current.Root, "MANAGED_PROJECT", app.current.Managed.ProjectRevision)
	if err != nil {
		t.Fatal(err)
	}
	app.activeSession = session.SessionID
	for i := 0; i < 3; i++ {
		state, err := app.GetExecutionNodeContext()
		if err != nil || state.Status != "READY" || state.RuntimeDigest != binding.reader.runtimeRelease["bundleDigest"] || app.binding != binding || app.activeSession != session.SessionID {
			t.Fatalf("draft render lost saved node evidence: %+v, %v", state, err)
		}
	}
	app.secrets.Clear()
	state, err := app.GetExecutionNodeContext()
	if err != nil || state.Status == "READY" || app.binding != nil {
		t.Fatal("draft presentation retained revoked credentials")
	}
}

func TestSavedPreviewFinishingAfterDraftOpens(t *testing.T) {
	for _, change := range []string{"draft", "address", "credential", "pin", "guard", "bundle", "revision"} {
		t.Run(change, func(t *testing.T) {
			app := preparedDraftApp(t)
			binding := app.binding
			release := binding.reader.runtimeRelease
			binding.reader.transport = draftPreviewTransport{build: func() (executionnode.ServiceConfigurationPreview, error) {
				app.editMu.Lock()
				defer app.editMu.Unlock()
				app.activeSession = "draft"
				switch change {
				case "address":
					app.current.Managed.Servers["node1"] = installer.ManagedServer{HostID: "node1", Address: "192.0.2.11"}
				case "credential":
					app.secrets.Clear()
				case "pin":
					binding.hostKeyPin = nil
				case "guard":
					binding.commandGuard = func() (func(), error) { return nil, errors.New("expired") }
				case "bundle":
					app.current.Project.Source.BundleDigest = "changed"
				case "revision":
					app.current.Managed.ProjectRevision = "changed"
				}
				return executionnode.ServiceConfigurationPreview{ProjectRevision: app.current.Managed.ProjectRevision,
					Runtime: executionnode.RuntimeEvidence{BundleDigest: release["bundleDigest"].(string), CatalogDigest: release["catalogDigest"].(string), CoreVersion: release["coreVersion"].(string), Protocol: release["planningProtocol"].(string)}}, nil
			}}
			preview, err := app.GetServiceConfigurationPreview()
			if err != nil {
				t.Fatal(err)
			}
			if change == "draft" {
				if preview.Diagnostic != nil || app.binding != binding || app.execution.context.Status != "READY" {
					t.Fatalf("saved projection lost during draft: %#v", preview)
				}
			} else if preview.Diagnostic == nil {
				t.Fatal("changed authority published saved preview")
			}
		})
	}
}

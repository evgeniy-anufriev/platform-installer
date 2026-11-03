package desktop

import (
	"context"
	"encoding/json"
	"strings"
	"testing"

	"platform-installer/internal/coreadapter"
	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
	"platform-installer/internal/runtimesecret"
)

func pendingApplicationFixture(t *testing.T) (*App, PendingApplicationSecretContext) {
	t.Helper()
	app, _, _ := installationPlanApp(t, false)
	t.Cleanup(app.secrets.Close)
	app.current.Managed.ApplicationLibraries = map[string]map[string]any{"library": {"libraryRef": "library@1", "applications": map[string]any{"gateway": map[string]any{}}}}
	app.current.Managed.ApplicationPackages = map[string]installer.ManagedApplicationPackage{
		"library:library@1":     {Definition: map[string]any{"slots": map[string]any{"gateway": map[string]any{"applicationRef": "gateway@1"}}}},
		"application:gateway@1": {Definition: map[string]any{"defaults": map[string]any{"accounts": map[string]any{"db": map[string]any{"credentials": map[string]any{"password": map[string]any{"source": map[string]any{"kind": "runtime_secret_ref", "ref": "{{ application_instance_id }}-password"}}}}}}}},
	}
	return app, PendingApplicationSecretContext{ApplicationLibrary: "library", ApplicationSlot: "gateway"}
}

func TestApplicationPendingSecretsDoNotRequireVerificationCoreOrSSH(t *testing.T) {
	app, scope := pendingApplicationFixture(t)
	app.binding = nil
	app.execution.setStatus("NOT_PREPARED")
	before, _ := app.projectRevision(app.current.Root)
	operation := app.GetPendingApplicationRuntimeSecretDescriptors(scope)
	if operation.Status != "READY" || len(operation.ApplicationInputs) != 1 {
		t.Fatal("local application sources unavailable")
	}
	ref := operation.ApplicationInputs[0].RequirementRef
	input := RuntimeSecretValuesInput{PendingApplicationInput: true, ApplicationLibrary: scope.ApplicationLibrary, ApplicationSlot: scope.ApplicationSlot, ProjectRevision: before, ApplicationRequirementRef: ref, Values: map[string]string{ref: "synthetic-local"}}
	for _, change := range []string{"revision", "library", "slot", "reference", "mixed", "draft"} {
		t.Run(change, func(t *testing.T) {
			candidate := input
			switch change {
			case "revision":
				candidate.ProjectRevision = "stale"
			case "library":
				candidate.ApplicationLibrary = "foreign"
			case "slot":
				candidate.ApplicationSlot = "foreign"
			case "reference":
				candidate.ApplicationRequirementRef = "foreign"
			case "mixed":
				candidate.DescriptorSetFingerprint = "core"
			case "draft":
				app.activeSession = "draft"
			}
			if app.SetDeploymentRuntimeSecretValues(candidate) == nil {
				t.Fatal("unsafe pending submission accepted")
			}
			app.activeSession = ""
		})
	}
	if err := app.SetDeploymentRuntimeSecretValues(input); err != nil {
		t.Fatal(err)
	}
	// Local field handles occupy a namespace that authored registry sources
	// cannot claim, even if a project explicitly requests that string.
	app.current.Managed.ApplicationLibraries[scope.ApplicationLibrary]["registry_credentials"] = map[string]any{"registry.example": map[string]any{"password": map[string]any{"source": map[string]any{"kind": "runtime_secret_ref", "ref": ref}}}}
	if app.SetDeploymentRuntimeSecretValues(RuntimeSecretValuesInput{ProjectRevision: before, ApplicationLibrary: scope.ApplicationLibrary, ApplicationSourceValues: map[string]string{ref: "synthetic-overwrite"}}) == nil {
		t.Fatal("registry source claimed a private field handle")
	}
	operation = app.GetPendingApplicationRuntimeSecretDescriptors(scope)
	if !operation.ApplicationSecretAvailability[ref] {
		t.Fatal("saved input not present")
	}
	public, _ := json.Marshal(operation)
	if strings.Contains(string(public), "synthetic-local") {
		t.Fatal("pending value leaked")
	}
	after, _ := app.projectRevision(app.current.Root)
	if before != after || app.current.Verification.Status == "VERIFIED" {
		t.Fatal("session input modified or verified project")
	}
}

type pendingApplicationProofTransport struct {
	applicationDescriptorTransport
	snapshot   *coreadapter.Snapshot
	proofCalls int
}

func (transport *pendingApplicationProofTransport) BuildProjectVerificationSnapshot(_ context.Context, _ executionnode.Node, _ string, release map[string]any) (executionnode.ProjectVerificationSnapshot, error) {
	transport.proofCalls++
	return executionnode.ProjectVerificationSnapshot{Snapshot: transport.snapshot, Runtime: executionnode.RuntimeEvidence{BundleDigest: release["bundleDigest"].(string), CoreVersion: release["coreVersion"].(string), CatalogDigest: release["catalogDigest"].(string), Protocol: release["planningProtocol"].(string)}}, nil
}

func TestPendingApplicationInputsAreAttachedOnlyThroughCurrentCoreProjection(t *testing.T) {
	for _, scenario := range []string{"current", "stale-projection", "changed-source"} {
		t.Run(scenario, func(t *testing.T) {
			app, scope := pendingApplicationFixture(t)
			local := app.GetPendingApplicationRuntimeSecretDescriptors(scope)
			ref := local.ApplicationInputs[0].RequirementRef
			if err := app.SetDeploymentRuntimeSecretValues(RuntimeSecretValuesInput{PendingApplicationInput: true, ApplicationLibrary: scope.ApplicationLibrary, ApplicationSlot: scope.ApplicationSlot, ProjectRevision: local.ProjectRevision, ApplicationRequirementRef: ref, Values: map[string]string{ref: "synthetic-local"}}); err != nil {
				t.Fatal(err)
			}
			binding, _ := app.credentialBindingLocked()
			if _, err := app.secrets.Set(binding, runtimesecret.Input{Username: "operator", SSHMode: runtimesecret.SSHPassword, SSHPassword: "synthetic-ssh"}); err != nil {
				t.Fatal(err)
			}
			coreRef := "application-secret-" + strings.Repeat("a", 32)
			transport := &pendingApplicationProofTransport{applicationDescriptorTransport: applicationDescriptorTransport{inputs: []executionnode.ApplicationSecretDescriptor{{RequirementRef: coreRef, SourceRef: "core-resolved-password", Purpose: "APPLICATION_SECRET", DisplayLabel: "Password", ApplicationLibraries: []string{"library"}, Hosts: []string{"node-1"}, Operations: []string{"APPLICATION_LIBRARIES_APPLY", "APPLICATION_LIBRARIES_VERIFY"}}}}}
			account := json.RawMessage(`{"credentials":{"password":{"source":{"kind":"runtime_secret_ref","ref":"core-resolved-password"}}}}`)
			transport.snapshot = &coreadapter.Snapshot{ProjectRevision: local.ProjectRevision, ApplicationLibraries: &coreadapter.ApplicationLibraries{Libraries: map[string]coreadapter.ApplicationLibrary{"library": {Instances: map[string]coreadapter.ApplicationInstance{"instance": {SlotID: "gateway", CredentialRequirements: map[string]json.RawMessage{"db": account}}}}}}}
			app.binding.reader.transport = transport
			if scenario == "stale-projection" {
				transport.snapshot.ProjectRevision = "stale"
			}
			if scenario == "changed-source" {
				app.current.Managed.ApplicationLibraries["library"]["applications"] = map[string]any{"gateway": map[string]any{"accounts": map[string]any{"db": map[string]any{"credentials": map[string]any{"password": map[string]any{"source": map[string]any{"kind": "runtime_secret_ref", "ref": "new-authored-source"}}}}}}}
			}
			operation := app.getRuntimeSecretDescriptorsLocked(true)
			missing := app.secrets.MissingRequiredSecrets(binding, []string{coreRef}, false, false)
			if scenario == "current" {
				if operation.Status != "READY" || len(missing) != 0 || transport.proofCalls != 1 {
					t.Fatal("current Core mapping did not authorize pending input")
				}
			} else if len(missing) != 1 {
				t.Fatal("unattested pending input attached")
			}
			if scenario == "changed-source" && transport.proofCalls != 0 {
				t.Fatal("unused pending input required Core projection")
			}
		})
	}
}

func TestPendingLibraryConnectionSecretUsesTheSameSessionAndCoreMapping(t *testing.T) {
	app, scope := pendingApplicationFixture(t)
	scope.ApplicationSlot = ""
	app.current.Managed.ApplicationPackages["library:library@1"].Definition["provided_connections"] = map[string]any{"sso": map[string]any{"credentials": map[string]any{"password": map[string]any{"source": map[string]any{"kind": "runtime_secret_ref", "ref": "provider-password"}}}}}
	local := app.GetPendingApplicationRuntimeSecretDescriptors(scope)
	if local.Status != "READY" || len(local.ApplicationInputs) != 1 {
		t.Fatal("saved library field unavailable")
	}
	ref := local.ApplicationInputs[0].RequirementRef
	if err := app.SetDeploymentRuntimeSecretValues(RuntimeSecretValuesInput{PendingApplicationInput: true, ApplicationLibrary: scope.ApplicationLibrary, ProjectRevision: local.ProjectRevision, ApplicationRequirementRef: ref, Values: map[string]string{ref: "synthetic-provider"}}); err != nil {
		t.Fatal(err)
	}
	if !app.GetPendingApplicationRuntimeSecretDescriptors(scope).ApplicationSecretAvailability[ref] {
		t.Fatal("provider input not present before Core")
	}
	binding, _ := app.credentialBindingLocked()
	if _, err := app.secrets.Set(binding, runtimesecret.Input{Username: "operator", SSHMode: runtimesecret.SSHPassword, SSHPassword: "synthetic-ssh"}); err != nil {
		t.Fatal(err)
	}
	coreRef := "application-secret-" + strings.Repeat("a", 32)
	transport := &pendingApplicationProofTransport{applicationDescriptorTransport: applicationDescriptorTransport{inputs: []executionnode.ApplicationSecretDescriptor{{RequirementRef: coreRef, SourceRef: "provider-password", Purpose: "APPLICATION_SECRET", DisplayLabel: "Provider", ApplicationLibraries: []string{"library"}, Hosts: []string{"node-1"}, Operations: []string{"APPLICATION_LIBRARIES_APPLY", "APPLICATION_LIBRARIES_VERIFY"}}}}}
	transport.snapshot = &coreadapter.Snapshot{ProjectRevision: local.ProjectRevision, ApplicationLibraries: &coreadapter.ApplicationLibraries{Libraries: map[string]coreadapter.ApplicationLibrary{"library": {ProvidedConnections: map[string]json.RawMessage{"sso": json.RawMessage(`{"credentials":{"password":{"source":{"kind":"runtime_secret_ref","ref":"provider-password"}}}}`)}}}}}
	app.binding.reader.transport = transport
	if result := app.getRuntimeSecretDescriptorsLocked(true); result.Status != "READY" || len(app.secrets.MissingRequiredSecrets(binding, []string{coreRef}, false, false)) != 0 {
		t.Fatal("Core did not attest library input")
	}
}

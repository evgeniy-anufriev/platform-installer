package desktop

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
	"platform-installer/internal/runtimesecret"
)

type refreshingRegistryDescriptorTransport struct {
	applicationDescriptorTransport
	calls int
	fail  bool
}

func TestAnonymousRegistryProbeNeedsTransportButNoSecretDiscovery(t *testing.T) {
	app, _, _ := installationPlanApp(t, false)
	binding, err := app.credentialBindingLocked()
	if err != nil {
		t.Fatal(err)
	}
	if _, err = app.secrets.Set(binding, runtimesecret.Input{Username: "operator", SSHMode: runtimesecret.SSHPassword, SSHPassword: "synthetic-transport", ElevationMode: runtimesecret.ElevationNone}); err != nil {
		t.Fatal(err)
	}
	scope := executionnode.ImagePreparationScope{ProjectIdentity: app.current.Project.ID, ProjectRevision: app.current.Managed.ProjectRevision,
		TargetConnections: map[string]executionnode.ImageTargetConnection{"node1": {Address: "192.0.2.10", Port: 22}}}
	credentials, err := app.imagePreparationCredentialsLocked(scope)
	if err != nil {
		t.Fatal(err)
	}
	if credentials.Payload.Username != "operator" || credentials.Payload.RuntimeSecretValues != nil || app.runtimeSecretEvidence != nil {
		t.Fatal("anonymous probe acquired unrelated secrets or constructed an invalid empty secret map")
	}
}

func (transport *refreshingRegistryDescriptorTransport) BuildRuntimeSecretDescriptors(ctx context.Context, node executionnode.Node, root string, runtime map[string]any, request executionnode.RuntimeSecretDescriptorRequest) (executionnode.RuntimeSecretDescriptorResult, error) {
	transport.calls++
	if transport.fail {
		return executionnode.RuntimeSecretDescriptorResult{}, errors.New("synthetic discovery failure")
	}
	return transport.applicationDescriptorTransport.BuildRuntimeSecretDescriptors(ctx, node, root, runtime, request)
}

func TestImagePreparationReattestsRetainedRegistrySecretsAfterProjectChanges(t *testing.T) {
	for _, scenario := range []string{"first-discovery", "save", "stale-revision", "new-requirement-reference", "new-source", "foreign-scope", "discovery-failure", "expired"} {
		t.Run(scenario, func(t *testing.T) {
			app, _, _ := installationPlanApp(t, false)
			app.execution.context.SelectedHostID = "node-1"
			now := time.Now()
			app.secrets.Close()
			app.secrets = runtimesecret.NewBroker(runtimesecret.WithClock(func() time.Time { return now }), runtimesecret.WithTTL(time.Hour))
			defer app.secrets.Close()
			inputs := []executionnode.ApplicationSecretDescriptor{}
			for i, purpose := range []string{"APPLICATION_REGISTRY_USERNAME", "APPLICATION_REGISTRY_PASSWORD", "APPLICATION_SECRET"} {
				inputs = append(inputs, executionnode.ApplicationSecretDescriptor{RequirementRef: "application-secret-" + strings.Repeat(string(rune('a'+i)), 32), Purpose: purpose, SourceRef: "source-" + string(rune('a'+i)), DisplayLabel: purpose, Hosts: []string{"node-1"}, ApplicationLibraries: []string{"sdku"}, Operations: []string{"APPLICATION_LIBRARIES_APPLY", "APPLICATION_LIBRARIES_VERIFY"}})
			}
			transport := &refreshingRegistryDescriptorTransport{applicationDescriptorTransport: applicationDescriptorTransport{inputs: inputs}}
			app.binding.reader.transport = transport
			binding, _ := app.credentialBindingLocked()
			if _, err := app.secrets.Set(binding, runtimesecret.Input{Username: "operator", SSHMode: runtimesecret.SSHPassword, SSHPassword: "synthetic-transport", ElevationMode: runtimesecret.ElevationNone}); err != nil {
				t.Fatal(err)
			}
			oldRevision := app.current.Managed.ProjectRevision
			app.current.Managed.ApplicationLibraries = map[string]map[string]any{"sdku": {"registry_credentials": map[string]any{"registry.example": map[string]any{
				"username": map[string]any{"source": map[string]any{"kind": "runtime_secret_ref", "ref": "source-a"}},
				"password": map[string]any{"source": map[string]any{"kind": "runtime_secret_ref", "ref": "source-b"}},
			}}}}
			if err := app.SetDeploymentRuntimeSecretValues(RuntimeSecretValuesInput{ProjectRevision: oldRevision, ApplicationLibrary: "sdku", ApplicationSourceValues: map[string]string{"source-a": "synthetic-user", "source-b": "synthetic-password"}}); err != nil {
				t.Fatal(err)
			}
			if scenario != "first-discovery" {
				if result := app.getRuntimeSecretDescriptorsLocked(true); result.Status != "READY" {
					t.Fatal("initial discovery failed")
				}
			}
			// Change the actual saved revision, then exercise Save's attachment
			// invalidation without asking the operator to resubmit any value.
			path := filepath.Join(app.current.Root, "project.yml")
			data, err := os.ReadFile(path)
			if err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(path, append(data, []byte("\n# unrelated project edit\n")...), 0600); err != nil {
				t.Fatal(err)
			}
			revision, err := installer.ProjectRevision(app.current.Root)
			if err != nil || revision == oldRevision {
				t.Fatal("saved revision did not change")
			}
			app.current.Managed.ProjectRevision = revision
			if scenario == "stale-revision" {
				app.secrets.ClearAttachedRuntimeSecretValues(binding)
			} else {
				app.clearRuntimeSecretDescriptorEvidenceLocked(true)
			}
			if scenario == "new-requirement-reference" {
				inputs[1].RequirementRef = "application-secret-" + strings.Repeat("d", 32)
			}
			if scenario == "new-source" {
				inputs[1].SourceRef = "new-source"
			}
			transport.fail = scenario == "discovery-failure"
			if scenario == "expired" {
				now = now.Add(2 * time.Hour)
			}
			app.current.Managed.Servers = map[string]installer.ManagedServer{"node-1": {HostID: "node-1", Address: "192.0.2.10"}}
			app.approvedTargetHostKeys = map[string]approvedTargetHostKey{"node-1": {root: app.current.Root, projectID: app.current.Project.ID, revision: revision, address: "192.0.2.10", port: 22, keyType: "ssh-ed25519", publicKey: "confirmed-key"}}
			scope := executionnode.ImagePreparationScope{ProjectIdentity: app.current.Project.ID, ProjectRevision: revision, TargetConnections: map[string]executionnode.ImageTargetConnection{"node-1": {Address: "192.0.2.10", Port: 22}}}
			data, _ = json.Marshal(inputs[:2])
			if err := json.Unmarshal(data, &scope.Requirements); err != nil {
				t.Fatal(err)
			}
			if scenario == "foreign-scope" {
				scope.Requirements[0].ApplicationLibraries = []string{"foreign"}
			}
			calls := transport.calls
			credentials, err := app.imagePreparationCredentialsLocked(scope)
			if transport.calls != calls+1 {
				t.Fatal("current Core descriptors were not requested exactly once")
			}
			wantError := map[string]string{"new-source": "APPLICATION_REGISTRY_RUNTIME_SECRET_REQUIRED", "foreign-scope": "RUNTIME_SECRET_DESCRIPTORS_STALE", "discovery-failure": "RUNTIME_SECRET_DESCRIPTORS_UNAVAILABLE", "expired": "RUNTIME_SECRET_INPUT_EXPIRED"}[scenario]
			if wantError != "" {
				if err == nil || err.Error() != wantError {
					t.Fatalf("expected %s, got %v", wantError, err)
				}
				if len(credentials.Payload.RuntimeSecretValues) != 0 {
					t.Fatal("failed preparation returned secrets")
				}
				return
			}
			if err != nil {
				t.Fatal(err)
			}
			if len(credentials.Payload.RuntimeSecretValues) != 2 || credentials.Payload.RuntimeSecretValues[inputs[0].RequirementRef] != "synthetic-user" || credentials.Payload.RuntimeSecretValues[inputs[1].RequirementRef] != "synthetic-password" {
				t.Fatal("saved registry values were lost or unrelated inputs were exposed")
			}
			if _, err := app.imagePreparationCredentialsLocked(scope); err != nil || transport.calls != calls+1 {
				t.Fatal("current evidence was not reused")
			}
		})
	}
}

func TestImagePreparationUsesPendingRegistrySessionValues(t *testing.T) {
	app, _, _ := installationPlanApp(t, false)
	app.execution.context.SelectedHostID = "node-1"
	inputs := []executionnode.ApplicationSecretDescriptor{}
	for i, purpose := range []string{"APPLICATION_REGISTRY_USERNAME", "APPLICATION_REGISTRY_PASSWORD", "APPLICATION_SECRET"} {
		inputs = append(inputs, executionnode.ApplicationSecretDescriptor{RequirementRef: "application-secret-" + strings.Repeat(string(rune('a'+i)), 32), Purpose: purpose, SourceRef: "source-" + string(rune('a'+i)), DisplayLabel: purpose, Hosts: []string{"node-1"}, ApplicationLibraries: []string{"sdku"}, Operations: []string{"APPLICATION_LIBRARIES_APPLY", "APPLICATION_LIBRARIES_VERIFY"}})
	}
	app.binding.reader.transport = applicationDescriptorTransport{inputs: inputs}
	binding, err := app.credentialBindingLocked()
	if err != nil {
		t.Fatal(err)
	}
	if _, err := app.secrets.Set(binding, runtimesecret.Input{Username: "operator", SSHMode: runtimesecret.SSHPassword, SSHPassword: "synthetic-transport", ElevationMode: runtimesecret.ElevationNone}); err != nil {
		t.Fatal(err)
	}
	descriptors := app.getRuntimeSecretDescriptorsLocked(true)
	if descriptors.Status != "READY" {
		t.Fatal("descriptors unavailable")
	}
	values := map[string]string{}
	for i, input := range inputs {
		values[input.RequirementRef] = "synthetic-value-" + string(rune('a'+i))
	}
	if err := app.SetDeploymentRuntimeSecretValues(RuntimeSecretValuesInput{ProjectRevision: descriptors.ProjectRevision, DescriptorSetFingerprint: descriptors.DescriptorSetFingerprint, ApplicationLibrary: "sdku", Values: values}); err != nil {
		t.Fatal(err)
	}
	sources := map[string]string{}
	for _, item := range inputs[:2] {
		sources[item.SourceRef] = "replacement-" + item.SourceRef
		values[item.RequirementRef] = sources[item.SourceRef]
	}
	if err := app.secrets.SetPendingApplicationSecretValues(binding, sources); err != nil {
		t.Fatal(err)
	}
	app.current.Managed = &installer.ManagedProjectView{ProjectRevision: descriptors.ProjectRevision, Servers: map[string]installer.ManagedServer{"node-1": {HostID: "node-1", Address: "192.0.2.10"}}}
	app.approvedTargetHostKeys = map[string]approvedTargetHostKey{"node-1": {root: app.current.Root, projectID: app.current.Project.ID, revision: descriptors.ProjectRevision, address: "192.0.2.10", port: 22, keyType: "ssh-ed25519", publicKey: "confirmed-key"}}
	scope := executionnode.ImagePreparationScope{ProjectIdentity: app.current.Project.ID, ProjectRevision: descriptors.ProjectRevision, TargetConnections: map[string]executionnode.ImageTargetConnection{"node-1": {Address: "192.0.2.10", Port: 22}}}
	data, _ := json.Marshal(inputs[:2])
	if err := json.Unmarshal(data, &scope.Requirements); err != nil {
		t.Fatal(err)
	}
	foreign := scope
	foreign.Requirements = append(foreign.Requirements[:0:0], scope.Requirements...)
	foreign.Requirements[0].ApplicationLibraries = []string{"other"}
	if _, err := app.imagePreparationCredentialsLocked(foreign); err == nil {
		t.Fatal("foreign scope accepted")
	}
	credentials, err := app.imagePreparationCredentialsLocked(scope)
	if err != nil {
		t.Fatal(err)
	}
	if len(credentials.Payload.RuntimeSecretValues) != 2 {
		t.Fatal("preparation received unrelated application values")
	}
	for _, input := range inputs[:2] {
		if credentials.Payload.RuntimeSecretValues[input.RequirementRef] != values[input.RequirementRef] {
			t.Fatal("saved session input missing from preparation")
		}
	}
}

func TestRegistrySecretSaveNeedsOnlySavedSourcesNotCore(t *testing.T) {
	app := preparedDraftApp(t)
	credential, _ := app.credentialBindingLocked()
	app.binding = nil
	app.execution.setStatus("NOT_PREPARED")
	app.current.Managed.ApplicationLibraries = map[string]map[string]any{"szi": {"registry_credentials": map[string]any{
		"registry.example": map[string]any{"password": map[string]any{"source": map[string]any{"kind": "runtime_secret_ref", "ref": "registry-password"}}},
	}}}
	input := RuntimeSecretValuesInput{ProjectRevision: app.current.Managed.ProjectRevision, ApplicationLibrary: "szi", ApplicationSourceValues: map[string]string{"registry-password": "synthetic-password"}}
	for _, change := range []string{"revision", "library", "source", "draft", "mixed"} {
		t.Run(change, func(t *testing.T) {
			candidate := input
			switch change {
			case "revision":
				candidate.ProjectRevision = "changed"
			case "library":
				candidate.ApplicationLibrary = "foreign"
			case "source":
				candidate.ApplicationSourceValues = map[string]string{"foreign-source": "synthetic"}
			case "draft":
				app.activeSession = "draft"
			case "mixed":
				candidate.Values = map[string]string{"unattested-ref": "synthetic"}
			}
			if err := app.SetDeploymentRuntimeSecretValues(candidate); err == nil {
				t.Fatal("unsafe input accepted")
			}
			app.activeSession = ""
		})
	}
	if err := app.SetDeploymentRuntimeSecretValues(input); err != nil {
		t.Fatal(err)
	}
	if err := app.secrets.WithTargetCredential(credential, func(value runtimesecret.TargetCredential) error {
		if len(value.RuntimeSecretValues) != 0 {
			t.Fatal("unattested source attached to target")
		}
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	if err := app.secrets.PromotePendingRuntimeSecretValues(credential, []string{"core-requirement"}, map[string]string{"registry-password": "core-requirement"}); err != nil {
		t.Fatal(err)
	}
	if missing := app.secrets.MissingRequiredSecrets(credential, []string{"core-requirement"}, false, false); len(missing) != 0 {
		t.Fatal("attested source was lost")
	}
}

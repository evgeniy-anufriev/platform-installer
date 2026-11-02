package desktop

import (
	"encoding/json"
	"strings"
	"testing"

	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
	"platform-installer/internal/runtimesecret"
)

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

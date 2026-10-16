package desktop

import (
	"context"
	"encoding/json"
	"platform-installer/internal/executionnode"
	"platform-installer/internal/runtimesecret"
	"strings"
	"testing"
)

type applicationDescriptorTransport struct {
	typedSecretDescriptorTransport
	inputs []executionnode.ApplicationSecretDescriptor
}

func (transport applicationDescriptorTransport) BuildRuntimeSecretDescriptors(ctx context.Context, node executionnode.Node, root string, runtime map[string]any, request executionnode.RuntimeSecretDescriptorRequest) (executionnode.RuntimeSecretDescriptorResult, error) {
	result, err := (typedSecretDescriptorTransport{}).BuildRuntimeSecretDescriptors(ctx, node, root, runtime, request)
	result.ApplicationInputs = []executionnode.ApplicationSecretDescriptor{{RequirementRef: "application-secret-" + strings.Repeat("a", 32), Purpose: "APPLICATION_SECRET", SourceRef: "db-password", DisplayLabel: "Database password", ApplicationLibraries: []string{"sdku"}, Hosts: []string{"node-1"}, Operations: []string{"APPLICATION_LIBRARIES_APPLY", "APPLICATION_LIBRARIES_VERIFY"}}}
	if transport.inputs != nil {
		result.ApplicationInputs = transport.inputs
	}
	return result, err
}

func TestApplicationLibraryInputExactScopeAndMerge(t *testing.T) {
	app, _, _ := installationPlanApp(t, false)
	app.execution.context.SelectedHostID = "node-1"
	base := executionnode.ApplicationSecretDescriptor{Purpose: "APPLICATION_SECRET", SourceRef: "password", DisplayLabel: "Password", Hosts: []string{"node-1"}, Operations: []string{"APPLICATION_LIBRARIES_APPLY", "APPLICATION_LIBRARIES_VERIFY"}}
	inputs := make([]executionnode.ApplicationSecretDescriptor, 3)
	for i, libraries := range [][]string{{"sdku"}, {"cspa"}, {"cspa", "sdku"}} {
		inputs[i] = base
		inputs[i].RequirementRef = "application-secret-" + strings.Repeat(string(rune('a'+i)), 32)
		inputs[i].SourceRef = "password-" + string(rune('a'+i))
		inputs[i].ApplicationLibraries = libraries
	}
	app.binding.reader.transport = applicationDescriptorTransport{inputs: inputs}
	binding, err := app.credentialBindingLocked()
	if err != nil {
		t.Fatal(err)
	}
	if _, err = app.secrets.Set(binding, runtimesecret.Input{Username: "operator", SSHMode: runtimesecret.SSHPassword, SSHPassword: "synthetic-transport", ElevationMode: runtimesecret.ElevationNone}); err != nil {
		t.Fatal(err)
	}
	evidence := app.getRuntimeSecretDescriptorsLocked(true)
	if evidence.Status != "READY" || len(evidence.ApplicationInputs) != 3 {
		t.Fatal("descriptor setup failed")
	}
	request := RuntimeSecretValuesInput{ProjectRevision: evidence.ProjectRevision, DescriptorSetFingerprint: evidence.DescriptorSetFingerprint, ApplicationLibrary: "sdku", Values: map[string]string{inputs[0].RequirementRef: "synthetic-a", inputs[2].RequirementRef: "synthetic-shared"}}
	for _, tc := range []struct {
		name   string
		change func(*RuntimeSecretValuesInput)
	}{
		{"stale revision", func(v *RuntimeSecretValuesInput) { v.ProjectRevision = "stale" }},
		{"stale fingerprint", func(v *RuntimeSecretValuesInput) { v.DescriptorSetFingerprint = "stale" }},
		{"unknown library", func(v *RuntimeSecretValuesInput) { v.ApplicationLibrary = "unknown" }},
		{"mixed scopes", func(v *RuntimeSecretValuesInput) { v.ServiceDeployment = "redis-main" }},
		{"foreign ref", func(v *RuntimeSecretValuesInput) {
			v.Values = map[string]string{inputs[1].RequirementRef: "synthetic-b", inputs[2].RequirementRef: "synthetic-shared"}
		}},
		{"missing shared ref", func(v *RuntimeSecretValuesInput) {
			v.Values = map[string]string{inputs[0].RequirementRef: "synthetic-a"}
		}},
	} {
		t.Run(tc.name, func(t *testing.T) {
			v := request
			tc.change(&v)
			if app.SetDeploymentRuntimeSecretValues(v) == nil {
				t.Fatal("invalid scope accepted")
			}
		})
	}
	if err = app.SetDeploymentRuntimeSecretValues(request); err != nil {
		t.Fatal(err)
	}
	request.ApplicationLibrary = "cspa"
	request.Values = map[string]string{inputs[1].RequirementRef: "synthetic-b", inputs[2].RequirementRef: "synthetic-shared"}
	if err = app.SetDeploymentRuntimeSecretValues(request); err != nil {
		t.Fatal(err)
	}
	if app.getRuntimeSecretDescriptorsLocked(false).Status != "READY" {
		t.Fatal("reattestation failed")
	}
	if err = app.secrets.WithTargetCredential(binding, func(value runtimesecret.TargetCredential) error {
		for i, want := range []string{"synthetic-a", "synthetic-b", "synthetic-shared"} {
			if string(value.RuntimeSecretValues[inputs[i].RequirementRef]) != want {
				t.Fatal("scoped save lost or changed an input")
			}
		}
		return nil
	}); err != nil {
		t.Fatal(err)
	}
}

func TestApplicationInputReattestationAndStaleBinding(t *testing.T) {
	app, _, _ := installationPlanApp(t, false)
	app.binding.reader.transport = applicationDescriptorTransport{}
	app.execution.context.SelectedHostID = "node-1"
	binding, err := app.credentialBindingLocked()
	if err != nil {
		t.Fatal(err)
	}
	if _, err = app.secrets.Set(binding, runtimesecret.Input{Username: "operator", SSHMode: runtimesecret.SSHPassword, SSHPassword: "synthetic-transport", ElevationMode: runtimesecret.ElevationNone}); err != nil {
		t.Fatal(err)
	}
	first := app.getRuntimeSecretDescriptorsLocked(true)
	if first.Status != "READY" || len(first.ApplicationInputs) != 1 {
		t.Fatalf("application descriptors unavailable: %+v", first.Error)
	}
	input := RuntimeSecretValuesInput{ProjectRevision: first.ProjectRevision, DescriptorSetFingerprint: first.DescriptorSetFingerprint, Values: map[string]string{first.ApplicationInputs[0].RequirementRef: "synthetic-application-value"}}
	stale := input
	stale.DescriptorSetFingerprint = "stale"
	if app.SetDeploymentRuntimeSecretValues(stale) == nil {
		t.Fatal("stale fingerprint accepted")
	}
	if err = app.SetDeploymentRuntimeSecretValues(input); err != nil {
		t.Fatal(err)
	}
	if result := app.getRuntimeSecretDescriptorsLocked(false); result.Status != "READY" {
		t.Fatal("Start reattestation lost input")
	}
	if err = app.secrets.WithTargetCredential(binding, func(value runtimesecret.TargetCredential) error {
		if string(value.RuntimeSecretValues[first.ApplicationInputs[0].RequirementRef]) != "synthetic-application-value" {
			t.Fatal("value not promoted to existing lease map")
		}
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	public, _ := json.Marshal(first)
	if strings.Contains(string(public), "synthetic-application-value") {
		t.Fatal("value leaked in public descriptors")
	}
	app.execution.context.SelectedHostID = "other"
	if app.SetDeploymentRuntimeSecretValues(input) == nil {
		t.Fatal("different node accepted")
	}
}

func TestApplicationSecretDescriptorScope(t *testing.T) {
	valid := executionnode.ApplicationSecretDescriptor{RequirementRef: "application-secret-" + strings.Repeat("a", 32), Purpose: "APPLICATION_SECRET", SourceRef: "db-password", DisplayLabel: "Database password", ApplicationLibraries: []string{"sdku"}, Hosts: []string{"node1"}, Operations: []string{"APPLICATION_LIBRARIES_APPLY", "APPLICATION_LIBRARIES_VERIFY"}}
	if !validApplicationSecretDescriptor(valid) {
		t.Fatal("valid descriptor rejected")
	}
	for _, change := range []func(*executionnode.ApplicationSecretDescriptor){
		func(v *executionnode.ApplicationSecretDescriptor) { v.Purpose = "SERVICE_PASSWORD" },
		func(v *executionnode.ApplicationSecretDescriptor) { v.Operations = []string{"SERVICE_APPLY"} },
		func(v *executionnode.ApplicationSecretDescriptor) { v.Hosts = []string{"node1", "node1"} },
		func(v *executionnode.ApplicationSecretDescriptor) { v.ApplicationLibraries = []string{"../escape"} },
		func(v *executionnode.ApplicationSecretDescriptor) { v.SourceRef = "../escape" },
		func(v *executionnode.ApplicationSecretDescriptor) {
			provider := "vault-main"
			v.ProviderDeployment = &provider
		},
	} {
		v := valid
		change(&v)
		if validApplicationSecretDescriptor(v) {
			t.Fatal("invalid scope accepted")
		}
	}
	provider := "vault-main"
	valid.Purpose = "APPLICATION_VAULT_ADMIN_TOKEN"
	valid.ProviderDeployment = &provider
	valid.SourceRef = "vault-admin-token-vault-main"
	if !validApplicationSecretDescriptor(valid) {
		t.Fatal("provider-bound token rejected")
	}
	valid.SourceRef = "vault-admin-token-other"
	if validApplicationSecretDescriptor(valid) {
		t.Fatal("wrong provider accepted")
	}
}

func TestApplicationPlanRequiresLeaseMapInputs(t *testing.T) {
	plan := executionnode.DeploymentPlan{RequiredCredentials: []executionnode.RequiredCredential{{RequirementRef: "application-secret-" + strings.Repeat("a", 32), Purpose: "APPLICATION_SECRET"}, {RequirementRef: "application-secret-" + strings.Repeat("b", 32), Purpose: "APPLICATION_VAULT_ADMIN_TOKEN"}}}
	refs, err := installationPlanRuntimeSecretRequirements(plan)
	if err != nil || len(refs) != 2 {
		t.Fatalf("application requirements missing: %v", err)
	}
}

func TestVerifyOnlyDescriptorScopeRemainsExact(t *testing.T) {
	descriptors := []RuntimeSecretDescriptorView{
		{RequirementRef: "admin-token", Purpose: "SERVICE_ADMIN_TOKEN", Operations: []string{"SERVICE_APPLY", "SERVICE_VERIFY"}},
		{RequirementRef: "unseal-shares", Purpose: "SERVICE_UNSEAL_SHARES", Operations: []string{"SERVICE_APPLY"}},
	}
	required := []executionnode.RuntimeSecretInputRequirement{{RequirementRef: "admin-token", Purpose: "SERVICE_ADMIN_TOKEN"}}
	if !runtimeDescriptorsMatchPlan(descriptors, required, executionnode.ApplicationLibrariesOnly) {
		t.Fatal("Apply-only descriptor must not enter Verify scope")
	}
	if runtimeDescriptorsMatchPlan(descriptors, required, executionnode.FullProject) {
		t.Fatal("full scope must not discard descriptors")
	}
	if runtimeDescriptorsMatchPlan(descriptors[:1], nil, executionnode.ApplicationLibrariesOnly) {
		t.Fatal("unexpected Verify input accepted")
	}
	if runtimeDescriptorsMatchPlan(descriptors[1:], required, executionnode.ApplicationLibrariesOnly) {
		t.Fatal("required Verify input missing")
	}
}

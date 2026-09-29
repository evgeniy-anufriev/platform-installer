package main

import (
	"context"
	"testing"

	"platform-installer/internal/executionnode"
	"platform-installer/internal/runtimesecret"
)

type typedSecretDescriptorTransport struct{ installationPlanTransport }

func (typedSecretDescriptorTransport) BuildRuntimeSecretDescriptors(_ context.Context, _ executionnode.Node, _ string, _ map[string]any, request executionnode.RuntimeSecretDescriptorRequest) (executionnode.RuntimeSecretDescriptorResult, error) {
	return executionnode.RuntimeSecretDescriptorResult{
		ProjectIdentity: request.ProjectIdentity, ProjectRevision: request.ProjectRevision,
		DescriptorSetFingerprint: "synthetic-fingerprint",
		Runtime:                  executionnode.RuntimeEvidence{BundleDigest: "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", CoreVersion: "test-core", CatalogDigest: "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc", Protocol: "platform.installer/execution-runtime/v1alpha1"},
		Descriptors: []executionnode.RuntimeSecretDescriptor{
			{RequirementRef: "admin-token", Purpose: "SERVICE_ADMIN_TOKEN", ServiceDeployment: "vault-main", DisplayLabel: "Admin", RequiredWhen: "INITIALIZED", Operations: []string{"SERVICE_APPLY", "SERVICE_VERIFY"}, Hosts: []string{"node-1"}},
			{RequirementRef: "unseal-shares", Purpose: "SERVICE_UNSEAL_SHARES", ServiceDeployment: "vault-main", DisplayLabel: "Shares", RequiredWhen: "SEALED", Operations: []string{"SERVICE_APPLY"}, Hosts: []string{"node-1"}},
		},
	}, nil
}

func TestAppDescriptorRefreshAndStartPreparationPreserveTypedInputs(t *testing.T) {
	app, _, _ := installationPlanApp(t, false)
	app.binding.reader.transport = typedSecretDescriptorTransport{}
	binding, err := app.credentialBindingLocked()
	if err != nil {
		t.Fatal(err)
	}
	if _, err := app.secrets.Set(binding, runtimesecret.Input{Username: "operator", SSHMode: runtimesecret.SSHPassword, SSHPassword: "synthetic-transport", ElevationMode: runtimesecret.ElevationNone}); err != nil {
		t.Fatal(err)
	}
	if err := app.secrets.SetPendingServiceSecretInput(binding, "vault-main", "SERVICE_ADMIN_TOKEN", []byte("synthetic-token"), nil); err != nil {
		t.Fatal(err)
	}
	if err := app.secrets.SetPendingServiceSecretInput(binding, "vault-main", "SERVICE_UNSEAL_SHARES", nil, [][]byte{[]byte("synthetic-share")}); err != nil {
		t.Fatal(err)
	}
	// Public refresh and Start's non-clearing refresh use the same application seam.
	for _, clearAttached := range []bool{true, false, true} {
		result := app.getRuntimeSecretDescriptorsLocked(clearAttached)
		if result.Status != "READY" || len(result.Descriptors) != 2 || app.runtimeSecretEvidence == nil {
			t.Fatal("typed-only descriptor refresh blocked")
		}
		if err := app.secrets.WithTargetCredential(binding, func(value runtimesecret.TargetCredential) error {
			if len(value.RuntimeSecretInputs) != 2 || len(value.RuntimeSecretValues) != 0 {
				t.Fatal("typed inputs lost or converted to passwords")
			}
			return nil
		}); err != nil {
			t.Fatal(err)
		}
	}
}

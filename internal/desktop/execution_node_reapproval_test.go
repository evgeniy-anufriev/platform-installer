package desktop

import (
	"encoding/base64"
	"os"
	"testing"
	"time"

	"platform-installer/internal/installer"
	"platform-installer/internal/projectlifecycle"
	"platform-installer/internal/runtimesecret"
)

func reapprovalFixture(t *testing.T) (*App, runtimesecret.Binding, []runtimesecret.RuntimeSecretInput) {
	t.Helper()
	app := NewApp(unavailableProjectReader{}, lifecycleStub{})
	t.Cleanup(func() { app.secrets.Clear(); app.invalidateDynamicBindingLocked() })
	root := t.TempDir()
	app.current = ProjectOpenResult{Status: "OPEN", Root: root,
		Project: &projectlifecycle.Project{ID: "reapproval-project"},
		Managed: &installer.ManagedProjectView{Servers: map[string]installer.ManagedServer{
			"node1": {HostID: "node1", Address: "192.0.2.10"},
		}}}
	app.execution.bind(root, "reapproval-project", managedSnapshotHosts(app.current.Managed))
	binding := runtimesecret.Binding{Root: root, ID: "reapproval-project"}
	if _, err := app.SetSessionCredential(runtimesecret.Input{Username: "platform-automation",
		SSHMode: runtimesecret.SSHPassword, SSHPassword: "synthetic-password", ElevationMode: runtimesecret.ElevationNone}); err != nil {
		t.Fatal(err)
	}
	setReapprovalProbe(t, app, false)
	if result := app.ApproveExecutionNodeHostKey("reapproval"); result.Status != "APPROVED" {
		t.Fatalf("initial approval: %s", result.Status)
	}
	for _, item := range []struct{ purpose string }{{"SERVICE_ADMIN_TOKEN"}, {"SERVICE_UNSEAL_SHARES"}} {
		var value []byte
		var shares [][]byte
		if item.purpose == "SERVICE_ADMIN_TOKEN" {
			value = []byte("synthetic-token")
		} else {
			shares = [][]byte{[]byte("synthetic-share")}
		}
		if err := app.secrets.SetPendingServiceSecretInput(binding, "vault-one", item.purpose, value, shares); err != nil {
			t.Fatal(err)
		}
	}
	inputs := []runtimesecret.RuntimeSecretInput{
		{Purpose: "SERVICE_ADMIN_TOKEN", ServiceDeployment: "vault-one"},
		{Purpose: "SERVICE_UNSEAL_SHARES", ServiceDeployment: "vault-one"},
	}
	if !app.secrets.ServiceSecretsPresent(binding, inputs) {
		t.Fatal("fixture inputs missing")
	}
	app.installationPlanID = "existing-plan"
	return app, binding, inputs
}

func setReapprovalProbe(t *testing.T, app *App, changedKey bool) {
	t.Helper()
	kind, key, fingerprint, err := parseScannedHostKey([]byte(testScannedED25519("192.0.2.10")), "192.0.2.10", 22)
	if err != nil {
		t.Fatal(err)
	}
	if changedKey {
		blob, _ := base64.StdEncoding.DecodeString(key)
		blob[len(blob)-1] ^= 1
		kind, key, fingerprint, err = parseScannedHostKey([]byte("192.0.2.10 ssh-ed25519 "+base64.StdEncoding.EncodeToString(blob)+"\n"), "192.0.2.10", 22)
		if err != nil {
			t.Fatal(err)
		}
	}
	binding, _ := app.credentialBindingLocked()
	identity, err := app.secrets.CurrentExecutionIdentity(binding)
	if err != nil {
		t.Fatal(err)
	}
	app.pendingHostKey = &pendingExecutionHostKey{id: "reapproval", hostID: "node1", address: "192.0.2.10", port: 22,
		keyType: kind, publicKey: key, fingerprint: fingerprint, credentialGeneration: identity.Generation,
		expires: time.Now().Add(time.Minute)}
}

func TestRepeatedHostKeyApprovalRetainsBindingPlanAndVaultInputs(t *testing.T) {
	for _, prepared := range []bool{false, true} {
		t.Run(map[bool]string{false: "before-preparation", true: "prepared-runtime"}[prepared], func(t *testing.T) {
			app, binding, inputs := reapprovalFixture(t)
			if prepared {
				bundle := v02TestBundle(t)
				app.availableBundleRoot = bundle.Root
				app.current.Project.Source.BundleDigest = bundle.Digest
				app.current.Project.Source.CatalogDigest = bundle.Manifest.CatalogDigest
				app.binding.bundleRoot = bundle.Root
				app.binding.reader.runtimeRelease = map[string]any{"bundleDigest": bundle.Digest}
			}
			previous := app.binding
			setReapprovalProbe(t, app, false)
			result := app.ApproveExecutionNodeHostKey("reapproval")
			if result.Status != "APPROVED" || app.binding != previous || app.installationPlanID != "existing-plan" {
				t.Fatalf("same connection/key must retain binding and plan: %s", result.Status)
			}
			if !app.secrets.ServiceSecretsPresent(binding, inputs) {
				t.Fatal("same-key confirmation cleared Vault inputs")
			}
		})
	}
}

func TestChangedHostKeyApprovalStillInvalidatesPlanAndVaultInputs(t *testing.T) {
	app, binding, inputs := reapprovalFixture(t)
	previous := app.binding
	setReapprovalProbe(t, app, true)
	result := app.ApproveExecutionNodeHostKey("reapproval")
	if result.Status != "APPROVED" || app.binding == previous || app.installationPlanID != "" {
		t.Fatalf("different key must replace binding and plan: %s", result.Status)
	}
	if app.secrets.ServiceSecretsPresent(binding, inputs) {
		t.Fatal("different key retained stale Vault inputs")
	}
}

func TestSameHostKeyApprovalDoesNotReuseTamperedPin(t *testing.T) {
	app, binding, inputs := reapprovalFixture(t)
	previous := app.binding
	if err := os.WriteFile(previous.hostKeyPin.knownHosts, []byte("tampered\n"), 0600); err != nil {
		t.Fatal(err)
	}
	setReapprovalProbe(t, app, false)
	result := app.ApproveExecutionNodeHostKey("reapproval")
	if result.Status != "APPROVED" || app.binding == previous || app.secrets.ServiceSecretsPresent(binding, inputs) {
		t.Fatal("damaged pin must take the normal replacement path")
	}
}

func TestSessionCredentialRenewalRetainsVaultInputsForReattestation(t *testing.T) {
	for _, password := range []string{"synthetic-password", "replacement-password"} {
		t.Run(password, func(t *testing.T) {
			app, binding, inputs := reapprovalFixture(t)
			app.runtimeSecretEvidence = &runtimeSecretDescriptorEvidence{}
			status, err := app.SetSessionCredential(runtimesecret.Input{Username: "platform-automation", SSHMode: runtimesecret.SSHPassword, SSHPassword: password, ElevationMode: runtimesecret.ElevationNone})
			if err != nil || status.Status != "PRESENT" {
				t.Fatalf("credential renewal: %v", err)
			}
			if app.binding != nil || app.installationPlanID != "" || app.runtimeSecretEvidence != nil {
				t.Fatal("SSH renewal must still invalidate node readiness, plan and descriptor evidence")
			}
			if !app.secrets.ServiceSecretsPresent(binding, inputs) {
				t.Fatal("SSH renewal erased imported Vault inputs")
			}
			setReapprovalProbe(t, app, false)
			if result := app.ApproveExecutionNodeHostKey("reapproval"); result.Status != "APPROVED" {
				t.Fatal(result.Status)
			}
			if !app.secrets.ServiceSecretsPresent(binding, inputs) {
				t.Fatal("fresh approval erased retained Vault inputs")
			}
			descriptors := []runtimesecret.RuntimeSecretInput{
				{RequirementRef: "vault-admin-input", Purpose: "SERVICE_ADMIN_TOKEN", ServiceDeployment: "vault-one", Operations: []string{"SERVICE_APPLY", "SERVICE_VERIFY"}},
				{RequirementRef: "vault-unseal-input", Purpose: "SERVICE_UNSEAL_SHARES", ServiceDeployment: "vault-one", Operations: []string{"SERVICE_APPLY"}},
			}
			token := runtimesecret.RuntimeSecretInput{RequirementRef: "application-vault-input", Purpose: "APPLICATION_VAULT_ADMIN_TOKEN", ServiceDeployment: "vault-one"}
			if err := app.secrets.BindPendingServiceSecretInputs(binding, descriptors, token); err != nil {
				t.Fatal(err)
			}
			if missing := app.secrets.MissingRequiredSecrets(binding, []string{token.RequirementRef}, false, false); len(missing) != 0 {
				t.Fatal("retained Vault token was not reattached")
			}
		})
	}
}

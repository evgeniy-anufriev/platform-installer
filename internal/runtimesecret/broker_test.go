package runtimesecret

import (
	"bytes"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/x509"
	"encoding/pem"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestBrokerSetReplaceClearAndBinding(t *testing.T) {
	broker := NewBroker()
	first := Binding{Root: `C:\projects\one`, ID: "project-one"}
	second := Binding{Root: `C:\projects\two`, ID: "project-two"}
	status, err := broker.Set(first, Input{Username: " installer ", SSHMode: SSHPassword, SSHPassword: "not-reported", ElevationMode: ElevationSudo, ElevationPassword: "also-not-reported"})
	if err != nil || status.Status != StatusPresent || status.Username != "installer" || status.SudoPasswordStatus != SudoPresent {
		t.Fatalf("unexpected safe status: %#v err=%v", status, err)
	}
	if got := broker.Status(second); got.Status != StatusMissing {
		t.Fatalf("other project status=%#v", got)
	}
	if _, err := broker.Set(first, Input{Username: "installer", SSHMode: SSHPassword, SSHPassword: "replacement", ElevationMode: ElevationNone}); err != nil {
		t.Fatalf("replace: %v", err)
	}
	broker.Clear()
	if got := broker.Status(first); got.Status != StatusMissing || got.Username != "" || got.SSHMode != "" {
		t.Fatalf("clear leaked metadata: %#v", got)
	}
}

func TestBrokerFailedReplacementPreservesLease(t *testing.T) {
	broker := NewBroker()
	binding := Binding{Root: `C:\projects\one`, ID: "project-one"}
	if _, err := broker.Set(binding, Input{Username: "installer", SSHMode: SSHPassword, SSHPassword: "valid", ElevationMode: ElevationNone}); err != nil {
		t.Fatal(err)
	}
	if _, err := broker.Set(binding, Input{Username: "installer", SSHMode: SSHPrivateKey, ElevationMode: ElevationNone}); err == nil || err.Error() != "SESSION_CREDENTIAL_MODE_INVALID" {
		t.Fatalf("error=%v", err)
	}
	if got := broker.Status(binding); got.Status != StatusPresent || got.Username != "installer" || got.SSHMode != SSHPassword {
		t.Fatalf("valid lease was lost: %#v", got)
	}
}

func TestBrokerRejectsOversizedPasswordWithoutReplacingLease(t *testing.T) {
	broker := NewBroker()
	binding := Binding{Root: `C:\projects\one`, ID: "project-one"}
	if _, err := broker.Set(binding, Input{Username: "installer", SSHMode: SSHPassword, SSHPassword: "valid", ElevationMode: ElevationNone}); err != nil {
		t.Fatal(err)
	}
	if _, err := broker.Set(binding, Input{Username: "installer", SSHMode: SSHPassword, SSHPassword: string(make([]byte, maxPasswordBytes+1)), ElevationMode: ElevationNone}); err == nil || err.Error() != "SESSION_CREDENTIAL_TOO_LARGE" {
		t.Fatalf("error=%v", err)
	}
	if got := broker.Status(binding); got.Status != StatusPresent {
		t.Fatalf("oversized replacement removed lease: %#v", got)
	}
}

func TestBrokerExpiresWithoutStatusActivity(t *testing.T) {
	broker := NewBroker(WithTTL(10 * time.Millisecond))
	binding := Binding{Root: `C:\projects\one`, ID: "project-one"}
	if _, err := broker.Set(binding, Input{Username: "installer", SSHMode: SSHPassword, SSHPassword: "value", ElevationMode: ElevationNone}); err != nil {
		t.Fatal(err)
	}
	time.Sleep(30 * time.Millisecond)
	if got := broker.Status(binding); got.Status != StatusExpired || got.Username != "" || got.ExpiresAt != "" {
		t.Fatalf("expiry status=%#v", got)
	}
}

func TestBrokerExposesTargetCredentialOnlyToSynchronousCallback(t *testing.T) {
	broker := NewBroker()
	binding := Binding{Root: `C:\projects\one`, ID: "project-one"}
	if _, err := broker.Set(binding, Input{Username: "installer", SSHMode: SSHPassword, SSHPassword: "not-reported", ElevationMode: ElevationSudo, ElevationPassword: "also-not-reported"}); err != nil {
		t.Fatal(err)
	}
	var observed TargetCredential
	if err := broker.WithTargetCredential(binding, func(value TargetCredential) error {
		if value.Username != "installer" || value.SSHMode != SSHPassword || string(value.SSHSecret) != "not-reported" || string(value.SudoSecret) != "also-not-reported" {
			t.Fatalf("unexpected callback value: %#v", value)
		}
		observed = value
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	if observed.SSHSecret[0] != 0 || observed.SudoSecret[0] != 0 {
		t.Fatal("callback copies were not zeroed")
	}
	if err := broker.WithTargetCredential(Binding{Root: "other", ID: "other"}, func(TargetCredential) error { return nil }); err == nil || err.Error() != "SESSION_CREDENTIAL_UNAVAILABLE" {
		t.Fatalf("binding error=%v", err)
	}
}

func TestBrokerReplacesOnlyAcknowledgedRuntimeSecretSubset(t *testing.T) {
	broker := NewBroker()
	binding := Binding{Root: `C:\projects\one`, ID: "project-one"}
	if _, err := broker.Set(binding, Input{Username: "installer", SSHMode: SSHPassword, SSHPassword: "transport-only", ElevationMode: ElevationNone}); err != nil {
		t.Fatal(err)
	}
	if err := broker.SetRuntimeSecretValuesForRequirements(binding, []string{"service-a-password"}, map[string]string{"service-a-password": "first"}); err != nil {
		t.Fatal(err)
	}
	if err := broker.SetRuntimeSecretValuesForRequirements(binding, []string{"service-b-password"}, map[string]string{"service-b-password": "second"}); err != nil {
		t.Fatal(err)
	}
	if err := broker.SetRuntimeSecretValuesForRequirements(binding, []string{"service-a-password"}, map[string]string{"service-a-password": "replacement"}); err != nil {
		t.Fatal(err)
	}
	if err := broker.WithTargetCredential(binding, func(value TargetCredential) error {
		if len(value.RuntimeSecretValues) != 2 || string(value.RuntimeSecretValues["service-a-password"]) != "replacement" || string(value.RuntimeSecretValues["service-b-password"]) != "second" {
			t.Fatalf("unexpected scoped secret set")
		}
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	broker.ClearRuntimeSecretValues(binding)
	if err := broker.WithTargetCredential(binding, func(value TargetCredential) error {
		if len(value.RuntimeSecretValues) != 0 {
			t.Fatal("runtime secrets were not cleared")
		}
		return nil
	}); err != nil {
		t.Fatal(err)
	}
}

func TestBrokerBindsTypedServiceInputsToCoreDescriptors(t *testing.T) {
	broker := NewBroker()
	binding := Binding{Root: `C:\projects\vault`, ID: "project-vault"}
	if err := broker.SetPendingServiceSecretInput(binding, "vault-ha", "SERVICE_ADMIN_TOKEN", []byte("admin-token"), nil); err != nil {
		t.Fatal("pending admin token rejected")
	}
	if err := broker.SetPendingServiceSecretInput(binding, "vault-ha", "SERVICE_UNSEAL_SHARES", nil, [][]byte{[]byte("share-a"), []byte("share-b")}); err != nil {
		t.Fatal("pending shares rejected")
	}
	if _, err := broker.Set(binding, Input{Username: "operator", SSHMode: SSHPassword, SSHPassword: "transport", ElevationMode: ElevationNone}); err != nil {
		t.Fatal("session setup failed")
	}
	descriptors := []RuntimeSecretInput{
		{RequirementRef: "si-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", Purpose: "SERVICE_ADMIN_TOKEN", ServiceDeployment: "vault-ha", Operations: []string{"SERVICE_APPLY", "SERVICE_VERIFY"}},
		{RequirementRef: "si-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", Purpose: "SERVICE_UNSEAL_SHARES", ServiceDeployment: "vault-ha", Operations: []string{"SERVICE_APPLY"}},
	}
	if err := broker.BindPendingServiceSecretInputs(binding, descriptors); err != nil {
		t.Fatal("Core descriptor binding failed")
	}
	if err := broker.WithTargetCredential(binding, func(value TargetCredential) error {
		if len(value.RuntimeSecretInputs) != 2 {
			t.Fatal("typed inputs missing")
		}
		for _, input := range value.RuntimeSecretInputs {
			switch input.Purpose {
			case "SERVICE_ADMIN_TOKEN":
				if input.RequirementRef != descriptors[0].RequirementRef || string(input.Value) != "admin-token" {
					t.Fatal("admin token not bound to Core ref")
				}
			case "SERVICE_UNSEAL_SHARES":
				if input.RequirementRef != descriptors[1].RequirementRef || len(input.Shares) != 2 || string(input.Shares[1]) != "share-b" {
					t.Fatal("shares not bound to Core ref")
				}
			default:
				t.Fatal("unexpected typed input purpose")
			}
		}
		return nil
	}); err != nil {
		t.Fatal("credential callback failed")
	}
	if err := broker.BindPendingServiceSecretInputs(binding, []RuntimeSecretInput{descriptors[0]}); err == nil || err.Error() != "RUNTIME_SECRET_DESCRIPTORS_STALE" {
		t.Fatal("missing current descriptor did not fail closed")
	}
}

func TestBrokerHoldsPendingServiceSecretsUntilCurrentCoreDescriptorsAndTargetCredentialExist(t *testing.T) {
	broker := NewBroker()
	binding := Binding{Root: `C:\projects\one`, ID: "project-one"}
	if err := broker.SetPendingRuntimeSecretValuesForRequirements(binding, []string{"redis-password"}, map[string]string{"redis-password": "not-reported"}); err != nil {
		t.Fatal(err)
	}
	if err := broker.PromotePendingRuntimeSecretValues(binding, []string{"redis-password"}); err != nil {
		t.Fatal(err)
	}
	if _, err := broker.Set(binding, Input{Username: "installer", SSHMode: SSHPassword, SSHPassword: "transport-only", ElevationMode: ElevationNone}); err != nil {
		t.Fatal(err)
	}
	if err := broker.PromotePendingRuntimeSecretValues(binding, []string{"other-password"}); err == nil || err.Error() != "RUNTIME_SECRET_DESCRIPTORS_STALE" {
		t.Fatalf("stale core descriptors error=%v", err)
	}
	if err := broker.PromotePendingRuntimeSecretValues(binding, []string{"redis-password"}); err != nil {
		t.Fatal(err)
	}
	if err := broker.WithTargetCredential(binding, func(value TargetCredential) error {
		if string(value.RuntimeSecretValues["redis-password"]) != "not-reported" || len(value.RuntimeSecretValues) != 1 {
			t.Fatalf("unexpected promoted values")
		}
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	broker.ClearRuntimeSecretValues(binding)
	if err := broker.PromotePendingRuntimeSecretValues(binding, []string{"redis-password"}); err != nil {
		t.Fatal(err)
	}
	if err := broker.WithTargetCredential(binding, func(value TargetCredential) error {
		if len(value.RuntimeSecretValues) != 0 {
			t.Fatal("cleared pending values were retained")
		}
		return nil
	}); err != nil {
		t.Fatal(err)
	}
}

func TestOutputEncryptionPasswordIsProjectBoundTransientAndClearedAfterUse(t *testing.T) {
	now := time.Now()
	broker := NewBroker(WithClock(func() time.Time { return now }))
	binding := Binding{Root: t.TempDir(), ID: "project-output"}
	secret := []byte("age-password-test")
	if err := broker.SetOutputEncryptionPassword(binding, secret); err != nil {
		t.Fatal(err)
	}
	var borrowed []byte
	if err := broker.WithOutputEncryptionPassword(binding, func(value []byte) error {
		borrowed = value
		if string(value) != string(secret) {
			t.Fatal("password mismatch")
		}
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(borrowed, make([]byte, len(borrowed))) {
		t.Fatal("borrowed password was not zeroed")
	}
	if err := broker.WithOutputEncryptionPassword(Binding{Root: binding.Root, ID: "other"}, func([]byte) error { t.Fatal("cross-project password access"); return nil }); err == nil {
		t.Fatal("cross-project password access accepted")
	}
	now = now.Add(59 * time.Minute)
	if err := broker.WithOutputEncryptionPassword(binding, func([]byte) error { return nil }); err != nil {
		t.Fatalf("output password expired before one-hour TTL: %v", err)
	}
	now = now.Add(time.Minute)
	if err := broker.WithOutputEncryptionPassword(binding, func([]byte) error { t.Fatal("expired password access"); return nil }); err == nil {
		t.Fatal("expired password accepted")
	}
	broker.Clear()
}

func TestBrokerDefaultCredentialAndSecretTTLIsOneHour(t *testing.T) {
	if broker := NewBroker(); broker.ttl != time.Hour {
		t.Fatalf("broker TTL=%s, want 1h", broker.ttl)
	}
}

func TestBrokerStoresBoundedPKIStorePasswordOnlyInMemory(t *testing.T) {
	broker := NewBroker()
	binding := Binding{Root: `C:\projects\one`, ID: "project-one"}
	if _, err := broker.Set(binding, Input{Username: "installer", SSHMode: SSHPassword, SSHPassword: "transport-only", ElevationMode: ElevationNone}); err != nil {
		t.Fatal(err)
	}
	if _, err := broker.SetPKIStorePassword(binding, string(make([]byte, maxPKIStorePasswordBytes))); err != nil {
		t.Fatal(err)
	}
	if status := broker.Status(binding); status.PKIStorePasswordStatus != PKIStorePasswordPresent {
		t.Fatalf("status=%#v", status)
	}
	var observed TargetCredential
	if err := broker.WithTargetCredential(binding, func(value TargetCredential) error { observed = value; return nil }); err != nil {
		t.Fatal(err)
	}
	if len(observed.PKIStorePassword) != maxPKIStorePasswordBytes || observed.PKIStorePassword[0] != 0 {
		t.Fatal("PKI callback value was not zeroed")
	}
	if _, err := broker.SetPKIStorePassword(binding, ""); err == nil || err.Error() != "PKI_STORE_PASSWORD_INPUT_INVALID" {
		t.Fatalf("empty error=%v", err)
	}
	if _, err := broker.SetPKIStorePassword(binding, string(make([]byte, maxPKIStorePasswordBytes+1))); err == nil || err.Error() != "PKI_STORE_PASSWORD_INPUT_INVALID" {
		t.Fatalf("oversize error=%v", err)
	}
}

func TestBrokerReadsRegularUnencryptedPEMKeyOnly(t *testing.T) {
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	der, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(t.TempDir(), "session-key.pem")
	if err := os.WriteFile(path, pem.EncodeToMemory(&pem.Block{Type: "PRIVATE KEY", Bytes: der}), 0600); err != nil {
		t.Fatal(err)
	}
	broker := NewBroker()
	binding := Binding{Root: `C:\projects\one`, ID: "project-one"}
	if got, err := broker.Set(binding, Input{Username: "installer", SSHMode: SSHPrivateKey, PrivateKeyPath: path, ElevationMode: ElevationNone}); err != nil || got.SSHMode != SSHPrivateKey {
		t.Fatalf("key status=%#v err=%v", got, err)
	}
	identity, err := broker.CurrentExecutionIdentity(binding)
	if err != nil || identity.Path != path || identity.Username != "installer" || identity.FileInfo == nil || identity.Generation == 0 {
		t.Fatalf("private identity metadata unavailable: %v", err)
	}
	if identity.Digest == [32]byte{} {
		t.Fatal("missing identity digest")
	}
	if _, err := broker.CurrentExecutionIdentity(Binding{Root: "other", ID: "other"}); err == nil {
		t.Fatal("cross-project identity accepted")
	}
	if _, err := broker.Set(binding, Input{Username: "installer", SSHMode: SSHPrivateKey, PrivateKeyPath: t.TempDir(), ElevationMode: ElevationNone}); err == nil || err.Error() != "SESSION_PRIVATE_KEY_NOT_REGULAR" {
		t.Fatalf("directory error=%v", err)
	}
	if _, err := broker.Set(binding, Input{Username: "installer", SSHMode: SSHPassword, SSHPassword: "runtime-only"}); err != nil {
		t.Fatal(err)
	}
	if _, err := broker.CurrentExecutionIdentity(binding); err == nil {
		t.Fatal("password mode authorized execution identity")
	}
}

func TestBrokerRunIdentityHoldSurvivesOrdinaryExpiryWithoutRetainingOtherSecrets(t *testing.T) {
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	der, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(t.TempDir(), "run-key.pem")
	if err := os.WriteFile(path, pem.EncodeToMemory(&pem.Block{Type: "PRIVATE KEY", Bytes: der}), 0600); err != nil {
		t.Fatal(err)
	}
	now := time.Now()
	broker := NewBroker(WithTTL(time.Hour), WithClock(func() time.Time { return now }))
	binding := Binding{Root: `C:\projects\one`, ID: "project-one"}
	if _, err := broker.Set(binding, Input{Username: "installer", SSHMode: SSHPrivateKey, PrivateKeyPath: path, ElevationMode: ElevationNone}); err != nil {
		t.Fatal(err)
	}
	if _, err := broker.SetPKIStorePassword(binding, "pki-only-until-expiry"); err != nil {
		t.Fatal(err)
	}
	identity, err := broker.CurrentExecutionIdentity(binding)
	if err != nil {
		t.Fatal(err)
	}
	if err := broker.ReserveExecutionIdentityForStart(binding, "plan-1", identity); err != nil {
		t.Fatalf("reserve active identity: %v", err)
	}
	if err := broker.ConfirmExecutionIdentityRun(binding, "plan-1", "installer-run-1"); err != nil {
		t.Fatalf("confirm active identity: %v", err)
	}

	now = now.Add(2 * time.Hour)
	broker.mu.Lock()
	broker.expireLocked(identity.Generation)
	broker.mu.Unlock()
	got, err := broker.CurrentExecutionIdentity(binding)
	if err != nil || !sameExecutionIdentity(got, identity) {
		t.Fatalf("held execution identity=%#v err=%v", got, err)
	}
	if status := broker.Status(binding); status.Status != StatusExpired || status.SudoPasswordStatus != SudoNotProvided || status.PKIStorePasswordStatus != PKIStorePasswordMissing {
		t.Fatalf("ordinary lease did not expire independently: %#v", status)
	}
	if err := broker.WithTargetCredential(binding, func(TargetCredential) error { return nil }); err == nil || err.Error() != "SESSION_CREDENTIAL_UNAVAILABLE" {
		t.Fatalf("expired general credentials remained available: %v", err)
	}
	if _, err := broker.Set(binding, Input{Username: "new-user", SSHMode: SSHPassword, SSHPassword: "new-session"}); err == nil || err.Error() != "INSTALLATION_RUN_ACTIVE" {
		t.Fatalf("credential replacement during run returned %v", err)
	}
	if _, err := broker.CurrentExecutionIdentity(Binding{Root: `C:\projects\two`, ID: "other-project"}); err == nil {
		t.Fatal("run identity hold crossed project binding")
	}

	broker.ReleaseExecutionIdentityForRun("installer-run-1")
	if _, err := broker.CurrentExecutionIdentity(binding); err == nil {
		t.Fatal("released run identity remained available")
	}
	if broker.runHold != nil {
		t.Fatalf("run hold metadata was not removed: %#v", broker.runHold)
	}
}

func TestBrokerRunIdentityHoldRejectsReplacedCredentialGeneration(t *testing.T) {
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	der, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(t.TempDir(), "run-key.pem")
	if err := os.WriteFile(path, pem.EncodeToMemory(&pem.Block{Type: "PRIVATE KEY", Bytes: der}), 0600); err != nil {
		t.Fatal(err)
	}
	binding := Binding{Root: `C:\projects\one`, ID: "project-one"}
	broker := NewBroker()
	if _, err := broker.Set(binding, Input{Username: "installer", SSHMode: SSHPrivateKey, PrivateKeyPath: path, ElevationMode: ElevationNone}); err != nil {
		t.Fatal(err)
	}
	identity, err := broker.CurrentExecutionIdentity(binding)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := broker.Set(binding, Input{Username: "replacement", SSHMode: SSHPrivateKey, PrivateKeyPath: path, ElevationMode: ElevationNone}); err != nil {
		t.Fatal(err)
	}
	if err := broker.ReserveExecutionIdentityForStart(binding, "plan-stale", identity); err == nil || err.Error() != "EXECUTION_RUN_IDENTITY_STALE" {
		t.Fatalf("stale credential generation was accepted: %v", err)
	}
}

func TestBrokerStartingIdentityReservationCanRetrySamePlanAndRejectsOtherPlan(t *testing.T) {
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	der, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(t.TempDir(), "run-key.pem")
	if err := os.WriteFile(path, pem.EncodeToMemory(&pem.Block{Type: "PRIVATE KEY", Bytes: der}), 0600); err != nil {
		t.Fatal(err)
	}
	binding := Binding{Root: `C:\projects\one`, ID: "project-one"}
	broker := NewBroker()
	if _, err := broker.Set(binding, Input{Username: "installer", SSHMode: SSHPrivateKey, PrivateKeyPath: path, ElevationMode: ElevationNone}); err != nil {
		t.Fatal(err)
	}
	identity, err := broker.CurrentExecutionIdentity(binding)
	if err != nil {
		t.Fatal(err)
	}
	if err := broker.ReserveExecutionIdentityForStart(binding, "plan-1", identity); err != nil {
		t.Fatal(err)
	}
	if _, err := broker.Set(Binding{Root: `C:\projects\other`, ID: "project-other"}, Input{Username: "replacement", SSHMode: SSHPassword, SSHPassword: "session"}); err == nil || err.Error() != "INSTALLATION_RUN_ACTIVE" {
		t.Fatalf("credential replacement during STARTING returned %v", err)
	}
	if err := broker.ReserveExecutionIdentityForStart(binding, "plan-1", identity); err != nil {
		t.Fatalf("same-plan retry did not reuse STARTING slot: %v", err)
	}
	if err := broker.ReserveExecutionIdentityForStart(binding, "plan-2", identity); err == nil || err.Error() != "INSTALLATION_RUN_ACTIVE" {
		t.Fatalf("different plan entered occupied slot: %v", err)
	}
	if err := broker.ConfirmExecutionIdentityRun(binding, "plan-1", "run-1"); err != nil {
		t.Fatal(err)
	}
	if err := broker.ReserveExecutionIdentityForStart(binding, "plan-1", identity); err == nil || err.Error() != "INSTALLATION_RUN_ACTIVE" {
		t.Fatalf("RUNNING slot was reused for Start: %v", err)
	}
	broker.ReleaseExecutionIdentityForRun("run-1")
}

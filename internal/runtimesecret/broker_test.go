package runtimesecret

import (
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
	if _, err := broker.Set(binding, Input{Username: "installer", SSHMode: SSHPrivateKey, PrivateKeyPath: t.TempDir(), ElevationMode: ElevationNone}); err == nil || err.Error() != "SESSION_PRIVATE_KEY_NOT_REGULAR" {
		t.Fatalf("directory error=%v", err)
	}
}

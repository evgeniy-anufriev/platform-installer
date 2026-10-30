package runtimesecret

import (
	"testing"
	"time"
)

func TestPasswordPromotionPreservesTypedInputsForCoreBinding(t *testing.T) {
	for _, withPassword := range []bool{false, true} {
		t.Run(map[bool]string{false: "typed-only", true: "mixed"}[withPassword], func(t *testing.T) {
			now := time.Now()
			b := NewBroker(WithClock(func() time.Time { return now }))
			t.Cleanup(b.Clear)
			binding := Binding{Root: t.TempDir(), ID: "project-test"}
			if withPassword {
				if err := b.SetPendingRuntimeSecretValuesForRequirements(binding, []string{"service-password"}, map[string]string{"service-password": "synthetic"}); err != nil {
					t.Fatal(err)
				}
			}
			if err := b.SetPendingServiceSecretInput(binding, "vault-main", "SERVICE_ADMIN_TOKEN", []byte("synthetic-token"), nil); err != nil {
				t.Fatal(err)
			}
			if err := b.SetPendingServiceSecretInput(binding, "vault-main", "SERVICE_UNSEAL_SHARES", nil, [][]byte{[]byte("synthetic-share")}); err != nil {
				t.Fatal(err)
			}
			if _, err := b.Set(binding, Input{Username: "operator", SSHMode: SSHPassword, SSHPassword: "synthetic-transport", ElevationMode: ElevationNone}); err != nil {
				t.Fatal(err)
			}
			expiresAt, generation := b.pending.expiresAt, b.pending.generation
			passwordBuffer := b.pending.values["service-password"]
			var typedBuffers [][]byte
			for _, value := range b.pending.typed {
				typedBuffers = append(typedBuffers, value.Value)
				typedBuffers = append(typedBuffers, value.Shares...)
			}
			descriptors := []RuntimeSecretInput{{RequirementRef: "admin-token", Purpose: "SERVICE_ADMIN_TOKEN", ServiceDeployment: "vault-main", Operations: []string{"SERVICE_APPLY", "SERVICE_VERIFY"}}, {RequirementRef: "unseal-shares", Purpose: "SERVICE_UNSEAL_SHARES", ServiceDeployment: "vault-main", Operations: []string{"SERVICE_APPLY"}}}
			requirements := []string{}
			if withPassword {
				requirements = append(requirements, "service-password")
			}
			for attempt := 0; attempt < 2; attempt++ {
				if attempt > 0 {
					b.ClearAttachedRuntimeSecretValues(binding)
				}
				if err := b.PromotePendingRuntimeSecretValues(binding, requirements); err != nil {
					t.Fatal("password promotion rejected typed bucket")
				}
				if b.pending == nil || b.pending.expiresAt != expiresAt || b.pending.generation != generation {
					t.Fatal("typed pending lifetime changed")
				}
				if err := b.BindPendingServiceSecretInputs(binding, descriptors); err != nil {
					t.Fatal("typed binding failed")
				}
				if err := b.WithTargetCredential(binding, func(value TargetCredential) error {
					if len(value.RuntimeSecretInputs) != 2 {
						t.Fatal("typed inputs lost")
					}
					if withPassword && len(value.RuntimeSecretValues) != 1 {
						t.Fatal("password lost")
					}
					return nil
				}); err != nil {
					t.Fatal(err)
				}
			}
			if b.BindPendingServiceSecretInputs(binding, descriptors[:1]) == nil {
				t.Fatal("missing typed descriptor admitted")
			}
			now = expiresAt
			if err := b.PromotePendingRuntimeSecretValues(binding, requirements); err == nil || err.Error() != "RUNTIME_SECRET_INPUT_EXPIRED" || b.pending != nil {
				t.Fatal("expired typed bucket retained")
			}
			for _, buffer := range append(typedBuffers, passwordBuffer) {
				for _, value := range buffer {
					if value != 0 {
						t.Fatal("expired typed input not wiped")
					}
				}
			}
		})
	}
}

func TestLegacyPasswordCanBeReattestedWithoutExtendingItsSession(t *testing.T) {
	now := time.Now()
	b := NewBroker(WithClock(func() time.Time { return now }))
	defer b.Close()
	binding := Binding{Root: "/project", ID: "one"}
	if _, err := b.Set(binding, Input{Username: "operator", SSHMode: SSHPassword, SSHPassword: "synthetic-transport"}); err != nil {
		t.Fatal(err)
	}
	if err := b.SetPendingRuntimeSecretValuesForRequirements(binding, []string{"clickhouse-password"}, map[string]string{"clickhouse-password": "synthetic-value"}); err != nil {
		t.Fatal(err)
	}
	expiresAt, generation := b.pending.expiresAt, b.pending.generation
	buffer := b.pending.values["clickhouse-password"]
	for i := 0; i < 3; i++ {
		b.ClearAttachedRuntimeSecretValues(binding)
		if err := b.PromotePendingRuntimeSecretValues(binding, []string{"different-requirement"}); err == nil {
			t.Fatal("changed requirements admitted old password")
		}
		if err := b.PromotePendingRuntimeSecretValues(binding, []string{"clickhouse-password"}); err != nil {
			t.Fatal(err)
		}
		if b.pending == nil || b.pending.expiresAt != expiresAt || b.pending.generation != generation {
			t.Fatal("reattestation changed input expiry")
		}
	}
	b.ClearRuntimeSecretValues(binding)
	for _, value := range buffer {
		if value != 0 {
			t.Fatal("strict clear retained the original password")
		}
	}
}

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
				for _, value := range passwordBuffer {
					if value != 0 {
						t.Fatal("consumed password not wiped")
					}
				}
				if err := b.BindPendingServiceSecretInputs(binding, descriptors); err != nil {
					t.Fatal("typed binding failed")
				}
				if err := b.WithTargetCredential(binding, func(value TargetCredential) error {
					if len(value.RuntimeSecretInputs) != 2 {
						t.Fatal("typed inputs lost")
					}
					if attempt == 0 && withPassword && len(value.RuntimeSecretValues) != 1 {
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
			for _, buffer := range typedBuffers {
				for _, value := range buffer {
					if value != 0 {
						t.Fatal("expired typed input not wiped")
					}
				}
			}
		})
	}
}

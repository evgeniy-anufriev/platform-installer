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

func TestSudoHoldIsExactAndWipedForPasswordAndPEM(t *testing.T) {
	for _, mode := range []string{SSHPassword, SSHPrivateKey} {
		t.Run(mode, func(t *testing.T) {
			now := time.Now()
			b := NewBroker(WithClock(func() time.Time { return now }), WithTTL(time.Minute))
			defer b.Close()
			binding := Binding{Root: "project", ID: "one"}
			input := Input{Username: "installer", SSHMode: mode, SSHPassword: "synthetic-ssh", ElevationMode: ElevationSudo, ElevationPassword: "synthetic-sudo"}
			if mode == SSHPrivateKey {
				key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
				if err != nil {
					t.Fatal(err)
				}
				der, err := x509.MarshalPKCS8PrivateKey(key)
				if err != nil {
					t.Fatal(err)
				}
				input.SSHPassword = ""
				input.PrivateKeyPath = filepath.Join(t.TempDir(), "test.pem")
				if err := os.WriteFile(input.PrivateKeyPath, pem.EncodeToMemory(&pem.Block{Type: "PRIVATE KEY", Bytes: der}), 0600); err != nil {
					t.Fatal(err)
				}
			}
			if _, err := b.Set(binding, input); err != nil {
				t.Fatal(err)
			}
			identity, err := b.CurrentExecutionIdentity(binding)
			if err != nil {
				t.Fatal(err)
			}
			if !b.HasExecutionSudoPassword(binding, identity) {
				t.Fatal("missing live sudo metadata")
			}
			if err := b.ReserveExecutionIdentityForStart(binding, "plan", identity); err != nil {
				t.Fatal(err)
			}
			held := b.runHold.sudoPassword
			now = now.Add(2 * time.Minute)
			if b.HasExecutionSudoPassword(binding, identity) {
				t.Fatal("ordinary expired sudo allowed")
			}
			for _, scope := range [][2]string{{"", ""}, {"wrong", ""}, {"", "other"}} {
				if err := b.WithExecutionSudoPassword(binding, identity, scope[0], scope[1], func([]byte) error { return nil }); err == nil {
					t.Fatal("unrelated sudo scope accepted")
				}
			}
			if err := b.ConfirmExecutionIdentityRun(binding, "plan", "run"); err != nil {
				t.Fatal(err)
			}
			var borrowed []byte
			if err := b.WithExecutionSudoPassword(binding, identity, "", "run", func(v []byte) error {
				borrowed = v
				if !bytes.Equal(v, []byte("synthetic-sudo")) {
					t.Fatal("wrong sudo")
				}
				return nil
			}); err != nil {
				t.Fatal(err)
			}
			if !bytes.Equal(borrowed, make([]byte, len(borrowed))) {
				t.Fatal("callback not wiped")
			}
			stale := identity
			stale.Generation++
			if err := b.WithExecutionSudoPassword(binding, stale, "", "run", func([]byte) error { return nil }); err == nil {
				t.Fatal("wrong generation allowed")
			}
			b.ReleaseExecutionIdentityForRun("run")
			if !bytes.Equal(held, make([]byte, len(held))) {
				t.Fatal("held sudo not wiped")
			}
			if err := b.WithExecutionSudoPassword(binding, identity, "", "run", func([]byte) error { return nil }); err == nil {
				t.Fatal("terminal sudo retained")
			}
		})
	}
}

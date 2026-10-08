package runtimesecret

import (
	"bytes"
	"testing"
	"time"
)

func TestPasswordRunHoldCannotAuthorizeNewOperations(t *testing.T) {
	now := time.Now()
	b := NewBroker(WithClock(func() time.Time { return now }), WithTTL(time.Minute))
	defer b.Close()
	binding := Binding{Root: "project", ID: "one"}
	if _, err := b.Set(binding, Input{Username: "installer", SSHMode: SSHPassword, SSHPassword: "synthetic-password"}); err != nil {
		t.Fatal(err)
	}
	identity, err := b.CurrentExecutionIdentity(binding)
	if err != nil {
		t.Fatal(err)
	}
	if err = b.ReserveExecutionIdentityForStart(binding, "plan", identity); err != nil {
		t.Fatal(err)
	}
	held := b.runHold.password
	now = now.Add(2 * time.Minute)
	if _, err = b.CurrentExecutionIdentity(binding); err == nil {
		t.Fatal("expired password authorized ordinary operation")
	}
	if _, err = b.CurrentExecutionIdentityForOperation(binding, "different", ""); err == nil {
		t.Fatal("foreign plan authorized")
	}
	if _, err = b.CurrentExecutionIdentityForOperation(binding, "plan", ""); err != nil {
		t.Fatal("unknown Start lost reservation")
	}
	if err = b.ConfirmExecutionIdentityRun(binding, "plan", "run"); err != nil {
		t.Fatal(err)
	}
	if _, err = b.CurrentExecutionIdentityForOperation(binding, "plan", ""); err == nil {
		t.Fatal("old Start scope accepted after confirmation")
	}
	for _, scope := range [][2]string{{"", ""}, {"", "other"}, {"plan", "run"}} {
		if err = b.WithExecutionPassword(binding, identity, scope[0], scope[1], func([]byte) error { return nil }); err == nil {
			t.Fatal("unrelated scope exposed retained password")
		}
	}
	var borrowed []byte
	if err = b.WithExecutionPassword(binding, identity, "", "run", func(value []byte) error {
		borrowed = value
		if string(value) != "synthetic-password" {
			t.Fatal("wrong secret")
		}
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(borrowed, make([]byte, len(borrowed))) {
		t.Fatal("callback bytes retained")
	}
	stale := identity
	stale.Generation++
	if err = b.WithExecutionPassword(binding, stale, "", "run", func([]byte) error { return nil }); err == nil {
		t.Fatal("different generation accepted")
	}
	b.ReleaseExecutionIdentityForRun("run")
	if !bytes.Equal(held, make([]byte, len(held))) {
		t.Fatal("terminal release did not wipe password")
	}
	if _, err = b.CurrentExecutionIdentityForOperation(binding, "", "run"); err == nil {
		t.Fatal("terminal password retained")
	}
}

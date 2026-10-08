package executionnode

import (
	"context"
	"platform-installer/internal/sshpassword"
	"strings"
	"testing"
)

func TestPasswordSSHAndSCPRetainHostPinAndDisableKeyFallback(t *testing.T) {
	transport := OpenSSHTransport{IsolatedHostKeyTrust: true, Password: func(context.Context, func([]byte) error) error { return nil }}
	node := testNode()
	for _, args := range [][]string{transport.base(node, ""), transport.scpBase(node, "")} {
		command := strings.Join(args, " ")
		for _, required := range []string{"-F none", "StrictHostKeyChecking=yes", "GlobalKnownHostsFile=none", "UserKnownHostsFile=", "BatchMode=no", "PreferredAuthentications=password", "PubkeyAuthentication=no", "KbdInteractiveAuthentication=no", "NumberOfPasswordPrompts=1"} {
			if !strings.Contains(command, required) {
				t.Fatalf("missing password option %s", required)
			}
		}
		for _, arg := range args {
			if arg == "-i" || arg == "BatchMode=yes" {
				t.Fatal("key-only option retained")
			}
		}
	}
	if identity, err := transport.identityFile("runtime:ssh"); err != nil || identity != "" {
		t.Fatal("password requires key file")
	}
	pem := OpenSSHTransport{Identity: fixedIdentity{}}
	args := strings.Join(pem.base(node, "runtime-key"), " ")
	if !strings.Contains(args, "BatchMode=yes") || !strings.Contains(args, "-i runtime-key") {
		t.Fatal("PEM options changed")
	}
}

func TestRunProtocolCarriesExactPasswordScope(t *testing.T) {
	runner := &outputRunner{}
	var scopes []string
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner, ContextCommandGuard: func(ctx context.Context) (func(), error) {
		// scope is applied by run methods, never by information/readiness.
		scopes = append(scopes, sshpassword.OperationScope(ctx).RunID)
		return func() {}, nil
	}}
	_, _ = transport.GetExecution(context.Background(), testNode(), "run-one")
	_, _ = transport.GetEvents(context.Background(), testNode(), "run-two", 0, 10)
	_, _ = transport.CancelExecution(context.Background(), testNode(), "run-three")
	if strings.Join(scopes, ",") != "run-one,run-two,run-three" {
		t.Fatal("run scope not exact")
	}
}

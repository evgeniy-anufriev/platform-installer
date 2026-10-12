package desktop

import (
	"context"
	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
	"platform-installer/internal/projectlifecycle"
	"platform-installer/internal/runtimesecret"
	"platform-installer/internal/sshpassword"
	"strings"
	"testing"
	"time"
)

func TestExpiredPasswordCannotDestroyActiveRunTransport(t *testing.T) {
	now := time.Now()
	broker := runtimesecret.NewBroker(runtimesecret.WithClock(func() time.Time { return now }), runtimesecret.WithTTL(time.Minute))
	defer broker.Close()
	root := t.TempDir()
	credential := runtimesecret.Binding{Root: root, ID: "one"}
	if _, err := broker.Set(credential, runtimesecret.Input{Username: "installer", SSHMode: runtimesecret.SSHPassword, SSHPassword: "test-only"}); err != nil {
		t.Fatal(err)
	}
	identity, err := broker.CurrentExecutionIdentity(credential)
	if err != nil {
		t.Fatal(err)
	}
	kind, key, _, err := parseScannedHostKey([]byte(testScannedED25519("192.0.2.10")), "192.0.2.10", 22)
	if err != nil {
		t.Fatal(err)
	}
	known, file, directory, dirInfo, digest, err := createSessionKnownHosts("192.0.2.10", 22, kind, key)
	if err != nil {
		t.Fatal(err)
	}
	defer removeSessionKnownHosts(known, file, directory, dirInfo)
	app := NewApp(unavailableProjectReader{}, lifecycleStub{})
	app.secrets = broker
	app.current = ProjectOpenResult{Status: "OPEN", Root: root, Project: &projectlifecycle.Project{ID: "one"}, Managed: &installer.ManagedProjectView{ProjectRevision: "r", Servers: map[string]installer.ManagedServer{"node1": {HostID: "node1", Address: "192.0.2.10"}}}}
	app.projectRevision = func(string) (string, error) { return "r", nil }
	app.execution.bind(root, "one", managedSnapshotHosts(app.current.Managed))
	transport := app.executionTransport(identity, credential, known, file, digest)
	binding := &executionNodeBinding{dynamic: true, node: executionnode.Node{ID: "node1", Address: "192.0.2.10", Port: 22, User: "installer"}, reader: projectReader{transport: transport}, service: executionnode.NewService(transport), credentialGeneration: identity.Generation, hostKeyPin: &approvedExecutionHostKey{}, commandGuard: transport.CommandGuard}
	app.binding = binding
	if err = broker.ReserveExecutionIdentityForStart(credential, "plan", identity); err != nil {
		t.Fatal(err)
	}
	if err = broker.ConfirmExecutionIdentityRun(credential, "plan", "run"); err != nil {
		t.Fatal(err)
	}
	now = now.Add(2 * time.Minute)
	if _, err = app.resolveTrustedExecutionConnectionLocked(); err == nil {
		t.Fatal("ordinary check authorized after expiry")
	}
	if app.binding != binding {
		t.Fatal("ordinary lookup revoked active run")
	}
	if err = app.revalidateBindingBeforePublicationLocked(binding); err == nil {
		t.Fatal("late ordinary result accepted")
	}
	if app.binding != binding {
		t.Fatal("late ordinary result revoked active run")
	}
	if _, err = app.resolveTrustedExecutionConnectionLocked(sshpassword.Scope{RunID: "run"}); err != nil {
		t.Fatal("active run lost binding")
	}
	ctx := sshpassword.WithScope(context.Background(), sshpassword.Scope{RunID: "run"})
	if err = transport.Password(ctx, func(password []byte) error {
		if strings.TrimSpace(string(password)) != "test-only" {
			t.Fatal("incorrect password")
		}
		return nil
	}); err != nil {
		t.Fatal("active transport lost password")
	}
	if err = transport.Password(context.Background(), func([]byte) error { return nil }); err == nil {
		t.Fatal("ordinary transport received held password")
	}
}

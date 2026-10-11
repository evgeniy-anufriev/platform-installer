package executionnode

import (
	"context"
	"errors"
	"platform-installer/internal/executionbundle"
	"strings"
	"testing"
)

func TestActivationPreparesPrivateExecutionStorageBeforePublication(t *testing.T) {
	runner := &recordingRunner{}
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	_, err := transport.ActivateStagedRuntime(context.Background(), testNode(), "/var/tmp/platform-installer-bootstrap-"+strings.Repeat("a", 32), executionbundle.Verified{Digest: "sha256:" + strings.Repeat("a", 64)})
	if err != nil {
		t.Fatal(err)
	}
	if len(runner.calls) != 2 {
		t.Fatalf("calls=%d", len(runner.calls))
	}
	script := runner.calls[0].input
	for _, expected := range []string{"sudo -n", "PYTHONDONTWRITEBYTECODE=1", "_directory(EXECUTION_STATE_ROOT, create=True)"} {
		if !strings.Contains(script, expected) {
			t.Fatalf("missing %s", expected)
		}
	}
	if strings.Contains(script, "chown") || strings.Contains(script, "chmod") {
		t.Fatal("preparation must not repair foreign storage")
	}
}

func TestBoundedOutputStopsRetainingAfterLimit(t *testing.T) {
	output := &boundedOutput{limit: 4}
	if written, err := output.Write([]byte("abcdef")); err != nil || written != 6 {
		t.Fatalf("written=%d err=%v", written, err)
	}
	if output.String() != "abcd" || !output.overflow {
		t.Fatalf("output=%q overflow=%v", output.String(), output.overflow)
	}
}

type fixedIdentity struct{}

func (fixedIdentity) IdentityFile(string) (string, error) { return "runtime-key", nil }

type recordedCommand struct {
	name  string
	args  []string
	input string
}
type recordingRunner struct{ calls []recordedCommand }

func (r *recordingRunner) Run(_ context.Context, name string, args []string, input []byte) ([]byte, error) {
	r.calls = append(r.calls, recordedCommand{name, append([]string(nil), args...), string(input)})
	return []byte("OS=redos\nVERSION=8.0\nARCH=x86_64\nELEVATION=yes\nFREE=100\n"), nil
}

type outputRunner struct {
	outputs [][]byte
	calls   []recordedCommand
}

func (r *outputRunner) Run(_ context.Context, name string, args []string, input []byte) ([]byte, error) {
	r.calls = append(r.calls, recordedCommand{name, append([]string(nil), args...), string(input)})
	if len(r.outputs) == 0 {
		return nil, nil
	}
	output := r.outputs[0]
	r.outputs = r.outputs[1:]
	return output, nil
}

func TestOpenSSHTransportUsesStrictHostKeyCheckingAndNoDownloader(t *testing.T) {
	runner := &recordingRunner{}
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	if _, err := transport.InspectExecutionNode(context.Background(), testNode()); err != nil {
		t.Fatal(err)
	}
	call := runner.calls[0]
	if call.name != "ssh" || !strings.Contains(strings.Join(call.args, " "), "StrictHostKeyChecking=yes") || strings.Contains(strings.Join(call.args, " "), "StrictHostKeyChecking=no") {
		t.Fatalf("%+v", call)
	}
	if strings.Contains(call.input, "curl") || strings.Contains(call.input, "dnf") || strings.Contains(call.input, "pip") {
		t.Fatalf("inspect invoked downloader: %s", call.input)
	}
}

func TestWorkspaceOwnershipReconciliationIsScopedAndVerifiesCurrentSSHOwner(t *testing.T) {
	runner := &outputRunner{outputs: [][]byte{[]byte("CHANGED=no\n")}}
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	if _, err := transport.ReconcileWorkspaceOwnership(context.Background(), testNode()); err != nil {
		t.Fatal(err)
	}
	if len(runner.calls) != 1 || runner.calls[0].name != "ssh" {
		t.Fatalf("calls=%+v", runner.calls)
	}
	script := runner.calls[0].input
	for _, required := range []string{
		"uid=$(id -u)",
		"owner=$(sudo -n stat -c %u -- \"$workspace\")",
		"if [ \"$owner\" != \"$uid\" ]; then",
		"find \"$workspace\" -mindepth 1 -maxdepth 1 -print -quit",
		"sudo -n chown -- \"$uid:$gid\" -- \"$workspace\"",
		"stat -c %u -- \"$workspace\"",
		"[ \"$(sudo -n stat -c %u -- \"$workspace\")\" = \"$uid\" ]",
		"workspace=$base/execution-plan",
		"sudo -n chmod 0711 -- \"$base\"",
		"printf 'CHANGED=%s\\n' \"$changed\"",
	} {
		if !strings.Contains(script, required) {
			t.Fatalf("ownership check omitted %q", required)
		}
	}
	for _, forbidden := range []string{"/var/lib/platform-installer", "private", "payload", "sudo -n chmod -R", "sudo -n chown -R", "sudo -n chown -- \"$uid:$gid\" -- \"$base\""} {
		if strings.Contains(script, forbidden) {
			t.Fatalf("ownership check exceeds workspace boundary with %q", forbidden)
		}
	}
}

func TestUITransportUsesOnlySessionHostKeyTrustAndGuard(t *testing.T) {
	runner := &recordingRunner{}
	guarded, released := 0, 0
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner, IsolatedHostKeyTrust: true, CommandGuard: func() (func(), error) { guarded++; return func() { released++ }, nil }}
	if _, err := transport.InspectExecutionNode(context.Background(), testNode()); err != nil {
		t.Fatal(err)
	}
	if guarded != 1 || released != 1 || len(runner.calls) != 1 {
		t.Fatalf("guard=%d release=%d calls=%d", guarded, released, len(runner.calls))
	}
	args := strings.Join(runner.calls[0].args, " ")
	destination := testNode().User + "@" + testNode().Address
	foundDestination := false
	for _, arg := range runner.calls[0].args {
		if arg == destination {
			foundDestination = true
			if strings.HasPrefix(arg, "-") {
				t.Fatal("SSH destination interpreted as option")
			}
		}
	}
	if !foundDestination {
		t.Fatal("SSH destination argument missing")
	}
	for _, required := range []string{"-F none", "GlobalKnownHostsFile=none", "KnownHostsCommand=none", "StrictHostKeyChecking=yes", "UserKnownHostsFile="} {
		if !strings.Contains(args, required) {
			t.Fatalf("missing isolated option %q", required)
		}
	}
	legacy := OpenSSHTransport{Identity: fixedIdentity{}, Runner: &recordingRunner{}}
	if strings.Contains(strings.Join(legacy.base(testNode(), "runtime-key"), " "), "-F none") {
		t.Fatal("legacy path changed")
	}
	rejected := OpenSSHTransport{Identity: fixedIdentity{}, Runner: &recordingRunner{}, IsolatedHostKeyTrust: true, CommandGuard: func() (func(), error) { return nil, errors.New("key changed") }}
	if _, err := rejected.InspectExecutionNode(context.Background(), testNode()); err == nil {
		t.Fatal("changed identity reached transport")
	}
}

func TestServiceWorkspaceHasSchemaSafeFallbackIdentifier(t *testing.T) {
	workspace := serviceWorkspace("node1", "kafka")
	if !strings.HasPrefix(workspace, "/var/tmp/platform-installer/service/run-") {
		t.Fatalf("workspace=%s", workspace)
	}
	if workspace != serviceWorkspace("node1", "kafka") || workspace == serviceWorkspace("node2", "kafka") {
		t.Fatalf("workspace is not deterministic and target-scoped: %s", workspace)
	}
}

func TestRemoteAcquisitionWorkspaceIsUniqueBoundedAndCleanedSafely(t *testing.T) {
	runner := &outputRunner{outputs: [][]byte{[]byte("/var/tmp/platform-installer-acquisition-a1B2c3D4e5\n"), nil}}
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	root, err := createRemoteAcquisitionWorkspace(context.Background(), transport, testNode())
	if err != nil {
		t.Fatal(err)
	}
	if err := validateRemoteAcquisitionWorkspace(root); err != nil {
		t.Fatal(err)
	}
	cleanupRemoteAcquisitionWorkspace(transport, testNode(), root)
	if len(runner.calls) != 2 {
		t.Fatalf("ssh calls=%d, want create and cleanup", len(runner.calls))
	}
	create := runner.calls[0]
	if create.name != "ssh" || !strings.Contains(create.input, "mktemp -d /var/tmp/platform-installer-acquisition-XXXXXXXXXX") || !strings.Contains(create.input, "chmod 700") {
		t.Fatalf("unsafe/missing isolated workspace creation: %+v", create)
	}
	cleanup := runner.calls[1]
	if cleanup.name != "ssh" || !strings.Contains(cleanup.input, "test ! -L") || !strings.Contains(cleanup.input, "rm -rf -- \"$root\"") {
		t.Fatalf("cleanup did not verify an owned directory path: %+v", cleanup)
	}
	if !strings.Contains(strings.Join(cleanup.args, " "), root) {
		t.Fatalf("cleanup target differs from allocated root: %+v", cleanup.args)
	}
}

func TestRemoteAcquisitionWorkspaceRejectsUntrustedPaths(t *testing.T) {
	for _, root := range []string{
		"/var/tmp/platform-installer/acquisition/bundle-build-abc",
		"/var/tmp/platform-installer-acquisition-abc",
		"/var/tmp/platform-installer-acquisition-1234567890/child",
		"/var/tmp/platform-installer-acquisition-1234567890\n/foreign",
	} {
		if err := validateRemoteAcquisitionWorkspace(root); err == nil {
			t.Errorf("accepted untrusted workspace path %q", root)
		}
	}
	for _, output := range [][]byte{
		[]byte("/var/tmp/platform-installer/acquisition/x\n"),
		[]byte("/var/tmp/platform-installer-acquisition-a1B2c3D4e5\nextra\n"),
	} {
		runner := &outputRunner{outputs: [][]byte{output}}
		transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
		if _, err := createRemoteAcquisitionWorkspace(context.Background(), transport, testNode()); err == nil {
			t.Errorf("accepted untrusted mktemp output %q", output)
		}
		if len(runner.calls) != 1 {
			t.Errorf("unexpected cleanup/action for unvalidated path %q: %d calls", output, len(runner.calls))
		}
	}
}

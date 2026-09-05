package executionnode

import (
	"context"
	"strings"
	"testing"
)

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

func TestServiceWorkspaceHasSchemaSafeFallbackIdentifier(t *testing.T) {
	workspace := serviceWorkspace("node1", "kafka")
	if !strings.HasPrefix(workspace, "/var/tmp/platform-installer/service/run-") {
		t.Fatalf("workspace=%s", workspace)
	}
	if workspace != serviceWorkspace("node1", "kafka") || workspace == serviceWorkspace("node2", "kafka") {
		t.Fatalf("workspace is not deterministic and target-scoped: %s", workspace)
	}
}

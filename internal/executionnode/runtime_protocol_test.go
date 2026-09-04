package executionnode

import (
	"context"
	"strings"
	"testing"
)

type protocolRunner struct{ calls []recordedCommand }

func (r *protocolRunner) Run(_ context.Context, name string, args []string, input []byte) ([]byte, error) {
	r.calls = append(r.calls, recordedCommand{name: name, args: append([]string(nil), args...), input: string(input)})
	return []byte(`{"run":{"state":"RUNNING"}}`), nil
}

func TestRuntimeProtocolIsTypedAndNeverCarriesClientCommandMaterial(t *testing.T) {
	runner := &protocolRunner{}
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	_, err := transport.StartExecution(context.Background(), testNode(), ExecutionStartRequest{RunID: "run-1", ProjectIdentity: "project-1", PlanFingerprint: "sha256:" + strings.Repeat("a", 64), RuntimeRelease: map[string]any{"bundleDigest": "sha256:" + strings.Repeat("b", 64)}})
	if err != nil {
		t.Fatal(err)
	}
	call := runner.calls[len(runner.calls)-1]
	joined := strings.Join(call.args, " ") + " " + string(call.input)
	for _, forbidden := range []string{"RunCommand", "RunShell", "RunPlaybook", "ansible-playbook", "playbook"} {
		if strings.Contains(joined, forbidden) {
			t.Fatalf("forbidden protocol material: %s", forbidden)
		}
	}
	if !strings.Contains(string(call.input), "StartExecution") {
		t.Fatalf("semantic request missing: %s", call.input)
	}
}

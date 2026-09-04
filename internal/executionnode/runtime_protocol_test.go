package executionnode

import (
	"context"
	"encoding/json"
	"strings"
	"testing"
)

type protocolRunner struct{ calls []recordedCommand }

func (r *protocolRunner) Run(_ context.Context, name string, args []string, input []byte) ([]byte, error) {
	r.calls = append(r.calls, recordedCommand{name: name, args: append([]string(nil), args...), input: string(input)})
	if strings.Contains(strings.Join(args, " "), "readlink") {
		return []byte("/var/lib/platform-installer/runtime/releases/" + strings.Repeat("a", 64) + "\n"), nil
	}
	if strings.Contains(strings.Join(args, " "), " cat ") {
		return []byte("BUNDLE_DIGEST=sha256:" + strings.Repeat("b", 64) + "\n"), nil
	}
	return []byte(`{"run":{"state":"RUNNING"}}`), nil
}

func TestDecodeBlockedDeploymentPlanPreservesSafeFindings(t *testing.T) {
	var value map[string]any
	if err := json.Unmarshal([]byte(`{
		"id":"plan-1","status":"BLOCKED","projectIdentity":"project-1",
		"projectRevision":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
		"fingerprints":{"plan":"sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},
		"runtimeRelease":{"bundleDigest":"sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"},
		"artifactRequirements":[],"acknowledgements":[],
		"findings":[{"code":"PROJECT_VALIDATION_BLOCKED","safeMessage":"Authoritative project validation is blocked"}]
	}`), &value); err != nil {
		t.Fatal(err)
	}
	plan, err := decodeDeploymentPlan(value)
	if err != nil {
		t.Fatal(err)
	}
	if plan.Status != "BLOCKED" || len(plan.Findings) != 1 || plan.Findings[0].Code != "PROJECT_VALIDATION_BLOCKED" {
		t.Fatalf("plan=%#v", plan)
	}
}

func TestRuntimeSecretFilesAcceptOnlyRuntimeRefsAndCleanAbsolutePaths(t *testing.T) {
	if !validRemoteSecretFiles(map[string]string{"runtime:pki-store-password": "/var/lib/platform-installer/secrets/pki-password"}) {
		t.Fatal("valid runtime secret file mapping was rejected")
	}
	for _, invalid := range []map[string]string{
		{"pki-store-password": "/var/lib/platform-installer/secrets/pki-password"},
		{"runtime:pki-store-password": "relative/password"},
		{"runtime:pki-store-password": "/var/lib/../tmp/password"},
	} {
		if validRemoteSecretFiles(invalid) {
			t.Fatalf("invalid runtime secret file mapping was accepted: %#v", invalid)
		}
	}
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

package executionnode

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

type protocolRunner struct {
	calls  []recordedCommand
	limits []int
}

func (r *protocolRunner) Run(_ context.Context, name string, args []string, input []byte) ([]byte, error) {
	r.calls = append(r.calls, recordedCommand{name: name, args: append([]string(nil), args...), input: string(input)})
	if strings.Contains(strings.Join(args, " "), "readlink") {
		return []byte("/var/lib/platform-installer/runtime/releases/" + strings.Repeat("a", 64) + "\n"), nil
	}
	if strings.Contains(strings.Join(args, " "), " cat ") {
		return []byte("BUNDLE_DIGEST=sha256:" + strings.Repeat("b", 64) + "\n"), nil
	}
	if strings.Contains(string(input), `"operation":"GetEvents"`) {
		return []byte(`{"events":[],"nextSequence":7,"hasMore":false}`), nil
	}
	return []byte(`{"run":{"state":"RUNNING"}}`), nil
}

func (r *protocolRunner) RunBounded(ctx context.Context, name string, args []string, input []byte, limit int) ([]byte, error) {
	r.limits = append(r.limits, limit)
	return r.Run(ctx, name, args, input)
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

func TestBuildProjectSnapshotUsesFixedSemanticRequestAndBoundedResponse(t *testing.T) {
	root := t.TempDir()
	if err := os.Mkdir(filepath.Join(root, "inventory"), 0o700); err != nil {
		t.Fatal(err)
	}
	runner := &snapshotProtocolRunner{}
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	snapshot, err := transport.BuildProjectSnapshot(context.Background(), testNode(), root, map[string]any{"bundleDigest": "sha256:" + strings.Repeat("b", 64)})
	if err != nil || snapshot.ProjectRevision == "" {
		t.Fatalf("snapshot=%+v err=%v", snapshot, err)
	}
	request := runner.protocolRequest
	if !strings.Contains(request, `"operation":"BuildProjectSnapshot"`) || strings.Contains(request, "playbook") || strings.Contains(request, "installerOwnedPaths") {
		t.Fatalf("unsafe snapshot request: %s", request)
	}
	if got := runner.limits[len(runner.limits)-1]; got != maxProjectSnapshotResponseBytes {
		t.Fatalf("response limit=%d", got)
	}
}

type snapshotProtocolRunner struct {
	protocolRunner
	protocolRequest string
}

func (r *snapshotProtocolRunner) Run(ctx context.Context, name string, args []string, input []byte) ([]byte, error) {
	if strings.Contains(string(input), `"operation":"BuildProjectSnapshot"`) {
		r.protocolRequest = string(input)
		return []byte(`{"projectSnapshot":{"projectRevision":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","status":"PASS"}}`), nil
	}
	return r.protocolRunner.Run(ctx, name, args, input)
}

func (r *snapshotProtocolRunner) RunBounded(ctx context.Context, name string, args []string, input []byte, limit int) ([]byte, error) {
	r.limits = append(r.limits, limit)
	return r.Run(ctx, name, args, input)
}

func TestGetEventsSendsBoundedPaginationRequest(t *testing.T) {
	runner := &protocolRunner{}
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	page, err := transport.GetEvents(context.Background(), testNode(), "installer-300", 7, 256)
	if err != nil {
		t.Fatal(err)
	}
	if page.NextSequence != 7 || page.HasMore || len(page.Events) != 0 {
		t.Fatalf("page=%+v", page)
	}
	wantLimits := []int{maxExecutionReleaseProbeBytes, maxExecutionStateProbeBytes, maxExecutionEventPageResponseBytes}
	if !reflect.DeepEqual(runner.limits, wantLimits) {
		t.Fatalf("bounded limits=%v want=%v", runner.limits, wantLimits)
	}
	call := runner.calls[len(runner.calls)-1]
	if !strings.Contains(call.input, `"operation":"GetEvents"`) || !strings.Contains(call.input, `"afterSequence":7`) || !strings.Contains(call.input, `"limit":256`) {
		t.Fatalf("pagination request missing: %s", call.input)
	}
}

func TestDecodeEventPagePreservesTypedTaskFieldsAndLegacyPagination(t *testing.T) {
	var response map[string]any
	payload := `{"events":[{"apiVersion":"platform.installer/event/v1alpha1","kind":"ExecutionEvent","runId":"installer-300","sequence":1,"timestamp":"2026-09-04T12:00:00Z","eventType":"TASK_COMPLETED","status":"CHANGED","phaseId":"apply","actionId":"apply:kafka-main","host":"node1","serviceDeployment":"kafka-main","task":{"uuid":"task-1","role":"platform.kafka","name":"Configure Kafka"},"elapsedMilliseconds":12,"safeMessage":"Ansible task completed","redaction":{"applied":true,"fields":[]},"x-future":"ignored"}]}`
	if err := json.Unmarshal([]byte(payload), &response); err != nil {
		t.Fatal(err)
	}
	page, err := decodeEventPage(response, "installer-300", 0, 256)
	if err != nil {
		t.Fatal(err)
	}
	event := page.Events[0]
	if page.NextSequence != 1 || page.HasMore || event.Task == nil || event.Task.UUID != "task-1" || event.Host != "node1" || event.ElapsedMillis == nil || *event.ElapsedMillis != 12 {
		t.Fatalf("page=%+v event=%+v", page, event)
	}
}

func TestDecodeEventPageRejectsWrongRunOversizeAndControlCharacters(t *testing.T) {
	event := validEvent("installer-301", 1)
	encoded, _ := json.Marshal(event)
	var value map[string]any
	_ = json.Unmarshal(encoded, &value)
	for name, mutate := range map[string]func(map[string]any){
		"wrong-run": func(v map[string]any) { v["runId"] = "installer-foreign" },
		"gap":       func(v map[string]any) { v["sequence"] = float64(2) },
		"oversize":  func(v map[string]any) { v["safeMessage"] = strings.Repeat("x", 8193) },
		"control":   func(v map[string]any) { v["safeMessage"] = "unsafe\x1b[31m" },
		"fingerprint": func(v map[string]any) {
			v["planFingerprint"] = "sha256:not-a-digest"
		},
		"unknown-oversize": func(v map[string]any) {
			v["x-future"] = strings.Repeat("x", maxDecodedExecutionEventBytes)
		},
	} {
		t.Run(name, func(t *testing.T) {
			copyValue := map[string]any{}
			for key, item := range value {
				copyValue[key] = item
			}
			mutate(copyValue)
			response := map[string]any{"events": []any{copyValue}, "nextSequence": float64(1), "hasMore": false}
			if _, err := decodeEventPage(response, "installer-301", 0, 256); err == nil {
				t.Fatal("invalid event accepted")
			}
		})
	}
}

func TestDecodeEventPageAcceptsExplicitHistoryTruncation(t *testing.T) {
	event := validEvent("installer-302", 5)
	encoded, _ := json.Marshal(event)
	var value map[string]any
	_ = json.Unmarshal(encoded, &value)
	response := map[string]any{"events": []any{value}, "nextSequence": float64(5), "hasMore": false, "earliestSequence": float64(5), "historyTruncated": true}
	page, err := decodeEventPage(response, "installer-302", 0, 256)
	if err != nil || !page.HistoryTruncated || page.EarliestSequence != 5 {
		t.Fatalf("page=%+v err=%v", page, err)
	}
}

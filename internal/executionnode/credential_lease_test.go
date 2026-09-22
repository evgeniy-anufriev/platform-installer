package executionnode

import (
	"context"
	"strings"
	"testing"
)

type leaseRunner struct {
	protocolRunner
	response string
}

func (r *leaseRunner) Run(ctx context.Context, name string, args []string, input []byte) ([]byte, error) {
	if strings.Contains(string(input), `"operation":"GetCapabilities"`) || strings.Contains(string(input), `runtime-secret-lease/v1alpha1`) || strings.Contains(string(input), `execution-start/v1alpha2`) {
		r.calls = append(r.calls, recordedCommand{name: name, args: append([]string(nil), args...), input: string(input)})
		return []byte(r.response), nil
	}
	return r.protocolRunner.Run(ctx, name, args, input)
}
func (r *leaseRunner) RunBounded(ctx context.Context, name string, args []string, input []byte, limit int) ([]byte, error) {
	r.limits = append(r.limits, limit)
	return r.Run(ctx, name, args, input)
}

func leaseCapabilityResponse() string {
	return `{"apiVersion":"platform.installer/execution-capabilities/v1alpha2","kind":"ExecutionCapabilities","bootstrapProtocol":"v1alpha1","coreVersion":"core","catalogDigest":"sha256:` + strings.Repeat("a", 64) + `","schemaDigest":"sha256:` + strings.Repeat("b", 64) + `","runtime":{"bundleVersion":"bundle","bundleDigest":"sha256:` + strings.Repeat("c", 64) + `"},"supportedOperations":["PutRuntimeSecretLease"],"executionStart":{"protocol":"StartExecution/v1alpha2"},"targetCredentialLease":{"protocol":"PutRuntimeSecretLease/v1alpha1","payloadVersions":["TargetCredentialLeasePayload/v1alpha1"],"maxPayloadBytes":1114112,"requiredStartProtocol":"StartExecution/v1alpha2"},"projectSnapshotRequestVersions":[]}`
}

func TestCredentialStartCapabilityRequiresClosedV2LeaseEnvelope(t *testing.T) {
	runner := &leaseRunner{response: leaseCapabilityResponse()}
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	capability, err := transport.CredentialStartCapability(context.Background(), testNode())
	if err != nil || capability.MaxPayloadBytes != 1114112 {
		t.Fatalf("capability=%+v err=%v", capability, err)
	}
	runner.response = strings.Replace(leaseCapabilityResponse(), `,"projectSnapshotRequestVersions":[]`, `,"unexpected":true,"projectSnapshotRequestVersions":[]`, 1)
	if _, err := transport.CredentialStartCapability(context.Background(), testNode()); err == nil || err.Error() != "TARGET_CREDENTIAL_LEASE_UNSUPPORTED" {
		t.Fatalf("malformed capability err=%v", err)
	}
}

func TestPutRuntimeSecretLeaseUsesStdinOnlyAndNeverReturnsPayload(t *testing.T) {
	id := strings.Repeat("1", 32)
	runner := &leaseRunner{response: `{"requestId":"` + id + `","startAttemptId":"` + strings.Repeat("2", 32) + `","status":"STORED","leaseId":"` + strings.Repeat("3", 32) + `","stagedExpiresAt":"2026-09-22T12:00:00Z"}`}
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	request := CredentialLeaseRequest{RequestID: id, StartAttemptID: strings.Repeat("2", 32), ProjectIdentity: "project-1", ProjectRevision: "sha256:" + strings.Repeat("a", 64), PlanFingerprint: "sha256:" + strings.Repeat("b", 64), ExecutionManifestDigest: "sha256:" + strings.Repeat("c", 64), RuntimeRelease: map[string]any{"bundleDigest": "sha256:" + strings.Repeat("d", 64), "coreVersion": "core", "catalogDigest": "sha256:" + strings.Repeat("e", 64), "planningProtocol": "v1alpha1"}}
	response, err := transport.PutRuntimeSecretLease(context.Background(), testNode(), request, TargetCredentialLeasePayload{Username: "operator", Password: "secret-value"}, 1114112)
	if err != nil || response.LeaseID == "" {
		t.Fatalf("response=%+v err=%v", response, err)
	}
	call := runner.calls[len(runner.calls)-1]
	if strings.Contains(strings.Join(call.args, " "), "secret-value") || !strings.Contains(call.input, "secret-value") || strings.Contains(response.LeaseID, "secret-value") {
		t.Fatalf("secret transport leak args=%v response=%+v", call.args, response)
	}
}

func TestStartExecutionV2RejectsCallerRunIDAndDecodesOnlyClosedResponse(t *testing.T) {
	runner := &leaseRunner{response: `{"apiVersion":"platform.installer/execution-start/v1alpha2","kind":"StartExecutionResponse","status":"STARTED","startAttemptId":"` + strings.Repeat("2", 32) + `","runId":"installer-123"}`}
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	request := ExecutionStartV2Request{StartAttemptID: strings.Repeat("2", 32), ProjectIdentity: "project-1", ProjectRevision: "sha256:" + strings.Repeat("a", 64), PlanFingerprint: "sha256:" + strings.Repeat("b", 64), ExecutionManifestDigest: "sha256:" + strings.Repeat("c", 64), LeaseID: strings.Repeat("3", 32), RuntimeRelease: map[string]any{"bundleDigest": "sha256:" + strings.Repeat("d", 64), "coreVersion": "core", "catalogDigest": "sha256:" + strings.Repeat("e", 64), "planningProtocol": "v1alpha1"}}
	response, err := transport.StartExecutionV2(context.Background(), testNode(), request)
	if err != nil || response.RunID != "installer-123" {
		t.Fatalf("response=%+v err=%v", response, err)
	}
	if strings.Contains(runner.calls[len(runner.calls)-1].input, `"runId"`) {
		t.Fatal("caller supplied run id")
	}
}

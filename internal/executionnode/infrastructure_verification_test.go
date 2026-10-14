package executionnode

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func testInfrastructureSummary(t *testing.T) map[string]any {
	t.Helper()
	var value map[string]any
	if err := json.Unmarshal([]byte(`{"status":"PASS","code":null,"infrastructureFingerprint":"sha256:`+strings.Repeat("a", 64)+`","evidenceRevision":"sha256:`+strings.Repeat("b", 64)+`","deployments":[{"deploymentId":"docker-main","sourceRunId":"installer-abc123","coverageDigest":"sha256:`+strings.Repeat("c", 64)+`","verifiedAt":"2026-10-14T10:00:00Z"}]}`), &value); err != nil {
		t.Fatal(err)
	}
	return value
}

func b0Capability() map[string]any {
	c := map[string]any{"apiVersion": "platform.installer/execution-capabilities/v1alpha8", "kind": "ExecutionCapabilities", "supportedOperations": []any{"BuildDeploymentPlan"}, "deploymentPlanRequestVersions": []any{"platform.installer/execution-runtime/v1alpha2", "platform.installer/execution-runtime/v1alpha3", "platform.installer/execution-runtime/v1alpha4"}, "infrastructureVerification": map[string]any{"protocol": "InfrastructureVerification/v1alpha1", "executionModes": []any{"FULL_PROJECT", "APPLICATION_LIBRARIES_ONLY", "INFRASTRUCTURE_VERIFY_ONLY"}, "requiredPlanRequestVersion": "platform.installer/execution-runtime/v1alpha4", "manifestContract": "platform.installer/execution-manifest/v1alpha3", "planContract": "platform.installer/plan/v1alpha5"}}
	for _, key := range []string{"bootstrapProtocol", "coreVersion", "catalogDigest", "schemaDigest", "runtime", "executionStart", "targetCredentialLease", "runtimeSecretDescriptors", "serviceConfigurationPreview", "projectSnapshotRequestVersions", "applicationExecution"} {
		c[key] = map[string]any{}
	}
	return c
}

func TestB0CapabilityVersionAndScope(t *testing.T) {
	if !b0PlanCapabilitySupported(b0Capability()) || !orderedDeploymentPlanRequestSupported(b0Capability()) {
		t.Fatal("B0 capability rejected")
	}
	for _, mutate := range []func(map[string]any){
		func(v map[string]any) { v["apiVersion"] = "platform.installer/execution-capabilities/v1alpha7" },
		func(v map[string]any) {
			v["deploymentPlanRequestVersions"] = []any{"platform.installer/execution-runtime/v1alpha2"}
		},
		func(v map[string]any) {
			v["infrastructureVerification"].(map[string]any)["executionModes"] = []any{"FULL_PROJECT"}
		},
		func(v map[string]any) {
			v["infrastructureVerification"].(map[string]any)["planContract"] = "platform.installer/plan/v99"
		},
	} {
		v := b0Capability()
		mutate(v)
		if b0PlanCapabilitySupported(v) {
			t.Fatal("incompatible capability accepted")
		}
	}
}

type b1PlanRunner struct {
	protocolRunner
	request   map[string]any
	summary   map[string]any
	wrongMode bool
}

func (r *b1PlanRunner) RunBounded(ctx context.Context, name string, args []string, input []byte, limit int) ([]byte, error) {
	var request map[string]any
	_ = json.Unmarshal(input, &request)
	if request["operation"] == "GetCapabilities" {
		return json.Marshal(b0Capability())
	}
	if request["operation"] == "BuildDeploymentPlan" {
		r.request = request
		mode := request["executionMode"]
		if r.wrongMode {
			mode = "FULL_PROJECT"
		}
		return json.Marshal(map[string]any{"deploymentPlan": map[string]any{"apiVersion": "platform.installer/plan/v1alpha5", "executionMode": mode, "infrastructureVerification": r.summary, "id": "plan-one", "status": "BLOCKED", "projectIdentity": "project-one", "projectRevision": "sha256:" + strings.Repeat("a", 64), "fingerprints": map[string]any{"plan": "sha256:" + strings.Repeat("b", 64)}, "runtimeRelease": request["runtimeRelease"], "acknowledgements": []any{}, "phases": []any{}, "requiredCredentials": []any{}, "findings": []any{}}})
	}
	return r.protocolRunner.RunBounded(ctx, name, args, input, limit)
}

func TestModePlanUsesExistingFixedProtocolAndRejectsWrongMode(t *testing.T) {
	for _, wrong := range []bool{false, true} {
		root := t.TempDir()
		if err := os.Mkdir(filepath.Join(root, "inventory"), 0o700); err != nil {
			t.Fatal(err)
		}
		runner := &b1PlanRunner{summary: testInfrastructureSummary(t), wrongMode: wrong}
		transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
		p, err := transport.BuildDeploymentPlanForMode(context.Background(), testNode(), root, map[string]any{"bundleDigest": "sha256:" + strings.Repeat("b", 64)}, []string{}, ApplicationLibrariesOnly, map[string]string{"vault-main": "RUNTIME_INPUT"})
		if wrong {
			if err == nil {
				t.Fatal("different mode accepted")
			}
			continue
		}
		if err != nil {
			t.Fatal(err)
		}
		if p.ExecutionMode != ApplicationLibrariesOnly || runner.request["apiVersion"] != "platform.installer/execution-runtime/v1alpha4" || runner.request["applicationVaultSources"].(map[string]any)["vault-main"] != "RUNTIME_INPUT" {
			t.Fatal("mode/source request changed")
		}
	}
}

func TestImageProjectionIsNotAnRPMRequirement(t *testing.T) {
	var v map[string]any
	_ = json.Unmarshal([]byte(`{"id":"image-gateway","name":"probe","artifactType":"container-image","imageId":"sha256:`+strings.Repeat("a", 64)+`","localReference":"platform-application:sha256-`+strings.Repeat("a", 64)+`","applicationLibrary":"sdku","instanceId":"gateway-sdku","hosts":["node1"],"sourcePolicy":"REPOSITORY_THEN_OFFLINE","platform":{"os":"linux","architecture":"amd64"}}`), &v)
	image, err := decodeApplicationImage(v)
	if err != nil || image.InstanceID != "gateway-sdku" {
		t.Fatal(err)
	}
	v["localReference"] = "platform-application:sha256-" + strings.Repeat("b", 64)
	if _, err := decodeApplicationImage(v); err == nil {
		t.Fatal("mismatched image identity accepted")
	}
	v["localReference"] = image.LocalReference
	v["token"] = "must-not-accept"
	if _, err := decodeApplicationImage(v); err == nil {
		t.Fatal("unknown image field accepted")
	}
}

func TestInfrastructureSummaryClosedAndBounded(t *testing.T) {
	if _, err := decodeInfrastructureVerification(testInfrastructureSummary(t)); err != nil {
		t.Fatal(err)
	}
	for _, mutate := range []func(map[string]any){
		func(v map[string]any) { delete(v, "code") },
		func(v map[string]any) { v["token"] = "must-not-accept" },
		func(v map[string]any) { v["status"] = "SUCCESS" },
		func(v map[string]any) { v["evidenceRevision"] = "untrusted" },
		func(v map[string]any) { v["deployments"].([]any)[0].(map[string]any)["verifiedAt"] = "yesterday" },
		func(v map[string]any) { v["deployments"].([]any)[0].(map[string]any)["deploymentId"] = "../docker" },
	} {
		v := testInfrastructureSummary(t)
		mutate(v)
		if _, err := decodeInfrastructureVerification(v); err == nil {
			t.Fatal("malformed evidence accepted")
		}
	}
}

func TestExecutionModeUnsupportedDoesNotStageOrFallback(t *testing.T) {
	runner := &protocolRunner{}
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	_, err := transport.BuildDeploymentPlanForMode(context.Background(), testNode(), t.TempDir(), map[string]any{"bundleDigest": "sha256:" + strings.Repeat("b", 64)}, []string{}, ApplicationLibrariesOnly, nil)
	if err == nil || err.Error() != "EXECUTION_MODE_RUNTIME_UNSUPPORTED" {
		t.Fatalf("err=%v", err)
	}
	for _, call := range runner.calls {
		if strings.Contains(call.input, `"operation":"BuildDeploymentPlan"`) || strings.Contains(call.input, "StageProject") || strings.Contains(call.name, "scp") {
			t.Fatal("unsupported runtime caused staging/plan")
		}
	}
}

func TestInfrastructurePlanModesPreserveAdmission(t *testing.T) {
	for _, mode := range []ExecutionMode{FullProject, ApplicationLibrariesOnly, InfrastructureVerifyOnly} {
		v := map[string]any{"apiVersion": "platform.installer/plan/v1alpha5", "executionMode": string(mode), "infrastructureVerification": testInfrastructureSummary(t), "id": "plan-one", "status": "BLOCKED", "projectIdentity": "project-one", "projectRevision": "sha256:" + strings.Repeat("a", 64), "fingerprints": map[string]any{"plan": "sha256:" + strings.Repeat("b", 64)}, "runtimeRelease": map[string]any{"bundleDigest": "sha256:" + strings.Repeat("c", 64)}, "acknowledgements": []any{}, "phases": []any{}, "requiredCredentials": []any{}, "findings": []any{}}
		p, err := decodeDeploymentPlan(v)
		if err != nil || p.ExecutionMode != mode || p.InfrastructureVerification.Status != "PASS" {
			t.Fatalf("mode=%s err=%v", mode, err)
		}
	}
}

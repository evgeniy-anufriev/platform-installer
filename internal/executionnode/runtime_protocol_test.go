package executionnode

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

type failedProtocolRunner struct{ protocolRunner }

func (r *failedProtocolRunner) Run(ctx context.Context, name string, args []string, input []byte) ([]byte, error) {
	if len(input) > 0 {
		return []byte(`{"status":"FAILED","error":"PROJECT_SNAPSHOT_INPUT_INVALID","diagnostic":{"findings":[{"code":"PROJECT_SNAPSHOT_INPUT_INVALID","safeMessage":"Project snapshot inputs could not be loaded"}]}}`), errors.New("exit status 2")
	}
	return r.protocolRunner.Run(ctx, name, args, input)
}

func (r *failedProtocolRunner) RunBounded(ctx context.Context, name string, args []string, input []byte, limit int) ([]byte, error) {
	r.limits = append(r.limits, limit)
	return r.Run(ctx, name, args, input)
}

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
		"artifactRequirements":[],"requiredCredentials":[],"phases":[],"acknowledgements":[],
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
	if err := bindExecutionManifest(&plan, map[string]any{"executionManifestDigest": nil}, "installer-plan"); err != nil {
		t.Fatalf("blocked plan must not require an execution manifest: %v", err)
	}
	if plan.executionManifestDigest != "" || plan.stagingID != "" {
		t.Fatalf("blocked plan acquired execution authority: %#v", plan)
	}
}

func TestDecodeDeploymentPlanRetainsBoundedPhasesActionsAndAcknowledgements(t *testing.T) {
	var value map[string]any
	if err := json.Unmarshal([]byte(`{
		"id":"plan-1","status":"EXECUTABLE","projectIdentity":"project-1",
		"projectRevision":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
		"fingerprints":{"plan":"sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},
		"runtimeRelease":{"bundleDigest":"sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc","coreVersion":"core","catalogDigest":"sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd","planningProtocol":"protocol"},
		"artifactRequirements":[],"requiredCredentials":[{"requirementRef":"pki-store-password","purpose":"PKI_STORE_PASSWORD","hosts":["node1"]}],"acknowledgements":[{"code":"ACK_RISK","summary":"Review"}],
		"phases":[{"id":"apply","order":0,"actions":[{"id":"apply:kafka","type":"SERVICE_APPLY","serviceDeployment":"kafka-main","targets":["node1"],"dependsOn":[],"mutating":true,"reboot":"NONE","summary":"Apply Kafka"}]}],"findings":[]
	}`), &value); err != nil {
		t.Fatal(err)
	}
	plan, err := decodeDeploymentPlan(value)
	if err != nil || len(plan.Phases) != 1 || len(plan.Phases[0].Actions) != 1 || plan.Phases[0].Actions[0].ServiceDeployment != "kafka-main" || len(plan.AcknowledgementDetails) != 1 || !planRequiresPKIStorePassword(plan) {
		t.Fatalf("plan=%#v err=%v", plan, err)
	}
	value["phases"].([]any)[0].(map[string]any)["actions"].([]any)[0].(map[string]any)["reboot"] = "MAYBE"
	if _, err := decodeDeploymentPlan(value); err == nil || err.Error() != "DEPLOYMENT_PLAN_RESPONSE_INVALID" {
		t.Fatalf("invalid reboot err=%v", err)
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

func TestRuntimeTokenAcceptsLegacyDecimalAndNodeGeneratedHex(t *testing.T) {
	for _, value := range []string{
		"installer-1234567890",
		"installer-f52a987bd1c9399624efdc5f7a2818d1",
	} {
		if !validRuntimeToken(value) {
			t.Fatalf("valid runtime token rejected: %q", value)
		}
	}
	for _, value := range []string{"installer-F52A", "installer-deadbeef!", "installer-"} {
		if validRuntimeToken(value) {
			t.Fatalf("invalid runtime token accepted: %q", value)
		}
	}
}

func TestPlanStagingAcceptsAnOmittedOptionalRequestID(t *testing.T) {
	root := t.TempDir()
	if err := os.Mkdir(filepath.Join(root, "inventory"), 0o700); err != nil {
		t.Fatal(err)
	}
	runner := &protocolRunner{}
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	if err := transport.stagePlanProject(context.Background(), testNode(), root, "installer-123", "plan"); err != nil {
		t.Fatal(err)
	}
	for _, call := range runner.calls {
		if call.name == "ssh" && strings.Contains(call.input, "purpose=$5") {
			if !strings.Contains(call.input, "request_id=${6-}") {
				t.Fatalf("plan staging did not safely default omitted requestId: %q", call.input)
			}
			return
		}
	}
	t.Fatal("plan staging command was not issued")
}

func TestPlanStagingClaimsPrivateDirectoryUnderStickyVarTmp(t *testing.T) {
	root := t.TempDir()
	if err := os.Mkdir(filepath.Join(root, "inventory"), 0700); err != nil {
		t.Fatal(err)
	}
	runner := &protocolRunner{}
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	if err := transport.stagePlanProject(context.Background(), testNode(), root, "installer-123", "plan"); err != nil {
		t.Fatal(err)
	}
	claim := runner.calls[0]
	if !strings.Contains(claim.input, "stat -c %a /var/tmp") || !strings.Contains(claim.input, `mkdir -- "$1"`) || strings.Contains(claim.input, "sudo") || strings.Contains(claim.input, "install -d") || !strings.HasSuffix(claim.args[len(claim.args)-1], "platform-installer-project-installer-123") {
		t.Fatal("private claim guards missing")
	}
}

func TestCandidateStagingCreatesOwnedPrivateBase(t *testing.T) {
	root := t.TempDir()
	if err := os.Mkdir(filepath.Join(root, "inventory"), 0700); err != nil {
		t.Fatal(err)
	}
	runner := &protocolRunner{}
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	archive, err := createProjectArchive(root)
	if err != nil {
		t.Fatal(err)
	}
	defer os.Remove(archive)
	if _, err := transport.stageProjectArchive(context.Background(), testNode(), archive, "installer-123", "candidate", strings.Repeat("a", 32)); err != nil {
		t.Fatal(err)
	}
	claim := runner.calls[0].input
	for _, guard := range []string{"stat -c %a /var/tmp", `mkdir -m 0700 -- "$base"`, `stat -c %u "$base"`, `[ ! -L "$base" ]`} {
		if !strings.Contains(claim, guard) {
			t.Fatalf("candidate staging guard %q missing", guard)
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

func TestRuntimeProtocolPreservesStructuredFailureFromNonZeroProcess(t *testing.T) {
	runner := &failedProtocolRunner{}
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	_, err := transport.runtimeProtocol(context.Background(), testNode(), map[string]any{"apiVersion": "platform.installer/execution-runtime/v1alpha1", "operation": "BuildProjectSnapshot"})
	var executionErr *ExecutionError
	if !errors.As(err, &executionErr) || executionErr.Code != "PROJECT_SNAPSHOT_INPUT_INVALID" || len(executionErr.Findings) != 1 {
		t.Fatalf("structured failure was lost: %#v", err)
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

func TestBuildCandidateProjectSnapshotNegotiatesAndSendsClosedRequest(t *testing.T) {
	root := t.TempDir()
	if err := os.Mkdir(filepath.Join(root, "inventory"), 0o700); err != nil {
		t.Fatal(err)
	}
	for name, content := range map[string]string{"inventory/hosts.yml": "all: {hosts: {node1: {ansible_host: 192.0.2.10}}}\n", "ansible.cfg": managedCandidateAnsibleConfig, "project.yml": "metadata: {id: project-1}\n"} {
		if err := os.WriteFile(filepath.Join(root, filepath.FromSlash(name)), []byte(content), 0o600); err != nil {
			t.Fatal(err)
		}
	}
	revision := "sha256:" + strings.Repeat("a", 64)
	runner := &candidateSnapshotRunner{revision: revision}
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	snapshot, err := transport.BuildCandidateProjectSnapshot(context.Background(), testNode(), root, map[string]any{"bundleDigest": "sha256:" + strings.Repeat("b", 64)}, CandidateProjectSnapshotRequest{
		ProjectIdentity: "project-1", CandidateProjectRevision: revision,
		ArtifactLockDigest: "sha256:" + strings.Repeat("c", 64), CatalogLockDigest: "sha256:" + strings.Repeat("d", 64),
		InstallerOwnedLogicalPaths: []string{"inventory/group_vars/all/platform-installer.yml"},
	})
	if err != nil || snapshot.ProjectRevision != revision {
		t.Fatalf("snapshot=%+v err=%v", snapshot, err)
	}
	request := runner.protocolRequest
	for _, required := range []string{`"snapshotRequest"`, `"apiVersion":"platform.installer/project-snapshot-request/v1alpha1"`, `"editContract":"v1alpha2"`, `"installerOwnedLogicalPaths"`} {
		if !strings.Contains(request, required) {
			t.Fatalf("candidate request missing %s: %s", required, request)
		}
	}
	for _, forbidden := range []string{`"command"`, `"argv"`, `"playbook"`} {
		if strings.Contains(request, forbidden) {
			t.Fatalf("unsafe candidate request: %s", request)
		}
	}
	if !runnerCalledCleanup(runner.calls) {
		t.Fatalf("candidate staging was not cleaned after success: %#v", runner.calls)
	}
}

func TestBuildCandidateProjectSnapshotRejectsUnsupportedCapabilityBeforeStaging(t *testing.T) {
	for name, capabilities := range map[string]string{
		"missing request version": `{"supportedOperations":["BuildProjectSnapshot"]}`,
		"missing operation":       `{"supportedOperations":["GetCapabilities"],"projectSnapshotRequestVersions":["platform.installer/project-snapshot-request/v1alpha1"]}`,
	} {
		t.Run(name, func(t *testing.T) {
			root := t.TempDir()
			runner := &unsupportedCandidateRunner{capabilities: capabilities}
			transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
			_, err := transport.BuildCandidateProjectSnapshot(context.Background(), testNode(), root, map[string]any{"bundleDigest": "sha256:" + strings.Repeat("b", 64)}, CandidateProjectSnapshotRequest{
				ProjectIdentity: "project-1", CandidateProjectRevision: "sha256:" + strings.Repeat("a", 64),
				ArtifactLockDigest: "sha256:" + strings.Repeat("b", 64), CatalogLockDigest: "sha256:" + strings.Repeat("c", 64),
			})
			if err == nil || err.Error() != "PROJECT_SNAPSHOT_CANDIDATE_UNSUPPORTED" {
				t.Fatalf("unexpected error: %v", err)
			}
			for _, call := range runner.calls {
				if call.name == "scp" {
					t.Fatal("unsupported node received candidate staging")
				}
			}
		})
	}
}

func TestCandidateCommitPreflightRequiresOperationAndRequestVersion(t *testing.T) {
	for name, capabilities := range map[string]string{
		"missing request version": `{"supportedOperations":["BuildProjectSnapshot"]}`,
		"missing operation":       `{"supportedOperations":["GetCapabilities"],"projectSnapshotRequestVersions":["platform.installer/project-snapshot-request/v1alpha1"]}`,
	} {
		t.Run(name, func(t *testing.T) {
			runner := &unsupportedCandidateRunner{capabilities: capabilities}
			transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
			err := transport.CheckCandidateProjectSnapshotCapability(context.Background(), testNode(), map[string]any{"bundleDigest": "sha256:" + strings.Repeat("b", 64)})
			if err == nil || err.Error() != "PROJECT_SNAPSHOT_CANDIDATE_UNSUPPORTED" {
				t.Fatalf("unexpected error: %v", err)
			}
		})
	}
}

func TestOrderedDeploymentPlanCapabilityRequiresExactVersionAndRequest(t *testing.T) {
	base := map[string]any{
		"apiVersion":        "platform.installer/execution-capabilities/v1alpha6",
		"kind":              "ExecutionCapabilities",
		"bootstrapProtocol": "v1alpha1", "coreVersion": "core",
		"catalogDigest":                  "sha256:" + strings.Repeat("a", 64),
		"schemaDigest":                   "sha256:" + strings.Repeat("b", 64),
		"runtime":                        map[string]any{"bundleVersion": "bundle", "bundleDigest": "sha256:" + strings.Repeat("c", 64)},
		"supportedOperations":            []any{"GetCapabilities", "BuildDeploymentPlan"},
		"executionStart":                 map[string]any{"protocol": "StartExecution/v1alpha2"},
		"targetCredentialLease":          map[string]any{},
		"runtimeSecretDescriptors":       map[string]any{},
		"serviceConfigurationPreview":    map[string]any{},
		"deploymentPlanRequestVersions":  []any{"platform.installer/execution-runtime/v1alpha2"},
		"projectSnapshotRequestVersions": []any{},
	}
	if !orderedDeploymentPlanRequestSupported(base) {
		t.Fatal("compatible ordered-plan capability rejected")
	}
	for name, mutate := range map[string]func(map[string]any){
		"old capability version":  func(value map[string]any) { value["apiVersion"] = "platform.installer/execution-capabilities/v1alpha5" },
		"missing operation":       func(value map[string]any) { value["supportedOperations"] = []any{"GetCapabilities"} },
		"missing request version": func(value map[string]any) { value["deploymentPlanRequestVersions"] = []any{} },
		"unknown field":           func(value map[string]any) { value["fallback"] = true },
	} {
		t.Run(name, func(t *testing.T) {
			value := make(map[string]any, len(base))
			for key, item := range base {
				value[key] = item
			}
			mutate(value)
			if orderedDeploymentPlanRequestSupported(value) {
				t.Fatal("invalid capability accepted")
			}
		})
	}
}

func TestCandidateCommitPreflightRejectsChangedRuntimeRelease(t *testing.T) {
	runner := &protocolRunner{}
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	err := transport.CheckCandidateProjectSnapshotCapability(context.Background(), testNode(), map[string]any{"bundleDigest": "sha256:" + strings.Repeat("c", 64)})
	if err == nil || err.Error() != "EXECUTION_RUNTIME_RELEASE_CHANGED" {
		t.Fatalf("unexpected error: %v", err)
	}
}

type secretOutputRunner struct {
	protocolRunner
	response                 string
	separatedErr             error
	separatedArgs            []string
	stdoutLimit, stderrLimit int
}

func (r *secretOutputRunner) RunSeparatedBounded(_ context.Context, name string, args []string, input []byte, stdoutLimit, stderrLimit int) ([]byte, []byte, error) {
	r.separatedArgs = append([]string{name}, args...)
	r.stdoutLimit, r.stderrLimit = stdoutLimit, stderrLimit
	r.calls = append(r.calls, recordedCommand{name: name, args: append([]string(nil), args...), input: string(input)})
	return []byte(r.response), []byte("discarded-stderr-canary"), r.separatedErr
}

func TestSecretOutputRecoveryErrorUsesOnlyClosedAttestedResponse(t *testing.T) {
	for _, item := range []struct {
		response string
		allowed  bool
	}{
		{`{"protocol":"SecretOutputDelivery/v1alpha1","operation":"ListPending","errorCode":"OUTPUT_RECOVERY_REQUIRED"}`, true},
		{`{"protocol":"SecretOutputDelivery/v1alpha1","operation":"Fetch","errorCode":"OUTPUT_RECOVERY_REQUIRED"}`, false},
		{`{"protocol":"SecretOutputDelivery/v1alpha1","operation":"ListPending","errorCode":"OUTPUT_RECOVERY_REQUIRED","raw":"unsafe-canary"}`, false},
		{`{"protocol":"SecretOutputDelivery/v1alpha1","operation":"ListPending","errorCode":"unsafe-canary"}`, false},
		{`{"protocol":"SecretOutputDelivery/v1alpha1","protocol":"other","operation":"ListPending","errorCode":"OUTPUT_RECOVERY_REQUIRED"}`, false},
	} {
		runner := &secretOutputRunner{response: item.response, separatedErr: errors.New("unsafe-process-canary")}
		transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
		_, err := transport.ListPendingSecretOutputs(context.Background(), testNode(), "sha256:"+strings.Repeat("b", 64), "project-test", 32, nil)
		if err == nil || errors.Is(err, ErrSecretOutputRecoveryRequired) != item.allowed || strings.Contains(err.Error(), "canary") {
			t.Fatalf("unsafe error classification: %v", err)
		}
	}
}

func TestSecretOutputListRejectsMalformedIdentityBoundsAndDuplicates(t *testing.T) {
	digest := "sha256:" + strings.Repeat("b", 64)
	valid := SecretOutputPackage{Protocol: secretOutputProtocol, PackageID: strings.Repeat("a", 32), ProjectID: "project-test", DeploymentID: "vault-ha", SourceRunID: "installer-1234", RuntimeDigest: digest, Generation: 1, State: "READY", Entries: []string{"admin-token", "unseal-shares"}}
	for _, scenario := range []string{"valid", "run", "deployment", "generation", "duplicate", "cursor"} {
		t.Run(scenario, func(t *testing.T) {
			list := SecretOutputList{Protocol: secretOutputProtocol, Operation: "ListPending", ProjectID: "project-test", Packages: []SecretOutputPackage{valid}}
			switch scenario {
			case "run":
				list.Packages[0].SourceRunID = "../run"
			case "deployment":
				list.Packages[0].DeploymentID = strings.Repeat("a", 129)
			case "generation":
				list.Packages[0].Generation = 2147483648
			case "duplicate":
				list.Packages = append(list.Packages, valid)
			case "cursor":
				cursor := "invalid"
				list.NextCursor = &cursor
			}
			encoded, err := json.Marshal(list)
			if err != nil {
				t.Fatal(err)
			}
			runner := &secretOutputRunner{response: string(encoded)}
			transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
			_, err = transport.ListPendingSecretOutputs(context.Background(), testNode(), digest, "project-test", 32, nil)
			if (scenario == "valid" && err != nil) || (scenario != "valid" && !errors.Is(err, errSecretOutputProtocol)) {
				t.Fatalf("scenario %s: %v", scenario, err)
			}
		})
	}
}

func TestSecretOutputHandshakeUsesAttestedRuntimeAndSeparateBinaryTransport(t *testing.T) {
	runner := &secretOutputRunner{response: `{"protocol":"SecretOutputDelivery/v1alpha1","operation":"GetCapabilities","maxPayloadBytes":65536,"operations":["ListPending","Fetch","Acknowledge"]}`}
	transport := OpenSSHTransport{Identity: fixedIdentity{}, Runner: runner}
	digest := "sha256:" + strings.Repeat("b", 64)
	capabilities, err := transport.GetSecretOutputCapabilities(context.Background(), testNode(), digest, "project-test")
	if err != nil || capabilities.MaxPayloadBytes != 65536 {
		t.Fatalf("caps=%#v err=%v", capabilities, err)
	}
	if runner.stdoutLimit != maxSecretOutputResponseBytes || runner.stderrLimit != maxSecretOutputStderrBytes {
		t.Fatalf("limits=%d/%d", runner.stdoutLimit, runner.stderrLimit)
	}
	call := runner.calls[len(runner.calls)-1]
	joined := strings.Join(call.args, " ")
	if !strings.Contains(joined, "execution_secret_output_protocol.py") || !strings.Contains(joined, "sudo -n env PYTHONPATH=") || strings.Contains(joined, "execution_protocol.py") {
		t.Fatalf("unexpected remote command: %s", joined)
	}
	if !strings.Contains(call.input, `"protocol":"SecretOutputDelivery/v1alpha1"`) || !strings.Contains(call.input, `"projectId":"project-test"`) {
		t.Fatalf("unexpected request: %s", call.input)
	}

	runner.response = `{"protocol":"SecretOutputDelivery/v1alpha1","operation":"GetCapabilities","maxPayloadBytes":65535,"operations":["ListPending","Fetch","Acknowledge"]}`
	if _, err := transport.GetSecretOutputCapabilities(context.Background(), testNode(), digest, "project-test"); !errors.Is(err, errSecretOutputProtocol) {
		t.Fatalf("malformed capabilities err=%v", err)
	}
	runner.response = `{"protocol":"SecretOutputDelivery/v1alpha1","operation":"GetCapabilities","maxPayloadBytes":65536,"operations":["ListPending","Fetch","Acknowledge"]}`
	if _, err := transport.GetSecretOutputCapabilities(context.Background(), testNode(), "sha256:"+strings.Repeat("c", 64), "project-test"); !errors.Is(err, errSecretOutputProtocol) {
		t.Fatalf("runtime mismatch err=%v", err)
	}
}

type unsupportedCandidateRunner struct {
	protocolRunner
	capabilities string
}

func (r *unsupportedCandidateRunner) Run(ctx context.Context, name string, args []string, input []byte) ([]byte, error) {
	if strings.Contains(string(input), `"operation":"GetCapabilities"`) {
		r.calls = append(r.calls, recordedCommand{name: name, args: append([]string(nil), args...), input: string(input)})
		return []byte(r.capabilities), nil
	}
	return r.protocolRunner.Run(ctx, name, args, input)
}

func (r *unsupportedCandidateRunner) RunBounded(ctx context.Context, name string, args []string, input []byte, limit int) ([]byte, error) {
	r.limits = append(r.limits, limit)
	return r.Run(ctx, name, args, input)
}

func runnerCalledCleanup(calls []recordedCommand) bool {
	for _, call := range calls {
		if strings.Contains(call.input, "--cleanup-snapshot-run-id") && strings.Contains(call.input, "--cleanup-request-id") && strings.Contains(call.input, "--cleanup-archive-digest") {
			return true
		}
	}
	return false
}

func runnerCalledUploadCleanup(calls []recordedCommand) bool {
	for _, call := range calls {
		if !strings.Contains(call.input, "sudo -n rm -rf -- \"$staging\"") && strings.Contains(call.input, "rm -rf -- \"$temporary\"") {
			return true
		}
	}
	return false
}

func TestGeneratedRunIDsAreUniqueRuntimeTokens(t *testing.T) {
	seen := make(map[string]bool)
	for index := 0; index < 128; index++ {
		runID, err := newRunID()
		if err != nil {
			t.Fatal(err)
		}
		if !validRuntimeToken(runID) || seen[runID] {
			t.Fatalf("invalid or duplicate generated run ID: %q", runID)
		}
		seen[runID] = true
	}
}

type candidateSnapshotRunner struct {
	protocolRunner
	revision, protocolRequest string
}

func (r *candidateSnapshotRunner) Run(ctx context.Context, name string, args []string, input []byte) ([]byte, error) {
	if strings.Contains(string(input), `"operation":"GetCapabilities"`) {
		return []byte(`{"supportedOperations":["BuildProjectSnapshot"],"projectSnapshotRequestVersions":["platform.installer/project-snapshot-request/v1alpha1"]}`), nil
	}
	if strings.Contains(string(input), `"operation":"BuildProjectSnapshot"`) {
		r.protocolRequest = string(input)
		return []byte(`{"projectSnapshot":{"projectRevision":"` + r.revision + `","status":"PASS"}}`), nil
	}
	return r.protocolRunner.Run(ctx, name, args, input)
}
func (r *candidateSnapshotRunner) RunBounded(ctx context.Context, name string, args []string, input []byte, limit int) ([]byte, error) {
	r.limits = append(r.limits, limit)
	return r.Run(ctx, name, args, input)
}

type snapshotProtocolRunner struct {
	protocolRunner
	protocolRequest string
}

func (r *snapshotProtocolRunner) Run(ctx context.Context, name string, args []string, input []byte) ([]byte, error) {
	if strings.Contains(string(input), `"operation":"BuildProjectSnapshot"`) {
		r.protocolRequest = string(input)
		return []byte(`{"projectSnapshot":{"projectRevision":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","status":"PASS"},"runtimeEvidence":{"bundleDigest":"sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","coreVersion":"test-core","catalogDigest":"sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc","protocol":"v1alpha1"}}`), nil
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

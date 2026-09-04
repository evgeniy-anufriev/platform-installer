package executionnode

// Typed access to the fixed UI-BE-04C runtime protocol.  This is transport
// plumbing only: it stores no plan, owns no session and cannot carry a remote
// command, playbook path or argv supplied by an Installer client.

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path"
	"strings"

	"platform-installer/internal/artifactsource"
)

func (t OpenSSHTransport) StageRuntimeProjection(ctx context.Context, node Node, runID, projectIdentity, planFingerprint, requirementsFingerprint string, projections map[string]map[string]artifactsource.Result, pkiSecretFiles map[string]string) error {
	if !validRuntimeToken(runID) || projectIdentity == "" || planFingerprint == "" || requirementsFingerprint == "" || !validRemoteSecretFiles(pkiSecretFiles) {
		return errors.New("RUNTIME_PROJECTION_INPUT_INVALID")
	}
	payload := map[string]any{
		"apiVersion":                                   "platform.installer/runtime-projection/v1alpha1",
		"platform_execution_run_id":                    runID,
		"platform_execution_project_identity":          projectIdentity,
		"platform_execution_plan_fingerprint":          planFingerprint,
		"platform_execution_requirements_fingerprint":  requirementsFingerprint,
		"platform_project_id":                          projectIdentity,
		"platform_service_catalog_path":                "/var/lib/platform-installer/runtime/current/catalog/service-catalog.yml",
		"platform_resolved_artifact_sources_by_target": projections,
		"platform_resolved_artifact_sources":           "{{ platform_resolved_artifact_sources_by_target[inventory_hostname] | default({}) }}",
		"platform_pki_secret_files":                    pkiSecretFiles,
	}
	data, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	local, err := os.CreateTemp("", "platform-runtime-projection-*.json")
	if err != nil {
		return err
	}
	localPath := local.Name()
	defer os.Remove(localPath)
	if _, err := local.Write(data); err != nil {
		_ = local.Close()
		return err
	}
	if err := local.Close(); err != nil {
		return err
	}
	identity, err := t.Identity.IdentityFile(node.CredentialRef)
	if err != nil {
		return err
	}
	remote := "/var/tmp/platform-installer/execution-projection/" + runID + ".json"
	if _, err := t.ssh(ctx, node, "sh", []string{"-s", "--", remote}, []byte("set -eu\ncase \"$1\" in /var/tmp/platform-installer/execution-projection/installer-*.json) ;; *) exit 64;; esac\nmkdir -p -- /var/tmp/platform-installer/execution-projection\nrm -f -- \"$1\"\n")); err != nil {
		return &ExecutionError{Code: ExecutionNodeUnavailable}
	}
	args := append(t.scpBase(node, identity), "-O", "--", localPath, t.destination(node, remote))
	if _, err := t.run(ctx, "scp", args, nil); err != nil {
		return &ExecutionError{Code: ExecutionNodeUnavailable}
	}
	script := "set -eu\nremote=$1\nrun=$2\ncase \"$remote:$run\" in /var/tmp/platform-installer/execution-projection/installer-*.json:installer-*) ;; *) exit 64;; esac\nsudo -n install -d -m 0700 /var/lib/platform-installer/execution/runs/$run\nsudo -n install -m 0600 \"$remote\" /var/lib/platform-installer/execution/runs/$run/runtime-projection.json\nrm -f -- \"$remote\"\n"
	if _, err := t.ssh(ctx, node, "sh", []string{"-s", "--", remote, runID}, []byte(script)); err != nil {
		return &ExecutionError{Code: ExecutionNodeUnavailable}
	}
	return nil
}

func validRemoteSecretFiles(values map[string]string) bool {
	for reference, secretPath := range values {
		if !strings.HasPrefix(reference, "runtime:") || len(reference) == len("runtime:") || !strings.HasPrefix(secretPath, "/") || path.Clean(secretPath) != secretPath || strings.ContainsAny(reference+secretPath, "\r\n\x00") {
			return false
		}
	}
	return true
}

func validRuntimeToken(value string) bool {
	if value == "" || !strings.HasPrefix(value, "installer-") {
		return false
	}
	for _, r := range value[len("installer-"):] {
		if r < '0' || r > '9' {
			return false
		}
	}
	return true
}

type ExecutionStartRequest struct {
	RunID           string         `json:"runId"`
	ProjectIdentity string         `json:"projectIdentity"`
	PlanFingerprint string         `json:"planFingerprint"`
	RuntimeRelease  map[string]any `json:"runtimeRelease"`
}

type ExecutionRun struct {
	RunID           string `json:"runId"`
	ProjectIdentity string `json:"projectIdentity,omitempty"`
	State           string `json:"state"`
	Sequence        int    `json:"sequence"`
}

type ExecutionEvent struct {
	RunID       string `json:"runId"`
	Sequence    int    `json:"sequence"`
	EventType   string `json:"eventType"`
	Status      string `json:"status"`
	SafeMessage string `json:"safeMessage"`
}

func (t OpenSSHTransport) BuildDeploymentPlan(ctx context.Context, node Node, projectRoot string, runtimeRelease map[string]any) (DeploymentPlan, error) {
	if projectRoot == "" || len(runtimeRelease) == 0 {
		return DeploymentPlan{}, errors.New("DEPLOYMENT_PLAN_INPUT_INVALID")
	}
	runID := newRunID()
	if err := t.stagePlanProject(ctx, node, projectRoot, runID); err != nil {
		return DeploymentPlan{}, err
	}
	response, err := t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": "platform.installer/execution-runtime/v1alpha1", "operation": "BuildDeploymentPlan", "runId": runID, "project": "/var/lib/platform-installer/execution/runs/" + runID + "/project", "runtimeRelease": runtimeRelease})
	if err != nil {
		return DeploymentPlan{}, err
	}
	value, ok := response["deploymentPlan"].(map[string]any)
	if !ok {
		return DeploymentPlan{}, errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
	}
	plan, err := decodeDeploymentPlan(value)
	if err == nil {
		plan.executionID = runID
	}
	return plan, err
}

func (t OpenSSHTransport) stagePlanProject(ctx context.Context, node Node, projectRoot, runID string) error {
	archive, err := createProjectArchive(projectRoot)
	if err != nil {
		return err
	}
	defer os.Remove(archive)
	identity, err := t.Identity.IdentityFile(node.CredentialRef)
	if err != nil {
		return err
	}
	remote := "/var/tmp/platform-installer/execution-plan/" + runID
	if _, err := t.ssh(ctx, node, "sh", []string{"-s", "--", remote}, []byte("set -eu\ncase \"$1\" in /var/tmp/platform-installer/execution-plan/installer-*) ;; *) exit 64;; esac\nsudo -n rm -rf -- \"$1\"\nmkdir -p -- \"$1\"\n")); err != nil {
		return &ExecutionError{Code: ExecutionNodeUnavailable}
	}
	args := append(t.scpBase(node, identity), "-O", "--", archive, t.destination(node, remote+"/project.tar"))
	if _, err := t.run(ctx, "scp", args, nil); err != nil {
		return &ExecutionError{Code: ExecutionNodeUnavailable}
	}
	script := "set -eu\nrun=$1; archive=$2\ncase \"$run\" in /var/tmp/platform-installer/execution-plan/installer-*) ;; *) exit 64;; esac\ncase \"$archive\" in \"$run/project.tar\") ;; *) exit 64;; esac\nsudo -n install -d -m 0700 /var/lib/platform-installer/execution/runs/$3/project\nsudo -n tar -xf \"$archive\" -C /var/lib/platform-installer/execution/runs/$3/project\nsudo -n rm -f -- \"$archive\"\nrm -rf -- \"$run\"\n"
	if _, err := t.ssh(ctx, node, "sh", []string{"-s", "--", remote, remote + "/project.tar", runID}, []byte(script)); err != nil {
		return &ExecutionError{Code: ExecutionNodeUnavailable}
	}
	return nil
}

func (t OpenSSHTransport) StartExecution(ctx context.Context, node Node, request ExecutionStartRequest) (ExecutionRun, error) {
	if request.RunID == "" || request.ProjectIdentity == "" || request.PlanFingerprint == "" || len(request.RuntimeRelease) == 0 {
		return ExecutionRun{}, errors.New("EXECUTION_START_INPUT_INVALID")
	}
	response, err := t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": "platform.installer/execution-runtime/v1alpha1", "operation": "StartExecution", "runId": request.RunID, "projectIdentity": request.ProjectIdentity, "planFingerprint": request.PlanFingerprint, "runtimeRelease": request.RuntimeRelease})
	if err != nil {
		return ExecutionRun{}, err
	}
	run, err := decodeRun(response)
	if err == nil {
		run.RunID = request.RunID
		run.ProjectIdentity = request.ProjectIdentity
	}
	return run, err
}

func (t OpenSSHTransport) GetExecution(ctx context.Context, node Node, runID string) (ExecutionRun, error) {
	response, err := t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": "platform.installer/execution-runtime/v1alpha1", "operation": "GetExecution", "runId": runID})
	if err != nil {
		return ExecutionRun{}, err
	}
	run, err := decodeRun(response)
	if err == nil {
		run.RunID = runID
	}
	return run, err
}

func (t OpenSSHTransport) GetEvents(ctx context.Context, node Node, runID string, afterSequence int) ([]ExecutionEvent, error) {
	if afterSequence < 0 {
		return nil, errors.New("EXECUTION_EVENTS_INPUT_INVALID")
	}
	response, err := t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": "platform.installer/execution-runtime/v1alpha1", "operation": "GetEvents", "runId": runID, "afterSequence": afterSequence})
	if err != nil {
		return nil, err
	}
	return decodeEvents(response)
}

func (t OpenSSHTransport) CancelExecution(ctx context.Context, node Node, runID string) (ExecutionRun, error) {
	response, err := t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": "platform.installer/execution-runtime/v1alpha1", "operation": "CancelExecution", "runId": runID})
	if err != nil {
		return ExecutionRun{}, err
	}
	return decodeRun(response)
}

func decodeRun(response map[string]any) (ExecutionRun, error) {
	value, ok := response["run"].(map[string]any)
	if !ok {
		return ExecutionRun{}, errors.New("EXECUTION_RUN_RESPONSE_INVALID")
	}
	run := ExecutionRun{}
	if v, ok := value["runId"].(string); ok {
		run.RunID = v
	}
	if v, ok := value["projectIdentity"].(string); ok {
		run.ProjectIdentity = v
	}
	if metadata, ok := response["metadata"].(map[string]any); ok {
		if v, ok := metadata["projectIdentity"].(string); ok {
			run.ProjectIdentity = v
		}
		if run.RunID == "" {
			if v, ok := metadata["runId"].(string); ok {
				run.RunID = v
			}
		}
	}
	if v, ok := value["state"].(string); ok {
		run.State = v
	}
	if v, ok := value["sequence"].(float64); ok {
		run.Sequence = int(v)
	}
	if run.State == "" {
		return ExecutionRun{}, errors.New("EXECUTION_RUN_RESPONSE_INVALID")
	}
	return run, nil
}
func decodeEvents(response map[string]any) ([]ExecutionEvent, error) {
	values, ok := response["events"].([]any)
	if !ok {
		return nil, errors.New("EXECUTION_EVENTS_RESPONSE_INVALID")
	}
	result := make([]ExecutionEvent, 0, len(values))
	for _, raw := range values {
		value, ok := raw.(map[string]any)
		if !ok {
			return nil, errors.New("EXECUTION_EVENT_RESPONSE_INVALID")
		}
		event := ExecutionEvent{}
		if v, ok := value["runId"].(string); ok {
			event.RunID = v
		}
		if v, ok := value["sequence"].(float64); ok {
			event.Sequence = int(v)
		}
		if v, ok := value["eventType"].(string); ok {
			event.EventType = v
		}
		if v, ok := value["status"].(string); ok {
			event.Status = v
		}
		if v, ok := value["safeMessage"].(string); ok {
			event.SafeMessage = v
		}
		result = append(result, event)
	}
	return result, nil
}
func decodeDeploymentPlan(value map[string]any) (DeploymentPlan, error) {
	plan := DeploymentPlan{}
	if v, ok := value["id"].(string); ok {
		plan.ID = v
	}
	if v, ok := value["status"].(string); ok {
		plan.Status = v
	}
	if v, ok := value["projectIdentity"].(string); ok {
		plan.ProjectIdentity = v
	}
	if v, ok := value["projectRevision"].(string); ok {
		plan.ProjectRevision = v
	}
	if f, ok := value["fingerprints"].(map[string]any); ok {
		if v, ok := f["plan"].(string); ok {
			plan.PlanFingerprint = v
		}
	}
	if a, ok := value["acknowledgements"].([]any); ok {
		for _, raw := range a {
			if item, ok := raw.(map[string]any); ok {
				if code, ok := item["code"].(string); ok {
					plan.Acknowledgements = append(plan.Acknowledgements, code)
				}
			}
		}
	}
	plan.Findings = decodeFindings(value["findings"])
	if requirements, ok := value["artifactRequirements"].([]any); ok {
		for _, raw := range requirements {
			item, ok := raw.(map[string]any)
			if !ok {
				return DeploymentPlan{}, errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
			}
			requirement := artifactsource.Requirement{}
			if v, ok := item["requirementId"].(string); ok {
				requirement.ID = v
			}
			if v, ok := item["name"].(string); ok {
				requirement.Name = v
			}
			if v, ok := item["version"].(string); ok {
				requirement.Version = v
			}
			if v, ok := item["os"].(string); ok {
				requirement.OS = v
			}
			if v, ok := item["architecture"].(string); ok {
				requirement.Architecture = v
			}
			if requirement.ID == "" || requirement.Name == "" || requirement.OS == "" || requirement.Architecture == "" {
				return DeploymentPlan{}, errors.New("DEPLOYMENT_PLAN_REQUIREMENT_INVALID")
			}
			plan.ArtifactRequirements = append(plan.ArtifactRequirements, requirement)
		}
	}
	if r, ok := value["runtimeRelease"].(map[string]any); ok {
		plan.RuntimeRelease = r
	}
	if plan.ID == "" || plan.ProjectRevision == "" || plan.PlanFingerprint == "" || len(plan.RuntimeRelease) == 0 || (plan.Status != "EXECUTABLE" && plan.Status != "BLOCKED") || (plan.Status == "EXECUTABLE" && plan.ProjectIdentity == "") {
		return DeploymentPlan{}, errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
	}
	return plan, nil
}

func decodeFindings(raw any) []Finding {
	values, ok := raw.([]any)
	if !ok {
		return nil
	}
	result := make([]Finding, 0, len(values))
	for _, rawFinding := range values {
		value, ok := rawFinding.(map[string]any)
		if !ok {
			continue
		}
		code, codeOK := value["code"].(string)
		message, messageOK := value["safeMessage"].(string)
		if codeOK && messageOK && code != "" && message != "" {
			result = append(result, Finding{Code: code, SafeMessage: message})
		}
	}
	return result
}

func (t OpenSSHTransport) runtimeProtocol(ctx context.Context, node Node, request map[string]any) (map[string]any, error) {
	payload, err := json.Marshal(request)
	if err != nil {
		return nil, err
	}
	// Resolve the active immutable release on the node, then invoke the fixed
	// protocol directly. No shell command is assembled from dynamic values.
	root := "/var/lib/platform-installer/runtime"
	releaseOutput, err := t.ssh(ctx, node, "sudo", []string{"-n", "readlink", "-f", root + "/current"}, nil)
	if err != nil {
		return nil, &ExecutionError{Code: ExecutionNodeUnavailable}
	}
	release := strings.TrimSpace(string(releaseOutput))
	if !strings.HasPrefix(release, root+"/releases/") || strings.ContainsAny(release, " \t\r\n") {
		return nil, &ExecutionError{Code: ExecutionNodeUnavailable}
	}
	active, err := t.ssh(ctx, node, "sudo", []string{"-n", "cat", root + "/state/active"}, nil)
	if err != nil {
		return nil, &ExecutionError{Code: ExecutionNodeUnavailable}
	}
	digest := parseFacts(string(active))["BUNDLE_DIGEST"]
	if !strings.HasPrefix(digest, "sha256:") || len(digest) != len("sha256:")+64 {
		return nil, &ExecutionError{Code: ExecutionNodeUnavailable}
	}
	args := []string{"-n", "env", "PYTHONPATH=" + release + "/ansible-core/tools", "python3", release + "/ansible-core/tools/execution_protocol.py", "--runtime-release", release, "--bundle-digest", digest, "--controller", release + "/ansible-core/tools/execution_controller.py"}
	output, err := t.ssh(ctx, node, "sudo", args, payload)
	var response map[string]any
	decodeErr := json.Unmarshal(output, &response)
	if decodeErr != nil {
		if err != nil {
			return nil, &ExecutionError{Code: ExecutionNodeUnavailable}
		}
		return nil, errors.New("EXECUTION_PROTOCOL_RESPONSE_INVALID")
	}
	if code, ok := response["error"].(string); ok && code != "" {
		var findings []Finding
		if diagnostic, ok := response["diagnostic"].(map[string]any); ok {
			findings = decodeFindings(diagnostic["findings"])
		}
		return response, &ExecutionError{Code: code, Findings: findings}
	}
	if err != nil {
		return nil, &ExecutionError{Code: ExecutionNodeUnavailable}
	}
	return response, nil
}

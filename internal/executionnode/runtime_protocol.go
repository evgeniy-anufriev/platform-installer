package executionnode

// Typed access to the fixed UI-BE-04C runtime protocol.  This is transport
// plumbing only: it stores no plan, owns no session and cannot carry a remote
// command, playbook path or argv supplied by an Installer client.

import (
	"context"
	"encoding/json"
	"errors"
)

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
	response, err := t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": "platform.installer/execution-runtime/v1alpha1", "operation": "BuildDeploymentPlan", "project": projectRoot, "runtimeRelease": runtimeRelease})
	if err != nil {
		return DeploymentPlan{}, err
	}
	value, ok := response["deploymentPlan"].(map[string]any)
	if !ok {
		return DeploymentPlan{}, errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
	}
	return decodeDeploymentPlan(value)
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
	if r, ok := value["runtimeRelease"].(map[string]any); ok {
		plan.RuntimeRelease = r
	}
	if plan.ID == "" || plan.ProjectIdentity == "" || plan.ProjectRevision == "" || plan.PlanFingerprint == "" || len(plan.RuntimeRelease) == 0 {
		return DeploymentPlan{}, errors.New("DEPLOYMENT_PLAN_RESPONSE_INVALID")
	}
	return plan, nil
}

func (t OpenSSHTransport) runtimeProtocol(ctx context.Context, node Node, request map[string]any) (map[string]any, error) {
	payload, err := json.Marshal(request)
	if err != nil {
		return nil, err
	}
	// The release and executable are selected only on the node.  stdin is the
	// versioned semantic request; stdout is its JSON response.
	script := "set -eu\nroot=/var/lib/platform-installer/runtime\nrelease=$(sudo -n readlink -f \"$root/current\")\ncase \"$release\" in \"$root\"/releases/[0-9a-f]*) ;; *) exit 64;; esac\ndigest=$(sudo -n awk -F= '$1 == \"BUNDLE_DIGEST\" {print $2}' \"$root/state/active\")\ncase \"$digest\" in sha256:[0-9a-f]*) ;; *) exit 64;; esac\nexec sudo -n env PYTHONPATH=\"$release/ansible-core/tools\" python3 \"$release/ansible-core/tools/execution_protocol.py\" --runtime-release \"$release\" --bundle-digest \"$digest\" --controller \"$release/ansible-core/tools/execution_controller.py\"\n"
	output, err := t.ssh(ctx, node, "sh", []string{"-c", script}, payload)
	if err != nil {
		return nil, &ExecutionError{Code: ExecutionNodeUnavailable}
	}
	var response map[string]any
	if err := json.Unmarshal(output, &response); err != nil {
		return nil, errors.New("EXECUTION_PROTOCOL_RESPONSE_INVALID")
	}
	if code, ok := response["error"].(string); ok && code != "" {
		return response, &ExecutionError{Code: code}
	}
	return response, nil
}

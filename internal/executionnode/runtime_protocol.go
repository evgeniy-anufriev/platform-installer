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
	RunID    string `json:"runId"`
	State    string `json:"state"`
	Sequence int    `json:"sequence"`
}

type ExecutionEvent struct {
	RunID       string `json:"runId"`
	Sequence    int    `json:"sequence"`
	EventType   string `json:"eventType"`
	Status      string `json:"status"`
	SafeMessage string `json:"safeMessage"`
}

func (t OpenSSHTransport) StartExecution(ctx context.Context, node Node, request ExecutionStartRequest) (map[string]any, error) {
	if request.RunID == "" || request.ProjectIdentity == "" || request.PlanFingerprint == "" || len(request.RuntimeRelease) == 0 {
		return nil, errors.New("EXECUTION_START_INPUT_INVALID")
	}
	return t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": "platform.installer/execution-runtime/v1alpha1", "operation": "StartExecution", "runId": request.RunID, "projectIdentity": request.ProjectIdentity, "planFingerprint": request.PlanFingerprint, "runtimeRelease": request.RuntimeRelease})
}

func (t OpenSSHTransport) GetExecution(ctx context.Context, node Node, runID string) (map[string]any, error) {
	return t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": "platform.installer/execution-runtime/v1alpha1", "operation": "GetExecution", "runId": runID})
}

func (t OpenSSHTransport) GetEvents(ctx context.Context, node Node, runID string, afterSequence int) (map[string]any, error) {
	if afterSequence < 0 {
		return nil, errors.New("EXECUTION_EVENTS_INPUT_INVALID")
	}
	return t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": "platform.installer/execution-runtime/v1alpha1", "operation": "GetEvents", "runId": runID, "afterSequence": afterSequence})
}

func (t OpenSSHTransport) CancelExecution(ctx context.Context, node Node, runID string) (map[string]any, error) {
	return t.runtimeProtocol(ctx, node, map[string]any{"apiVersion": "platform.installer/execution-runtime/v1alpha1", "operation": "CancelExecution", "runId": runID})
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
		return nil, err
	}
	var response map[string]any
	if err := json.Unmarshal(output, &response); err != nil {
		return nil, errors.New("EXECUTION_PROTOCOL_RESPONSE_INVALID")
	}
	if response["error"] != nil {
		return response, errors.New("EXECUTION_PROTOCOL_FAILED")
	}
	return response, nil
}

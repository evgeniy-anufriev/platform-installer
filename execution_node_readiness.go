package main

import (
	"context"
	"errors"
	"time"

	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
)

// executionNodeLifecycle is the existing narrow execution-node lifecycle. The
// application keeps its trusted binding private; Wails receives only the safe
// result types below.
type executionNodeLifecycle interface {
	InspectExecutionNode(context.Context, executionnode.Node) (executionnode.Inspection, error)
	PlanExecutionNodePreparation(context.Context, executionnode.Node, string) (executionnode.Plan, error)
	Prepare(context.Context, executionnode.Node, string, string) (executionnode.Result, error)
}

type executionNodeBinding struct {
	node       executionnode.Node
	reader     projectReader
	service    executionNodeLifecycle
	bundleRoot string
}

// ExecutionNodeReadiness contains no connection, host-key, credential, or
// runtime-path material. It is the only readiness state exposed to Wails.
type ExecutionNodeReadiness struct {
	Status    string                     `json:"status"`
	NodeID    string                     `json:"nodeId,omitempty"`
	SafeLabel string                     `json:"safeLabel,omitempty"`
	CheckedAt string                     `json:"checkedAt,omitempty"`
	Findings  []ExecutionNodeSafeFinding `json:"findings,omitempty"`
	Error     *ProjectOpenError          `json:"error,omitempty"`
}

// ExecutionNodePreparation is a bounded, in-memory confirmation request. Its
// plan is owned and verified by executionnode.Service; the UI may return only
// PlanID to confirm it.
type ExecutionNodePreparation struct {
	Status       string                     `json:"status"`
	PlanID       string                     `json:"planId,omitempty"`
	ExpiresAt    string                     `json:"expiresAt,omitempty"`
	Steps        []ExecutionNodeSafeStep    `json:"steps,omitempty"`
	Findings     []ExecutionNodeSafeFinding `json:"findings,omitempty"`
	Error        *ProjectOpenError          `json:"error,omitempty"`
	Verification *ProjectVerification       `json:"verification,omitempty"`
}

type ExecutionNodeSafeFinding struct {
	Code        string `json:"code"`
	SafeMessage string `json:"safeMessage"`
}

type ExecutionNodeSafeStep struct {
	ID      string `json:"id"`
	Action  string `json:"action"`
	Mutates bool   `json:"mutates"`
}

func safeNodeFindings(findings []executionnode.Finding) []ExecutionNodeSafeFinding {
	const maxFindings = 64
	if len(findings) > maxFindings {
		findings = findings[:maxFindings]
	}
	result := make([]ExecutionNodeSafeFinding, 0, len(findings))
	for _, finding := range findings {
		if finding.Code == "" || finding.SafeMessage == "" || len(finding.Code) > 128 || len(finding.SafeMessage) > 512 {
			continue
		}
		result = append(result, ExecutionNodeSafeFinding{Code: finding.Code, SafeMessage: finding.SafeMessage})
	}
	return result
}

func safeNodeSteps(steps []executionnode.Step) []ExecutionNodeSafeStep {
	const maxSteps = 16
	if len(steps) > maxSteps {
		steps = steps[:maxSteps]
	}
	result := make([]ExecutionNodeSafeStep, 0, len(steps))
	for _, step := range steps {
		if step.ID == "" || step.Action == "" || len(step.ID) > 128 || len(step.Action) > 128 {
			continue
		}
		result = append(result, ExecutionNodeSafeStep{ID: step.ID, Action: step.Action, Mutates: step.Mutates})
	}
	return result
}

type verificationContinuation struct {
	root, projectID, revision, bindingID, planID, planDigest string
	expiresAt                                                time.Time
}

func (a *App) resolveSelectedExecutionNodeBindingLocked() (*executionNodeBinding, error) {
	if a.binding == nil || a.binding.service == nil || a.binding.reader.transport == nil || a.binding.node.ID == "" || a.binding.bundleRoot == "" {
		return nil, errors.New("BINDING_REQUIRED")
	}
	if a.execution.context.SelectionKind != "EXPLICIT_EXTERNAL" || a.execution.external == nil || a.execution.external.hostID != a.binding.node.ID {
		return nil, errors.New("BINDING_REQUIRED")
	}
	return a.binding, nil
}

func readinessFromInspection(binding *executionNodeBinding, label string, inspection executionnode.Inspection) ExecutionNodeReadiness {
	return ExecutionNodeReadiness{Status: string(inspection.State), NodeID: binding.node.ID, SafeLabel: label, CheckedAt: time.Now().UTC().Format(time.RFC3339), Findings: safeNodeFindings(inspection.Findings)}
}

func (a *App) readinessFailureLocked(err error) ExecutionNodeReadiness {
	code := projectErrorCode(err)
	return ExecutionNodeReadiness{Status: code, CheckedAt: time.Now().UTC().Format(time.RFC3339), Error: &ProjectOpenError{Code: code, Message: projectErrorMessage(code)}}
}

func (a *App) CheckExecutionNode() ExecutionNodeReadiness {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	if a.current.Status != "OPEN" || a.current.Project == nil {
		return a.readinessFailureLocked(errors.New("PROJECT_NOT_OPEN"))
	}
	binding, err := a.resolveSelectedExecutionNodeBindingLocked()
	if err != nil {
		return a.readinessFailureLocked(err)
	}
	ctx, cancel := a.operationContext(90 * time.Second)
	defer cancel()
	inspection, err := binding.service.InspectExecutionNode(ctx, binding.node)
	if err != nil {
		return a.readinessFailureLocked(err)
	}
	readiness := readinessFromInspection(binding, a.execution.context.SafeLabel, inspection)
	a.execution.setStatus(readiness.Status)
	return readiness
}

func (a *App) PlanExecutionNodePreparation() ExecutionNodePreparation {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	if a.current.Status != "OPEN" || a.current.Project == nil || a.current.Root == "" {
		return preparationFailure(errors.New("PROJECT_NOT_OPEN"))
	}
	binding, err := a.resolveSelectedExecutionNodeBindingLocked()
	if err != nil {
		return preparationFailure(err)
	}
	revision, err := installer.ProjectRevision(a.current.Root)
	if err != nil {
		return preparationFailure(err)
	}
	ctx, cancel := a.operationContext(2 * time.Minute)
	defer cancel()
	plan, err := binding.service.PlanExecutionNodePreparation(ctx, binding.node, binding.bundleRoot)
	if err != nil {
		return preparationFailure(err)
	}
	a.execution.setStatus(string(plan.State))
	if plan.State == executionnode.Incompatible || plan.State == executionnode.Broken || plan.State == executionnode.Unreachable || plan.ID == "" || plan.Digest == "" {
		a.continuation = nil
		return ExecutionNodePreparation{Status: string(plan.State), Steps: safeNodeSteps(plan.Steps)}
	}
	a.continuation = &verificationContinuation{root: a.current.Root, projectID: a.current.Project.ID, revision: revision, bindingID: binding.node.ID, planID: plan.ID, planDigest: plan.Digest, expiresAt: plan.ExpiresAt}
	return ExecutionNodePreparation{Status: "CONFIRMATION_REQUIRED", PlanID: plan.ID, ExpiresAt: plan.ExpiresAt.UTC().Format(time.RFC3339), Steps: safeNodeSteps(plan.Steps)}
}

func preparationFailure(err error) ExecutionNodePreparation {
	code := projectErrorCode(err)
	return ExecutionNodePreparation{Status: "BLOCKED", Error: &ProjectOpenError{Code: code, Message: projectErrorMessage(code)}}
}

// PrepareExecutionNode continues only the exact preparation plan generated for
// the current saved revision and trusted binding. After a successful Prepare it
// performs a fresh inspection and then Verify; no pre-Prepare runtime evidence
// is retained as final verification proof.
func (a *App) PrepareExecutionNode(planID string) ExecutionNodePreparation {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	continuation := a.continuation
	a.continuation = nil
	if continuation == nil || continuation.planDigest == "" || planID == "" || planID != continuation.planID || !time.Now().Before(continuation.expiresAt) {
		return preparationFailure(errors.New("EXECUTION_NODE_PLAN_INVALID"))
	}
	if a.current.Status != "OPEN" || a.current.Project == nil || a.current.Root != continuation.root || a.current.Project.ID != continuation.projectID {
		return preparationFailure(errors.New("PROJECT_REVISION_CHANGED"))
	}
	revision, err := installer.ProjectRevision(a.current.Root)
	if err != nil || revision != continuation.revision {
		if err == nil {
			err = errors.New("PROJECT_REVISION_CHANGED")
		}
		return preparationFailure(err)
	}
	binding, err := a.resolveSelectedExecutionNodeBindingLocked()
	if err != nil || binding.node.ID != continuation.bindingID {
		if err == nil {
			err = errors.New("BINDING_REQUIRED")
		}
		return preparationFailure(err)
	}
	ctx, cancel := a.operationContext(5 * time.Minute)
	defer cancel()
	result, err := binding.service.Prepare(ctx, binding.node, binding.bundleRoot, continuation.planID)
	if err != nil {
		return preparationFailure(err)
	}
	a.execution.setStatus(string(result.State))
	if result.State != executionnode.Ready {
		return ExecutionNodePreparation{Status: string(result.State), Findings: safeNodeFindings(result.Findings)}
	}
	inspection, err := binding.service.InspectExecutionNode(ctx, binding.node)
	if err != nil {
		return preparationFailure(err)
	}
	a.execution.setStatus(string(inspection.State))
	if inspection.State != executionnode.Ready {
		return ExecutionNodePreparation{Status: string(inspection.State), Findings: safeNodeFindings(inspection.Findings)}
	}
	verification := a.verifyProjectWithBindingLocked(binding, continuation.revision, false)
	return ExecutionNodePreparation{Status: "PREPARED", Verification: &verification}
}

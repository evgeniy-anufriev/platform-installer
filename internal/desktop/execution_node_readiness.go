package desktop

import (
	"context"
	"errors"
	"time"

	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
	"platform-installer/internal/sshpassword"
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
	node                 executionnode.Node
	reader               projectReader
	service              executionNodeLifecycle
	plans                *executionnode.ExecutionService
	bundleRoot           string
	dynamic              bool
	credentialGeneration uint64
	hostKeyPin           *approvedExecutionHostKey
	commandGuard         func() (func(), error)
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
		if finding.Code == "EXECUTION_NODE_ELEVATION_REQUIRED" {
			finding.SafeMessage = "Подключение по SSH выполнено, но права sudo не подтверждены. На странице «Серверы» включите «Требуется пароль sudo», введите пароль и сохраните данные в сеансе. Затем повторите проверку сервера."
		}
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

func (a *App) resolveSelectedExecutionNodeBindingLocked(scope ...sshpassword.Scope) (*executionNodeBinding, error) {
	binding, err := a.resolveTrustedExecutionConnectionLocked(scope...)
	if err != nil || binding.bundleRoot == "" {
		return nil, errors.New("BINDING_REQUIRED")
	}
	if binding.dynamic {
		verified, err := a.verifySelectedBundleLocked()
		if err != nil || verified.Digest != binding.reader.runtimeRelease["bundleDigest"] {
			return nil, errors.New("BINDING_REQUIRED")
		}
	}
	return binding, nil
}

// Trusted connection is transport authority only. It can inspect a node or
// resolve an already-known run, but cannot authorize Core/plan/Start without
// resolveSelectedExecutionNodeBindingLocked's runtime release check.
func (a *App) resolveTrustedExecutionConnectionLocked(scope ...sshpassword.Scope) (*executionNodeBinding, error) {
	if a.binding == nil || a.binding.service == nil || a.binding.reader.transport == nil || a.binding.node.ID == "" {
		return nil, errors.New("BINDING_REQUIRED")
	}
	if a.binding.dynamic {
		id, address, port, err := a.selectedSavedExecutionServerLocked()
		if err != nil || id != a.binding.node.ID || address != a.binding.node.Address || port != a.binding.node.Port {
			a.invalidateDynamicBindingLocked()
			return nil, errors.New("BINDING_REQUIRED")
		}
		credentialBinding, err := a.credentialBindingLocked()
		if err != nil {
			a.invalidateDynamicBindingLocked()
			return nil, errors.New("BINDING_REQUIRED")
		}
		identity, err := a.secrets.CurrentExecutionIdentity(credentialBinding)
		if len(scope) == 1 {
			identity, err = a.secrets.CurrentExecutionIdentityForOperation(credentialBinding, scope[0].PlanID, scope[0].RunID)
		}
		if err != nil || identity.Generation != a.binding.credentialGeneration || identity.Username != a.binding.node.User {
			if !a.secrets.HasRunExecutionIdentityHold(credentialBinding) {
				a.invalidateDynamicBindingLocked()
			}
			return nil, errors.New("BINDING_REQUIRED")
		}
		if a.binding.hostKeyPin == nil {
			a.invalidateDynamicBindingLocked()
			return nil, errors.New("BINDING_REQUIRED")
		}
		if a.binding.commandGuard == nil {
			a.invalidateDynamicBindingLocked()
			return nil, errors.New("BINDING_REQUIRED")
		}
		var release func()
		var guardErr error
		if transport, ok := a.binding.reader.transport.(executionnode.OpenSSHTransport); ok && transport.ContextCommandGuard != nil && len(scope) == 1 {
			release, guardErr = transport.ContextCommandGuard(sshpassword.WithScope(context.Background(), scope[0]))
		} else {
			release, guardErr = a.binding.commandGuard()
		}
		if guardErr != nil {
			a.invalidateDynamicBindingLocked()
			return nil, errors.New("BINDING_REQUIRED")
		}
		release()
		return a.binding, nil
	}
	if a.execution.context.SelectionKind != "EXPLICIT_EXTERNAL" || a.execution.external == nil || a.execution.external.hostID != a.binding.node.ID {
		return nil, errors.New("BINDING_REQUIRED")
	}
	return a.binding, nil
}

// A long remote call may outlive its session credential. Never publish its
// result unless the same private binding is still current after the call.
func (a *App) revalidateBindingBeforePublicationLocked(binding *executionNodeBinding) error {
	if !binding.dynamic {
		return nil
	}
	current, err := a.resolveSelectedExecutionNodeBindingLocked()
	if err != nil || current != binding {
		credentialBinding, credentialErr := a.credentialBindingLocked()
		if a.binding != binding || credentialErr != nil || !a.secrets.HasRunExecutionIdentityHold(credentialBinding) {
			a.invalidateDynamicBindingLocked()
		}
		return errors.New("BINDING_REQUIRED")
	}
	return nil
}

func (a *App) revalidateTrustedConnectionLocked(binding *executionNodeBinding) error {
	if !binding.dynamic {
		return nil
	}
	current, err := a.resolveTrustedExecutionConnectionLocked()
	if err != nil || current != binding {
		return errors.New("BINDING_REQUIRED")
	}
	return nil
}

func readinessFromInspection(binding *executionNodeBinding, label string, inspection executionnode.Inspection) ExecutionNodeReadiness {
	status := string(inspection.State)
	findings := append([]executionnode.Finding(nil), inspection.Findings...)
	if inspection.State == executionnode.Ready {
		expectedDigest, _ := binding.reader.runtimeRelease["bundleDigest"].(string)
		if expectedDigest != "" && inspection.Runtime.BundleDigest != expectedDigest {
			status = string(executionnode.UpdateRequired)
			findings = append(findings, executionnode.Finding{
				Code:        "EXECUTION_NODE_RUNTIME_BUNDLE_MISMATCH",
				SafeMessage: "Активный runtime bundle на узле не совпадает с проверенным bundle проекта; требуется обновление узла.",
			})
		}
	}
	return ExecutionNodeReadiness{Status: status, NodeID: binding.node.ID, SafeLabel: label, CheckedAt: time.Now().UTC().Format(time.RFC3339), Findings: safeNodeFindings(findings)}
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
	binding, err := a.resolveTrustedExecutionConnectionLocked()
	if err != nil {
		return a.readinessFailureLocked(err)
	}
	ctx, cancel := a.operationContext(90 * time.Second)
	defer cancel()
	inspection, err := binding.service.InspectExecutionNode(ctx, binding.node)
	if err != nil {
		if binding.dynamic {
			a.invalidateDynamicBindingLocked()
		}
		return a.readinessFailureLocked(err)
	}
	if err := a.revalidateTrustedConnectionLocked(binding); err != nil {
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
		if binding.dynamic {
			a.invalidateDynamicBindingLocked()
		}
		return preparationFailure(err)
	}
	if err := a.revalidateBindingBeforePublicationLocked(binding); err != nil {
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
	// Bundle transfer and extraction can exceed five minutes for offline images.
	ctx, cancel := a.operationContext(20 * time.Minute)
	defer cancel()
	result, err := binding.service.Prepare(ctx, binding.node, binding.bundleRoot, continuation.planID)
	if err != nil {
		if binding.dynamic {
			a.invalidateDynamicBindingLocked()
		}
		return preparationFailure(err)
	}
	if err := a.revalidateBindingBeforePublicationLocked(binding); err != nil {
		return preparationFailure(err)
	}
	a.execution.setStatus(string(result.State))
	if result.State != executionnode.Ready {
		return ExecutionNodePreparation{Status: string(result.State), Findings: safeNodeFindings(result.Findings)}
	}
	inspection, err := binding.service.InspectExecutionNode(ctx, binding.node)
	if err != nil {
		if binding.dynamic {
			a.invalidateDynamicBindingLocked()
		}
		return preparationFailure(err)
	}
	if err := a.revalidateBindingBeforePublicationLocked(binding); err != nil {
		return preparationFailure(err)
	}
	a.execution.setStatus(string(inspection.State))
	if inspection.State != executionnode.Ready {
		return ExecutionNodePreparation{Status: string(inspection.State), Findings: safeNodeFindings(inspection.Findings)}
	}
	verification := a.verifyProjectWithBindingLocked(binding, continuation.revision, false)
	return ExecutionNodePreparation{Status: "PREPARED", Verification: &verification}
}

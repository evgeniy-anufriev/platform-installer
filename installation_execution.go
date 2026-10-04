package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/wailsapp/wails/v2/pkg/runtime"

	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
	"platform-installer/internal/runtimesecret"
)

const installationEventName = "installation-run-event"
const maxInstallationSubscriptions = 32

const (
	observerDisconnected   = "OBSERVER_DISCONNECTED"
	observerHistoryGap     = "OBSERVER_HISTORY_GAP"
	observerSubscriberSlow = "OBSERVER_SUBSCRIBER_SLOW"
	observerUnavailable    = "OBSERVER_UNAVAILABLE"
	observabilityDegraded  = "OBSERVABILITY_DEGRADED"
)

// InstallationRunView is deliberately smaller than ExecutionRun: it is the
// stable Wails result boundary and contains neither transport nor journal data.
type InstallationRunView struct {
	RunID    string `json:"runId"`
	State    string `json:"state"`
	Sequence int    `json:"sequence"`
}

type InstallationRunOperation struct {
	Status string                  `json:"status"`
	Run    *InstallationRunView    `json:"run,omitempty"`
	Result *InstallationResultView `json:"result,omitempty"`
	Error  *ProjectOpenError       `json:"error,omitempty"`
}

// InstallationResultView is terminal lifecycle evidence only. It is not a
// raw execution result or a substitute for the authoritative run journal.
type InstallationResultView struct {
	RunID    string `json:"runId"`
	State    string `json:"state"`
	Sequence int    `json:"sequence"`
}

type InstallationEventView struct {
	RunID               string                `json:"runId"`
	Sequence            int                   `json:"sequence"`
	Timestamp           string                `json:"timestamp"`
	EventType           string                `json:"eventType"`
	Status              string                `json:"status"`
	PhaseID             string                `json:"phaseId,omitempty"`
	ActionID            string                `json:"actionId,omitempty"`
	Host                string                `json:"host,omitempty"`
	ServiceDeployment   string                `json:"serviceDeployment,omitempty"`
	Task                *InstallationTaskView `json:"task,omitempty"`
	ElapsedMilliseconds *int                  `json:"elapsedMilliseconds,omitempty"`
	SafeMessage         string                `json:"safeMessage"`
	ErrorCode           string                `json:"errorCode,omitempty"`
	ErrorSummary        string                `json:"errorSummary,omitempty"`
	Redacted            bool                  `json:"redacted"`
}

type InstallationTaskView struct {
	Role string `json:"role,omitempty"`
	Name string `json:"name,omitempty"`
	UUID string `json:"uuid,omitempty"`
}
type InstallationSubscriptionEvent struct {
	SubscriptionID string                 `json:"subscriptionId"`
	Event          *InstallationEventView `json:"event,omitempty"`
	ErrorCode      string                 `json:"errorCode,omitempty"`
}
type InstallationSubscriptionResult struct {
	Status         string                         `json:"status"`
	SubscriptionID string                         `json:"subscriptionId,omitempty"`
	Event          *InstallationSubscriptionEvent `json:"event,omitempty"`
	Error          *ProjectOpenError              `json:"error,omitempty"`
}

type installationStartContext struct {
	generation uint64
	root       string
	projectID  string
	revision   string
	planID     string
	nodeID     string
	runtime    InstallationRuntimeBinding
}

type installationRunSubscription struct {
	cancel context.CancelFunc
	sub    *executionnode.ObserverSubscription
}
type installationRunRegistry struct {
	mu            sync.Mutex
	subscriptions map[string]installationRunSubscription
	observers     map[string]*executionnode.RunObserver
	runs          map[string]struct{}
}

func newInstallationRunRegistry() *installationRunRegistry {
	return &installationRunRegistry{subscriptions: map[string]installationRunSubscription{}, observers: map[string]*executionnode.RunObserver{}, runs: map[string]struct{}{}}
}
func (r *installationRunRegistry) add(id string, item installationRunSubscription) bool {
	r.mu.Lock()
	defer r.mu.Unlock()
	if len(r.subscriptions) >= maxInstallationSubscriptions {
		return false
	}
	r.subscriptions[id] = item
	return true
}
func (r *installationRunRegistry) remove(id string) {
	r.mu.Lock()
	item, ok := r.subscriptions[id]
	if ok {
		delete(r.subscriptions, id)
	}
	r.mu.Unlock()
	if ok {
		item.cancel()
		if item.sub != nil {
			item.sub.Close()
		}
	}
}
func (r *installationRunRegistry) clear() {
	r.mu.Lock()
	ids := make([]string, 0, len(r.subscriptions))
	for id := range r.subscriptions {
		ids = append(ids, id)
	}
	r.mu.Unlock()
	for _, id := range ids {
		r.remove(id)
	}
	r.mu.Lock()
	r.observers = map[string]*executionnode.RunObserver{}
	r.runs = map[string]struct{}{}
	r.mu.Unlock()
}
func (r *installationRunRegistry) rememberRun(runID string) {
	r.mu.Lock()
	r.runs[runID] = struct{}{}
	r.mu.Unlock()
}
func (r *installationRunRegistry) knowsRun(runID string) bool {
	r.mu.Lock()
	defer r.mu.Unlock()
	_, ok := r.runs[runID]
	return ok
}

// publishKnownInstallationRunLocked binds an authoritative run only while the
// caller holds App.editMu. Project/node replacement takes that same lock before
// it clears the registry, which keeps a completed Start in its own generation.
func (a *App) publishKnownInstallationRunLocked(generation uint64, runID string) bool {
	if a.installationGeneration != generation {
		return false
	}
	a.installationRuns.rememberRun(runID)
	return true
}

// publishInstallationSubscriptionLocked has the same App generation boundary
// as run publication. A false result means either a replacement won the race
// or the local presentation-subscription bound was reached.
func (a *App) publishInstallationSubscriptionLocked(generation uint64, runID, id string, item installationRunSubscription) bool {
	if a.installationGeneration != generation || !a.installationRuns.knowsRun(runID) {
		return false
	}
	return a.installationRuns.add(id, item)
}

func (r *installationRunRegistry) observer(key string, client executionnode.ExecutionClient, root string) (*executionnode.RunObserver, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if observer := r.observers[key]; observer != nil {
		return observer, nil
	}
	observer, err := executionnode.NewRunObserver(client, root)
	if err != nil {
		return nil, err
	}
	r.observers[key] = observer
	return observer, nil
}

func (a *App) configureTargetCredentialLease() {
	if a.binding == nil || a.binding.plans == nil {
		return
	}
	a.binding.plans.ConfigureTargetCredentialLease(func(request executionnode.TargetCredentialLeaseRequest, use func(executionnode.TargetCredentialLeasePayload) error) error {
		a.editMu.Lock()
		defer a.editMu.Unlock()
		binding, err := a.credentialBindingLocked()
		if err != nil {
			return err
		}
		return a.secrets.WithTargetCredential(binding, func(credential runtimesecret.TargetCredential) error {
			payload := executionnode.TargetCredentialLeasePayload{Username: credential.Username, SudoPassword: string(credential.SudoSecret)}
			if credential.SSHMode == runtimesecret.SSHPassword {
				payload.Password = string(credential.SSHSecret)
			} else {
				payload.PrivateKey = string(credential.SSHSecret)
			}
			if request.RequiresPKIStorePassword {
				payload.PKIStorePassword = string(credential.PKIStorePassword)
			}
			if len(request.RuntimeSecretRequirements) > 0 {
				payload.RuntimeSecretValues = make(map[string]string, len(credential.RuntimeSecretValues))
				for reference, value := range credential.RuntimeSecretValues {
					payload.RuntimeSecretValues[reference] = string(value)
				}
			}
			if len(request.RuntimeSecretInputs) > 0 {
				payload.UseTypedRuntimeInputs = true
				expected := make(map[string]string, len(request.RuntimeSecretInputs))
				for _, item := range request.RuntimeSecretInputs {
					expected[item.RequirementRef] = item.Purpose
				}
				for _, item := range credential.RuntimeSecretInputs {
					if expected[item.RequirementRef] != item.Purpose {
						return errors.New("RUNTIME_SECRET_DESCRIPTORS_STALE")
					}
					payload.RuntimeSecretInputs = append(payload.RuntimeSecretInputs, executionnode.RuntimeSecretInputPayload{
						RequirementRef: item.RequirementRef, Purpose: item.Purpose, ServiceDeployment: item.ServiceDeployment,
						Operations: append([]string(nil), item.Operations...), Value: string(item.Value), Shares: byteSlicesToStrings(item.Shares),
					})
				}
			}
			return use(payload)
		})
	})
}

func byteSlicesToStrings(values [][]byte) []string {
	result := make([]string, len(values))
	for i, value := range values {
		result[i] = string(value)
	}
	return result
}

func installationRunView(run executionnode.ExecutionRun) InstallationRunView {
	return InstallationRunView{RunID: run.RunID, State: run.State, Sequence: run.Sequence}
}
func installationResultView(run executionnode.ExecutionRun) *InstallationResultView {
	switch run.State {
	case "SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED":
		return &InstallationResultView{RunID: run.RunID, State: run.State, Sequence: run.Sequence}
	default:
		return nil
	}
}
func installationEventView(event executionnode.ExecutionEvent) InstallationEventView {
	view := InstallationEventView{RunID: event.RunID, Sequence: event.Sequence, Timestamp: event.Timestamp, EventType: event.EventType, Status: event.Status, PhaseID: event.PhaseID, ActionID: event.ActionID, Host: event.Host, ServiceDeployment: event.ServiceDeployment, ElapsedMilliseconds: event.ElapsedMillis, SafeMessage: event.SafeMessage, Redacted: event.Redaction.Applied}
	taskNameRedacted := false
	for _, field := range event.Redaction.Fields {
		if field == "task.name" {
			taskNameRedacted = true
			break
		}
	}
	if event.Task != nil && !taskNameRedacted {
		view.Task = &InstallationTaskView{Role: event.Task.Role, Name: event.Task.Name, UUID: event.Task.UUID}
	} else if event.Task != nil {
		view.Task = &InstallationTaskView{Role: event.Task.Role, UUID: event.Task.UUID}
	}
	if event.Error != nil {
		view.ErrorCode = event.Error.Code
		view.ErrorSummary = event.Error.Summary
	}
	return view
}

func installationObserverDiagnostic(err error) string {
	if err == nil {
		return ""
	}
	switch err.Error() {
	case executionnode.ObserverTransportFailure:
		return observerDisconnected
	case executionnode.ObserverHistoryTruncated:
		return observerHistoryGap
	case executionnode.ObserverSubscriberSlow:
		return observerSubscriberSlow
	case executionnode.ObserverCapacityExceeded:
		return observerUnavailable
	default:
		return observabilityDegraded
	}
}

func (a *App) StartApprovedInstallation(planID string) InstallationRunOperation {
	a.editMu.Lock()
	if planID == "" || planID != a.installationPlanID {
		a.editMu.Unlock()
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "INSTALLATION_PLAN_NOT_FOUND", Message: projectErrorMessage("INSTALLATION_PLAN_NOT_FOUND")}}
	}
	binding, err := a.resolveSelectedExecutionNodeBindingLocked()
	if err != nil || binding.plans == nil {
		a.editMu.Unlock()
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "EXECUTION_NODE_BINDING_REQUIRED", Message: projectErrorMessage("EXECUTION_NODE_BINDING_REQUIRED")}}
	}
	revision, revisionErr := installer.ProjectRevision(a.current.Root)
	if revisionErr != nil {
		a.editMu.Unlock()
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "PROJECT_REVISION_UNAVAILABLE", Message: projectErrorMessage("PROJECT_REVISION_UNAVAILABLE")}}
	}
	runtimeBinding, runtimeOK := installationRuntimeBinding(binding.reader.runtimeRelease)
	if !runtimeOK || a.current.Project == nil || revision == "" {
		a.editMu.Unlock()
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "EXECUTION_NODE_BINDING_REQUIRED", Message: projectErrorMessage("EXECUTION_NODE_BINDING_REQUIRED")}}
	}
	planRecord, planErr := binding.plans.GetPlan(planID)
	if planErr != nil || !installationPlanMatches(planRecord, a.current.Project.ID, revision, binding) {
		a.editMu.Unlock()
		if planErr == nil {
			planErr = errors.New("PLAN_STALE")
		}
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: projectErrorCode(planErr), Message: projectErrorMessage(projectErrorCode(planErr))}}
	}
	outputRequired := a.secretOutputEncryptionRequiredLocked()
	if outputRequired {
		credentialBinding, bindingErr := a.credentialBindingLocked()
		if bindingErr != nil || !a.secrets.HasOutputEncryptionPassword(credentialBinding) {
			a.editMu.Unlock()
			return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "SECRET_OUTPUT_ENCRYPTION_PASSWORD_REQUIRED", Message: "Set and confirm the password for locally encrypted service output files before approval and Start."}}
		}
	}
	typedInputs := typedRuntimeSecretRequirements(planRecord.Plan)
	if len(typedInputs) > 0 {
		descriptors := a.getRuntimeSecretDescriptorsLocked(false)
		if descriptors.Status != "READY" || !runtimeDescriptorsMatchPlan(descriptors.Descriptors, typedInputs) {
			a.editMu.Unlock()
			return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "RUNTIME_SECRET_DESCRIPTORS_STALE", Message: "Core did not confirm the exact service input requirements for this saved plan."}}
		}
	}
	requirements, requirementsErr := installationPlanRuntimeSecretRequirements(planRecord.Plan)
	if requirementsErr != nil {
		a.editMu.Unlock()
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: projectErrorCode(requirementsErr), Message: projectErrorMessage(projectErrorCode(requirementsErr))}}
	}
	credentialBinding, credentialErr := a.credentialBindingLocked()
	if credentialErr == nil {
		credentialErr = a.secrets.PromotePendingRuntimeSecretValues(credentialBinding, requirements)
	}
	if credentialErr != nil {
		a.editMu.Unlock()
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: projectErrorCode(credentialErr), Message: projectErrorMessage(projectErrorCode(credentialErr))}}
	}
	captured := installationStartContext{generation: a.installationGeneration, root: a.current.Root, projectID: a.current.Project.ID, revision: revision, planID: planID, nodeID: binding.node.ID, runtime: runtimeBinding}
	a.editMu.Unlock()
	ctx, cancel := a.operationContext(2 * time.Minute)
	defer cancel()
	if outputRequired {
		client, ok := binding.reader.transport.(secretOutputDeliveryClient)
		if !ok {
			return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "SECRET_OUTPUT_UNSUPPORTED", Message: "Execution Node does not support protected output delivery."}}
		}
		capability, capabilityErr := client.GetSecretOutputCapabilities(ctx, binding.node, runtimeBinding.BundleDigest, captured.projectID)
		if capabilityErr != nil || capability.Protocol != "SecretOutputDelivery/v1alpha1" || capability.Operation != "GetCapabilities" || capability.MaxPayloadBytes != 65536 || len(capability.Operations) != 3 || capability.Operations[0] != "ListPending" || capability.Operations[1] != "Fetch" || capability.Operations[2] != "Acknowledge" {
			return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "SECRET_OUTPUT_UNAVAILABLE", Message: "Protected output delivery capabilities were not confirmed; execution was not started."}}
		}
	}
	run, err := binding.plans.Start(ctx, binding.node, planID)
	if err != nil {
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: projectErrorCode(err), Message: projectErrorMessage(projectErrorCode(err))}}
	}
	a.editMu.Lock()
	currentRevision, currentRevisionErr := installer.ProjectRevision(a.current.Root)
	currentBinding, currentBindingErr := a.resolveSelectedExecutionNodeBindingLocked()
	currentRuntime, currentRuntimeOK := InstallationRuntimeBinding{}, false
	if currentBindingErr == nil {
		currentRuntime, currentRuntimeOK = installationRuntimeBinding(currentBinding.reader.runtimeRelease)
	}
	current := currentRevisionErr == nil && currentBindingErr == nil && currentRuntimeOK && a.installationGeneration == captured.generation && a.current.Status == "OPEN" && a.current.Root == captured.root && a.current.Project != nil && a.current.Project.ID == captured.projectID && currentRevision == captured.revision && a.installationPlanID == captured.planID && currentBinding.node.ID == captured.nodeID && currentRuntime == captured.runtime
	if !current {
		a.editMu.Unlock()
		return InstallationRunOperation{Status: "START_CONTEXT_CHANGED", Run: ptrInstallationRun(installationRunView(run))}
	}
	// Keep this generation check and registry publication under editMu. A
	// replacement clears the registry under the same lock, so an old Start
	// cannot rebind its run to the replacement project after this point.
	if !a.publishKnownInstallationRunLocked(captured.generation, run.RunID) {
		a.editMu.Unlock()
		return InstallationRunOperation{Status: "START_CONTEXT_CHANGED", Run: ptrInstallationRun(installationRunView(run))}
	}
	a.editMu.Unlock()
	return InstallationRunOperation{Status: "STARTED", Run: ptrInstallationRun(installationRunView(run))}
}
func ptrInstallationRun(v InstallationRunView) *InstallationRunView { return &v }

func (a *App) GetInstallationRun(runID string) InstallationRunOperation {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	if !a.installationRuns.knowsRun(runID) {
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "INSTALLATION_RUN_NOT_FOUND", Message: "Выполнение не известно текущему сеансу"}}
	}
	binding, err := a.resolveSelectedExecutionNodeBindingLocked()
	if err != nil {
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "EXECUTION_NODE_BINDING_REQUIRED", Message: projectErrorMessage("EXECUTION_NODE_BINDING_REQUIRED")}}
	}
	client, ok := binding.reader.transport.(executionnode.ExecutionClient)
	if !ok {
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "EXECUTION_NODE_BINDING_REQUIRED", Message: projectErrorMessage("EXECUTION_NODE_BINDING_REQUIRED")}}
	}
	ctx, cancel := a.operationContext(30 * time.Second)
	defer cancel()
	run, err := client.GetExecution(ctx, binding.node, runID)
	if err != nil {
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: projectErrorCode(err), Message: projectErrorMessage(projectErrorCode(err))}}
	}
	return InstallationRunOperation{Status: "READY", Run: ptrInstallationRun(installationRunView(run)), Result: installationResultView(run)}
}

func (a *App) SubscribeInstallationRun(runID string, afterSequence int) InstallationSubscriptionResult {
	if !a.installationRuns.knowsRun(runID) {
		return InstallationSubscriptionResult{Status: "BLOCKED", Error: &ProjectOpenError{Code: "INSTALLATION_RUN_NOT_FOUND", Message: "Выполнение не известно текущему сеансу"}}
	}
	a.editMu.Lock()
	binding, err := a.resolveSelectedExecutionNodeBindingLocked()
	root := a.current.Root
	ctx := a.ctx
	generation := a.installationGeneration
	a.editMu.Unlock()
	if err != nil || root == "" || afterSequence < 0 {
		return InstallationSubscriptionResult{Status: "BLOCKED", Error: &ProjectOpenError{Code: "EXECUTION_NODE_BINDING_REQUIRED", Message: projectErrorMessage("EXECUTION_NODE_BINDING_REQUIRED")}}
	}
	client, ok := binding.reader.transport.(executionnode.ExecutionClient)
	if !ok {
		return InstallationSubscriptionResult{Status: "BLOCKED", Error: &ProjectOpenError{Code: "EXECUTION_NODE_BINDING_REQUIRED", Message: projectErrorMessage("EXECUTION_NODE_BINDING_REQUIRED")}}
	}
	observerKey := binding.node.ID + "\x00" + runID
	runtimeRoot, rootErr := installationRuntimeRoot()
	if rootErr != nil {
		return InstallationSubscriptionResult{Status: "BLOCKED", Error: &ProjectOpenError{Code: "EXECUTION_OBSERVER_UNAVAILABLE", Message: projectErrorMessage("EXECUTION_OBSERVER_UNAVAILABLE")}}
	}
	observer, err := a.installationRuns.observer(observerKey, client, runtimeRoot)
	if err != nil {
		return InstallationSubscriptionResult{Status: "BLOCKED", Error: &ProjectOpenError{Code: "EXECUTION_OBSERVER_UNAVAILABLE", Message: projectErrorMessage("EXECUTION_OBSERVER_UNAVAILABLE")}}
	}
	if ctx == nil {
		ctx = context.Background()
	}
	subscription, err := observer.SubscribeAfter(ctx, binding.node, runID, afterSequence, 128)
	if err != nil {
		return InstallationSubscriptionResult{Status: "BLOCKED", Error: &ProjectOpenError{Code: projectErrorCode(err), Message: projectErrorMessage(projectErrorCode(err))}}
	}
	bytes := make([]byte, 16)
	if _, err = rand.Read(bytes); err != nil {
		subscription.Close()
		return InstallationSubscriptionResult{Status: "BLOCKED", Error: &ProjectOpenError{Code: "INSTALLATION_SUBSCRIPTION_UNAVAILABLE", Message: "Подписка на выполнение недоступна"}}
	}
	id := hex.EncodeToString(bytes)
	watchCtx, cancel := context.WithCancel(ctx)
	item := installationRunSubscription{cancel: cancel, sub: subscription}
	a.editMu.Lock()
	// Registry publication is deliberately atomic with generation validation:
	// project/node replacement takes editMu before it clears this registry.
	contextCurrent := a.installationGeneration == generation && a.installationRuns.knowsRun(runID)
	added := false
	if contextCurrent {
		added = a.publishInstallationSubscriptionLocked(generation, runID, id, item)
	}
	a.editMu.Unlock()
	if !contextCurrent {
		subscription.Close()
		cancel()
		return InstallationSubscriptionResult{Status: "BLOCKED", Error: &ProjectOpenError{Code: "START_CONTEXT_CHANGED", Message: "Контекст проекта изменился до подключения к выполнению"}}
	}
	if !added {
		subscription.Close()
		cancel()
		return InstallationSubscriptionResult{Status: "BLOCKED", Error: &ProjectOpenError{Code: "INSTALLATION_SUBSCRIPTION_LIMIT", Message: "Достигнут предел локальных подписок"}}
	}
	go a.forwardInstallationSubscription(watchCtx, id, item)
	return InstallationSubscriptionResult{Status: "SUBSCRIBED", SubscriptionID: id}
}

func installationRuntimeRoot() (string, error) {
	cache, err := os.UserCacheDir()
	if err != nil || cache == "" {
		return "", errors.New("EXECUTION_OBSERVER_UNAVAILABLE")
	}
	return filepath.Join(cache, "platform-installer", "executions"), nil
}
func (a *App) forwardInstallationSubscription(ctx context.Context, id string, item installationRunSubscription) {
	defer a.installationRuns.remove(id)
	for {
		select {
		case <-ctx.Done():
			return
		case event, ok := <-item.sub.Events:
			if !ok {
				return
			}
			if a.ctx != nil {
				runtime.EventsEmit(a.ctx, installationEventName, InstallationSubscriptionEvent{SubscriptionID: id, Event: ptrInstallationEvent(installationEventView(event))})
			}
		case err, ok := <-item.sub.Errors:
			if !ok {
				return
			}
			if a.ctx != nil && err != nil {
				runtime.EventsEmit(a.ctx, installationEventName, InstallationSubscriptionEvent{SubscriptionID: id, ErrorCode: installationObserverDiagnostic(err)})
			}
		}
	}
}
func ptrInstallationEvent(v InstallationEventView) *InstallationEventView { return &v }
func (a *App) UnsubscribeInstallationRun(id string)                       { a.installationRuns.remove(id) }
func (a *App) CancelInstallationRun(runID string) InstallationRunOperation {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	if !a.installationRuns.knowsRun(runID) {
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "INSTALLATION_RUN_NOT_FOUND", Message: "Выполнение не известно текущему сеансу"}}
	}
	binding, err := a.resolveSelectedExecutionNodeBindingLocked()
	if err != nil || binding.plans == nil {
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "EXECUTION_NODE_BINDING_REQUIRED", Message: projectErrorMessage("EXECUTION_NODE_BINDING_REQUIRED")}}
	}
	ctx, cancel := a.operationContext(30 * time.Second)
	defer cancel()
	run, err := binding.plans.Cancel(ctx, binding.node, runID)
	if err != nil {
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: projectErrorCode(err), Message: projectErrorMessage(projectErrorCode(err))}}
	}
	return InstallationRunOperation{Status: "CANCELLING", Run: ptrInstallationRun(installationRunView(run))}
}

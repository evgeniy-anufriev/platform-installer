package desktop

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"os"
	"path/filepath"
	"slices"
	"sync"
	"time"

	"platform-installer/internal/executionnode"
	"platform-installer/internal/installer"
	"platform-installer/internal/runtimesecret"
	"platform-installer/internal/sshpassword"
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
	Reconnected       bool                    `json:"reconnected,omitempty"`
	CancelUnconfirmed bool                    `json:"cancelUnconfirmed,omitempty"`
	ProjectRevision   string                  `json:"projectRevision,omitempty"`
	Status            string                  `json:"status"`
	Run               *InstallationRunView    `json:"run,omitempty"`
	Result            *InstallationResultView `json:"result,omitempty"`
	Error             *ProjectOpenError       `json:"error,omitempty"`
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
	monitors      map[string]context.CancelFunc
	terminal      map[string]executionnode.ExecutionRun
}

func newInstallationRunRegistry() *installationRunRegistry {
	return &installationRunRegistry{subscriptions: map[string]installationRunSubscription{}, observers: map[string]*executionnode.RunObserver{}, runs: map[string]struct{}{}, monitors: map[string]context.CancelFunc{}, terminal: map[string]executionnode.ExecutionRun{}}
}

// clearInstallationRunsLocked is called under App.editMu at shutdown or when
// project/trusted-node context changes. It cancels app-owned monitors and
// releases their in-memory SSH identity metadata together.
func (a *App) clearInstallationRunsLocked() {
	a.recoveredRun = nil
	a.recoveredCancelUnconfirmed = false
	if a.installationRuns != nil {
		a.installationRuns.clear()
	}
	if a.secrets != nil {
		a.secrets.ClearRunExecutionIdentityHolds()
	}
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
	monitorCancels := make([]context.CancelFunc, 0, len(r.monitors))
	for _, cancel := range r.monitors {
		monitorCancels = append(monitorCancels, cancel)
	}
	r.mu.Unlock()
	for _, cancel := range monitorCancels {
		cancel()
	}
	for _, id := range ids {
		r.remove(id)
	}
	r.mu.Lock()
	r.observers = map[string]*executionnode.RunObserver{}
	r.runs = map[string]struct{}{}
	r.monitors = map[string]context.CancelFunc{}
	r.terminal = map[string]executionnode.ExecutionRun{}
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

func (r *installationRunRegistry) runIDs() []string {
	r.mu.Lock()
	defer r.mu.Unlock()
	ids := make([]string, 0, len(r.runs))
	for id := range r.runs {
		ids = append(ids, id)
	}
	return ids
}

func (r *installationRunRegistry) startMonitor(runID string) (context.Context, bool) {
	if runID == "" {
		return nil, false
	}
	ctx, cancel := context.WithCancel(context.Background())
	r.mu.Lock()
	if _, known := r.runs[runID]; !known || len(r.monitors) != 0 {
		r.mu.Unlock()
		cancel()
		return nil, false
	}
	r.monitors[runID] = cancel
	delete(r.terminal, runID)
	r.mu.Unlock()
	return ctx, true
}

func (r *installationRunRegistry) finishMonitor(runID string, terminal *executionnode.ExecutionRun) {
	r.mu.Lock()
	cancel := r.monitors[runID]
	delete(r.monitors, runID)
	if terminal != nil {
		r.terminal[runID] = *terminal
	}
	r.mu.Unlock()
	if cancel != nil {
		cancel()
	}
}

func (r *installationRunRegistry) hasActiveRun() bool {
	r.mu.Lock()
	defer r.mu.Unlock()
	return len(r.monitors) > 0
}

func (r *installationRunRegistry) terminalRun(runID string) (executionnode.ExecutionRun, bool) {
	r.mu.Lock()
	defer r.mu.Unlock()
	run, ok := r.terminal[runID]
	return run, ok
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
				for _, reference := range request.RuntimeSecretRequirements {
					if value, ok := credential.RuntimeSecretValues[reference]; ok {
						payload.RuntimeSecretValues[reference] = string(value)
					}
				}
			}
			if len(request.RuntimeSecretInputs) > 0 {
				payload.UseTypedRuntimeInputs = true
				expected := make(map[string]string, len(request.RuntimeSecretInputs))
				for _, item := range request.RuntimeSecretInputs {
					expected[item.RequirementRef] = item.Purpose
				}
				for _, item := range credential.RuntimeSecretInputs {
					if _, required := expected[item.RequirementRef]; !required {
						continue
					}
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
	// Applied marks the event as safely redacted, not every task field as hidden.
	// The closed redaction field list identifies the withheld task name.
	if event.Task != nil && !slices.Contains(event.Redaction.Fields, "task.name") {
		view.Task = &InstallationTaskView{Role: event.Task.Role, Name: event.Task.Name, UUID: event.Task.UUID}
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
	if a.recoveredRunActiveLocked() {
		a.editMu.Unlock()
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "INSTALLATION_RUN_ACTIVE", Message: "Прежний запуск ещё выполняется на узле исполнения"}}
	}
	// A later ordinary Start uses its original credential and trust guards.
	a.recoveredRun, a.recoveredCancelUnconfirmed = nil, false
	if a.startInFlight || a.runtimeUpdateInFlight {
		a.editMu.Unlock()
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "INSTALLATION_OPERATION_IN_PROGRESS", Message: "Другая операция запуска или обновления набора установки ещё выполняется"}}
	}
	if planID == "" || planID != a.installationPlanID {
		a.editMu.Unlock()
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "INSTALLATION_PLAN_NOT_FOUND", Message: projectErrorMessage("INSTALLATION_PLAN_NOT_FOUND")}}
	}
	scope := sshpassword.Scope{}
	if a.startOutcomeUnknown {
		scope.PlanID = planID
	}
	binding, err := a.resolveSelectedExecutionNodeBindingLocked(scope)
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
	if !a.startOutcomeUnknown {
		typedInputs := typedRuntimeSecretRequirements(planRecord.Plan)
		passwordRequirements, requirementErr := installationPlanRuntimeSecretRequirements(planRecord.Plan)
		if requirementErr != nil {
			a.editMu.Unlock()
			return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: projectErrorCode(requirementErr), Message: projectErrorMessage(projectErrorCode(requirementErr))}}
		}
		if len(passwordRequirements) > 0 {
			missing, secretErr := a.missingInstallationSecretsLocked(planRecord.Plan, false)
			if secretErr != nil {
				a.editMu.Unlock()
				return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: projectErrorCode(secretErr), Message: projectErrorMessage(projectErrorCode(secretErr))}}
			}
			if len(missing) > 0 {
				a.editMu.Unlock()
				return InstallationRunOperation{Status: "BLOCKED", Error: missingInstallationSecretsError(missing)}
			}
		}
		if len(typedInputs) > 0 || len(passwordRequirements) > 0 {
			descriptors := a.getRuntimeSecretDescriptorsLocked(false)
			if descriptors.Status != "READY" {
				a.editMu.Unlock()
				if descriptors.Error != nil {
					return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: descriptors.Error.Code, Message: projectErrorMessage(descriptors.Error.Code), DiagnosticCodes: descriptors.Error.DiagnosticCodes}}
				}
				code := "RUNTIME_SECRET_DESCRIPTORS_UNAVAILABLE"
				return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: code, Message: projectErrorMessage(code)}}
			}
			if len(typedInputs) > 0 && !runtimeDescriptorsMatchPlan(descriptors.Descriptors, typedInputs, planRecord.Plan.ExecutionMode) {
				a.editMu.Unlock()
				return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "RUNTIME_SECRET_DESCRIPTORS_STALE", Message: "Типизированные входы сервисов не совпадают с требованиями одобренного плана. Сформируйте свежий план и повторите ввод секретов."}}
			}
		}
		missing, secretErr := a.missingInstallationSecretsLocked(planRecord.Plan, true)
		if secretErr != nil {
			a.editMu.Unlock()
			return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: projectErrorCode(secretErr), Message: projectErrorMessage(projectErrorCode(secretErr))}}
		}
		if len(missing) > 0 {
			a.editMu.Unlock()
			return InstallationRunOperation{Status: "BLOCKED", Error: missingInstallationSecretsError(missing)}
		}
	}
	credentialBinding, credentialErr := a.credentialBindingLocked()
	retryingUnknown := a.startOutcomeUnknown
	if credentialErr != nil {
		a.editMu.Unlock()
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: projectErrorCode(credentialErr), Message: projectErrorMessage(projectErrorCode(credentialErr))}}
	}
	var runIdentity runtimesecret.ExecutionIdentity
	holdRunIdentity := binding.dynamic
	if holdRunIdentity {
		runIdentity, credentialErr = a.secrets.CurrentExecutionIdentityForOperation(credentialBinding, scope.PlanID, scope.RunID)
		if credentialErr != nil || runIdentity.Generation != binding.credentialGeneration {
			a.editMu.Unlock()
			return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "EXECUTION_NODE_BINDING_REQUIRED", Message: projectErrorMessage("EXECUTION_NODE_BINDING_REQUIRED")}}
		}
	}
	previousRecord, recordErr := readLocalRunRecord(a.localRunRecordRoot, a.current.Root, a.current.Project.ID)
	if recordErr != nil {
		a.editMu.Unlock()
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "LOCAL_RUN_RECORD_UNAVAILABLE", Message: "Не удалось проверить локальную запись запуска; Start не отправлен"}}
	}
	if retryingUnknown && (previousRecord == nil || previousRecord.State != "PENDING" || previousRecord.RunID != "" ||
		previousRecord.ProjectID != a.current.Project.ID || previousRecord.PlanID != planID ||
		previousRecord.ProjectRevision != revision || previousRecord.NodeID != binding.node.ID ||
		!a.secrets.HasStartingExecutionIdentity(credentialBinding, planID)) {
		a.editMu.Unlock()
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "INSTALLATION_RUN_ACTIVE", Message: "Предыдущий запуск не подтверждён; повтор допустим только для того же плана и узла"}}
	}
	if !a.knownRunsTerminalLocked() && !retryingUnknown {
		a.editMu.Unlock()
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "INSTALLATION_RUN_ACTIVE", Message: "Предыдущий запуск не подтверждён как завершённый"}}
	}
	captured := installationStartContext{generation: a.installationGeneration, root: a.current.Root, projectID: a.current.Project.ID, revision: revision, planID: planID, nodeID: binding.node.ID, runtime: runtimeBinding}
	a.startInFlight = true
	a.editMu.Unlock()
	defer func() {
		a.editMu.Lock()
		a.startInFlight = false
		a.editMu.Unlock()
	}()
	// Start rebuilds the authoritative plan, including offline image preparation.
	ctx, cancel := a.operationContext(10 * time.Minute)
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
	a.editMu.Lock()
	if a.installationGeneration != captured.generation || a.current.Root != captured.root || a.installationPlanID != captured.planID {
		a.editMu.Unlock()
		return InstallationRunOperation{Status: "START_CONTEXT_CHANGED"}
	}
	canonicalRoot, rootErr := canonicalRunProjectRoot(captured.root)
	if rootErr != nil {
		a.editMu.Unlock()
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "LOCAL_RUN_RECORD_UNAVAILABLE", Message: "Не удалось подготовить локальную запись запуска"}}
	}
	record := localRunRecord{Version: localRunRecordVersion, ProjectRoot: canonicalRoot, ProjectID: captured.projectID, ProjectRevision: captured.revision, PlanID: captured.planID, NodeID: binding.node.ID, NodeAddress: binding.node.Address, NodePort: binding.node.Port, NodeUser: binding.node.User, HostKeyFingerprint: binding.node.HostKey.Fingerprint, State: "PENDING"}
	if holdRunIdentity && !retryingUnknown {
		if err := a.secrets.ReserveExecutionIdentityForStart(credentialBinding, planID, runIdentity); err != nil {
			a.editMu.Unlock()
			return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: projectErrorCode(err), Message: projectErrorMessage(projectErrorCode(err))}}
		}
	}
	if !retryingUnknown {
		if err := writeLocalRunRecord(a.localRunRecordRoot, record); err != nil {
			if holdRunIdentity {
				a.secrets.ReleaseStartingExecutionIdentity(credentialBinding, planID)
			}
			a.editMu.Unlock()
			return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "LOCAL_RUN_RECORD_UNAVAILABLE", Message: "Не удалось сохранить локальную запись запуска; Start не отправлен"}}
		}
	}
	a.startOutcomeUnknown = true // a transport failure can conceal a committed run
	a.editMu.Unlock()
	run, err := binding.plans.Start(sshpassword.WithScope(ctx, sshpassword.Scope{PlanID: planID}), binding.node, planID)
	if err != nil {
		var dispatchStatus interface{ StartWasNotDispatched() bool }
		if errors.As(err, &dispatchStatus) && dispatchStatus.StartWasNotDispatched() {
			if !retryingUnknown {
				a.editMu.Lock()
				restoreErr := restoreLocalRunRecordAfterUnsentStart(a.localRunRecordRoot, record, previousRecord)
				if holdRunIdentity {
					a.secrets.ReleaseStartingExecutionIdentity(credentialBinding, planID)
				}
				if restoreErr != nil {
					// Restore the fail-closed marker if the rollback failed after
					// removing it (for example, a directory sync error).
					if current, readErr := readLocalRunRecord(a.localRunRecordRoot, captured.root, captured.projectID); readErr == nil && current == nil {
						_ = writeLocalRunRecord(a.localRunRecordRoot, record)
					}
				}
				if restoreErr == nil && a.installationGeneration == captured.generation && a.current.Root == captured.root {
					a.startOutcomeUnknown = false
				}
				a.editMu.Unlock()
				if restoreErr != nil {
					return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "LOCAL_RUN_RECORD_UNAVAILABLE", Message: "Запуск не был отправлен, но прежнюю локальную запись не удалось восстановить. Повторный запуск заблокирован до восстановления этой записи."}}
				}
			}
		}
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: projectErrorCode(err), Message: projectErrorMessage(projectErrorCode(err))}}
	}
	a.editMu.Lock()
	if a.installationGeneration != captured.generation || a.current.Root != captured.root || a.current.Project == nil || a.current.Project.ID != captured.projectID || a.binding != binding {
		a.editMu.Unlock()
		return InstallationRunOperation{Status: "START_CONTEXT_CHANGED", Run: ptrInstallationRun(installationRunView(run))}
	}
	if holdRunIdentity {
		if holdErr := a.secrets.ConfirmExecutionIdentityRun(credentialBinding, planID, run.RunID); holdErr != nil {
			a.editMu.Unlock()
			return InstallationRunOperation{Status: "BLOCKED", Run: ptrInstallationRun(installationRunView(run)), Error: &ProjectOpenError{Code: "EXECUTION_RUN_CREDENTIAL_HOLD_FAILED", Message: "Узел принял запуск, но локальное удержание SSH-доступа не удалось. Не запускайте план повторно; проверьте этот идентификатор запуска."}}
		}
	}
	record.State, record.RunID = "RUNNING", run.RunID
	localRecordErr := writeLocalRunRecord(a.localRunRecordRoot, record)
	a.startOutcomeUnknown = false
	currentRevision, currentRevisionErr := installer.ProjectRevision(a.current.Root)
	currentBinding, currentBindingErr := a.resolveSelectedExecutionNodeBindingLocked(sshpassword.Scope{RunID: run.RunID})
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
	monitorCtx, monitorStarted := a.installationRuns.startMonitor(run.RunID)
	a.editMu.Unlock()
	if monitorStarted {
		go a.monitorInstallationRun(monitorCtx, binding, captured, run.RunID)
	}
	if localRecordErr != nil {
		return InstallationRunOperation{Status: "BLOCKED", Run: ptrInstallationRun(installationRunView(run)), Error: &ProjectOpenError{Code: "LOCAL_RUN_RECORD_UNAVAILABLE", Message: "Узел принял запуск; локальная запись будет повторно сохранена наблюдателем. Повторно запускать план нельзя."}}
	}
	return InstallationRunOperation{Status: "STARTED", Run: ptrInstallationRun(installationRunView(run))}
}
func ptrInstallationRun(v InstallationRunView) *InstallationRunView { return &v }

func (a *App) GetInstallationRun(runID string) InstallationRunOperation {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	if !a.installationRuns.knowsRun(runID) {
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "INSTALLATION_RUN_NOT_FOUND", Message: "Выполнение не известно текущему сеансу"}}
	}
	if run, ok := a.installationRuns.terminalRun(runID); ok {
		return a.observedInstallationRunLocked(run)
	}
	binding, err := a.resolveInstallationObservationLocked(runID)
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
	if run.RunID == runID && run.ProjectIdentity == a.current.Project.ID && rebindTerminalRun(run.State) && !a.recoveredCancelUnconfirmed {
		record, readErr := readLocalRunRecord(a.localRunRecordRoot, a.current.Root, a.current.Project.ID)
		if readErr == nil && record != nil && record.RunID == runID && run.ProjectIdentity == record.ProjectID {
			record.State, record.TerminalState = "TERMINAL", run.State
			if writeLocalRunRecord(a.localRunRecordRoot, *record) == nil {
				a.installationRuns.finishMonitor(runID, &run)
				a.secrets.ReleaseExecutionIdentityForRun(runID)
			}
		}
	}
	if run.RunID != runID || a.current.Project == nil || run.ProjectIdentity != a.current.Project.ID {
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "ORPHAN_RUN_IDENTITY_UNVERIFIED", Message: "Принадлежность запуска проекту не подтверждена"}}
	}
	return a.observedInstallationRunLocked(run)
}

// monitorInstallationRun owns an internal RunObserver subscription independent
// of the presentation page. It keeps run state authoritative across navigation
// and releases the credential hold only after the trusted observer has drained
// through the terminal status and GetExecution confirms the same run.
func (a *App) monitorInstallationRun(ctx context.Context, binding *executionNodeBinding, captured installationStartContext, runID string) {
	client, ok := binding.reader.transport.(executionnode.ExecutionClient)
	if !ok || ctx == nil {
		return
	}
	observerKey := binding.node.ID + "\x00" + runID
	var observer *executionnode.RunObserver
	after := 0
	for ctx.Err() == nil {
		if observer == nil {
			runtimeRoot, rootErr := installationRuntimeRoot()
			if rootErr == nil {
				observer, rootErr = a.installationRuns.observer(observerKey, client, runtimeRoot)
			}
			if rootErr != nil {
				if !waitInstallationRunMonitor(ctx, time.Second) {
					return
				}
				continue
			}
		}
		subscription, subscribeErr := observer.SubscribeAfter(ctx, binding.node, runID, after, 128)
		if subscribeErr == nil {
			events, observerErrors := subscription.Events, subscription.Errors
			for events != nil || observerErrors != nil {
				select {
				case event, open := <-events:
					if !open {
						events = nil
						continue
					}
					if event.Sequence > after {
						after = event.Sequence
					}
				case _, open := <-observerErrors:
					if !open {
						observerErrors = nil
					}
				case <-ctx.Done():
					subscription.Close()
					return
				}
			}
			subscription.Close()
		}
		if ctx.Err() != nil {
			return
		}
		checkCtx, cancel := context.WithTimeout(ctx, 30*time.Second)
		run, checkErr := client.GetExecution(checkCtx, binding.node, runID)
		cancel()
		if checkErr == nil && run.RunID == runID && run.ProjectIdentity == captured.projectID && rebindTerminalRun(run.State) {
			a.editMu.Lock()
			if a.recoveredCancelUnconfirmed && a.recoveredRun != nil && a.recoveredRun.RunID == runID {
				a.editMu.Unlock()
				if !waitInstallationRunMonitor(ctx, time.Second) {
					return
				}
				continue
			}
			contextCurrent := a.installationGeneration == captured.generation && a.current.Root == captured.root && a.current.Project != nil && a.current.Project.ID == captured.projectID
			terminalSaved := false
			if contextCurrent {
				if record, readErr := readLocalRunRecord(a.localRunRecordRoot, captured.root, captured.projectID); readErr == nil && record != nil &&
					((record.RunID == runID && record.ProjectID == captured.projectID) ||
						(record.State == "PENDING" && record.RunID == "" && record.PlanID == captured.planID && record.ProjectID == captured.projectID && record.NodeID == captured.nodeID)) {
					record.State, record.RunID, record.TerminalState = "TERMINAL", runID, run.State
					terminalSaved = writeLocalRunRecord(a.localRunRecordRoot, *record) == nil
				}
			}
			if contextCurrent && terminalSaved {
				if a.recoveredRun != nil && a.recoveredRun.RunID == runID {
					a.recoveredRun.State, a.recoveredRun.TerminalState = "TERMINAL", run.State
				}
				a.installationRuns.finishMonitor(runID, &run)
				a.secrets.ReleaseExecutionIdentityForRun(runID)
			}
			a.editMu.Unlock()
			if contextCurrent && terminalSaved {
				return
			}
		}
		if !waitInstallationRunMonitor(ctx, time.Second) {
			return
		}
	}
}

func waitInstallationRunMonitor(ctx context.Context, duration time.Duration) bool {
	timer := time.NewTimer(duration)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return false
	case <-timer.C:
		return true
	}
}

func (a *App) SubscribeInstallationRun(runID string, afterSequence int) InstallationSubscriptionResult {
	if !a.installationRuns.knowsRun(runID) {
		return InstallationSubscriptionResult{Status: "BLOCKED", Error: &ProjectOpenError{Code: "INSTALLATION_RUN_NOT_FOUND", Message: "Выполнение не известно текущему сеансу"}}
	}
	a.editMu.Lock()
	binding, err := a.resolveInstallationObservationLocked(runID)
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
	events, errors := item.sub.Events, item.sub.Errors
	for events != nil || errors != nil {
		select {
		case <-ctx.Done():
			return
		case event, ok := <-events:
			if !ok {
				events = nil
				continue
			}
			a.events.Publish(a.ctx, installationEventName, InstallationSubscriptionEvent{SubscriptionID: id, Event: ptrInstallationEvent(installationEventView(event))})
		case err, ok := <-errors:
			if !ok {
				errors = nil
				continue
			}
			if err != nil {
				a.events.Publish(a.ctx, installationEventName, InstallationSubscriptionEvent{SubscriptionID: id, ErrorCode: installationObserverDiagnostic(err)})
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
	if run, ok := a.installationRuns.terminalRun(runID); ok {
		return InstallationRunOperation{Status: "READY", Run: ptrInstallationRun(installationRunView(run)), Result: installationResultView(run)}
	}
	binding, err := a.resolveInstallationObservationLocked(runID)
	if err != nil || binding.plans == nil {
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "EXECUTION_NODE_BINDING_REQUIRED", Message: projectErrorMessage("EXECUTION_NODE_BINDING_REQUIRED")}}
	}
	ctx, cancel := a.operationContext(30 * time.Second)
	defer cancel()
	var cancelView *InstallationRunView
	if a.recoveredRun != nil && a.recoveredRun.RunID == runID {
		client, ok := binding.reader.transport.(executionnode.ExecutionClient)
		if !ok {
			return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: "EXECUTION_NODE_BINDING_REQUIRED", Message: projectErrorMessage("EXECUTION_NODE_BINDING_REQUIRED")}}
		}
		current, getErr := client.GetExecution(ctx, binding.node, runID)
		if getErr != nil || current.RunID != runID || current.ProjectIdentity != a.recoveredRun.ProjectID || a.revalidateTrustedConnectionLocked(binding) != nil {
			return InstallationRunOperation{Status: "BLOCKED", Reconnected: true, Error: &ProjectOpenError{Code: "ORPHAN_RUN_IDENTITY_UNVERIFIED", Message: projectErrorMessage("ORPHAN_RUN_IDENTITY_UNVERIFIED")}}
		}
		cancelView = ptrInstallationRun(installationRunView(current))
	}
	run, err := binding.plans.Cancel(ctx, binding.node, runID)
	if err != nil {
		if a.recoveredRun != nil && a.recoveredRun.RunID == runID {
			a.recoveredCancelUnconfirmed = true
			return InstallationRunOperation{Status: "BLOCKED", Reconnected: true, CancelUnconfirmed: true, ProjectRevision: a.recoveredRun.ProjectRevision, Run: cancelView, Error: &ProjectOpenError{Code: "ORPHAN_RUN_CANCEL_UNCONFIRMED", Message: "Остановка не подтверждена. Повторите запрос отмены; запуск не разблокирован."}}
		}
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: projectErrorCode(err), Message: projectErrorMessage(projectErrorCode(err))}}
	}
	a.recoveredCancelUnconfirmed = false
	result := a.observedInstallationRunLocked(run)
	result.Status = "CANCELLING"
	return result
}

package desktop

import (
	"crypto/rand"
	"encoding/hex"
	"errors"
	"time"

	"platform-installer/internal/executionnode"
	"platform-installer/internal/sshpassword"
)

type orphanRunRecovery struct {
	id          string
	projectRoot string
	projectID   string
	runID       string
	expires     time.Time
}

type OrphanRunRecoveryResult struct {
	Status          string            `json:"status"`
	RecoveryID      string            `json:"recoveryId,omitempty"`
	RunID           string            `json:"runId,omitempty"`
	RunState        string            `json:"runState,omitempty"`
	ProjectRevision string            `json:"projectRevision,omitempty"`
	Error           *ProjectOpenError `json:"error,omitempty"`
}

func orphanRecoveryError(code string) OrphanRunRecoveryResult {
	return OrphanRunRecoveryResult{Status: "BLOCKED", Error: &ProjectOpenError{Code: code, Message: projectErrorMessage(code)}}
}

// InspectOrphanRun discovers only the locally recorded prior run on its original
// trusted node. The short-lived candidate permits explicit attach or cancellation.
func (a *App) InspectOrphanRun() OrphanRunRecoveryResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	a.orphanRecovery = nil
	if a.current.Status != "OPEN" || a.current.Project == nil || a.startInFlight || a.runtimeUpdateInFlight {
		return orphanRecoveryError("PROJECT_NOT_OPEN")
	}
	record, err := readLocalRunRecord(a.localRunRecordRoot, a.current.Root, a.current.Project.ID)
	if err != nil {
		return orphanRecoveryError("LOCAL_RUN_RECORD_INVALID")
	}
	if record == nil || record.State == "TERMINAL" {
		return OrphanRunRecoveryResult{Status: "NONE"}
	}
	if record.State != "RUNNING" || record.RunID == "" {
		return OrphanRunRecoveryResult{Status: "UNKNOWN"}
	}
	if a.installationRuns.knowsRun(record.RunID) {
		return OrphanRunRecoveryResult{Status: "CURRENT"}
	}
	binding, err := a.resolveTrustedExecutionConnectionLocked()
	if err != nil || !sameLocalRunNode(*record, binding.node) {
		return OrphanRunRecoveryResult{Status: "UNAVAILABLE"}
	}
	client, ok := binding.reader.transport.(executionnode.ExecutionClient)
	if !ok {
		return OrphanRunRecoveryResult{Status: "UNAVAILABLE"}
	}
	ctx, cancel := a.operationContext(30 * time.Second)
	defer cancel()
	run, err := client.GetExecution(ctx, binding.node, record.RunID)
	if err != nil || run.ProjectIdentity != record.ProjectID {
		return OrphanRunRecoveryResult{Status: "UNAVAILABLE"}
	}
	if rebindTerminalRun(run.State) && !a.recoveredStopUnconfirmedLocked(record.RunID) {
		record.State, record.TerminalState = "TERMINAL", run.State
		if err := writeLocalRunRecord(a.localRunRecordRoot, *record); err != nil {
			return orphanRecoveryError("LOCAL_RUN_RECORD_UNAVAILABLE")
		}
		return OrphanRunRecoveryResult{Status: "RESOLVED", RunID: record.RunID, RunState: run.State}
	}
	if !orphanRunCancellable(run.State) && !a.recoveredStopUnconfirmedLocked(record.RunID) {
		return OrphanRunRecoveryResult{Status: "UNAVAILABLE"}
	}
	var nonce [16]byte
	if _, err := rand.Read(nonce[:]); err != nil {
		return orphanRecoveryError("LOCAL_RUN_RECORD_UNAVAILABLE")
	}
	id := hex.EncodeToString(nonce[:])
	a.orphanRecovery = &orphanRunRecovery{id: id, projectRoot: a.current.Root, projectID: record.ProjectID, runID: record.RunID, expires: time.Now().Add(2 * time.Minute)}
	result := OrphanRunRecoveryResult{Status: "FOUND", RecoveryID: id, RunID: record.RunID, RunState: run.State, ProjectRevision: record.ProjectRevision}
	if a.recoveredStopUnconfirmedLocked(record.RunID) {
		result.Error = &ProjectOpenError{Code: "ORPHAN_RUN_CANCEL_UNCONFIRMED", Message: "Остановка не подтверждена. Подключитесь и повторите отмену."}
	}
	return result
}

// AttachOrphanRun restores the existing execution session without a new Start.
func (a *App) AttachOrphanRun(recoveryID string) InstallationRunOperation {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	p := a.orphanRecovery
	a.orphanRecovery = nil
	fail := func(code string) InstallationRunOperation {
		return InstallationRunOperation{Status: "BLOCKED", Error: &ProjectOpenError{Code: code, Message: projectErrorMessage(code)}}
	}
	if p == nil || recoveryID == "" || recoveryID != p.id || !time.Now().Before(p.expires) || a.current.Status != "OPEN" || a.current.Root != p.projectRoot || a.current.Project == nil || a.current.Project.ID != p.projectID || a.startInFlight || a.runtimeUpdateInFlight {
		return fail("ORPHAN_RUN_RECOVERY_STALE")
	}
	record, err := readLocalRunRecord(a.localRunRecordRoot, p.projectRoot, p.projectID)
	if err != nil || record == nil || record.State != "RUNNING" || record.RunID != p.runID {
		return fail("ORPHAN_RUN_RECOVERY_STALE")
	}
	binding, err := a.resolveTrustedExecutionConnectionLocked()
	if err != nil || !sameLocalRunNode(*record, binding.node) {
		return fail("ORPHAN_RUN_IDENTITY_UNVERIFIED")
	}
	client, ok := binding.reader.transport.(executionnode.ExecutionClient)
	if !ok {
		return fail("EXECUTION_NODE_BINDING_REQUIRED")
	}
	ctx, cancel := a.operationContext(30 * time.Second)
	defer cancel()
	run, err := client.GetExecution(ctx, binding.node, record.RunID)
	if err != nil || run.RunID != record.RunID || run.ProjectIdentity != record.ProjectID || a.revalidateTrustedConnectionLocked(binding) != nil {
		return fail("ORPHAN_RUN_IDENTITY_UNVERIFIED")
	}
	if !orphanRunCancellable(run.State) && !rebindTerminalRun(run.State) {
		return fail("ORPHAN_RUN_STATE_UNKNOWN")
	}
	if binding.plans == nil {
		return fail("EXECUTION_NODE_BINDING_REQUIRED")
	}
	reconnected, _, err := binding.plans.Reconnect(ctx, binding.node, record.RunID)
	if err != nil || reconnected.RunID != record.RunID || reconnected.ProjectIdentity != record.ProjectID || a.revalidateTrustedConnectionLocked(binding) != nil {
		return fail("ORPHAN_RUN_IDENTITY_UNVERIFIED")
	}
	run = reconnected
	if !orphanRunCancellable(run.State) && !rebindTerminalRun(run.State) {
		return fail("ORPHAN_RUN_STATE_UNKNOWN")
	}
	a.pauseRecoveredObservationLocked()
	a.recoveredRun = record
	a.installationRuns.rememberRun(run.RunID)
	if rebindTerminalRun(run.State) && !a.recoveredStopUnconfirmedLocked(run.RunID) {
		record.State, record.TerminalState = "TERMINAL", run.State
		if err := writeLocalRunRecord(a.localRunRecordRoot, *record); err != nil {
			return fail("LOCAL_RUN_RECORD_UNAVAILABLE")
		}
		a.installationRuns.finishMonitor(run.RunID, &run)
	} else {
		captured := installationStartContext{generation: a.installationGeneration, root: a.current.Root, projectID: record.ProjectID, revision: record.ProjectRevision, planID: record.PlanID, nodeID: record.NodeID}
		monitorCtx, started := a.installationRuns.startMonitor(run.RunID)
		if !started {
			return fail("INSTALLATION_OPERATION_IN_PROGRESS")
		}
		go a.monitorInstallationRun(monitorCtx, binding, captured, run.RunID)
	}
	return a.observedInstallationRunLocked(run)
}

func (a *App) recoveredRunActiveLocked() bool {
	return a.recoveredRun != nil && a.recoveredRun.State == "RUNNING"
}

func (a *App) recoveredStopUnconfirmedLocked(runID string) bool {
	return a.recoveredCancelUnconfirmed && a.recoveredRun != nil && a.recoveredRun.RunID == runID
}

func (a *App) canRenewRecoveredConnectionLocked() bool {
	return a.recoveredRunActiveLocked() && !a.startInFlight && !a.secrets.HasAnyRunExecutionIdentityHold()
}

// Credential renewal stops old local observers, never the remote controller.
func (a *App) pauseRecoveredObservationLocked() {
	if a.recoveredRun != nil {
		a.installationRuns.clear()
	}
}

func (a *App) resolveInstallationObservationLocked(runID string) (*executionNodeBinding, error) {
	if a.recoveredRun == nil || a.recoveredRun.RunID != runID {
		return a.resolveSelectedExecutionNodeBindingLocked(sshpassword.Scope{RunID: runID})
	}
	record := a.recoveredRun
	root, err := canonicalRunProjectRoot(a.current.Root)
	if err != nil || a.current.Project == nil || root != record.ProjectRoot || a.current.Project.ID != record.ProjectID {
		return nil, errors.New("ORPHAN_RUN_IDENTITY_UNVERIFIED")
	}
	binding, err := a.resolveTrustedExecutionConnectionLocked(sshpassword.Scope{RunID: runID})
	if err != nil || !sameLocalRunNode(*record, binding.node) {
		return nil, errors.New("ORPHAN_RUN_IDENTITY_UNVERIFIED")
	}
	return binding, nil
}

func (a *App) observedInstallationRunLocked(run executionnode.ExecutionRun) InstallationRunOperation {
	result := InstallationRunOperation{Status: "READY", Run: ptrInstallationRun(installationRunView(run)), Result: installationResultView(run)}
	if a.recoveredRun != nil && a.recoveredRun.RunID == run.RunID {
		result.Reconnected = true
		result.CancelUnconfirmed = a.recoveredCancelUnconfirmed
		result.ProjectRevision = a.recoveredRun.ProjectRevision
		if a.recoveredCancelUnconfirmed {
			result.Result = nil
		}
		if rebindTerminalRun(run.State) && !a.recoveredCancelUnconfirmed {
			a.recoveredRun.State, a.recoveredRun.TerminalState = "TERMINAL", run.State
		}
	}
	return result
}

func orphanRunCancellable(state string) bool {
	switch state {
	case "STARTING", "RUNNING", "CANCELLING":
		return true
	default:
		return false
	}
}

// CancelOrphanRun only uses the run ID kept by Go in the one-use preview. It
// never deletes remote run files and never unlocks on timeout or unknown state.
func (a *App) CancelOrphanRun(recoveryID string) OrphanRunRecoveryResult {
	a.editMu.Lock()
	defer a.editMu.Unlock()
	p := a.orphanRecovery
	a.orphanRecovery = nil
	if p == nil || recoveryID == "" || recoveryID != p.id || time.Now().After(p.expires) || a.current.Status != "OPEN" || a.current.Root != p.projectRoot || a.current.Project == nil || a.current.Project.ID != p.projectID || a.startInFlight || a.runtimeUpdateInFlight || a.installationRuns.knowsRun(p.runID) {
		return orphanRecoveryError("ORPHAN_RUN_RECOVERY_STALE")
	}
	record, err := readLocalRunRecord(a.localRunRecordRoot, p.projectRoot, p.projectID)
	if err != nil || record == nil || record.State != "RUNNING" || record.RunID != p.runID {
		return orphanRecoveryError("ORPHAN_RUN_RECOVERY_STALE")
	}
	binding, err := a.resolveTrustedExecutionConnectionLocked()
	if err != nil || !sameLocalRunNode(*record, binding.node) {
		return orphanRecoveryError("EXECUTION_NODE_BINDING_REQUIRED")
	}
	client, ok := binding.reader.transport.(executionnode.ExecutionClient)
	if !ok {
		return orphanRecoveryError("EXECUTION_NODE_BINDING_REQUIRED")
	}
	ctx, cancel := a.operationContext(90 * time.Second)
	defer cancel()
	run, err := client.GetExecution(ctx, binding.node, record.RunID)
	if err != nil || run.ProjectIdentity != record.ProjectID {
		return orphanRecoveryError("ORPHAN_RUN_IDENTITY_UNVERIFIED")
	}
	if !rebindTerminalRun(run.State) || a.recoveredStopUnconfirmedLocked(record.RunID) {
		if !orphanRunCancellable(run.State) {
			return orphanRecoveryError("ORPHAN_RUN_STATE_UNKNOWN")
		}
		if _, err := client.CancelExecution(ctx, binding.node, record.RunID); err != nil {
			return orphanRecoveryError("ORPHAN_RUN_CANCEL_UNCONFIRMED")
		}
		for {
			run, err = client.GetExecution(ctx, binding.node, record.RunID)
			if err != nil || run.ProjectIdentity != record.ProjectID {
				return orphanRecoveryError("ORPHAN_RUN_IDENTITY_UNVERIFIED")
			}
			if rebindTerminalRun(run.State) {
				break
			}
			if !orphanRunCancellable(run.State) {
				return orphanRecoveryError("ORPHAN_RUN_STATE_UNKNOWN")
			}
			select {
			case <-ctx.Done():
				return OrphanRunRecoveryResult{Status: "CANCELLING", RunID: record.RunID}
			case <-time.After(time.Second):
			}
		}
	}
	record.State, record.TerminalState = "TERMINAL", run.State
	if err := writeLocalRunRecord(a.localRunRecordRoot, *record); err != nil {
		return orphanRecoveryError("LOCAL_RUN_RECORD_UNAVAILABLE")
	}
	if a.recoveredStopUnconfirmedLocked(record.RunID) {
		a.recoveredCancelUnconfirmed = false
		a.recoveredRun.State, a.recoveredRun.TerminalState = "TERMINAL", run.State
	}
	return OrphanRunRecoveryResult{Status: "RESOLVED", RunID: record.RunID, RunState: run.State}
}

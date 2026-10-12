package desktop

import (
	"crypto/rand"
	"encoding/hex"
	"time"

	"platform-installer/internal/executionnode"
)

type orphanRunRecovery struct {
	id          string
	projectRoot string
	projectID   string
	runID       string
	expires     time.Time
}

type OrphanRunRecoveryResult struct {
	Status     string            `json:"status"`
	RecoveryID string            `json:"recoveryId,omitempty"`
	RunID      string            `json:"runId,omitempty"`
	RunState   string            `json:"runState,omitempty"`
	Error      *ProjectOpenError `json:"error,omitempty"`
}

func orphanRecoveryError(code string) OrphanRunRecoveryResult {
	return OrphanRunRecoveryResult{Status: "BLOCKED", Error: &ProjectOpenError{Code: code, Message: projectErrorMessage(code)}}
}

// InspectOrphanRun is read-only. It only offers emergency cancellation when
// an old, locally recorded run is found on its original trusted node and does
// not belong to the current in-memory Start session.
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
	if rebindTerminalRun(run.State) {
		record.State, record.TerminalState = "TERMINAL", run.State
		if err := writeLocalRunRecord(a.localRunRecordRoot, *record); err != nil {
			return orphanRecoveryError("LOCAL_RUN_RECORD_UNAVAILABLE")
		}
		return OrphanRunRecoveryResult{Status: "RESOLVED", RunID: record.RunID, RunState: run.State}
	}
	if !orphanRunCancellable(run.State) {
		return OrphanRunRecoveryResult{Status: "UNAVAILABLE"}
	}
	var nonce [16]byte
	if _, err := rand.Read(nonce[:]); err != nil {
		return orphanRecoveryError("LOCAL_RUN_RECORD_UNAVAILABLE")
	}
	id := hex.EncodeToString(nonce[:])
	a.orphanRecovery = &orphanRunRecovery{id: id, projectRoot: a.current.Root, projectID: record.ProjectID, runID: record.RunID, expires: time.Now().Add(2 * time.Minute)}
	return OrphanRunRecoveryResult{Status: "FOUND", RecoveryID: id, RunID: record.RunID, RunState: run.State}
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
	if !rebindTerminalRun(run.State) {
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
	return OrphanRunRecoveryResult{Status: "RESOLVED", RunID: record.RunID, RunState: run.State}
}

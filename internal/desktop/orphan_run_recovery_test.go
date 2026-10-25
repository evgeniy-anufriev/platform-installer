package desktop

import (
	"context"
	"errors"
	"reflect"
	"sync"
	"testing"
	"time"

	"platform-installer/internal/coreadapter"
	"platform-installer/internal/executionnode"
	"platform-installer/internal/runtimesecret"
)

type orphanRecoveryClientStub struct {
	mu          sync.Mutex
	run         executionnode.ExecutionRun
	cancelCalls int
	cancelErr   error
}

func recoveredObservationFixture(t *testing.T) (*App, *orphanRecoveryClientStub, localRunRecord) {
	t.Helper()
	app, root, _ := rebindTestApp(t)
	storeRoot, record := testLocalRunRecord(t)
	app.localRunRecordRoot = storeRoot
	canonical, err := canonicalRunProjectRoot(root)
	if err != nil {
		t.Fatal(err)
	}
	record.ProjectRoot, record.ProjectID = canonical, app.current.Project.ID
	record.State, record.RunID = "RUNNING", "installer-0123456789abcdef"
	if err := writeLocalRunRecord(storeRoot, record); err != nil {
		t.Fatal(err)
	}
	client := &orphanRecoveryClientStub{run: executionnode.ExecutionRun{RunID: record.RunID, ProjectIdentity: record.ProjectID, State: "RUNNING"}}
	node := executionnode.Node{ID: record.NodeID, Address: record.NodeAddress, Port: record.NodePort, User: record.NodeUser, HostKey: executionnode.HostKeyPolicy{Fingerprint: record.HostKeyFingerprint}}
	app.binding = &executionNodeBinding{node: node, reader: projectReader{transport: client}, service: &executionLifecycleStub{}}
	app.binding.plans = executionnode.NewExecutionService(nil, client)
	app.execution.external = &executionNodeCandidate{hostID: node.ID}
	app.execution.context.SelectionKind = "EXPLICIT_EXTERNAL"
	t.Cleanup(func() { app.editMu.Lock(); app.clearInstallationRunsLocked(); app.editMu.Unlock() })
	return app, client, record
}

func TestAttachOrphanRestoresTrustedObservationWithoutPreparedBundle(t *testing.T) {
	app, client, record := recoveredObservationFixture(t)
	found := app.InspectOrphanRun()
	if found.ProjectRevision != record.ProjectRevision {
		t.Fatalf("revision missing: %+v", found)
	}
	got := app.AttachOrphanRun(found.RecoveryID)
	if got.Status != "READY" || !got.Reconnected || got.ProjectRevision != record.ProjectRevision || got.Run.RunID != record.RunID {
		t.Fatalf("attach: %+v", got)
	}
	if observed := app.GetInstallationRun(record.RunID); observed.Status != "READY" || !observed.Reconnected {
		t.Fatalf("observation requires prepared bundle: %+v", observed)
	}
	if !app.installationRuns.hasActiveRun() {
		t.Fatal("active observation guard missing")
	}
	if got := app.StartApprovedInstallation("unrelated-plan"); got.Status != "BLOCKED" || got.Error.Code != "INSTALLATION_RUN_ACTIVE" {
		t.Fatalf("second Start allowed: %+v", got)
	}
	if got := app.CancelInstallationRun(record.RunID); got.Status != "CANCELLING" || client.cancelCalls != 1 {
		t.Fatalf("existing cancellation unavailable: %+v", got)
	}
	if got := app.AttachOrphanRun(found.RecoveryID); got.Status != "BLOCKED" {
		t.Fatalf("token reused: %+v", got)
	}
}

func TestAttachOrphanRestoresSavedDisplayPlanWithoutNewApproval(t *testing.T) {
	app, _, record := recoveredObservationFixture(t)
	record.Plan = &InstallationPlanView{ID: record.PlanID, ProjectRevision: record.ProjectRevision, ExecutionNodeID: record.NodeID,
		Phases: []InstallationPlanPhase{{ID: "applications", Actions: []InstallationPlanAction{{ID: "apply", Type: "APPLICATION_LIBRARIES_APPLY", Summary: "Apply libraries"}, {ID: "verify", Type: "APPLICATION_LIBRARIES_VERIFY"}}}}}
	if err := writeLocalRunRecord(app.localRunRecordRoot, record); err != nil {
		t.Fatal(err)
	}
	got := app.AttachOrphanRun(app.InspectOrphanRun().RecoveryID)
	if got.Status != "READY" || !reflect.DeepEqual(got.Plan, record.Plan) {
		t.Fatalf("attach lost saved plan: %+v", got)
	}
	if app.installationPlanID != "" {
		t.Fatal("display evidence became a current approved plan")
	}
	observed := app.GetInstallationRun(record.RunID)
	if !reflect.DeepEqual(observed.Plan, record.Plan) {
		t.Fatal("subsequent observation lost display plan")
	}
}

func TestAttachOrphanRejectsChangedCandidate(t *testing.T) {
	for _, change := range []string{"expired", "node", "project", "run", "record"} {
		t.Run(change, func(t *testing.T) {
			app, client, record := recoveredObservationFixture(t)
			found := app.InspectOrphanRun()
			switch change {
			case "expired":
				app.orphanRecovery.expires = time.Now().Add(-time.Second)
			case "node":
				app.binding.node.Address = "192.0.2.99"
			case "project":
				client.run.ProjectIdentity = "foreign-project"
			case "run":
				client.run.RunID = "installer-ffffffff"
			case "record":
				record.State, record.TerminalState = "TERMINAL", "FAILED"
				if err := writeLocalRunRecord(app.localRunRecordRoot, record); err != nil {
					t.Fatal(err)
				}
			}
			if got := app.AttachOrphanRun(found.RecoveryID); got.Status != "BLOCKED" || app.installationRuns.knowsRun(record.RunID) {
				t.Fatalf("changed candidate accepted: %+v", got)
			}
		})
	}
}

func TestAttachOrphanHandlesTerminalRaceAndCachesResult(t *testing.T) {
	app, client, record := recoveredObservationFixture(t)
	found := app.InspectOrphanRun()
	client.run.State = "SUCCEEDED"
	got := app.AttachOrphanRun(found.RecoveryID)
	if got.Status != "READY" || got.Result == nil || !got.Reconnected || app.installationRuns.hasActiveRun() {
		t.Fatalf("terminal race: %+v", got)
	}
	app.binding = nil
	if got := app.GetInstallationRun(record.RunID); got.Result == nil || got.ProjectRevision != record.ProjectRevision {
		t.Fatalf("cached result lost: %+v", got)
	}
	stored, err := readLocalRunRecord(app.localRunRecordRoot, app.current.Root, record.ProjectID)
	if err != nil || stored.State != "TERMINAL" || stored.TerminalState != "SUCCEEDED" {
		t.Fatalf("terminal record %+v, %v", stored, err)
	}
}

func TestRecoveredCredentialRenewalKeepsOriginalIdentityAndRemoteRun(t *testing.T) {
	app, client, record := recoveredObservationFixture(t)
	found := app.InspectOrphanRun()
	if got := app.AttachOrphanRun(found.RecoveryID); got.Status != "READY" {
		t.Fatal(got)
	}
	input := runtimesecret.Input{Username: "foreign-user", SSHMode: "SSH_PASSWORD", SSHPassword: "unit-test-only-password", ElevationMode: runtimesecret.ElevationNone}
	if _, err := app.SetSessionCredential(input); err == nil {
		t.Fatal("changed SSH account accepted")
	}
	input.Username = record.NodeUser
	if _, err := app.SetSessionCredential(input); err != nil {
		t.Fatal(err)
	}
	if !app.recoveredRunActiveLocked() || client.cancelCalls != 0 || app.installationRuns.hasActiveRun() {
		t.Fatal("renewal lost remote-run guard or retained old monitor")
	}
	if got := app.StartApprovedInstallation("unrelated-plan"); got.Error == nil || got.Error.Code != "INSTALLATION_RUN_ACTIVE" {
		t.Fatalf("renewal allowed Start: %+v", got)
	}
}

func TestRecoveredCancelErrorKeepsGuardAndAllowsExistingCancelRetry(t *testing.T) {
	app, client, record := recoveredObservationFixture(t)
	found := app.InspectOrphanRun()
	if got := app.AttachOrphanRun(found.RecoveryID); got.Status != "READY" {
		t.Fatal(got)
	}
	client.mu.Lock()
	client.cancelErr = errors.New("unit stop unconfirmed")
	client.mu.Unlock()
	got := app.CancelInstallationRun(record.RunID)
	if !got.CancelUnconfirmed || got.Error == nil || got.Result != nil {
		t.Fatalf("error not preserved: %+v", got)
	}
	observed := app.GetInstallationRun(record.RunID)
	if !observed.CancelUnconfirmed || observed.Result != nil || !app.recoveredRunActiveLocked() {
		t.Fatalf("terminal journal prematurely released guard: %+v", observed)
	}
	if chosen := app.ChooseRuntimeBundleUpdate(); chosen.Error == nil || chosen.Error.Code != "INSTALLATION_RUN_ACTIVE" {
		t.Fatalf("Choose bypassed unconfirmed stop: %+v", chosen)
	}
	app.bundlePreview = &runtimeBundlePreview{id: "test-preview", projectRoot: app.current.Root, expires: time.Now().Add(time.Minute)}
	if confirmed := app.ConfirmRuntimeBundleUpdate("test-preview"); confirmed.Error == nil || confirmed.Error.Code != "INSTALLATION_RUN_ACTIVE" {
		t.Fatalf("Confirm bypassed unconfirmed stop: %+v", confirmed)
	}
	input := runtimesecret.Input{Username: record.NodeUser, SSHMode: runtimesecret.SSHPassword, SSHPassword: "unit-test-only-password", ElevationMode: runtimesecret.ElevationNone}
	if _, err := app.SetSessionCredential(input); err != nil {
		t.Fatal(err)
	}
	found = app.InspectOrphanRun()
	if found.Status != "FOUND" || found.Error == nil || found.Error.Code != "ORPHAN_RUN_CANCEL_UNCONFIRMED" {
		t.Fatalf("Inspect bypassed unconfirmed stop: %+v", found)
	}
	reattached := app.AttachOrphanRun(found.RecoveryID)
	if !reattached.CancelUnconfirmed || reattached.Result != nil || !app.recoveredRunActiveLocked() {
		t.Fatalf("reattach bypassed unconfirmed stop: %+v", reattached)
	}
	stored, err := readLocalRunRecord(app.localRunRecordRoot, app.current.Root, record.ProjectID)
	if err != nil || stored.State != "RUNNING" {
		t.Fatalf("record unlocked before stop: %+v %v", stored, err)
	}
	client.mu.Lock()
	client.cancelErr = nil
	client.mu.Unlock()
	got = app.CancelInstallationRun(record.RunID)
	if got.Status != "CANCELLING" || got.CancelUnconfirmed || client.cancelCalls != 2 {
		t.Fatalf("existing Cancel retry failed: %+v", got)
	}
}

func (*orphanRecoveryClientStub) BuildProjectSnapshot(context.Context, executionnode.Node, string, map[string]any) (*coreadapter.Snapshot, error) {
	return nil, errors.New("Core must not be called by orphan recovery")
}
func (*orphanRecoveryClientStub) StartExecution(context.Context, executionnode.Node, executionnode.ExecutionStartRequest) (executionnode.ExecutionRun, error) {
	return executionnode.ExecutionRun{}, errors.New("Start must not be called by orphan recovery")
}
func (client *orphanRecoveryClientStub) GetExecution(_ context.Context, _ executionnode.Node, runID string) (executionnode.ExecutionRun, error) {
	client.mu.Lock()
	defer client.mu.Unlock()
	if runID != client.run.RunID {
		return executionnode.ExecutionRun{}, errors.New("unknown run")
	}
	return client.run, nil
}
func (*orphanRecoveryClientStub) GetEvents(_ context.Context, _ executionnode.Node, _ string, after, _ int) (executionnode.ExecutionEventPage, error) {
	return executionnode.ExecutionEventPage{NextSequence: after}, nil
}
func (client *orphanRecoveryClientStub) CancelExecution(_ context.Context, _ executionnode.Node, runID string) (executionnode.ExecutionRun, error) {
	client.mu.Lock()
	defer client.mu.Unlock()
	if runID != client.run.RunID {
		return executionnode.ExecutionRun{}, errors.New("unknown run")
	}
	client.cancelCalls++
	client.run.State = "CANCELLED"
	if client.cancelErr != nil {
		return executionnode.ExecutionRun{}, client.cancelErr
	}
	return client.run, nil
}

func TestOrphanRecoveryRequiresOriginalNodeAndProjectIdentity(t *testing.T) {
	app, root, _ := rebindTestApp(t)
	storeRoot, record := testLocalRunRecord(t)
	app.localRunRecordRoot = storeRoot
	canonical, err := canonicalRunProjectRoot(root)
	if err != nil {
		t.Fatal(err)
	}
	record.ProjectRoot, record.ProjectID = canonical, app.current.Project.ID
	record.State, record.RunID = "RUNNING", "installer-0123456789abcdef"
	if err := writeLocalRunRecord(storeRoot, record); err != nil {
		t.Fatal(err)
	}
	client := &orphanRecoveryClientStub{run: executionnode.ExecutionRun{RunID: record.RunID, ProjectIdentity: "foreign-project", State: "RUNNING"}}
	node := executionnode.Node{ID: record.NodeID, Address: record.NodeAddress, Port: record.NodePort, User: record.NodeUser, HostKey: executionnode.HostKeyPolicy{Fingerprint: record.HostKeyFingerprint}}
	app.binding = &executionNodeBinding{node: node, reader: projectReader{transport: client}, service: &executionLifecycleStub{}}
	app.execution.external = &executionNodeCandidate{hostID: node.ID}
	app.execution.context.SelectionKind = "EXPLICIT_EXTERNAL"
	if got := app.InspectOrphanRun(); got.Status != "UNAVAILABLE" || got.RecoveryID != "" {
		t.Fatalf("foreign project offered cancellation: %+v", got)
	}
	app.binding.node.Address = "192.0.2.99"
	client.run.ProjectIdentity = record.ProjectID
	if got := app.InspectOrphanRun(); got.Status != "UNAVAILABLE" || got.RecoveryID != "" {
		t.Fatalf("changed node offered cancellation: %+v", got)
	}
	app.binding.node.Address = record.NodeAddress
	found := app.InspectOrphanRun()
	if found.Status != "FOUND" || found.RunID != record.RunID || found.RecoveryID == "" {
		t.Fatalf("original run not found: %+v", found)
	}
	resolved := app.CancelOrphanRun(found.RecoveryID)
	if resolved.Status != "RESOLVED" || resolved.RunState != "CANCELLED" || client.cancelCalls != 1 {
		t.Fatalf("cancel=%+v calls=%d", resolved, client.cancelCalls)
	}
	stored, err := readLocalRunRecord(storeRoot, root, record.ProjectID)
	if err != nil || stored == nil || stored.State != "TERMINAL" || stored.RunID != record.RunID {
		t.Fatalf("terminal record=%+v err=%v", stored, err)
	}
	if again := app.CancelOrphanRun(found.RecoveryID); again.Status != "BLOCKED" || client.cancelCalls != 1 {
		t.Fatalf("reused recovery token=%+v", again)
	}
}

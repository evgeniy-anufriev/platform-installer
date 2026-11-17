package desktop

import (
	"context"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/x509"
	"encoding/pem"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"platform-installer/internal/coreadapter"
	"platform-installer/internal/executionnode"
	"platform-installer/internal/projectlifecycle"
	"platform-installer/internal/runtimesecret"
)

type runLifecycleMonitorClient struct {
	mu           sync.Mutex
	run          executionnode.ExecutionRun
	finalEvent   *executionnode.ExecutionEvent
	terminalRead chan struct{}
}

func (c *runLifecycleMonitorClient) StartExecution(context.Context, executionnode.Node, executionnode.ExecutionStartRequest) (executionnode.ExecutionRun, error) {
	return executionnode.ExecutionRun{}, nil
}

func (c *runLifecycleMonitorClient) GetExecution(_ context.Context, _ executionnode.Node, runID string) (executionnode.ExecutionRun, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if runID != c.run.RunID {
		return executionnode.ExecutionRun{}, context.Canceled
	}
	if c.run.State == "SUCCEEDED" && c.terminalRead != nil {
		close(c.terminalRead)
		c.terminalRead = nil
	}
	return c.run, nil
}

func (c *runLifecycleMonitorClient) GetEvents(_ context.Context, _ executionnode.Node, runID string, after, _ int) (executionnode.ExecutionEventPage, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if runID != c.run.RunID {
		return executionnode.ExecutionEventPage{}, context.Canceled
	}
	if c.run.State == "SUCCEEDED" && after == 0 {
		if c.finalEvent == nil {
			// A malformed page ends the observer subscription. The monitor
			// must retry even though GetExecution already reports success.
			return executionnode.ExecutionEventPage{NextSequence: 1}, nil
		}
		return executionnode.ExecutionEventPage{Events: []executionnode.ExecutionEvent{*c.finalEvent}, NextSequence: 1}, nil
	}
	return executionnode.ExecutionEventPage{Events: []executionnode.ExecutionEvent{}, NextSequence: after}, nil
}

func (c *runLifecycleMonitorClient) CancelExecution(context.Context, executionnode.Node, string) (executionnode.ExecutionRun, error) {
	return executionnode.ExecutionRun{}, nil
}

func (*runLifecycleMonitorClient) BuildProjectSnapshot(context.Context, executionnode.Node, string, map[string]any) (*coreadapter.Snapshot, error) {
	return nil, nil
}

func TestActiveRunMonitorReleasesSSHHoldAfterFinalEventAndCachesResult(t *testing.T) {
	cacheRoot := t.TempDir()
	t.Setenv("LOCALAPPDATA", cacheRoot)
	t.Setenv("XDG_CACHE_HOME", cacheRoot)
	projectRoot := t.TempDir()
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	der, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		t.Fatal(err)
	}
	keyPath := filepath.Join(t.TempDir(), "exec.pem")
	if err := os.WriteFile(keyPath, pem.EncodeToMemory(&pem.Block{Type: "PRIVATE KEY", Bytes: der}), 0600); err != nil {
		t.Fatal(err)
	}
	credentialBinding := runtimesecret.Binding{Root: projectRoot, ID: "project-one"}
	secrets := runtimesecret.NewBroker()
	if _, err := secrets.Set(credentialBinding, runtimesecret.Input{Username: "installer", SSHMode: runtimesecret.SSHPrivateKey, PrivateKeyPath: keyPath, ElevationMode: runtimesecret.ElevationNone}); err != nil {
		t.Fatal(err)
	}
	identity, err := secrets.CurrentExecutionIdentity(credentialBinding)
	if err != nil {
		t.Fatal(err)
	}
	const runID = "installer-123"
	if err := secrets.ReserveExecutionIdentityForStart(credentialBinding, "plan-one", identity); err != nil {
		t.Fatal(err)
	}
	if err := secrets.ConfirmExecutionIdentityRun(credentialBinding, "plan-one", runID); err != nil {
		t.Fatal(err)
	}
	runRoot := t.TempDir()
	canonicalRoot, err := canonicalRunProjectRoot(projectRoot)
	if err != nil {
		t.Fatal(err)
	}
	// Simulate Start accepted remotely while the local RUNNING record write
	// failed. The monitor must recover the exact run ID into this PENDING row.
	record := localRunRecord{Version: localRunRecordVersion, ProjectRoot: canonicalRoot, ProjectID: "project-one", ProjectRevision: "revision-one", PlanID: "plan-one", NodeID: "node1", NodeAddress: "192.0.2.10", NodePort: 22, NodeUser: "installer", HostKeyFingerprint: "SHA256:approved", State: "PENDING"}
	if !validLocalRunRecord(record) {
		t.Fatalf("test local run record is invalid: %+v", record)
	}
	if err := writeLocalRunRecord(runRoot, record); err != nil {
		t.Fatal(err)
	}
	terminalRead := make(chan struct{})
	client := &runLifecycleMonitorClient{
		run:          executionnode.ExecutionRun{RunID: runID, ProjectIdentity: "project-one", State: "RUNNING"},
		terminalRead: terminalRead,
	}
	runtimeRoot, err := installationRuntimeRoot()
	if err != nil {
		t.Fatalf("run monitor runtime root: %v", err)
	}
	if _, err := executionnode.NewRunObserver(client, runtimeRoot); err != nil {
		t.Fatalf("run monitor observer: %v", err)
	}
	node := executionnode.Node{ID: "node1", Address: "192.0.2.10", Port: 22, User: "installer", CredentialRef: "runtime:ssh", HostKey: executionnode.HostKeyPolicy{State: "TRUSTED", Fingerprint: "SHA256:approved"}}
	registry := newInstallationRunRegistry()
	registry.rememberRun(runID)
	ctx, ok := registry.startMonitor(runID)
	if !ok {
		t.Fatal("failed to establish app-owned run monitor")
	}
	app := &App{
		installationRuns:       registry,
		secrets:                secrets,
		localRunRecordRoot:     runRoot,
		installationGeneration: 7,
		current:                ProjectOpenResult{Status: "OPEN", Root: projectRoot, Project: &projectlifecycle.Project{ID: "project-one"}},
	}
	binding := &executionNodeBinding{node: node, reader: projectReader{transport: client}}
	captured := installationStartContext{generation: 7, root: projectRoot, projectID: "project-one", planID: "plan-one", nodeID: "node1"}
	defer func() {
		app.editMu.Lock()
		app.clearInstallationRunsLocked()
		app.editMu.Unlock()
	}()
	if _, err := secrets.CurrentExecutionIdentity(credentialBinding); err != nil {
		t.Fatalf("active run did not retain SSH identity: %v", err)
	}
	client.run.State, client.run.Sequence = "SUCCEEDED", 1
	go app.monitorInstallationRun(ctx, binding, captured, runID)
	select {
	case <-terminalRead:
	case <-time.After(3 * time.Second):
		t.Fatal("terminal status was not read")
	}
	if !secrets.HasRunExecutionIdentityHold(credentialBinding) {
		t.Fatal("SSH identity released before the final event")
	}
	client.mu.Lock()
	client.finalEvent = &executionnode.ExecutionEvent{
		APIVersion:  "platform.installer/event/v1alpha1",
		Kind:        "ExecutionEvent",
		RunID:       runID,
		Sequence:    1,
		Timestamp:   "2026-09-04T12:00:00Z",
		EventType:   "TASK_COMPLETED",
		Status:      "SUCCESS",
		Host:        "node1",
		Task:        &executionnode.ExecutionEventTask{UUID: "task-1", Role: "platform.core", Name: "Post-install completed"},
		SafeMessage: "Ansible task completed",
		Redaction:   executionnode.ExecutionRedaction{Applied: true, Fields: []string{}},
	}
	client.mu.Unlock()
	deadline := time.Now().Add(4 * time.Second)
	for time.Now().Before(deadline) && registry.hasActiveRun() {
		time.Sleep(10 * time.Millisecond)
	}
	if registry.hasActiveRun() {
		t.Fatal("monitor did not stop after authoritative terminal state")
	}
	saved, err := readLocalRunRecord(runRoot, projectRoot, "project-one")
	if err != nil || saved == nil || saved.State != "TERMINAL" || saved.RunID != runID || saved.TerminalState != "SUCCEEDED" {
		t.Fatalf("monitor did not repair pending local run record: record=%+v err=%v", saved, err)
	}
	if secrets.HasRunExecutionIdentityHold(credentialBinding) {
		t.Fatal("SSH identity hold remained after terminal state")
	}
	result := app.GetInstallationRun(runID)
	if result.Status != "READY" || result.Run == nil || result.Run.State != "SUCCEEDED" || result.Run.Sequence != 1 || result.Result == nil || result.Result.State != "SUCCEEDED" {
		t.Fatalf("cached terminal result unavailable after credential release: %+v", result)
	}
}

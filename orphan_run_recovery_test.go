package main

import (
	"context"
	"errors"
	"testing"

	"platform-installer/internal/coreadapter"
	"platform-installer/internal/executionnode"
)

type orphanRecoveryClientStub struct {
	run         executionnode.ExecutionRun
	cancelCalls int
}

func (*orphanRecoveryClientStub) BuildProjectSnapshot(context.Context, executionnode.Node, string, map[string]any) (*coreadapter.Snapshot, error) {
	return nil, errors.New("Core must not be called by orphan recovery")
}
func (*orphanRecoveryClientStub) StartExecution(context.Context, executionnode.Node, executionnode.ExecutionStartRequest) (executionnode.ExecutionRun, error) {
	return executionnode.ExecutionRun{}, errors.New("Start must not be called by orphan recovery")
}
func (client *orphanRecoveryClientStub) GetExecution(_ context.Context, _ executionnode.Node, runID string) (executionnode.ExecutionRun, error) {
	if runID != client.run.RunID {
		return executionnode.ExecutionRun{}, errors.New("unknown run")
	}
	return client.run, nil
}
func (*orphanRecoveryClientStub) GetEvents(context.Context, executionnode.Node, string, int, int) (executionnode.ExecutionEventPage, error) {
	return executionnode.ExecutionEventPage{}, errors.New("events must not be called by orphan recovery")
}
func (client *orphanRecoveryClientStub) CancelExecution(_ context.Context, _ executionnode.Node, runID string) (executionnode.ExecutionRun, error) {
	if runID != client.run.RunID {
		return executionnode.ExecutionRun{}, errors.New("unknown run")
	}
	client.cancelCalls++
	client.run.State = "CANCELLED"
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

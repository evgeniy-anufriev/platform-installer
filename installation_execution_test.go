package main

import (
	"encoding/json"
	"errors"
	"strings"
	"testing"

	"platform-installer/internal/executionnode"
)

func TestInstallationEventViewIsClosedAndRedacted(t *testing.T) {
	elapsed := 7
	view := installationEventView(executionnode.ExecutionEvent{
		RunID: "installer-123", Sequence: 2, Timestamp: "2026-09-22T10:00:00Z", EventType: "TASK_COMPLETED", Status: "SUCCESS",
		SafeMessage: "safe", ElapsedMillis: &elapsed, Redaction: executionnode.ExecutionRedaction{Applied: true, Fields: []string{"stdout"}},
		Error: &executionnode.ExecutionEventError{Code: "FAILED", Summary: "safe summary", DiagnosticRef: "/private/diagnostic"},
	})
	encoded, err := json.Marshal(view)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(encoded), "diagnosticRef") || strings.Contains(string(encoded), "/private/") || strings.Contains(string(encoded), "stdout") {
		t.Fatalf("private event data escaped Wails projection: %s", encoded)
	}
	if !view.Redacted || view.ErrorCode != "FAILED" || view.ElapsedMilliseconds == nil {
		t.Fatalf("safe event fields were not preserved: %#v", view)
	}
}

func TestInstallationEventViewPreservesOnlyUnredactedTaskName(t *testing.T) {
	base := executionnode.ExecutionEvent{
		RunID: "installer-123", Sequence: 2, EventType: "TASK_STARTED", Status: "RUNNING",
		SafeMessage: "Ansible task started", Task: &executionnode.ExecutionEventTask{UUID: "task-1", Role: "platform.vault", Name: "Require host swap disabled for Vault Raft"},
		Redaction: executionnode.ExecutionRedaction{Applied: true, Fields: []string{"stdout"}},
	}
	view := installationEventView(base)
	if view.Task == nil || view.Task.Name != base.Task.Name || !view.Redacted {
		t.Fatalf("safe task name lost from redacted event: %#v", view)
	}
	base.Task.Name = ""
	base.Redaction.Fields = []string{"task.name"}
	view = installationEventView(base)
	if view.Task != nil || !view.Redacted || view.SafeMessage != "Ansible task started" {
		t.Fatalf("redacted task name escaped or fallback lost: %#v", view)
	}
}

func TestInstallationObserverDiagnosticIsClosed(t *testing.T) {
	if got := installationObserverDiagnostic(errors.New("ssh failed /private/path secret")); got != observabilityDegraded {
		t.Fatalf("hostile observer error became %q", got)
	}
	if got := installationObserverDiagnostic(&executionnode.ObserverError{Code: executionnode.ObserverHistoryTruncated}); got != observerHistoryGap {
		t.Fatalf("known observer error became %q", got)
	}
}

func TestInstallationRunRegistryIsBoundedAndCleanupDoesNotCancelExecution(t *testing.T) {
	registry := newInstallationRunRegistry()
	registry.rememberRun("installer-123")
	if !registry.knowsRun("installer-123") || registry.knowsRun("installer-456") {
		t.Fatal("run ownership was not tracked as a current-session boundary")
	}
	stopped := 0
	for i := 0; i < maxInstallationSubscriptions; i++ {
		id := string(rune('a' + i))
		if !registry.add(id, installationRunSubscription{cancel: func() { stopped++ }}) {
			t.Fatalf("subscription %d rejected before bound", i)
		}
	}
	if registry.add("overflow", installationRunSubscription{cancel: func() {}}) {
		t.Fatal("registry accepted subscription beyond bound")
	}
	registry.clear()
	if stopped != maxInstallationSubscriptions {
		t.Fatalf("cleanup stopped %d local subscriptions, want %d", stopped, maxInstallationSubscriptions)
	}
	if registry.knowsRun("installer-123") {
		t.Fatal("project/session cleanup retained a run identity")
	}
}

func TestInstallationRunPublicationCannotRebindAfterGenerationSwitch(t *testing.T) {
	app := &App{installationRuns: newInstallationRunRegistry(), installationGeneration: 11}
	app.editMu.Lock()
	switchAttempted := make(chan struct{})
	switchDone := make(chan struct{})
	go func() {
		close(switchAttempted)
		app.editMu.Lock()
		app.installationGeneration++
		app.installationRuns.clear()
		app.editMu.Unlock()
		close(switchDone)
	}()
	<-switchAttempted
	// This mirrors the final Start publication: the generation guard and run
	// registration share editMu, while replacement needs that same lock.
	if !app.publishKnownInstallationRunLocked(11, "installer-old") {
		app.editMu.Unlock()
		t.Fatal("run publication rejected its own generation")
	}
	select {
	case <-switchDone:
		app.editMu.Unlock()
		t.Fatal("generation switch entered between guarded publication steps")
	default:
	}
	app.editMu.Unlock()
	<-switchDone
	if app.installationRuns.knowsRun("installer-old") {
		t.Fatal("old run was rebound after project-generation replacement")
	}
}

func TestInstallationSubscriptionPublicationCannotSurviveGenerationSwitch(t *testing.T) {
	app := &App{installationRuns: newInstallationRunRegistry(), installationGeneration: 17}
	app.installationRuns.rememberRun("installer-old")
	stopped := 0
	app.editMu.Lock()
	switchAttempted := make(chan struct{})
	switchDone := make(chan struct{})
	go func() {
		close(switchAttempted)
		app.editMu.Lock()
		app.installationGeneration++
		app.installationRuns.clear()
		app.editMu.Unlock()
		close(switchDone)
	}()
	<-switchAttempted
	current := app.installationGeneration == 17 && app.installationRuns.knowsRun("installer-old")
	added := false
	if current {
		added = app.publishInstallationSubscriptionLocked(17, "installer-old", "subscription-old", installationRunSubscription{cancel: func() { stopped++ }})
	}
	select {
	case <-switchDone:
		app.editMu.Unlock()
		t.Fatal("generation switch entered between guarded subscription steps")
	default:
	}
	app.editMu.Unlock()
	<-switchDone
	if !current || !added {
		t.Fatal("initial subscription publication failed")
	}
	if app.installationRuns.knowsRun("installer-old") {
		t.Fatal("old run remained known after generation switch")
	}
	if stopped != 1 {
		t.Fatalf("old subscription cleanup count = %d, want 1", stopped)
	}
}

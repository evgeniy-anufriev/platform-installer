package desktop

import (
	"errors"
	"testing"

	"platform-installer/internal/projectlifecycle"
)

func TestExecutionNodeContextDeterministicAndExplicitSelection(t *testing.T) {
	store := newExecutionNodeContextStore(nil, nil)
	store.bind("project", "project-a", map[string]map[string]any{
		"node2": {"ansibleHost": "192.0.2.12"},
		"node1": {"ansibleHost": "192.0.2.11"},
	})
	if got := store.context; got.Status != executionNodeNotPrepared || got.SelectedHostID != "node1" || got.SelectionSource != "AUTO_FIRST_ELIGIBLE" {
		t.Fatalf("initial context=%+v", got)
	}
	if err := store.selectProjectServer("node2"); err != nil {
		t.Fatal(err)
	}
	if got := store.context; got.SelectedHostID != "node2" || got.SelectionSource != "EXPLICIT" {
		t.Fatalf("explicit context=%+v", got)
	}
	if err := store.selectProjectServer("missing"); !errors.Is(err, errExecutionNodeSelectionInvalid) {
		t.Fatalf("invalid selection error=%v", err)
	}
}

func TestExecutionNodeContextDraftSelectionClearsOnDiscard(t *testing.T) {
	store := newExecutionNodeContextStore(nil, nil)
	store.bind("project", "project-a", nil)
	store.applyCommand("node1", "CreateServer", "192.0.2.10")
	if got := store.context; got.SelectedHostID != "node1" || got.Status != executionNodeNotPrepared {
		t.Fatalf("draft context=%+v", got)
	}
	store.discardDraft(nil)
	if got := store.context; got.Status != executionNodeNotConfigured || got.SelectedHostID != "" {
		t.Fatalf("discard context=%+v", got)
	}
}

func TestExecutionNodeContextExternalDoesNotBecomeTransport(t *testing.T) {
	store := newExecutionNodeContextStore(&executionNodeCandidate{label: "desktop-node · 192.0.2.1"}, nil)
	store.bind("project", "project-a", map[string]map[string]any{"node1": {"ansibleHost": "192.0.2.10"}})
	if got := store.context; got.SelectionKind != "EXPLICIT_EXTERNAL" || got.SelectedHostID != "" || got.Status != executionNodeNotPrepared {
		t.Fatalf("external context=%+v", got)
	}
	if err := store.selectProjectServer("node1"); err != nil {
		t.Fatal(err)
	}
	if got := store.context; got.SelectionKind != "PROJECT_SERVER" || got.SelectedHostID != "node1" {
		t.Fatalf("manual project context=%+v", got)
	}
}

func TestAppExecutionNodeContextRequiresOpenProject(t *testing.T) {
	app := NewApp(unavailableProjectReader{}, lifecycleStub{})
	if _, err := app.GetExecutionNodeContext(); projectErrorCode(err) != "PROJECT_NOT_OPEN" {
		t.Fatalf("GetExecutionNodeContext error=%v", err)
	}
	project := &projectlifecycle.Project{ID: "project-aaaaaaaaaaaaaaaa", Name: "Test"}
	app.current = ProjectOpenResult{Status: "OPEN", Root: t.TempDir(), Project: project}
	app.execution.bind(app.current.Root, project.ID, map[string]map[string]any{"node1": {"ansibleHost": "192.0.2.10"}})
	context, err := app.SelectExecutionNode("node1")
	if err != nil || context.SelectedHostID != "node1" || context.Status != executionNodeNotPrepared {
		t.Fatalf("context=%+v err=%v", context, err)
	}
}

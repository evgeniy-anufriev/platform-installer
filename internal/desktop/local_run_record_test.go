package desktop

import (
	"os"
	"path/filepath"
	"platform-installer/internal/executionnode"
	"reflect"
	"strings"
	"testing"
)

func testLocalRunRecord(t *testing.T) (string, localRunRecord) {
	t.Helper()
	project := t.TempDir()
	canonical, err := canonicalRunProjectRoot(project)
	if err != nil {
		t.Fatal(err)
	}
	return t.TempDir(), localRunRecord{Version: 1, ProjectRoot: canonical, ProjectID: "project-aaaaaaaaaaaaaaaa", ProjectRevision: "sha256:revision", PlanID: "plan-one", NodeID: "node1", NodeAddress: "192.0.2.1", NodePort: 22, NodeUser: "operator", HostKeyFingerprint: "SHA256:approved", State: "PENDING"}
}

func TestLocalRunRecordSurvivesReopenAndTransitions(t *testing.T) {
	root, record := testLocalRunRecord(t)
	if got, err := readLocalRunRecord(root, record.ProjectRoot, record.ProjectID); err != nil || got != nil {
		t.Fatalf("absent=%+v err=%v", got, err)
	}
	for _, state := range []string{"PENDING", "RUNNING", "TERMINAL"} {
		record.State = state
		if state != "PENDING" {
			record.RunID = "installer-0123456789abcdef"
		}
		if state == "TERMINAL" {
			record.TerminalState = "SUCCEEDED"
		}
		if err := writeLocalRunRecord(root, record); err != nil {
			t.Fatal(err)
		}
		got, err := readLocalRunRecord(root, record.ProjectRoot, record.ProjectID)
		if err != nil || got == nil || *got != record {
			t.Fatalf("state=%s got=%+v err=%v", state, got, err)
		}
	}
}

func TestLocalRunRecordRetainsDisplayPlanAcrossReopenAndUnsentStart(t *testing.T) {
	root, record := testLocalRunRecord(t)
	record.Plan = &InstallationPlanView{ID: record.PlanID, ProjectRevision: record.ProjectRevision, ExecutionNodeID: record.NodeID,
		Phases: []InstallationPlanPhase{{ID: "applications", Actions: []InstallationPlanAction{{ID: "apply", Summary: strings.Repeat("safe display text", 600),
			ProgressSteps: []executionnode.DeploymentProgressStep{{ID: "applications:library:sdku", Summary: "SDKU"}}}}}}}
	if err := writeLocalRunRecord(root, record); err != nil {
		t.Fatal(err)
	}
	got, err := readLocalRunRecord(root, record.ProjectRoot, record.ProjectID)
	if err != nil || got == nil || !reflect.DeepEqual(*got, record) {
		t.Fatalf("display plan lost: %v", err)
	}
	if err := restoreLocalRunRecordAfterUnsentStart(root, record, nil); err != nil {
		t.Fatalf("snapshot changed reservation comparison: %v", err)
	}
	for _, field := range []string{"id", "revision", "node"} {
		t.Run(field, func(t *testing.T) {
			copy := *record.Plan
			switch field {
			case "id":
				copy.ID = "other"
			case "revision":
				copy.ProjectRevision = "other"
			case "node":
				copy.ExecutionNodeID = "other"
			}
			invalid := record
			invalid.Plan = &copy
			if err := writeLocalRunRecord(root, invalid); err == nil {
				t.Fatal("foreign display plan accepted")
			}
		})
	}
}

func TestRestoreLocalRunRecordAfterUnsentStart(t *testing.T) {
	for _, withPrevious := range []bool{false, true} {
		t.Run(map[bool]string{false: "remove_new_reservation", true: "restore_previous_terminal"}[withPrevious], func(t *testing.T) {
			root, pending := testLocalRunRecord(t)
			var previous *localRunRecord
			if withPrevious {
				old := pending
				old.State, old.RunID, old.TerminalState = "TERMINAL", "installer-0123456789abcdef", "FAILED"
				if err := writeLocalRunRecord(root, old); err != nil {
					t.Fatal(err)
				}
				previous = &old
			}
			if err := writeLocalRunRecord(root, pending); err != nil {
				t.Fatal(err)
			}
			if err := restoreLocalRunRecordAfterUnsentStart(root, pending, previous); err != nil {
				t.Fatal(err)
			}
			got, err := readLocalRunRecord(root, pending.ProjectRoot, pending.ProjectID)
			if err != nil {
				t.Fatal(err)
			}
			if !withPrevious && got != nil {
				t.Fatalf("new pending record remained: %+v", got)
			}
			if withPrevious && (got == nil || *got != *previous) {
				t.Fatalf("previous record not restored: got=%+v want=%+v", got, previous)
			}
		})
	}
}

func TestRestoreLocalRunRecordRequiresExactPendingReservation(t *testing.T) {
	root, pending := testLocalRunRecord(t)
	changed := pending
	changed.PlanID = "another-plan"
	if err := writeLocalRunRecord(root, changed); err != nil {
		t.Fatal(err)
	}
	if err := restoreLocalRunRecordAfterUnsentStart(root, pending, nil); err == nil {
		t.Fatal("changed local reservation was cleared")
	}
	got, err := readLocalRunRecord(root, changed.ProjectRoot, changed.ProjectID)
	if err != nil || got == nil || *got != changed {
		t.Fatalf("record changed after rejected cleanup: got=%+v err=%v", got, err)
	}
}

func TestLocalRunRecordRejectsInvalidOrForeignState(t *testing.T) {
	root, record := testLocalRunRecord(t)
	path, err := localRunRecordPath(root, record.ProjectRoot, record.ProjectID)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(`{"version":1,"state":"TERMINAL"}`), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := readLocalRunRecord(root, record.ProjectRoot, record.ProjectID); err == nil {
		t.Fatal("malformed record accepted")
	}
	if err := os.Remove(path); err != nil {
		t.Fatal(err)
	}
	record.ProjectID = "project-other"
	if _, err := readLocalRunRecord(root, record.ProjectRoot, record.ProjectID); err != nil {
		t.Fatal(err)
	}
	record.State = "RUNNING"
	if err := writeLocalRunRecord(root, record); err == nil {
		t.Fatal("running record without run ID accepted")
	}
	record.State = "PENDING"
	record.RunID = "installer-0123"
	if err := writeLocalRunRecord(root, record); err == nil {
		t.Fatal("pending record with run ID accepted")
	}
}

func TestLocalRunRecordRejectsSymlink(t *testing.T) {
	root, record := testLocalRunRecord(t)
	path, err := localRunRecordPath(root, record.ProjectRoot, record.ProjectID)
	if err != nil {
		t.Fatal(err)
	}
	target := filepath.Join(root, "foreign.json")
	if err := os.WriteFile(target, []byte(`{}`), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(target, path); err != nil {
		t.Skipf("symlink unavailable: %v", err)
	}
	if _, err := readLocalRunRecord(root, record.ProjectRoot, record.ProjectID); err == nil {
		t.Fatal("symlink record accepted")
	}
	if err := writeLocalRunRecord(root, record); err == nil {
		t.Fatal("symlink destination accepted")
	}
}

func TestLocalRunRecordRejectsSymlinkedStore(t *testing.T) {
	_, record := testLocalRunRecord(t)
	base := t.TempDir()
	target := t.TempDir()
	store := filepath.Join(base, "records")
	if err := os.Symlink(target, store); err != nil {
		t.Skipf("directory symlink unavailable: %v", err)
	}
	if err := writeLocalRunRecord(store, record); err == nil {
		t.Fatal("symlinked record store accepted for write")
	}
	if _, err := readLocalRunRecord(store, record.ProjectRoot, record.ProjectID); err == nil {
		t.Fatal("symlinked record store accepted for read")
	}
}

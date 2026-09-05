package executionnode

import (
	"encoding/json"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

const testMirrorFingerprint = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

func validEvent(runID string, sequence int) ExecutionEvent {
	return ExecutionEvent{
		APIVersion:  "platform.installer/event/v1alpha1",
		Kind:        "ExecutionEvent",
		RunID:       runID,
		Sequence:    sequence,
		Timestamp:   "2026-09-04T12:00:00Z",
		EventType:   "TASK_COMPLETED",
		Status:      "SUCCESS",
		Host:        "node1",
		Task:        &ExecutionEventTask{UUID: "task-1", Role: "platform.kafka", Name: "Safe task"},
		SafeMessage: "Ansible task completed",
		Redaction:   ExecutionRedaction{Applied: true, Fields: []string{}},
	}
}

func TestEventMirrorAppendDuplicateAndTrailingRecovery(t *testing.T) {
	root := t.TempDir()
	runID := "installer-100"
	mirror, err := OpenEventMirror(root, runID, testMirrorFingerprint)
	if err != nil {
		t.Fatal(err)
	}
	first := validEvent(runID, 1)
	if appended, err := mirror.Append(first); err != nil || !appended {
		t.Fatalf("append=%v err=%v", appended, err)
	}
	if appended, err := mirror.Append(first); err != nil || appended {
		t.Fatalf("duplicate append=%v err=%v", appended, err)
	}
	conflict := first
	conflict.Status = "FAILED"
	if _, err := mirror.Append(conflict); err == nil || err.Error() != "EXECUTION_MIRROR_DUPLICATE_CONFLICT" {
		t.Fatalf("conflict err=%v", err)
	}
	if _, err := mirror.Append(validEvent(runID, 3)); err == nil || err.Error() != "EXECUTION_MIRROR_SEQUENCE_GAP" {
		t.Fatalf("gap err=%v", err)
	}
	path := mirror.Path()
	if err := mirror.Close(); err != nil {
		t.Fatal(err)
	}
	file, err := os.OpenFile(path, os.O_APPEND|os.O_WRONLY, 0o600)
	if err != nil {
		t.Fatal(err)
	}
	_, _ = file.WriteString(`{"sequence":2`)
	_ = file.Close()
	recovered, err := OpenEventMirror(root, runID, testMirrorFingerprint)
	if err != nil {
		t.Fatal(err)
	}
	defer recovered.Close()
	if recovered.LastSequence() != 1 {
		t.Fatalf("last=%d", recovered.LastSequence())
	}
	if appended, err := recovered.Append(validEvent(runID, 2)); err != nil || !appended {
		t.Fatalf("recovered append=%v err=%v", appended, err)
	}
	data, _ := os.ReadFile(path)
	if strings.Count(string(data), "\n") != 2 || !strings.HasSuffix(string(data), "\n") {
		t.Fatalf("mirror=%q", data)
	}
	if runtime.GOOS != "windows" {
		info, _ := os.Stat(path)
		if info.Mode().Perm() != 0o600 {
			t.Fatalf("mode=%o", info.Mode().Perm())
		}
	}
}

func TestEventMirrorRejectsSymlinkAndCompleteCorruption(t *testing.T) {
	root := t.TempDir()
	outside := t.TempDir()
	if err := os.Symlink(outside, filepath.Join(root, "executions")); err != nil {
		if runtime.GOOS == "windows" {
			t.Skipf("symlink unavailable: %v", err)
		}
		t.Fatal(err)
	}
	if _, err := OpenEventMirror(root, "installer-101", testMirrorFingerprint); err == nil || err.Error() != "EXECUTION_MIRROR_PATH_UNSAFE" {
		t.Fatalf("symlink err=%v", err)
	}

	clean := t.TempDir()
	directory := filepath.Join(clean, "executions", "installer-102")
	if err := os.MkdirAll(directory, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(directory, "events.jsonl"), []byte("not-json\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := OpenEventMirror(clean, "installer-102", testMirrorFingerprint); err == nil || err.Error() != "EXECUTION_MIRROR_CORRUPT" {
		t.Fatalf("corruption err=%v", err)
	}
}

func TestEventMirrorWriteFailureIsLocal(t *testing.T) {
	mirror, err := OpenEventMirror(t.TempDir(), "installer-103", testMirrorFingerprint)
	if err != nil {
		t.Fatal(err)
	}
	defer mirror.Close()
	if err := mirror.file.Close(); err != nil {
		t.Fatal(err)
	}
	if _, err := mirror.Append(validEvent("installer-103", 1)); err == nil || err.Error() != "EXECUTION_MIRROR_WRITE_FAILED" {
		t.Fatalf("write err=%v", err)
	}
}

func TestEventMirrorRejectsDifferentRunAndInvalidRuntimeToken(t *testing.T) {
	root := t.TempDir()
	for _, invalid := range []string{"installer-", "installer-not-digits", "../installer-1"} {
		if _, err := EventMirrorPath(root, invalid); err == nil {
			t.Fatalf("invalid run ID accepted: %q", invalid)
		}
	}
	mirror, err := OpenEventMirror(root, "installer-105", testMirrorFingerprint)
	if err != nil {
		t.Fatal(err)
	}
	defer mirror.Close()
	if _, err := mirror.Append(validEvent("installer-106", 1)); err == nil || err.Error() != "EXECUTION_MIRROR_EVENT_INVALID" {
		t.Fatalf("different run err=%v", err)
	}
}

func TestEventMirrorHasExclusiveWriterButRemainsReadable(t *testing.T) {
	root := t.TempDir()
	runID := "installer-107"
	first, err := OpenEventMirror(root, runID, testMirrorFingerprint)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := first.Append(validEvent(runID, 1)); err != nil {
		t.Fatal(err)
	}
	if data, err := os.ReadFile(first.Path()); err != nil || !strings.Contains(string(data), `"sequence":1`) {
		t.Fatalf("active mirror is not tail-readable: data=%q err=%v", data, err)
	}
	if _, err := OpenEventMirror(root, runID, testMirrorFingerprint); err == nil || err.Error() != "EXECUTION_MIRROR_IN_USE" {
		t.Fatalf("second writer err=%v", err)
	}
	if err := first.Close(); err != nil {
		t.Fatal(err)
	}
	second, err := OpenEventMirror(root, runID, testMirrorFingerprint)
	if err != nil {
		t.Fatal(err)
	}
	defer second.Close()
	if second.LastSequence() != 1 {
		t.Fatalf("restart sequence=%d", second.LastSequence())
	}
}

func TestEventMirrorCanStartAtExplicitRemoteEarliestSequence(t *testing.T) {
	root := t.TempDir()
	runID := "installer-108"
	mirror, err := OpenEventMirror(root, runID, testMirrorFingerprint)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := mirror.Append(validEvent(runID, 5)); err != nil {
		t.Fatal(err)
	}
	if err := mirror.Close(); err != nil {
		t.Fatal(err)
	}
	recovered, err := OpenEventMirror(root, runID, testMirrorFingerprint)
	if err != nil {
		t.Fatal(err)
	}
	defer recovered.Close()
	if values := recovered.Events(0); recovered.LastSequence() != 5 || len(values) != 1 || values[0].Sequence != 5 {
		t.Fatalf("last=%d values=%v", recovered.LastSequence(), values)
	}
}

func TestEventMirrorCreatesMissingRuntimeRootSafely(t *testing.T) {
	root := filepath.Join(t.TempDir(), "runtime")
	mirror, err := OpenEventMirror(root, "installer-109", testMirrorFingerprint)
	if err != nil {
		t.Fatal(err)
	}
	defer mirror.Close()
	if _, err := os.Stat(mirror.Path()); err != nil {
		t.Fatal(err)
	}
}

func TestEventMirrorRejectsSequentialDifferentNodeIdentity(t *testing.T) {
	root := t.TempDir()
	runID := "installer-110"
	first, err := OpenEventMirror(root, runID, testMirrorFingerprint)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := first.Append(validEvent(runID, 1)); err != nil {
		t.Fatal(err)
	}
	if err := first.Close(); err != nil {
		t.Fatal(err)
	}
	other := "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
	if _, err := OpenEventMirror(root, runID, other); err == nil || err.Error() != "EXECUTION_MIRROR_NODE_CONFLICT" {
		t.Fatalf("node conflict err=%v", err)
	}
	data, err := os.ReadFile(filepath.Join(root, "executions", runID, "events.jsonl"))
	if err != nil || !strings.Contains(string(data), `"sequence":1`) {
		t.Fatalf("existing mirror changed: data=%q err=%v", data, err)
	}
}

func TestTypedEventJSONNeverCarriesUnknownPayload(t *testing.T) {
	var raw map[string]any
	if err := json.Unmarshal([]byte(`{"events":[{"apiVersion":"platform.installer/event/v1alpha1","kind":"ExecutionEvent","runId":"installer-104","sequence":1,"timestamp":"2026-09-04T12:00:00Z","eventType":"TASK_COMPLETED","status":"SUCCESS","task":{"uuid":"task-1"},"safeMessage":"safe","redaction":{"applied":true,"fields":[]},"unknownSecret":"must-not-survive"}],"nextSequence":1,"hasMore":false}`), &raw); err != nil {
		t.Fatal(err)
	}
	page, err := decodeEventPage(raw, "installer-104", 0, 256)
	if err != nil {
		t.Fatal(err)
	}
	encoded, _ := json.Marshal(page.Events[0])
	if strings.Contains(string(encoded), "unknownSecret") || strings.Contains(string(encoded), "must-not-survive") {
		t.Fatalf("typed event retained unknown payload: %s", encoded)
	}
}

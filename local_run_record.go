package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"
)

const localRunRecordVersion = 1

// This is operational start evidence, never desired project state. The
// initial PENDING record is durable before a remote Start can be sent.
type localRunRecord struct {
	Version            int    `json:"version"`
	ProjectRoot        string `json:"projectRoot"`
	ProjectID          string `json:"projectId"`
	ProjectRevision    string `json:"projectRevision"`
	PlanID             string `json:"planId"`
	NodeID             string `json:"nodeId"`
	NodeAddress        string `json:"nodeAddress"`
	NodePort           uint16 `json:"nodePort"`
	NodeUser           string `json:"nodeUser"`
	HostKeyFingerprint string `json:"hostKeyFingerprint"`
	State              string `json:"state"` // PENDING, RUNNING, TERMINAL
	RunID              string `json:"runId,omitempty"`
	TerminalState      string `json:"terminalState,omitempty"`
}

func defaultLocalRunRecordRoot() string {
	base, err := os.UserConfigDir()
	if err != nil || base == "" {
		return ""
	}
	return filepath.Join(base, "platform-installer", "run-records")
}

func canonicalRunProjectRoot(root string) (string, error) {
	if root == "" {
		return "", errors.New("LOCAL_RUN_RECORD_INVALID")
	}
	absolute, err := filepath.Abs(root)
	if err != nil {
		return "", errors.New("LOCAL_RUN_RECORD_INVALID")
	}
	absolute = filepath.Clean(absolute)
	if runtime.GOOS == "windows" {
		absolute = strings.ToLower(absolute)
	}
	return absolute, nil
}

func localRunRecordPath(storeRoot, projectRoot, projectID string) (string, error) {
	if storeRoot == "" || projectID == "" {
		return "", errors.New("LOCAL_RUN_RECORD_UNAVAILABLE")
	}
	canonical, err := canonicalRunProjectRoot(projectRoot)
	if err != nil {
		return "", err
	}
	hash := sha256.Sum256([]byte(canonical + "\x00" + projectID))
	return filepath.Join(storeRoot, hex.EncodeToString(hash[:])+".json"), nil
}

func validLocalRunID(id string) bool {
	if len(id) <= len("installer-") || len(id) > 128 || !strings.HasPrefix(id, "installer-") {
		return false
	}
	for _, ch := range id[len("installer-"):] {
		if ch < '0' || ch > '9' && (ch < 'a' || ch > 'f') {
			return false
		}
	}
	return true
}

func validLocalRunRecord(record localRunRecord) bool {
	if record.Version != localRunRecordVersion || record.ProjectRoot == "" || record.ProjectID == "" || record.ProjectRevision == "" || record.PlanID == "" || record.NodeID == "" || record.NodeAddress == "" || record.NodePort == 0 || record.NodeUser == "" || !strings.HasPrefix(record.HostKeyFingerprint, "SHA256:") {
		return false
	}
	switch record.State {
	case "PENDING":
		return record.RunID == "" && record.TerminalState == ""
	case "RUNNING":
		return validLocalRunID(record.RunID) && record.TerminalState == ""
	case "TERMINAL":
		return validLocalRunID(record.RunID) && rebindTerminalRun(record.TerminalState)
	default:
		return false
	}
}

func readLocalRunRecord(storeRoot, projectRoot, projectID string) (*localRunRecord, error) {
	path, err := localRunRecordPath(storeRoot, projectRoot, projectID)
	if err != nil {
		return nil, err
	}
	if err := safeLocalRunRecordRoot(storeRoot); err != nil {
		return nil, err
	}
	info, err := os.Lstat(path)
	if errors.Is(err, os.ErrNotExist) {
		return nil, nil
	}
	if err != nil || !info.Mode().IsRegular() || info.Size() < 2 || info.Size() > 8192 {
		return nil, errors.New("LOCAL_RUN_RECORD_INVALID")
	}
	content, err := os.ReadFile(path)
	if err != nil || len(content) > 8192 {
		return nil, errors.New("LOCAL_RUN_RECORD_INVALID")
	}
	decoder := json.NewDecoder(bytes.NewReader(content))
	decoder.DisallowUnknownFields()
	var record localRunRecord
	if err := decoder.Decode(&record); err != nil {
		return nil, errors.New("LOCAL_RUN_RECORD_INVALID")
	}
	var extra any
	if err := decoder.Decode(&extra); !errors.Is(err, io.EOF) {
		return nil, errors.New("LOCAL_RUN_RECORD_INVALID")
	}
	canonical, err := canonicalRunProjectRoot(projectRoot)
	if err != nil || !validLocalRunRecord(record) || record.ProjectRoot != canonical || record.ProjectID != projectID {
		return nil, errors.New("LOCAL_RUN_RECORD_INVALID")
	}
	return &record, nil
}

func writeLocalRunRecord(storeRoot string, record localRunRecord) error {
	if !validLocalRunRecord(record) {
		return errors.New("LOCAL_RUN_RECORD_INVALID")
	}
	canonical, err := canonicalRunProjectRoot(record.ProjectRoot)
	if err != nil || canonical != record.ProjectRoot {
		return errors.New("LOCAL_RUN_RECORD_INVALID")
	}
	path, err := localRunRecordPath(storeRoot, record.ProjectRoot, record.ProjectID)
	if err != nil {
		return err
	}
	if err := os.MkdirAll(storeRoot, 0o700); err != nil {
		return fmt.Errorf("LOCAL_RUN_RECORD_UNAVAILABLE: %w", err)
	}
	if err := safeLocalRunRecordRoot(storeRoot); err != nil {
		return err
	}
	if info, err := os.Lstat(path); err == nil && !info.Mode().IsRegular() {
		return errors.New("LOCAL_RUN_RECORD_INVALID")
	} else if err != nil && !errors.Is(err, os.ErrNotExist) {
		return errors.New("LOCAL_RUN_RECORD_INVALID")
	}
	data, err := json.Marshal(record)
	if err != nil || len(data) > 8192 {
		return errors.New("LOCAL_RUN_RECORD_INVALID")
	}
	temp, err := os.CreateTemp(storeRoot, ".run-record-")
	if err != nil {
		return err
	}
	defer os.Remove(temp.Name())
	if err := temp.Chmod(0o600); err != nil {
		temp.Close()
		return err
	}
	if _, err := temp.Write(data); err != nil {
		temp.Close()
		return err
	}
	if err := temp.Sync(); err != nil {
		temp.Close()
		return err
	}
	if err := temp.Close(); err != nil {
		return err
	}
	if err := replaceLocalRunRecord(temp.Name(), path); err != nil {
		return err
	}
	return syncLocalRunRecordDir(storeRoot)
}

func safeLocalRunRecordRoot(root string) error {
	info, err := os.Lstat(root)
	if errors.Is(err, os.ErrNotExist) {
		return nil
	}
	if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return errors.New("LOCAL_RUN_RECORD_UNAVAILABLE")
	}
	return nil
}

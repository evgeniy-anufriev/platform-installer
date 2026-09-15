package main

import (
	"errors"
	"os"
	"runtime"
	"sort"
	"strings"
)

const (
	executionNodeNotConfigured = "NOT_CONFIGURED"
	executionNodeNotPrepared   = "NOT_PREPARED"
)

var errExecutionNodeSelectionInvalid = errors.New("EXECUTION_NODE_SELECTION_INVALID")

// probeLocalExecutionNodeCandidate is intentionally fail-closed. Platform
// Installer currently ships no local Execution Node adapter, therefore no
// Linux host is offered merely because it looks compatible. When such an
// adapter is implemented, this fixed seam is the only place that may turn the
// bounded local OS/architecture observations into a selectable candidate.
func probeLocalExecutionNodeCandidate() *executionNodeCandidate {
	if runtime.GOOS != "linux" || runtime.GOARCH != "amd64" {
		return nil
	}
	content, err := os.ReadFile("/etc/os-release")
	if err != nil || !supportedLocalExecutionNodeOS(string(content)) {
		return nil
	}
	// No supported local adapter is implemented in this release.
	return nil
}

func supportedLocalExecutionNodeOS(content string) bool {
	for _, line := range strings.Split(content, "\n") {
		if strings.HasPrefix(line, "ID=") && strings.Trim(strings.TrimPrefix(line, "ID="), "\"") == "redos" {
			return true
		}
	}
	return false
}

// ExecutionNodeContext is safe, application-only selection state. It is never
// a portable-project field and deliberately cannot represent READY.
type ExecutionNodeContext struct {
	Status          string `json:"status"`
	SelectionKind   string `json:"selectionKind"`
	SelectionSource string `json:"selectionSource"`
	SelectedHostID  string `json:"selectedHostId,omitempty"`
	SafeLabel       string `json:"safeLabel,omitempty"`
	Locked          bool   `json:"locked"`
}

type executionNodeCandidate struct {
	hostID string
	label  string
}

type executionNodeContextStore struct {
	root, projectID string
	external        *executionNodeCandidate
	local           *executionNodeCandidate
	candidates      map[string]executionNodeCandidate
	context         ExecutionNodeContext
}

func newExecutionNodeContextStore(external, local *executionNodeCandidate) *executionNodeContextStore {
	return &executionNodeContextStore{external: external, local: local, candidates: map[string]executionNodeCandidate{}, context: emptyExecutionNodeContext()}
}

func emptyExecutionNodeContext() ExecutionNodeContext {
	return ExecutionNodeContext{Status: executionNodeNotConfigured, SelectionKind: "NONE", SelectionSource: "NONE"}
}

func (s *executionNodeContextStore) bind(root, projectID string, hosts map[string]map[string]any) {
	s.root, s.projectID = root, projectID
	s.replaceSnapshotHosts(hosts)
	s.context = emptyExecutionNodeContext()
	s.selectInitial()
}

func (s *executionNodeContextStore) clear() {
	s.root, s.projectID = "", ""
	s.candidates = map[string]executionNodeCandidate{}
	s.context = emptyExecutionNodeContext()
}

func (s *executionNodeContextStore) setStatus(status string) {
	if status == "" || s.context.SelectionKind == "NONE" {
		return
	}
	s.context.Status = status
}

func (s *executionNodeContextStore) replaceSnapshotHosts(hosts map[string]map[string]any) {
	s.candidates = map[string]executionNodeCandidate{}
	for hostID, host := range hosts {
		if candidate, ok := candidateFromHost(hostID, host); ok {
			s.candidates[hostID] = candidate
		}
	}
}

func candidateFromHost(hostID string, host map[string]any) (executionNodeCandidate, bool) {
	address, _ := host["ansibleHost"].(string)
	if hostID == "" || address == "" {
		return executionNodeCandidate{}, false
	}
	return executionNodeCandidate{hostID: hostID, label: hostID + " · " + address}, true
}

func (s *executionNodeContextStore) applyCommand(commandHostID, operation, address string) {
	if s.root == "" || commandHostID == "" {
		return
	}
	switch operation {
	case "CreateServer":
		if address != "" {
			s.candidates[commandHostID] = executionNodeCandidate{hostID: commandHostID, label: commandHostID + " · " + address}
			if !s.context.Locked && s.context.Status == executionNodeNotConfigured {
				s.selectInitial()
			}
		}
	case "UpdateServer":
		if candidate, ok := s.candidates[commandHostID]; ok && address != "" {
			candidate.label = commandHostID + " · " + address
			s.candidates[commandHostID] = candidate
			if s.context.SelectionKind == "PROJECT_SERVER" && s.context.SelectedHostID == commandHostID {
				s.context.SafeLabel = candidate.label
			}
		}
	case "DeleteServer":
		delete(s.candidates, commandHostID)
		if s.context.SelectionKind == "PROJECT_SERVER" && s.context.SelectedHostID == commandHostID {
			s.context = emptyExecutionNodeContext()
		}
	}
}

func (s *executionNodeContextStore) discardDraft(hosts map[string]map[string]any) {
	selected := s.context
	s.replaceSnapshotHosts(hosts)
	if selected.SelectionKind == "PROJECT_SERVER" {
		if candidate, ok := s.candidates[selected.SelectedHostID]; ok {
			s.context.SafeLabel = candidate.label
			return
		}
		s.context = emptyExecutionNodeContext()
	}
}

func (s *executionNodeContextStore) selectInitial() {
	if s.external != nil {
		s.context = ExecutionNodeContext{Status: executionNodeNotPrepared, SelectionKind: "EXPLICIT_EXTERNAL", SelectionSource: "EXPLICIT", SafeLabel: s.external.label, Locked: true}
		return
	}
	if s.local != nil {
		s.context = ExecutionNodeContext{Status: executionNodeNotPrepared, SelectionKind: "LOCAL_LINUX", SelectionSource: "AUTO_LOCAL_LINUX", SafeLabel: s.local.label, Locked: true}
		return
	}
	ids := make([]string, 0, len(s.candidates))
	for hostID := range s.candidates {
		ids = append(ids, hostID)
	}
	if len(ids) == 0 {
		return
	}
	sort.Strings(ids)
	candidate := s.candidates[ids[0]]
	s.context = ExecutionNodeContext{Status: executionNodeNotPrepared, SelectionKind: "PROJECT_SERVER", SelectionSource: "AUTO_FIRST_ELIGIBLE", SelectedHostID: candidate.hostID, SafeLabel: candidate.label, Locked: true}
}

func (s *executionNodeContextStore) selectProjectServer(hostID string) error {
	candidate, ok := s.candidates[hostID]
	if !ok {
		return errExecutionNodeSelectionInvalid
	}
	s.context = ExecutionNodeContext{Status: executionNodeNotPrepared, SelectionKind: "PROJECT_SERVER", SelectionSource: "EXPLICIT", SelectedHostID: candidate.hostID, SafeLabel: candidate.label, Locked: true}
	return nil
}

package installer

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"strings"
	"sync"
	"time"
)

const (
	maxEditSessions    = 8
	maxSessionCommands = 1024
	maxSessionBytes    = 4 * 1024 * 1024
	defaultSessionTTL  = 30 * time.Minute
)

type editSessionState struct {
	public   EditSession
	commands []EditCommand
	updated  time.Time
	busy     bool
}

// EditSessionStore owns transient draft ordering. It persists neither desired
// state nor secrets and serializes review/append/discard for each session.
type EditSessionStore struct {
	mu        sync.Mutex
	now       func() time.Time
	ttl       time.Duration
	sessions  map[string]*editSessionState
	byProject map[string]string
}

func NewEditSessionStore() *EditSessionStore {
	return &EditSessionStore{now: time.Now, ttl: defaultSessionTTL,
		sessions: make(map[string]*editSessionState), byProject: make(map[string]string)}
}

func opaqueID() (string, error) {
	value := make([]byte, 16)
	if _, err := rand.Read(value); err != nil {
		return "", err
	}
	return hex.EncodeToString(value), nil
}

func (s *EditSessionStore) expireLocked() {
	now := s.now()
	for id, state := range s.sessions {
		if s.ttl > 0 && now.Sub(state.updated) > s.ttl {
			delete(s.byProject, state.public.ProjectContextID)
			delete(s.sessions, id)
		}
	}
}

// Active reconciles an application-held session identifier with the bounded
// transient store. It intentionally exposes no draft contents.
func (s *EditSessionStore) Active(sessionID string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.expireLocked()
	_, ok := s.sessions[sessionID]
	return ok
}

func (s *EditSessionStore) Start(projectContextID, projectRoot, classification, revision string) (EditSession, error) {
	if projectContextID == "" || projectRoot == "" || !validSHA256(revision) {
		return EditSession{}, blocked("INVALID_EDIT_SESSION", "Project context and revision are required", "session")
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	s.expireLocked()
	if existing := s.byProject[projectContextID]; existing != "" {
		return s.sessions[existing].public, nil
	}
	if len(s.sessions) >= maxEditSessions {
		return EditSession{}, blocked("EDIT_SESSION_LIMIT", "Too many edit sessions are active", "session")
	}
	id, err := opaqueID()
	if err != nil {
		return EditSession{}, err
	}
	now := s.now()
	public := EditSession{APIVersion: EditSessionAPIVersion, Kind: "EditSession", SessionID: id,
		ProjectContextID: projectContextID, ProjectRoot: projectRoot, ProjectClassification: classification,
		BaseProjectRevision: revision, Status: "EDITING", ExpiresAt: now.Add(s.ttl)}
	s.sessions[id] = &editSessionState{public: public, updated: now}
	s.byProject[projectContextID] = id
	return public, nil
}

func validSHA256(value string) bool {
	if !strings.HasPrefix(value, "sha256:") || len(value) != len("sha256:")+64 {
		return false
	}
	digest := strings.TrimPrefix(value, "sha256:")
	if _, err := hex.DecodeString(digest); err != nil {
		return false
	}
	return digest == strings.ToLower(digest)
}

func (s *EditSessionStore) Append(sessionID string, command EditCommand, backend *Backend) (EditSession, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.expireLocked()
	state := s.sessions[sessionID]
	if state == nil {
		return EditSession{}, blocked("EDIT_SESSION_EXPIRED", "Edit session is absent or expired", "sessionId")
	}
	if state.busy {
		return EditSession{}, blocked("EDIT_SESSION_BUSY", "Edit session review is in progress", "sessionId")
	}
	command.APIVersion = EditCommandAPIVersionV10
	if applicationEditOperation(command.Operation) {
		command.APIVersion = EditCommandAPIVersionV11
	}
	command.Kind = "EditCommand"
	command.BaseProjectRevision = state.public.BaseProjectRevision
	if backend == nil {
		return EditSession{}, blocked("APPLICATION_CONFIG_UNAVAILABLE", "Application configuration is unavailable", "command.type")
	}
	if err := backend.validateCommand(command); err != nil {
		return EditSession{}, err
	}
	encoded, err := json.Marshal(command)
	if err != nil {
		return EditSession{}, blocked("INVALID_EDIT_COMMAND", "Edit command cannot be encoded", "command")
	}
	if len(state.commands) >= maxSessionCommands || state.public.EncodedBytes+len(encoded) > maxSessionBytes {
		return EditSession{}, blocked("EDIT_SESSION_LIMIT", "Edit session command limit was reached", "command")
	}
	state.commands = append(state.commands, command)
	if state.public.ReviewedPlanID != "" && backend != nil {
		backend.plans.Discard(state.public.ReviewedPlanID)
	}
	state.public.CommandCount = len(state.commands)
	state.public.EncodedBytes += len(encoded)
	state.public.Status = "EDITING"
	state.public.ReviewedPlanID = ""
	state.updated = s.now()
	state.public.ExpiresAt = state.updated.Add(s.ttl)
	return state.public, nil
}

// AmendConfiguration changes only one previously acknowledged configuration
// command. The expected command is a compare-and-swap guard against a stale UI;
// structural commands and other draft targets are never rewritten.
func (s *EditSessionStore) AmendConfiguration(sessionID string, index int, expected EditCommand, replacement *EditCommand, backend *Backend) (EditSession, error) {
	return s.amendCommand(sessionID, index, expected, replacement, backend, false)
}

func (s *EditSessionStore) AmendApplication(sessionID string, index int, expected EditCommand, replacement *EditCommand, backend *Backend) (EditSession, error) {
	return s.amendCommand(sessionID, index, expected, replacement, backend, true)
}

func (s *EditSessionStore) amendCommand(sessionID string, index int, expected EditCommand, replacement *EditCommand, backend *Backend, application bool) (EditSession, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.expireLocked()
	state := s.sessions[sessionID]
	if state == nil {
		return EditSession{}, blocked("EDIT_SESSION_EXPIRED", "Edit session is absent or expired", "sessionId")
	}
	if state.busy {
		return EditSession{}, blocked("EDIT_SESSION_BUSY", "Edit session review is in progress", "sessionId")
	}
	if backend == nil || index < 0 || index >= len(state.commands) {
		return EditSession{}, blocked("EDIT_COMMAND_CONFLICT", "Configuration draft changed", "command")
	}
	allowed := isConfigurationCommand
	sameTarget := sameConfigurationTarget
	if application {
		allowed = func(c EditCommand) bool { return applicationEditOperation(c.Operation) }
		sameTarget = func(a, b EditCommand) bool {
			return a.DeploymentID == b.DeploymentID && a.EntityID == b.EntityID && a.HostID == b.HostID && a.Property == b.Property && a.Setting == b.Setting && applicationCommandFamily(a.Operation) == applicationCommandFamily(b.Operation)
		}
	}
	normalize := func(command *EditCommand) {
		command.APIVersion = EditCommandAPIVersionV10
		if application {
			command.APIVersion = EditCommandAPIVersionV11
		}
		command.Kind = "EditCommand"
		command.BaseProjectRevision = state.public.BaseProjectRevision
	}
	normalize(&expected)
	prior := state.commands[index]
	if !allowed(prior) || !allowed(expected) {
		return EditSession{}, blocked("EDIT_COMMAND_CONFLICT", "Only configuration draft commands can be amended", "command")
	}
	want, err := json.Marshal(expected)
	if err != nil {
		return EditSession{}, blocked("INVALID_EDIT_COMMAND", "Expected command cannot be encoded", "command")
	}
	old, err := json.Marshal(prior)
	if err != nil || !bytes.Equal(want, old) {
		return EditSession{}, blocked("EDIT_COMMAND_CONFLICT", "Configuration draft changed", "command")
	}
	if replacement != nil {
		normalize(replacement)
		if !allowed(*replacement) || !sameTarget(prior, *replacement) {
			return EditSession{}, blocked("EDIT_COMMAND_CONFLICT", "Configuration target cannot change", "command")
		}
		if err := backend.validateCommand(*replacement); err != nil {
			return EditSession{}, err
		}
	}
	newBytes := 0
	if replacement != nil {
		encoded, err := json.Marshal(replacement)
		if err != nil {
			return EditSession{}, blocked("INVALID_EDIT_COMMAND", "Replacement command cannot be encoded", "command")
		}
		newBytes = len(encoded)
	}
	if state.public.EncodedBytes-len(old)+newBytes > maxSessionBytes {
		return EditSession{}, blocked("EDIT_SESSION_LIMIT", "Edit session byte limit was reached", "command")
	}
	if replacement == nil {
		state.commands = append(state.commands[:index], state.commands[index+1:]...)
	} else {
		state.commands[index] = *replacement
	}
	if state.public.ReviewedPlanID != "" {
		backend.plans.Discard(state.public.ReviewedPlanID)
	}
	state.public.CommandCount = len(state.commands)
	state.public.EncodedBytes += newBytes - len(old)
	state.public.Status = "EDITING"
	state.public.ReviewedPlanID = ""
	state.updated = s.now()
	state.public.ExpiresAt = state.updated.Add(s.ttl)
	return state.public, nil
}

func isConfigurationCommand(command EditCommand) bool {
	return command.Operation == "SetServiceConfigurationValue" || command.Operation == "RemoveServiceConfigurationOverride"
}

func sameConfigurationTarget(a, b EditCommand) bool {
	return a.DeploymentID == b.DeploymentID && a.Scope == b.Scope && a.MemberID == b.MemberID && a.Setting == b.Setting
}

func (s *EditSessionStore) Review(ctx context.Context, backend *Backend, sessionID string) (*EditPlan, error) {
	s.mu.Lock()
	s.expireLocked()
	state := s.sessions[sessionID]
	if state == nil {
		s.mu.Unlock()
		return nil, blocked("EDIT_SESSION_EXPIRED", "Edit session is absent or expired", "sessionId")
	}
	if state.busy {
		s.mu.Unlock()
		return nil, blocked("EDIT_SESSION_BUSY", "Edit session review is already in progress", "sessionId")
	}
	if len(state.commands) == 0 {
		s.mu.Unlock()
		return nil, blocked("EDIT_SESSION_EMPTY", "Edit session contains no commands", "sessionId")
	}
	if state.public.ReviewedPlanID != "" {
		backend.plans.Discard(state.public.ReviewedPlanID)
		state.public.ReviewedPlanID = ""
		state.public.Status = "EDITING"
	}
	state.busy = true
	commands := append([]EditCommand(nil), state.commands...)
	root, classification, revision := state.public.ProjectRoot, state.public.ProjectClassification, state.public.BaseProjectRevision
	s.mu.Unlock()

	plan, err := backend.planCommands(ctx, root, classification, revision, commands)

	s.mu.Lock()
	defer s.mu.Unlock()
	state = s.sessions[sessionID]
	if state != nil {
		state.busy = false
		state.updated = s.now()
		state.public.ExpiresAt = state.updated.Add(s.ttl)
		if err == nil && plan != nil && plan.CommitAllowed {
			state.public.Status = "REVIEWED"
			state.public.ReviewedPlanID = plan.PlanID
		}
	}
	return plan, err
}

// ReviewStructural builds the local-only Save preview for the current draft.
func (s *EditSessionStore) ReviewStructural(ctx context.Context, backend *Backend, sessionID string) (*StructuralEditPlan, error) {
	s.mu.Lock()
	s.expireLocked()
	state := s.sessions[sessionID]
	if state == nil {
		s.mu.Unlock()
		return nil, blocked("EDIT_SESSION_EXPIRED", "Edit session is absent or expired", "sessionId")
	}
	if state.busy {
		s.mu.Unlock()
		return nil, blocked("EDIT_SESSION_BUSY", "Edit session review is already in progress", "sessionId")
	}
	if len(state.commands) == 0 {
		s.mu.Unlock()
		return nil, blocked("EDIT_SESSION_EMPTY", "Edit session contains no commands", "sessionId")
	}
	if state.public.ReviewedPlanID != "" {
		backend.plans.Discard(state.public.ReviewedPlanID)
		state.public.ReviewedPlanID = ""
		state.public.Status = "EDITING"
	}
	state.busy = true
	commands := append([]EditCommand(nil), state.commands...)
	root, classification, revision := state.public.ProjectRoot, state.public.ProjectClassification, state.public.BaseProjectRevision
	s.mu.Unlock()

	plan, err := backend.PlanStructuralSave(ctx, root, classification, revision, commands)

	s.mu.Lock()
	defer s.mu.Unlock()
	state = s.sessions[sessionID]
	if state != nil {
		state.busy = false
		state.updated = s.now()
		state.public.ExpiresAt = state.updated.Add(s.ttl)
		if err == nil && plan != nil && plan.SaveAllowed {
			state.public.Status = "REVIEWED"
			state.public.ReviewedPlanID = plan.PlanID
		}
	}
	return plan, err
}

func (s *EditSessionStore) BeginCommit(sessionID, planID string) (EditSession, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.expireLocked()
	state := s.sessions[sessionID]
	if state == nil {
		return EditSession{}, blocked("EDIT_SESSION_EXPIRED", "Edit session is absent or expired", "sessionId")
	}
	if state.busy || state.public.Status != "REVIEWED" || planID == "" || state.public.ReviewedPlanID != planID {
		return EditSession{}, blocked("EDIT_PLAN_NOT_CURRENT", "Only the latest reviewed plan can be committed", "planId")
	}
	state.busy = true
	state.public.Status = "COMMITTING"
	return state.public, nil
}

// ReviewApplicationPackageImport uses the same session, opaque plan store and
// commit path. Imports cannot be mixed with pending structural edit commands.
func (s *EditSessionStore) ReviewApplicationPackageImport(ctx context.Context, backend *Backend, sessionID, source, kind, name, version, digest string) (*StructuralEditPlan, error) {
	s.mu.Lock()
	s.expireLocked()
	state := s.sessions[sessionID]
	if state == nil || backend == nil {
		s.mu.Unlock()
		return nil, blocked("EDIT_SESSION_EXPIRED", "Edit session is absent", "sessionId")
	}
	if state.busy || len(state.commands) != 0 {
		s.mu.Unlock()
		return nil, blocked("EDIT_SESSION_ACTIVE", "Save or discard the current draft before importing", "sessionId")
	}
	if state.public.ReviewedPlanID != "" {
		backend.plans.Discard(state.public.ReviewedPlanID)
		state.public.ReviewedPlanID = ""
		state.public.Status = "EDITING"
	}
	state.busy = true
	root, revision := state.public.ProjectRoot, state.public.BaseProjectRevision
	s.mu.Unlock()
	plan, err := backend.PlanApplicationPackageImport(ctx, root, source, revision, kind, name, version, digest)
	s.mu.Lock()
	defer s.mu.Unlock()
	state = s.sessions[sessionID]
	if state != nil {
		state.busy = false
		state.updated = s.now()
		state.public.ExpiresAt = state.updated.Add(s.ttl)
		if err == nil && plan != nil && plan.SaveAllowed {
			state.public.Status = "REVIEWED"
			state.public.ReviewedPlanID = plan.PlanID
		}
	}
	return plan, err
}

func (s *EditSessionStore) FinishCommit(sessionID, planID string, committed bool) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	state := s.sessions[sessionID]
	if state == nil || !state.busy || state.public.ReviewedPlanID != planID {
		return false
	}
	if committed {
		delete(s.byProject, state.public.ProjectContextID)
		delete(s.sessions, sessionID)
		return true
	}
	state.busy = false
	state.public.Status = "REVIEWED"
	state.updated = s.now()
	state.public.ExpiresAt = state.updated.Add(s.ttl)
	return true
}

func (s *EditSessionStore) Discard(sessionID string, backend *Backend) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	state := s.sessions[sessionID]
	if state == nil || state.busy {
		return false
	}
	if state.public.ReviewedPlanID != "" && backend != nil {
		backend.plans.Discard(state.public.ReviewedPlanID)
	}
	delete(s.byProject, state.public.ProjectContextID)
	delete(s.sessions, sessionID)
	return true
}

func (s *EditSessionStore) ConsumePlan(sessionID, planID string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	state := s.sessions[sessionID]
	if state == nil || state.public.ReviewedPlanID != planID {
		return false
	}
	delete(s.byProject, state.public.ProjectContextID)
	delete(s.sessions, sessionID)
	return true
}

func applicationCommandFamily(operation string) string {
	switch operation {
	case "SetApplicationLibraryOverride", "RemoveApplicationLibraryOverride":
		return "override"
	case "SetApplicationLibrarySlot", "RemoveApplicationLibrarySlot":
		return "slot"
	case "SetApplicationLibraryPlacement", "RemoveApplicationLibraryPlacement":
		return "placement"
	}
	return operation
}

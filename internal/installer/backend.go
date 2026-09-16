package installer

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"platform-installer/internal/coreadapter"
	"platform-installer/internal/projectlifecycle"
)

type Backend struct {
	core            coreadapter.Adapter
	plans           PlanStore
	now             func() time.Time
	planTTL         time.Duration
	lockWait        time.Duration
	replace         replaceFunc
	serverTypes     map[string]bool
	catalogResolver func(context.Context, string) (*projectlifecycle.ProjectCatalogView, error)
}

type Option func(*Backend)

func WithPlanStore(store PlanStore) Option { return func(backend *Backend) { backend.plans = store } }
func WithPlanTTL(ttl time.Duration) Option { return func(backend *Backend) { backend.planTTL = ttl } }
func WithServerTypes(values []string) Option {
	return func(backend *Backend) {
		backend.serverTypes = make(map[string]bool, len(values))
		for _, value := range values {
			backend.serverTypes[value] = true
		}
	}
}
func WithProjectCatalogResolver(resolver func(context.Context, string) (*projectlifecycle.ProjectCatalogView, error)) Option {
	return func(backend *Backend) { backend.catalogResolver = resolver }
}
func withReplace(function replaceFunc) Option {
	return func(backend *Backend) { backend.replace = function }
}

func NewBackend(adapter coreadapter.Adapter, options ...Option) *Backend {
	backend := &Backend{core: adapter, now: time.Now, planTTL: 5 * time.Minute,
		lockWait: 5 * time.Second, replace: atomicReplace}
	for _, option := range options {
		option(backend)
	}
	if backend.plans == nil {
		backend.plans = NewMemoryPlanStore(backend.planTTL)
	}
	return backend
}

func (b *Backend) validateCommand(command EditCommand) error {
	return b.validateCommandWithInternalBatch(command, false)
}

func (b *Backend) validateCommandWithInternalBatch(command EditCommand, allowBatch bool) error {
	if err := validateCommandWithInternalBatch(command, allowBatch); err != nil {
		return err
	}
	return b.validateConfiguredTypes(command)
}

func (b *Backend) validateConfiguredTypes(command EditCommand) error {
	if command.Operation == "Batch" {
		for _, child := range command.Commands {
			child.APIVersion = command.APIVersion
			child.Kind = command.Kind
			child.BaseProjectRevision = command.BaseProjectRevision
			if err := b.validateConfiguredTypes(child); err != nil {
				return err
			}
		}
		return nil
	}
	if (command.APIVersion == EditCommandAPIVersionV3 || command.APIVersion == EditCommandAPIVersionV4 || isEditCommandV5OrLater(command.APIVersion)) && (command.Operation == "CreateServer" || command.Operation == "UpdateServer" && command.ServerType != "") {
		if len(b.serverTypes) == 0 {
			return blocked("APPLICATION_CONFIG_UNAVAILABLE", "Application configuration is unavailable", "command.type")
		}
	}
	return nil
}

func blockedPlan(command EditCommand, revision string, err error) *EditPlan {
	finding := Finding{APIVersion: "platform.installer/finding/v1alpha1", Kind: "Finding",
		Code: "EDIT_PLAN_FAILED", Status: "BLOCKED", Category: "project-writer", Field: "command",
		SafeMessage: "Edit plan could not be created"}
	if typed, ok := err.(*writerError); ok {
		finding = typed.finding()
	}
	version := EditPlanAPIVersion
	if isEditCommandV2OrLater(command.APIVersion) {
		version = EditPlanAPIVersionV2
	}
	return &EditPlan{APIVersion: version, Kind: "EditPlan", Status: "BLOCKED",
		BaseProjectRevision: revision, CommandSummary: commandSummary(command),
		SemanticChanges: []SemanticChange{}, AffectedEntities: []string{},
		AffectedDocuments: []DocumentChange{}, Impacts: []string{},
		Validation: Validation{Status: "BLOCKED", Findings: []Finding{finding}},
		ReviewDiff: "", CommitAllowed: false, ApplyRequired: false}
}

func planVersion(command EditCommand) string {
	if isEditCommandV2OrLater(command.APIVersion) {
		return EditPlanAPIVersionV2
	}
	return EditPlanAPIVersion
}

func blockedCorePlan(command EditCommand, revision string, snapshot *coreadapter.Snapshot) *EditPlan {
	plan := blockedPlan(command, revision,
		blocked("VALIDATION_BLOCKED", "Authoritative Core validation is blocked", "project"))
	if snapshot == nil || len(snapshot.Findings) == 0 {
		return plan
	}
	findings := make([]Finding, 0, len(snapshot.Findings))
	for _, item := range snapshot.Findings {
		finding := Finding{APIVersion: "platform.installer/finding/v1alpha1", Kind: "Finding",
			Status: "BLOCKED", Category: "core-validation", Field: "project",
			Code: "CORE_VALIDATION_BLOCKED", SafeMessage: "Core validation blocked the proposed project"}
		if value, ok := item["code"].(string); ok && value != "" {
			finding.Code = value
		}
		if value, ok := item["field"].(string); ok && value != "" {
			finding.Field = value
		}
		if value, ok := item["category"].(string); ok && value != "" {
			finding.Category = value
		}
		if value, ok := item["safeMessage"].(string); ok && value != "" {
			finding.SafeMessage = value
		}
		findings = append(findings, finding)
	}
	plan.Validation.Findings = findings
	return plan
}

func documentOwnership(snapshot *coreadapter.Snapshot) map[string]string {
	result := make(map[string]string, len(snapshot.Documents))
	for _, document := range snapshot.Documents {
		result[document.LogicalPath] = document.Ownership
	}
	return result
}

func boundedDiff(logical string, before, after []byte) string {
	return fmt.Sprintf("--- %s (%s)\n+++ %s (%s)\n@@ Installer-owned document changed; values are shown by semantic changes @@\n",
		logical, digestBytes(before), logical, digestBytes(after))
}

func affectedEntities(changes []SemanticChange) []string {
	set := make(map[string]bool)
	for _, change := range changes {
		if change.EntityID != "" {
			set[change.EntityID] = true
		}
	}
	result := make([]string, 0, len(set))
	for item := range set {
		result = append(result, item)
	}
	sort.Strings(result)
	return result
}

func coreDerivedImpacts(before, after *coreadapter.Snapshot) []string {
	candidates := []struct {
		name        string
		beforeValue any
		afterValue  any
	}{
		{"CONFIGURATION_CHANGED", before.EffectiveConfiguration, after.EffectiveConfiguration},
		{"TOPOLOGY_CHANGED", before.Topology, after.Topology},
		{"ENDPOINT_CHANGED", before.Endpoints, after.Endpoints},
		{"INTEGRATION_CHANGED", before.Integrations, after.Integrations},
		{"PKI_INPUT_CHANGED", before.PKI, after.PKI},
	}
	result := make([]string, 0, len(candidates))
	for _, candidate := range candidates {
		if !semanticEqual(candidate.beforeValue, candidate.afterValue) {
			result = append(result, candidate.name)
		}
	}
	return result
}

func mergeImpacts(groups ...[]string) []string {
	set := make(map[string]bool)
	for _, group := range groups {
		for _, item := range group {
			set[item] = true
		}
	}
	result := make([]string, 0, len(set))
	for item := range set {
		result = append(result, item)
	}
	sort.Strings(result)
	return result
}

func (b *Backend) PlanEdit(ctx context.Context, projectRoot string, command EditCommand) (*EditPlan, error) {
	return b.planEdit(ctx, projectRoot, command, false)
}

func (b *Backend) planEdit(ctx context.Context, projectRoot string, command EditCommand, allowV2Batch bool) (*EditPlan, error) {
	started := b.now()
	root, err := cleanRoot(projectRoot)
	if err != nil {
		return blockedPlan(command, command.BaseProjectRevision, err), nil
	}
	if err := b.validateCommandWithInternalBatch(command, allowV2Batch); err != nil {
		return blockedPlan(command, command.BaseProjectRevision, err), nil
	}
	owned, err := discoverOwnedPaths(root)
	if err != nil {
		return blockedPlan(command, command.BaseProjectRevision, err), nil
	}
	coreStarted := b.now()
	snapshot, err := b.core.BuildSnapshot(ctx, root, owned)
	initialSnapshotDuration := b.now().Sub(coreStarted)
	if err != nil {
		return blockedPlan(command, command.BaseProjectRevision,
			blocked("CORE_SNAPSHOT_FAILED", "Authoritative project snapshot could not be built", "project")), nil
	}
	if command.BaseProjectRevision != snapshot.ProjectRevision {
		return blockedPlan(command, snapshot.ProjectRevision,
			blocked("PROJECT_CHANGED", "Project changed before planning", "baseProjectRevision")), nil
	}
	if snapshot.Status != "PASS" {
		return blockedCorePlan(command, snapshot.ProjectRevision, snapshot), nil
	}
	candidates := make(map[string]map[string]any)
	originals := make(map[string][]byte)
	expectations, changes, impacts, err := applyCommand(command, root, snapshot, candidates, originals)
	if err != nil {
		return blockedPlan(command, snapshot.ProjectRevision, err), nil
	}
	if len(expectations) == 0 {
		return &EditPlan{APIVersion: planVersion(command), Kind: "EditPlan", Status: "NO_CHANGE",
			BaseProjectRevision: snapshot.ProjectRevision, CommandSummary: commandSummary(command),
			SemanticChanges: []SemanticChange{}, AffectedEntities: []string{},
			AffectedDocuments: []DocumentChange{}, Impacts: []string{},
			Validation: Validation{Status: "PASS", Findings: []Finding{}}, ReviewDiff: "",
			CommitAllowed: false, ApplyRequired: false,
			Timing: PlanTiming{Application: b.now().Sub(started) - initialSnapshotDuration,
				InitialSnapshot: initialSnapshotDuration}}, nil
	}
	ownership := documentOwnership(snapshot)
	storedDocuments := make([]storedDocument, 0, len(candidates))
	documentChanges := make([]DocumentChange, 0, len(candidates))
	diffParts := make([]string, 0, len(candidates))
	paths := make([]string, 0, len(candidates))
	for logical := range candidates {
		paths = append(paths, logical)
	}
	sort.Strings(paths)
	for _, logical := range paths {
		if ownership[logical] != "INSTALLER_OWNED" {
			return blockedPlan(command, snapshot.ProjectRevision,
				blocked("WRITE_NOT_ALLOWED", "Edit requires a non-Installer-owned document", "document")), nil
		}
		after, serializationErr := deterministicYAML(candidates[logical])
		if serializationErr != nil {
			return blockedPlan(command, snapshot.ProjectRevision,
				blocked("INVALID_VALUE", "Edit value cannot be serialized safely", "command.value")), nil
		}
		before := originals[logical]
		if bytes.Equal(before, after) {
			continue
		}
		storedDocuments = append(storedDocuments, storedDocument{LogicalPath: logical,
			Before: append([]byte(nil), before...), After: after, Existed: true})
		change := DocumentChange{LogicalPath: logical, BeforeDigest: digestBytes(before), AfterDigest: digestBytes(after)}
		if isEditCommandV2OrLater(command.APIVersion) {
			change.Before = &DocumentState{State: "PRESENT", Digest: digestBytes(before)}
			change.After = &DocumentState{State: "PRESENT", Digest: digestBytes(after)}
			change.BeforeDigest, change.AfterDigest = "", ""
		}
		documentChanges = append(documentChanges, change)
		diffParts = append(diffParts, boundedDiff(logical, before, after))
	}
	if len(storedDocuments) == 0 {
		return &EditPlan{APIVersion: planVersion(command), Kind: "EditPlan", Status: "NO_CHANGE",
			BaseProjectRevision: snapshot.ProjectRevision, CommandSummary: commandSummary(command),
			SemanticChanges: []SemanticChange{}, AffectedEntities: []string{},
			AffectedDocuments: []DocumentChange{}, Impacts: []string{},
			Validation: Validation{Status: "PASS", Findings: []Finding{}}, ReviewDiff: "",
			CommitAllowed: false, ApplyRequired: false,
			Timing: PlanTiming{Application: b.now().Sub(started) - initialSnapshotDuration,
				InitialSnapshot: initialSnapshotDuration}}, nil
	}
	stagedRoot, cleanup, err := copyProject(root)
	if err != nil {
		return blockedPlan(command, snapshot.ProjectRevision, err), nil
	}
	defer cleanup()
	for _, document := range storedDocuments {
		path, pathErr := safeProjectPath(stagedRoot, document.LogicalPath, false)
		if pathErr != nil {
			return blockedPlan(command, snapshot.ProjectRevision, pathErr), nil
		}
		if writeErr := os.WriteFile(path, document.After, 0o600); writeErr != nil {
			return blockedPlan(command, snapshot.ProjectRevision,
				blocked("STAGING_FAILED", "Staged managed document could not be written", "document")), nil
		}
	}
	stagedOwned, err := discoverOwnedPaths(stagedRoot)
	if err != nil {
		return blockedPlan(command, snapshot.ProjectRevision, err), nil
	}
	stagedCoreStarted := b.now()
	staged, err := b.core.BuildSnapshot(ctx, stagedRoot, stagedOwned)
	stagedSnapshotDuration := b.now().Sub(stagedCoreStarted)
	if err != nil || staged.Status != "PASS" {
		if err != nil {
			return blockedPlan(command, snapshot.ProjectRevision,
				blocked("CORE_SNAPSHOT_FAILED", "Staged authoritative snapshot could not be built", "project")), nil
		}
		return blockedCorePlan(command, snapshot.ProjectRevision, staged), nil
	}
	if serverReferenceInUse(staged, expectations) {
		return blockedPlan(command, snapshot.ProjectRevision,
			blocked("REFERENCE_IN_USE", "Server is still referenced by the canonical project", "command.hostId")), nil
	}
	if !proveSnapshot(staged, expectations) {
		return blockedPlan(command, snapshot.ProjectRevision,
			blocked("EDIT_SHADOWED", "Authoritative Core resolution did not make the requested edit effective", "command")), nil
	}
	impacts = mergeImpacts(impacts, coreDerivedImpacts(snapshot, staged))
	plan := EditPlan{APIVersion: planVersion(command), Kind: "EditPlan", Status: "READY",
		BaseProjectRevision: snapshot.ProjectRevision, CommandSummary: commandSummary(command),
		SemanticChanges: changes, AffectedEntities: affectedEntities(changes),
		AffectedDocuments: documentChanges, Impacts: impacts,
		Validation:                  Validation{Status: "PASS", Findings: []Finding{}},
		ExpectedEffectiveState:      expectedState(expectations),
		ExpectedSnapshotFingerprint: staged.SnapshotFingerprint,
		ReviewDiff:                  strings.Join(diffParts, ""), CommitAllowed: true, ApplyRequired: true,
		ExpiresAt: b.now().Add(b.planTTL)}
	identifier, err := b.plans.Put(storedPlan{Created: b.now(), ProjectRoot: root,
		Public: plan, Documents: storedDocuments})
	if err != nil {
		return nil, fmt.Errorf("store edit plan: %w", err)
	}
	plan.PlanID = identifier
	plan.Timing = PlanTiming{Application: b.now().Sub(started) - initialSnapshotDuration - stagedSnapshotDuration,
		InitialSnapshot: initialSnapshotDuration, StagedSnapshot: stagedSnapshotDuration}
	return &plan, nil
}

func (b *Backend) planCommands(ctx context.Context, projectRoot, classification, revision string, commands []EditCommand) (*EditPlan, error) {
	if len(commands) == 0 {
		return blockedPlan(EditCommand{}, revision, blocked("EDIT_SESSION_EMPTY", "Edit session contains no commands", "session")), nil
	}
	if isEmptyManagedClassification(classification) {
		return b.planFirstWrite(ctx, projectRoot, revision, commands)
	}
	if len(commands) > 16 {
		return blockedPlan(commands[0], revision, blocked("EDIT_SESSION_COMMANDS_UNSUPPORTED", "This edit set must be split until full-model reconciliation is available", "session")), nil
	}
	command := commands[0]
	if len(commands) > 1 {
		command = EditCommand{APIVersion: commands[0].APIVersion, Kind: "EditCommand", BaseProjectRevision: revision, Operation: "Batch", Commands: commands}
	}
	return b.planEdit(ctx, projectRoot, command, true)
}

func (b *Backend) DiscardEditPlan(planID string) EditCommitResult {
	return EditCommitResult{APIVersion: EditResultAPIVersion, Kind: "EditCommitResult",
		Status: "DISCARDED", Changed: false, Discarded: b.plans.Discard(planID)}
}

func runtimePath(root string, elements ...string) string {
	items := append([]string{root, ".runtime"}, elements...)
	return filepath.Join(items...)
}

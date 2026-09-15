package installer

import (
	"bytes"
	"context"
	"sort"
	"strings"

	"platform-installer/internal/coreadapter"
	"platform-installer/internal/projectlifecycle"
)

// ReadManagedProjectView reads only fields directly owned by the Installer in
// its canonical inventory document. It does not implement Ansible precedence.
func ReadManagedProjectView(projectRoot string) (*ManagedProjectView, error) {
	root, err := cleanRoot(projectRoot)
	if err != nil {
		return nil, err
	}
	document, _, err := loadOwnedDocument(root, managedInventoryDocument)
	if err != nil {
		return nil, err
	}
	all := asMap(document["all"])
	hosts := asMap(all["hosts"])
	targets := asMap(asMap(asMap(all["children"])["platform_targets"])["hosts"])
	if all == nil || hosts == nil || targets == nil {
		return nil, blocked("MANAGED_DOCUMENT_INVALID", "Managed inventory roots are missing or malformed", managedInventoryDocument)
	}
	view := &ManagedProjectView{Servers: make(map[string]ManagedServer)}
	for hostID := range targets {
		host := asMap(hosts[hostID])
		if host == nil {
			return nil, blocked("MANAGED_DOCUMENT_INVALID", "Managed target is missing its canonical host record", managedInventoryDocument)
		}
		platformHost := asMap(host["platform_host"])
		server := ManagedServer{HostID: hostID}
		server.Address, _ = host["ansible_host"].(string)
		server.Type, _ = platformHost["type"].(string)
		server.DesiredHostname, _ = platformHost["desiredHostname"].(string)
		if raw, found := host["ansible_port"]; found {
			port, ok := yamlInteger(raw)
			if !ok || port < 1 || port > 65535 {
				return nil, blocked("MANAGED_DOCUMENT_INVALID", "Managed server SSH port is invalid", managedInventoryDocument)
			}
			server.SSHPort = &port
		}
		view.Servers[hostID] = server
	}
	view.ProjectRevision, err = ProjectRevision(root)
	return view, err
}

func yamlInteger(value any) (int, bool) {
	switch typed := value.(type) {
	case int:
		return typed, true
	case int64:
		return int(typed), int64(int(typed)) == typed
	case uint64:
		return int(typed), uint64(int(typed)) == typed
	default:
		return 0, false
	}
}

func blockedStructuralPlan(revision string, err error) *StructuralEditPlan {
	plan := &StructuralEditPlan{APIVersion: StructuralPlanAPIVersion, Kind: "StructuralEditPlan", Status: "BLOCKED",
		BaseProjectRevision: revision, SemanticChanges: []SemanticChange{}, AffectedEntities: []string{},
		AffectedDocuments: []DocumentChange{}, SaveAllowed: false}
	if typed, ok := err.(*writerError); ok {
		finding := typed.finding()
		plan.Finding = &finding
	}
	return plan
}

// PlanStructuralSave builds a bounded local preview for server intents and
// stores its candidate bytes in the existing opaque plan store.
func (b *Backend) PlanStructuralSave(ctx context.Context, projectRoot, classification, revision string, commands []EditCommand) (*StructuralEditPlan, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	if len(commands) == 0 {
		return blockedStructuralPlan(revision, blocked("EDIT_SESSION_EMPTY", "Edit session contains no commands", "session")), nil
	}
	if len(commands) > 16 {
		return blockedStructuralPlan(revision, blocked("EDIT_SESSION_COMMANDS_UNSUPPORTED", "This edit set must be split", "session")), nil
	}
	for _, command := range commands {
		if command.Operation != "CreateServer" && command.Operation != "UpdateServer" && command.Operation != "DeleteServer" {
			return blockedStructuralPlan(revision, blocked("EDIT_OPERATION_NOT_AVAILABLE", "Only server intents are available in this editor", "command.operation")), nil
		}
		if err := b.validateCommand(command); err != nil {
			return blockedStructuralPlan(revision, err), nil
		}
	}
	root, err := cleanRoot(projectRoot)
	if err != nil {
		return blockedStructuralPlan(revision, err), nil
	}
	if isEmptyManagedClassification(classification) {
		return b.planStructuralFirstWrite(root, revision, commands)
	}
	return b.planStructuralManaged(root, revision, commands)
}

func (b *Backend) planStructuralFirstWrite(root, revision string, commands []EditCommand) (*StructuralEditPlan, error) {
	if !projectlifecycle.FirstSaveEligible(root) {
		return blockedStructuralPlan(revision, blocked("WRITE_OWNERSHIP_REQUIRED", "First save requires a valid empty managed project", "project")), nil
	}
	_, currentRevision, err := collectProjectDocuments(root)
	if err != nil || currentRevision != revision {
		if err == nil {
			err = blocked("PROJECT_CHANGED", "Project changed before review", "baseProjectRevision")
		}
		return blockedStructuralPlan(currentRevision, err), nil
	}
	seen := map[string]bool{}
	servers := make([]firstSaveServer, 0, len(commands))
	changes := make([]SemanticChange, 0, len(commands))
	for _, command := range commands {
		if command.Operation != "CreateServer" || seen[command.HostID] {
			return blockedStructuralPlan(revision, blocked("FIRST_SAVE_COMMAND_UNSUPPORTED", "First save accepts unique server creation intents only", "command.operation")), nil
		}
		seen[command.HostID] = true
		servers = append(servers, firstSaveServer{id: command.HostID, typeID: command.ServerType, desiredHostname: command.DesiredHostname, address: command.Address, port: command.SSHPort, portSet: portWasSupplied(command)})
		changes = append(changes, commandSummary(command))
	}
	desired, err := deterministicYAML(map[string]any{"platform_desired_state": map[string]any{"serviceDeployments": map[string]any{}}})
	if err != nil {
		return nil, err
	}
	documents := []storedDocument{
		{LogicalPath: "ansible.cfg", After: append([]byte(nil), firstSaveAnsibleConfig...), Existed: false},
		{LogicalPath: managedInventoryDocument, After: firstSaveInventory(servers), Existed: false},
		{LogicalPath: desiredDocument, After: desired, Existed: false},
	}
	return b.storeStructuralPlan(root, revision, changes, documents)
}

func (b *Backend) planStructuralManaged(root, revision string, commands []EditCommand) (*StructuralEditPlan, error) {
	_, currentRevision, err := collectProjectDocuments(root)
	if err != nil || currentRevision != revision {
		if err == nil {
			err = blocked("PROJECT_CHANGED", "Project changed before review", "baseProjectRevision")
		}
		return blockedStructuralPlan(currentRevision, err), nil
	}
	owned, err := discoverOwnedPaths(root)
	if err != nil {
		return blockedStructuralPlan(revision, err), nil
	}
	foundInventory := false
	for _, logical := range owned {
		foundInventory = foundInventory || logical == managedInventoryDocument
	}
	if !foundInventory {
		return blockedStructuralPlan(revision, blocked("WRITE_OWNERSHIP_REQUIRED", "Managed inventory is not Installer-owned", managedInventoryDocument)), nil
	}
	command := commands[0]
	if len(commands) > 1 {
		command = EditCommand{APIVersion: EditCommandAPIVersionV4, Kind: "EditCommand", BaseProjectRevision: revision, Operation: "Batch", Commands: commands}
	}
	candidates := map[string]map[string]any{}
	originals := map[string][]byte{}
	_, changes, _, err := applyCommand(command, root, &coreadapter.Snapshot{}, candidates, originals)
	if err != nil {
		return blockedStructuralPlan(revision, err), nil
	}
	documents := make([]storedDocument, 0, len(candidates))
	paths := make([]string, 0, len(candidates))
	for logical := range candidates {
		paths = append(paths, logical)
	}
	sort.Strings(paths)
	for _, logical := range paths {
		after, encodeErr := deterministicYAML(candidates[logical])
		if encodeErr != nil {
			return blockedStructuralPlan(revision, blocked("INVALID_VALUE", "Edit value cannot be serialized safely", "command")), nil
		}
		before := originals[logical]
		if !bytes.Equal(before, after) {
			documents = append(documents, storedDocument{LogicalPath: logical, Before: append([]byte(nil), before...), After: after, Existed: true})
		}
	}
	return b.storeStructuralPlan(root, revision, changes, documents)
}

func (b *Backend) storeStructuralPlan(root, revision string, changes []SemanticChange, documents []storedDocument) (*StructuralEditPlan, error) {
	if len(documents) == 0 {
		return &StructuralEditPlan{APIVersion: StructuralPlanAPIVersion, Kind: "StructuralEditPlan", Status: "NO_CHANGE", BaseProjectRevision: revision,
			SemanticChanges: []SemanticChange{}, AffectedEntities: []string{}, AffectedDocuments: []DocumentChange{}, SaveAllowed: false}, nil
	}
	documentChanges := make([]DocumentChange, 0, len(documents))
	diffs := make([]string, 0, len(documents))
	for _, document := range documents {
		before := &DocumentState{State: "ABSENT"}
		if document.Existed {
			before = &DocumentState{State: "PRESENT", Digest: digestBytes(document.Before)}
		}
		documentChanges = append(documentChanges, DocumentChange{LogicalPath: document.LogicalPath, Before: before,
			After: &DocumentState{State: "PRESENT", Digest: digestBytes(document.After)}})
		diffs = append(diffs, boundedDiff(document.LogicalPath, document.Before, document.After))
	}
	plan := StructuralEditPlan{APIVersion: StructuralPlanAPIVersion, Kind: "StructuralEditPlan", Status: "READY", BaseProjectRevision: revision,
		SemanticChanges: changes, AffectedEntities: affectedEntities(changes), AffectedDocuments: documentChanges,
		ReviewDiff: strings.Join(diffs, ""), SaveAllowed: true, ExpiresAt: b.now().Add(b.planTTL)}
	internal := EditPlan{APIVersion: EditPlanAPIVersionV2, Kind: "EditPlan", Status: "READY", BaseProjectRevision: revision,
		AffectedDocuments: documentChanges, CommitAllowed: true, ApplyRequired: true}
	id, err := b.plans.Put(storedPlan{Created: b.now(), ProjectRoot: root, Public: internal, LocalOnly: true, Documents: documents})
	if err != nil {
		return nil, err
	}
	plan.PlanID = id
	return &plan, nil
}

func (b *Backend) CommitStructuralSave(ctx context.Context, planID string) StructuralSaveResult {
	result := b.CommitEditPlanV2(ctx, planID)
	return StructuralSaveResult{APIVersion: StructuralResultAPIVersion, Kind: "StructuralSaveResult", Status: result.Status,
		Changed: result.Changed, Finding: result.Finding, OldProjectRevision: result.OldProjectRevision,
		NewProjectRevision: result.NewProjectRevision, AffectedDocuments: result.AffectedDocuments, Timing: result.Timing, Managed: result.Managed}
}

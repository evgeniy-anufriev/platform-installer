package installer

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"platform-installer/internal/projectlifecycle"
)

var managedConfigHeader = []byte("# Managed by Platform Installer.\n# This is standard Ansible configuration; formatting may be normalized.\n")
var firstSaveAnsibleConfig = append(append([]byte(nil), managedConfigHeader...), []byte("[defaults]\ninventory = ./inventory/hosts.yml\nretry_files_enabled = False\nhost_key_checking = True\ninterpreter_python = auto_silent\nhash_behaviour = merge\n")...)

type firstSaveServer struct {
	id      string
	address string
	port    int
}

func firstSaveInventory(servers []firstSaveServer) []byte {
	sort.Slice(servers, func(i, j int) bool { return servers[i].id < servers[j].id })
	var value strings.Builder
	value.Write(managedHeader)
	value.WriteString("all:\n  hosts:\n")
	for _, server := range servers {
		fmt.Fprintf(&value, "    %s:\n      ansible_host: %s\n", server.id, server.address)
		if server.port != 0 && server.port != 22 {
			fmt.Fprintf(&value, "      ansible_port: %d\n", server.port)
		}
	}
	value.WriteString("  children:\n    platform_targets:\n      hosts:\n")
	for _, server := range servers {
		fmt.Fprintf(&value, "        %s: {}\n", server.id)
	}
	return []byte(value.String())
}

func (b *Backend) planFirstWrite(ctx context.Context, root, revision string, commands []EditCommand) (*EditPlan, error) {
	skeleton := EditCommand{APIVersion: EditCommandAPIVersionV2, Kind: "EditCommand", BaseProjectRevision: revision, Operation: "Batch", Commands: commands}
	if !projectlifecycle.FirstSaveEligible(root) {
		return blockedPlan(skeleton, revision, blocked("WRITE_OWNERSHIP_REQUIRED", "First save requires a valid empty managed project", "project")), nil
	}
	_, currentRevision, err := collectProjectDocuments(root)
	if err != nil {
		return blockedPlan(skeleton, revision, err), nil
	}
	if currentRevision != revision {
		return blockedPlan(skeleton, currentRevision, blocked("PROJECT_CHANGED", "Project changed before planning", "baseProjectRevision")), nil
	}
	seen := make(map[string]bool)
	servers := make([]firstSaveServer, 0, len(commands))
	changes := make([]SemanticChange, 0, len(commands))
	for _, command := range commands {
		if command.Operation != "CreateServer" {
			return blockedPlan(skeleton, revision, blocked("FIRST_SAVE_COMMAND_UNSUPPORTED", "First save currently accepts only server creation intents", "command.operation")), nil
		}
		if err := validateCommand(command); err != nil {
			return blockedPlan(skeleton, revision, err), nil
		}
		if seen[command.HostID] {
			return blockedPlan(skeleton, revision, blocked("INVALID_EDIT_COMMAND", "Server identifier is duplicated", "command.hostId")), nil
		}
		seen[command.HostID] = true
		servers = append(servers, firstSaveServer{id: command.HostID, address: command.Address, port: command.SSHPort})
		changes = append(changes, SemanticChange{Operation: "CreateServer", EntityID: command.HostID, SafeSummary: "CreateServer " + command.HostID})
	}
	if len(servers) == 0 {
		return blockedPlan(skeleton, revision, blocked("EDIT_SESSION_EMPTY", "First save requires at least one server", "session")), nil
	}
	desired, err := deterministicYAML(map[string]any{"platform_desired_state": map[string]any{"serviceDeployments": map[string]any{}}})
	if err != nil {
		return nil, err
	}
	documents := []storedDocument{
		{LogicalPath: "ansible.cfg", After: append([]byte(nil), firstSaveAnsibleConfig...), Existed: false},
		{LogicalPath: "inventory/hosts.yml", After: firstSaveInventory(servers), Existed: false},
		{LogicalPath: desiredDocument, After: desired, Existed: false},
	}
	stagedRoot, cleanup, err := copyProject(root)
	if err != nil {
		return blockedPlan(skeleton, revision, err), nil
	}
	defer cleanup()
	for _, document := range documents {
		path, pathErr := safeProjectPath(stagedRoot, document.LogicalPath, true)
		if pathErr != nil {
			return blockedPlan(skeleton, revision, pathErr), nil
		}
		if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
			return blockedPlan(skeleton, revision, blocked("STAGING_FAILED", "Candidate parent could not be created", "document")), nil
		}
		if err := os.WriteFile(path, document.After, 0o644); err != nil {
			return blockedPlan(skeleton, revision, blocked("STAGING_FAILED", "Candidate document could not be created", "document")), nil
		}
	}
	owned, err := discoverOwnedPaths(stagedRoot)
	if err != nil {
		return blockedPlan(skeleton, revision, err), nil
	}
	staged, err := b.core.BuildSnapshot(ctx, stagedRoot, owned)
	if err != nil {
		return blockedPlan(skeleton, revision, blocked("CORE_SNAPSHOT_FAILED", "Candidate snapshot could not be built", "project")), nil
	}
	if staged.Status != "PASS" {
		return blockedCorePlan(skeleton, revision, staged), nil
	}
	for _, server := range servers {
		if staged.Hosts[server.id] == nil {
			return blockedPlan(skeleton, revision, blocked("EDIT_SHADOWED", "Core snapshot did not contain the created server", "command.hostId")), nil
		}
	}
	documentChanges := make([]DocumentChange, 0, len(documents))
	var diffs []string
	for _, document := range documents {
		digest := digestBytes(document.After)
		documentChanges = append(documentChanges, DocumentChange{LogicalPath: document.LogicalPath,
			Before: &DocumentState{State: "ABSENT"}, After: &DocumentState{State: "PRESENT", Digest: digest}})
		diffs = append(diffs, boundedDiff(document.LogicalPath, nil, document.After))
	}
	plan := EditPlan{APIVersion: EditPlanAPIVersionV2, Kind: "EditPlan", Status: "READY", BaseProjectRevision: revision,
		CommandSummary:  SemanticChange{Operation: "FirstSave", SafeSummary: "Create first managed Ansible project inputs"},
		SemanticChanges: changes, AffectedEntities: affectedEntities(changes), AffectedDocuments: documentChanges,
		Impacts: []string{"TOPOLOGY_CHANGED"}, Validation: Validation{Status: "PASS", Findings: []Finding{}},
		ExpectedSnapshotFingerprint: staged.SnapshotFingerprint, ReviewDiff: strings.Join(diffs, ""), CommitAllowed: true, ApplyRequired: true,
		ExpiresAt: b.now().Add(b.planTTL)}
	identifier, err := b.plans.Put(storedPlan{Created: b.now(), ProjectRoot: root, Public: plan, Documents: documents})
	if err != nil {
		return nil, err
	}
	plan.PlanID = identifier
	return &plan, nil
}

func isEmptyManagedClassification(value string) bool {
	return value == projectlifecycle.ClassificationEmpty
}

func absentDocument(document DocumentChange) bool {
	return document.Before != nil && document.Before.State == "ABSENT" && document.Before.Digest == "" && document.BeforeDigest == ""
}

func presentBeforeDigest(document DocumentChange) string {
	if document.Before != nil && document.Before.State == "PRESENT" {
		return document.Before.Digest
	}
	return document.BeforeDigest
}

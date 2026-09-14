package installer

import (
	"context"
	"os"
	"path/filepath"
	"strings"

	"platform-installer/internal/projectlifecycle"
)

var managedConfigHeader = []byte("# Managed by Platform Installer.\n# This is standard Ansible configuration; formatting may be normalized.\n")
var firstSaveAnsibleConfig = append(append([]byte(nil), managedConfigHeader...), []byte("[defaults]\ninventory = ./inventory/hosts.yml\nretry_files_enabled = False\nhost_key_checking = True\ninterpreter_python = auto_silent\nhash_behaviour = merge\n")...)

type firstSaveServer struct {
	id              string
	typeID          string
	desiredHostname string
	address         string
	port            int
	portSet         bool
}

func firstSaveInventory(servers []firstSaveServer) []byte {
	hosts := make(map[string]any, len(servers))
	targets := make(map[string]any, len(servers))
	for _, server := range servers {
		value := map[string]any{"ansible_host": server.address}
		platformHost := map[string]any{}
		if server.typeID != "" {
			platformHost["type"] = server.typeID
		}
		if server.desiredHostname != "" {
			platformHost["desiredHostname"] = server.desiredHostname
		}
		if len(platformHost) > 0 {
			value["platform_host"] = platformHost
		}
		if server.portSet {
			value["ansible_port"] = server.port
		}
		hosts[server.id] = value
		targets[server.id] = map[string]any{}
	}
	value, err := deterministicYAML(map[string]any{"all": map[string]any{
		"hosts": hosts, "children": map[string]any{"platform_targets": map[string]any{"hosts": targets}},
	}})
	if err != nil {
		panic("first-save inventory is not serializable")
	}
	return value
}

func (b *Backend) planFirstWrite(ctx context.Context, root, revision string, commands []EditCommand) (*EditPlan, error) {
	skeleton := EditCommand{APIVersion: EditCommandAPIVersionV4, Kind: "EditCommand", BaseProjectRevision: revision, Operation: "Batch", Commands: commands}
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
		if err := b.validateCommand(command); err != nil {
			return blockedPlan(skeleton, revision, err), nil
		}
		if seen[command.HostID] {
			return blockedPlan(skeleton, revision, blocked("INVALID_EDIT_COMMAND", "Server identifier is duplicated", "command.hostId")), nil
		}
		seen[command.HostID] = true
		servers = append(servers, firstSaveServer{id: command.HostID, typeID: command.ServerType, desiredHostname: command.DesiredHostname, address: command.Address, port: command.SSHPort, portSet: command.SSHPort != 0 || command.presentFields["sshPort"]})
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
		host := staged.Hosts[server.id]
		if host == nil || (server.typeID != "" && host["type"] != server.typeID) || (server.desiredHostname != "" && host["desiredHostname"] != server.desiredHostname) || (server.portSet && !samePort(host["ansiblePort"], server.port)) {
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

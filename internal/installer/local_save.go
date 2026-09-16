package installer

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

const (
	maxManagedDocumentBytes  int64 = 4 * 1024 * 1024
	maxManagedAggregateBytes int64 = 64 * 1024 * 1024
	maxManagedHostDocuments        = 4096
	maxManagedEntities             = 4096
	maxManagedPlacements           = 16384
	maxManagedRoles                = 128
)

// ReadManagedProjectView reads only directly Installer-owned canonical fields.
// It does not implement Ansible precedence, service validation or derived
// provider/VIP semantics.
func ReadManagedProjectView(projectRoot string) (*ManagedProjectView, error) {
	root, err := cleanRoot(projectRoot)
	if err != nil {
		return nil, err
	}
	read := managedReadBudget{}
	document, _, err := read.ownedDocument(root, managedInventoryDocument)
	if err != nil {
		return nil, err
	}
	all := asMap(document["all"])
	hosts := asMap(all["hosts"])
	targets := asMap(asMap(asMap(all["children"])["platform_targets"])["hosts"])
	if all == nil || hosts == nil || targets == nil {
		return nil, blocked("MANAGED_DOCUMENT_INVALID", "Managed inventory roots are missing or malformed", managedInventoryDocument)
	}
	view := &ManagedProjectView{Servers: make(map[string]ManagedServer), Deployments: make(map[string]ManagedDeployment), EndpointGroups: make(map[string]ManagedEndpointGroup), MemberPlacements: []ManagedMemberPlacement{}, HostPlacements: []ManagedHostPlacement{}}
	for hostID := range targets {
		if len(view.Servers) >= maxManagedEntities || !identifierPattern.MatchString(hostID) {
			return nil, managedReadError("Managed server collection is invalid or exceeds its limit", managedInventoryDocument)
		}
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
	if err := readManagedDesiredState(root, &read, view); err != nil {
		return nil, err
	}
	if err := readManagedHostPlacements(root, &read, view); err != nil {
		return nil, err
	}
	sortManagedView(view)
	view.ProjectRevision, err = ProjectRevision(root)
	return view, err
}

type managedReadBudget struct{ total int64 }

func (budget *managedReadBudget) ownedDocument(root, logical string) (map[string]any, []byte, error) {
	content, err := readF1OwnedDocument(root, logical)
	if err != nil || int64(len(content)) > maxManagedDocumentBytes || budget.total+int64(len(content)) > maxManagedAggregateBytes {
		return nil, nil, managedReadError("Managed document is unsafe, malformed, or exceeds the read limit", logical)
	}
	budget.total += int64(len(content))
	document, err := parseManagedYAML(content)
	if err != nil {
		return nil, nil, err
	}
	return document, content, nil
}

func (budget *managedReadBudget) ownedDocumentOptional(root, logical string) (map[string]any, bool, error) {
	document, _, exists, err := budget.ownedDocumentOptionalBytes(root, logical)
	return document, exists, err
}

func (budget *managedReadBudget) ownedDocumentOptionalBytes(root, logical string) (map[string]any, []byte, bool, error) {
	content, err := readF1OwnedDocument(root, logical)
	if errors.Is(err, os.ErrNotExist) || os.IsNotExist(err) {
		return nil, nil, false, nil
	}
	// This is only an absence classification after the authoritative
	// handle-bound read failed. It never authorizes a later pathname read.
	if err != nil {
		if _, statErr := os.Lstat(filepath.Join(root, filepath.FromSlash(logical))); errors.Is(statErr, os.ErrNotExist) {
			return nil, nil, false, nil
		}
	}
	if err != nil || int64(len(content)) > maxManagedDocumentBytes || budget.total+int64(len(content)) > maxManagedAggregateBytes {
		return nil, nil, false, managedReadError("Managed document is unsafe, malformed, or exceeds the read limit", logical)
	}
	budget.total += int64(len(content))
	document, err := parseManagedYAML(content)
	if err != nil {
		return nil, nil, false, err
	}
	return document, content, true, nil
}

func managedReadError(message, field string) error {
	return blocked("MANAGED_DOCUMENT_INVALID", message, field)
}

func readManagedDesiredState(root string, budget *managedReadBudget, view *ManagedProjectView) error {
	document, _, err := budget.ownedDocument(root, desiredDocument)
	if err != nil {
		return err
	}
	state := asMap(document["platform_desired_state"])
	deployments := asMap(state["serviceDeployments"])
	groups := asMap(state["endpointGroups"])
	if state == nil || deployments == nil {
		return managedReadError("Managed desired-state roots are missing or malformed", desiredDocument)
	}
	if groups == nil {
		groups = map[string]any{}
	}
	for id, raw := range deployments {
		if len(view.Deployments) >= maxManagedEntities || !identifierPattern.MatchString(id) {
			return managedReadError("Managed deployment collection is invalid or exceeds its limit", desiredDocument)
		}
		deployment := asMap(raw)
		serviceType, serviceOK := deployment["serviceType"].(string)
		mode, modeOK := deployment["mode"].(string)
		endpointGroup, endpointOK := optionalString(deployment, "endpointGroup")
		if deployment == nil || !serviceOK || !identifierPattern.MatchString(serviceType) || !modeOK || !identifierPattern.MatchString(mode) || !endpointOK || (endpointGroup != "" && !identifierPattern.MatchString(endpointGroup)) {
			return managedReadError("Managed deployment is malformed", desiredDocument)
		}
		view.Deployments[id] = ManagedDeployment{DeploymentID: id, ServiceType: serviceType, Mode: mode, EndpointGroup: endpointGroup}
	}
	for id, raw := range groups {
		if len(view.EndpointGroups) >= maxManagedEntities || !identifierPattern.MatchString(id) {
			return managedReadError("Managed endpoint-group collection is invalid or exceeds its limit", desiredDocument)
		}
		group := asMap(raw)
		address := asMap(group["address"])
		domain, domainOK := address["domain"].(string)
		wildcard, wildcardOK := address["wildcard"].(bool)
		if group == nil || address == nil || !domainOK || domain == "" || !wildcardOK {
			return managedReadError("Managed endpoint group is malformed", desiredDocument)
		}
		view.EndpointGroups[id] = ManagedEndpointGroup{EndpointGroupID: id, Domain: domain, Wildcard: wildcard}
	}
	return nil
}

func readManagedHostPlacements(root string, budget *managedReadBudget, view *ManagedProjectView) error {
	hostIDs := make([]string, 0, len(view.Servers))
	for hostID := range view.Servers {
		hostIDs = append(hostIDs, hostID)
	}
	sort.Strings(hostIDs)
	if len(hostIDs) > maxManagedHostDocuments {
		return managedReadError("Managed host document collection exceeds its limit", "inventory/host_vars")
	}
	for _, hostID := range hostIDs {
		logical := managedHostDocument(hostID)
		document, exists, documentErr := budget.ownedDocumentOptional(root, logical)
		if documentErr != nil {
			// A server without an owned host-vars document has no direct placement.
			// Do not inspect an unbound pathname merely to distinguish absence.
			return documentErr
		}
		if !exists {
			continue
		}
		placements := asMap(document["platform_deployments"])
		if placements == nil {
			return managedReadError("Managed placement root is missing or malformed", logical)
		}
		for deploymentID, raw := range placements {
			if !identifierPattern.MatchString(deploymentID) {
				return managedReadError("Managed placement deployment identifier is invalid", logical)
			}
			placement := asMap(raw)
			if placement == nil {
				return managedReadError("Managed placement is malformed", logical)
			}
			members, hasMembers := placement["members"]
			_, hasRoles := placement["roles"]
			if hasMembers && hasRoles {
				return managedReadError("Managed placement ambiguously mixes member and host forms", logical)
			}
			if hasMembers {
				memberMap := asMap(members)
				if memberMap == nil {
					return managedReadError("Managed member placement is malformed", logical)
				}
				for memberID, memberRaw := range memberMap {
					roles, rolesErr := managedRoles(asMap(memberRaw)["roles"], logical)
					if rolesErr != nil || !identifierPattern.MatchString(memberID) || len(view.MemberPlacements)+len(view.HostPlacements) >= maxManagedPlacements {
						return managedReadError("Managed member placement is invalid or exceeds its limit", logical)
					}
					view.MemberPlacements = append(view.MemberPlacements, ManagedMemberPlacement{DeploymentID: deploymentID, MemberID: memberID, HostID: hostID, Roles: roles})
				}
				continue
			}
			roles, rolesErr := managedRoles(placement["roles"], logical)
			if rolesErr != nil || len(view.MemberPlacements)+len(view.HostPlacements) >= maxManagedPlacements {
				return managedReadError("Managed host placement is invalid or exceeds its limit", logical)
			}
			view.HostPlacements = append(view.HostPlacements, ManagedHostPlacement{DeploymentID: deploymentID, HostID: hostID, Roles: roles})
		}
	}
	return nil
}

func optionalString(value map[string]any, key string) (string, bool) {
	raw, found := value[key]
	if !found {
		return "", true
	}
	text, ok := raw.(string)
	return text, ok
}

func managedRoles(raw any, field string) ([]string, error) {
	if raw == nil {
		return []string{}, nil
	}
	values := asSlice(raw)
	if values == nil || len(values) > maxManagedRoles {
		return nil, managedReadError("Managed placement roles are malformed or exceed their limit", field)
	}
	seen := make(map[string]bool, len(values))
	roles := make([]string, 0, len(values))
	for _, rawRole := range values {
		role, ok := rawRole.(string)
		if !ok || !identifierPattern.MatchString(role) || seen[role] {
			return nil, managedReadError("Managed placement roles are invalid", field)
		}
		seen[role] = true
		roles = append(roles, role)
	}
	sort.Strings(roles)
	return roles, nil
}

func sortManagedView(view *ManagedProjectView) {
	sort.Slice(view.MemberPlacements, func(left, right int) bool {
		leftValue, rightValue := view.MemberPlacements[left], view.MemberPlacements[right]
		return leftValue.DeploymentID+"\x00"+leftValue.MemberID+"\x00"+leftValue.HostID < rightValue.DeploymentID+"\x00"+rightValue.MemberID+"\x00"+rightValue.HostID
	})
	sort.Slice(view.HostPlacements, func(left, right int) bool {
		leftValue, rightValue := view.HostPlacements[left], view.HostPlacements[right]
		return leftValue.DeploymentID+"\x00"+leftValue.HostID < rightValue.DeploymentID+"\x00"+rightValue.HostID
	})
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

// PlanStructuralSave builds a bounded local preview for server and topology intents and
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
		if command.Operation != "CreateServer" && command.Operation != "UpdateServer" && command.Operation != "DeleteServer" && !topologyOperation(command.Operation) {
			return blockedStructuralPlan(revision, blocked("EDIT_OPERATION_NOT_AVAILABLE", "Edit operation is not available in this editor", "command.operation")), nil
		}
		if err := b.validateCommand(command); err != nil {
			return blockedStructuralPlan(revision, err), nil
		}
	}
	root, err := cleanRoot(projectRoot)
	if err != nil {
		return blockedStructuralPlan(revision, err), nil
	}
	return b.planStructuralCandidate(ctx, root, classification, revision, commands)
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

package installer

import (
	"bytes"
	"context"
	"sort"
	"strings"

	"platform-installer/internal/projectlifecycle"
)

const maxStructuralDocuments = 64

type structuralCandidate struct {
	root       string
	documents  map[string]map[string]any
	originals  map[string][]byte
	existed    map[string]bool
	dirty      map[string]bool
	sourceHost map[string]bool
	firstSave  bool
}

type topologyMutationSet struct {
	deletedServers     map[string]bool
	deletedDeployments map[string]bool
	deletedGroups      map[string]bool
	reconciled         map[string]bool
	deletedAuthorities map[string]bool
	deletedProfiles    map[string]bool
	deletedTLSProfiles map[string]bool
}

func topologyOperation(operation string) bool {
	if applicationEditOperation(operation) {
		return true
	}
	switch operation {
	case "SetProjectSetting":
		return true
	case "CreateServiceDeployment", "DeleteServiceDeployment",
		"ReconcileDeploymentPlacement", "ReconcileHostScopedDeploymentPlacement",
		"CreateEndpointGroup", "UpdateEndpointGroup", "DeleteEndpointGroup",
		"SetServiceEndpointGroup", "ClearServiceEndpointGroup",
		"ReconcileEndpointProvider", "ClearEndpointProvider":
		return true
	case "SetServiceConfigurationValue", "RemoveServiceConfigurationOverride":
		return true
	case "CreateCertificateAuthority", "UpdateCertificateAuthority", "DeleteCertificateAuthority",
		"CreateCertificateProfile", "UpdateCertificateProfile", "DeleteCertificateProfile",
		"CreateTLSProfile", "UpdateTLSProfile", "DeleteTLSProfile",
		"CreateCertificateScope", "UpdateCertificateScope", "DeleteCertificateScope":
		return true
	default:
		return false
	}
}

func commandNeedsCatalog(command EditCommand) bool {
	switch command.Operation {
	case "CreateServiceDeployment", "SetServiceEndpointGroup", "ReconcileEndpointProvider", "SetServiceConfigurationValue", "RemoveServiceConfigurationOverride", "DeleteTLSProfile":
		return true
	case "ReconcileDeploymentPlacement":
		return len(command.Members) != 0
	case "ReconcileHostScopedDeploymentPlacement":
		return len(command.Hosts) != 0
	default:
		return false
	}
}

func (b *Backend) planStructuralCandidate(ctx context.Context, root, classification, revision string, commands []EditCommand) (*StructuralEditPlan, error) {
	currentRevision, err := ProjectRevision(root)
	if err != nil || currentRevision != revision {
		if err == nil {
			err = blocked("PROJECT_CHANGED", "Project changed before review", "baseProjectRevision")
		}
		return blockedStructuralPlan(currentRevision, err), nil
	}
	if err := validateStructuralCommandConflicts(commands); err != nil {
		return blockedStructuralPlan(revision, err), nil
	}
	var catalog *projectlifecycle.ProjectCatalogView
	for _, command := range commands {
		if !commandNeedsCatalog(command) {
			continue
		}
		if b.catalogResolver == nil {
			return blockedStructuralPlan(revision, blocked("PROJECT_CATALOG_UNAVAILABLE", "Compatible project catalog is unavailable", "project.catalogLock")), nil
		}
		catalog, err = b.catalogResolver(ctx, root)
		if err != nil || catalog == nil || catalog.Status != "READY" {
			code := "PROJECT_CATALOG_UNAVAILABLE"
			if catalog != nil && catalog.Status == "INCOMPATIBLE" {
				code = "PROJECT_CATALOG_INCOMPATIBLE"
			}
			return blockedStructuralPlan(revision, blocked(code, "Compatible project catalog cannot authorize this edit", "project.catalogLock")), nil
		}
		break
	}
	// Optional local metadata enables authoring defaults without making Save
	// depend on a runtime or blocking unrelated edits when a bundle is absent.
	if catalog == nil && b.catalogResolver != nil {
		if available, readErr := b.catalogResolver(ctx, root); readErr == nil && available != nil && available.Status == "READY" {
			catalog = available
		}
	}
	candidate, err := loadStructuralCandidate(root, classification)
	if err != nil {
		return blockedStructuralPlan(revision, err), nil
	}
	changes, mutations, err := candidate.reduce(commands, catalog)
	if err != nil {
		return blockedStructuralPlan(revision, err), nil
	}
	if err := candidate.validateFinalReferences(mutations, catalog); err != nil {
		return blockedStructuralPlan(revision, err), nil
	}
	documents, err := candidate.storedDocuments()
	if err != nil {
		return blockedStructuralPlan(revision, err), nil
	}
	if len(documents) > maxStructuralDocuments {
		return blockedStructuralPlan(revision, blocked("EDIT_SESSION_COMMANDS_UNSUPPORTED", "This edit affects too many managed documents", "session")), nil
	}
	afterRevision, revisionErr := ProjectRevision(root)
	if revisionErr != nil || afterRevision != revision {
		return blockedStructuralPlan(afterRevision, blocked("PROJECT_CHANGED", "Project changed during review", "baseProjectRevision")), nil
	}
	return b.storeStructuralPlan(root, revision, changes, documents)
}

func validateStructuralCommandConflicts(commands []EditCommand) error {
	lifecycle := make(map[string]bool)
	applicationWrites := map[string]bool{}
	relations := make(map[string]bool)
	placements := make(map[string]bool)
	for _, command := range commands {
		if applicationEditOperation(command.Operation) {
			for _, key := range applicationWritePaths(command) {
				for prior := range applicationWrites {
					if key == prior || strings.HasPrefix(key, prior+"/") || strings.HasPrefix(prior, key+"/") {
						return blocked("EDIT_COMMAND_CONFLICT", "Application library edits overlap", "command")
					}
				}
				applicationWrites[key] = true
			}
		}
		var key string
		switch command.Operation {
		case "CreateServiceDeployment", "DeleteServiceDeployment":
			key = "deployment/" + command.DeploymentID
		case "CreateEndpointGroup", "UpdateEndpointGroup", "DeleteEndpointGroup":
			key = "endpoint/" + command.EndpointGroupID
		}
		if key != "" {
			if lifecycle[key] {
				return blocked("EDIT_COMMAND_CONFLICT", "Edit session contains conflicting entity lifecycle intents", "command")
			}
			lifecycle[key] = true
		}
		switch command.Operation {
		case "SetProjectSetting":
			key = "project-setting/" + command.Setting
			if relations[key] {
				return blocked("EDIT_COMMAND_CONFLICT", "Edit session contains conflicting project setting intents", "command.setting")
			}
			relations[key] = true
		case "SetServiceEndpointGroup", "ClearServiceEndpointGroup":
			key = "endpoint-relation/" + command.DeploymentID
			if relations[key] {
				return blocked("EDIT_COMMAND_CONFLICT", "Edit session contains conflicting endpoint intents", "command")
			}
			relations[key] = true
		case "ReconcileEndpointProvider", "ClearEndpointProvider":
			key = "provider-relation/" + command.DeploymentID
			if relations[key] {
				return blocked("EDIT_COMMAND_CONFLICT", "Edit session contains conflicting provider intents", "command")
			}
			relations[key] = true
		case "ReconcileDeploymentPlacement", "ReconcileHostScopedDeploymentPlacement":
			key = command.DeploymentID
			if placements[key] {
				return blocked("EDIT_COMMAND_CONFLICT", "Edit session contains conflicting placement intents", "command")
			}
			placements[key] = true
		case "SetServiceConfigurationValue", "RemoveServiceConfigurationOverride":
			key = "configuration/" + command.DeploymentID + "/" + command.Scope + "/" + command.MemberID + "/" + command.Setting
			if relations[key] {
				return blocked("EDIT_COMMAND_CONFLICT", "Edit session contains conflicting configuration intents", "command")
			}
			relations[key] = true
		}
	}
	return nil
}

func loadStructuralCandidate(root, classification string) (*structuralCandidate, error) {
	value := &structuralCandidate{root: root, documents: make(map[string]map[string]any), originals: make(map[string][]byte), existed: make(map[string]bool), dirty: make(map[string]bool), sourceHost: make(map[string]bool)}
	if isEmptyManagedClassification(classification) {
		if !projectlifecycle.FirstSaveEligible(root) {
			return nil, blocked("WRITE_OWNERSHIP_REQUIRED", "First save requires a valid empty managed project", "project")
		}
		value.firstSave = true
		value.documents[managedInventoryDocument] = map[string]any{"all": map[string]any{"hosts": map[string]any{}, "children": map[string]any{"platform_targets": map[string]any{"hosts": map[string]any{}}}}}
		value.documents[desiredDocument] = map[string]any{"platform_desired_state": map[string]any{"serviceDeployments": map[string]any{}, "endpointGroups": map[string]any{}}}
		value.dirty[managedInventoryDocument] = true
		value.dirty[desiredDocument] = true
		return value, nil
	}
	if classification != projectlifecycle.ClassificationManaged {
		return nil, blocked("WRITE_OWNERSHIP_REQUIRED", "Structural save requires an Installer-managed project", "project")
	}
	budget := &managedReadBudget{}
	for _, logical := range []string{managedInventoryDocument, desiredDocument} {
		document, content, err := budget.ownedDocument(root, logical)
		if err != nil {
			return nil, err
		}
		value.documents[logical], value.originals[logical], value.existed[logical] = document, content, true
	}
	hostPaths, err := enumerateManagedHostDocuments(root)
	if err != nil {
		return nil, err
	}
	for _, logical := range hostPaths {
		document, content, exists, err := budget.ownedDocumentOptionalBytes(root, logical)
		if err != nil {
			return nil, err
		}
		if !exists {
			continue
		}
		value.documents[logical], value.originals[logical] = document, content
		value.existed[logical] = true
		value.sourceHost[hostIDFromManagedDocument(logical)] = true
	}
	return value, nil
}

func hostIDFromManagedDocument(logical string) string {
	const prefix = "inventory/host_vars/"
	return strings.TrimSuffix(strings.TrimPrefix(logical, prefix), "/platform-installer.yml")
}

func (candidate *structuralCandidate) inventory() (*managedServerInventory, error) {
	document := candidate.documents[managedInventoryDocument]
	all := asMap(document["all"])
	hosts := asMap(all["hosts"])
	children := asMap(all["children"])
	targets := asMap(asMap(children["platform_targets"])["hosts"])
	if document == nil || all == nil || hosts == nil || children == nil || targets == nil {
		return nil, managedReadError("Managed inventory roots are missing or malformed", managedInventoryDocument)
	}
	return &managedServerInventory{document: document, hosts: hosts, targets: targets}, nil
}

func (candidate *structuralCandidate) desired() (map[string]any, map[string]any, map[string]any, error) {
	document := candidate.documents[desiredDocument]
	state := asMap(document["platform_desired_state"])
	deployments := asMap(state["serviceDeployments"])
	groups := asMap(state["endpointGroups"])
	if document == nil || state == nil || deployments == nil {
		return nil, nil, nil, managedReadError("Managed desired-state roots are missing or malformed", desiredDocument)
	}
	if groups == nil {
		groups = map[string]any{}
		state["endpointGroups"] = groups
	}
	return state, deployments, groups, nil
}

func (candidate *structuralCandidate) reduce(commands []EditCommand, catalog *projectlifecycle.ProjectCatalogView) ([]SemanticChange, topologyMutationSet, error) {
	mutations := topologyMutationSet{deletedServers: make(map[string]bool), deletedDeployments: make(map[string]bool), deletedGroups: make(map[string]bool), reconciled: make(map[string]bool), deletedAuthorities: make(map[string]bool), deletedProfiles: make(map[string]bool), deletedTLSProfiles: make(map[string]bool)}
	changes := make([]SemanticChange, 0, len(commands))
	inventory, err := candidate.inventory()
	if err != nil {
		return nil, mutations, err
	}
	state, deployments, groups, err := candidate.desired()
	if err != nil {
		return nil, mutations, err
	}
	for _, command := range commands {
		if command.Operation != "SetProjectSetting" {
			continue
		}
		candidate.documents[desiredDocument][command.Setting] = command.Value
		candidate.dirty[desiredDocument] = true
		changes = append(changes, commandSummary(command))
	}
	for _, command := range commands {
		if command.Operation != "CreateServer" && command.Operation != "UpdateServer" && command.Operation != "DeleteServer" {
			continue
		}
		if _, _, err := applyServerCommand(command, candidate.root, nil, candidate.documents, candidate.originals); err != nil {
			return nil, mutations, err
		}
		candidate.dirty[managedInventoryDocument] = true
		if command.Operation == "DeleteServer" {
			mutations.deletedServers[command.HostID] = true
		}
		changes = append(changes, commandSummary(command))
	}
	for _, command := range commands {
		if !pkiOperation(command.Operation) {
			continue
		}
		if err := reducePKICommand(state, command, mutations); err != nil {
			return nil, mutations, err
		}
		candidate.dirty[desiredDocument] = true
		changes = append(changes, commandSummary(command))
	}
	for _, command := range commands {
		switch command.Operation {
		case "CreateServiceDeployment":
			if deployments[command.DeploymentID] != nil {
				return nil, mutations, blocked("INVALID_EDIT_COMMAND", "Deployment identifier already exists", "command.deploymentId")
			}
			if err := admitCatalogDeployment(catalog, command.ServiceType, command.Mode); err != nil {
				return nil, mutations, err
			}
			deployments[command.DeploymentID] = map[string]any{"serviceType": command.ServiceType, "mode": command.Mode}
			candidate.dirty[desiredDocument] = true
			changes = append(changes, commandSummary(command))
		case "DeleteServiceDeployment":
			if deployments[command.DeploymentID] == nil {
				return nil, mutations, blocked("INVALID_EDIT_COMMAND", "Deployment does not exist", "command.deploymentId")
			}
			delete(deployments, command.DeploymentID)
			mutations.deletedDeployments[command.DeploymentID] = true
			candidate.dirty[desiredDocument] = true
			changes = append(changes, commandSummary(command))
		case "CreateEndpointGroup":
			if groups[command.EndpointGroupID] != nil {
				return nil, mutations, blocked("INVALID_EDIT_COMMAND", "Endpoint-group identifier already exists", "command.endpointGroupId")
			}
			groups[command.EndpointGroupID] = deepCopy(command.EndpointGroup)
			candidate.dirty[desiredDocument] = true
			changes = append(changes, commandSummary(command))
		case "UpdateEndpointGroup":
			existing := asMap(groups[command.EndpointGroupID])
			if existing == nil {
				return nil, mutations, blocked("INVALID_EDIT_COMMAND", "Endpoint group does not exist", "command.endpointGroupId")
			}
			// Address is the only F2-owned endpoint-group field. Preserve
			// extension fields instead of serializing the transport DTO back
			// over the complete canonical object.
			existing["address"] = deepCopy(command.EndpointGroup["address"])
			candidate.dirty[desiredDocument] = true
			changes = append(changes, commandSummary(command))
		case "DeleteEndpointGroup":
			if groups[command.EndpointGroupID] == nil {
				return nil, mutations, blocked("INVALID_EDIT_COMMAND", "Endpoint group does not exist", "command.endpointGroupId")
			}
			delete(groups, command.EndpointGroupID)
			mutations.deletedGroups[command.EndpointGroupID] = true
			candidate.dirty[desiredDocument] = true
			changes = append(changes, commandSummary(command))
		}
	}
	for _, command := range commands {
		switch command.Operation {
		case "SetServiceEndpointGroup":
			deployment := asMap(deployments[command.DeploymentID])
			if deployment == nil || groups[command.EndpointGroupID] == nil {
				return nil, mutations, blocked("REFERENCE_NOT_FOUND", "Endpoint assignment references a missing entity", "command")
			}
			serviceType, _ := deployment["serviceType"].(string)
			if !catalogEndpointConsumer(catalog, serviceType) {
				return nil, mutations, blocked("CAPABILITY_NOT_SUPPORTED", "Service does not declare endpoint-consumer capability", "command.deploymentId")
			}
			deployment["endpointGroup"] = command.EndpointGroupID
			candidate.dirty[desiredDocument] = true
			changes = append(changes, commandSummary(command))
		case "ClearServiceEndpointGroup":
			deployment := asMap(deployments[command.DeploymentID])
			if deployment != nil {
				delete(deployment, "endpointGroup")
				candidate.dirty[desiredDocument] = true
			}
			changes = append(changes, commandSummary(command))
		case "ReconcileEndpointProvider":
			deployment := asMap(deployments[command.DeploymentID])
			if deployment == nil || groups[command.EndpointGroupID] == nil {
				return nil, mutations, blocked("REFERENCE_NOT_FOUND", "Provider reconcile references a missing entity", "command")
			}
			serviceType, _ := deployment["serviceType"].(string)
			if !catalogEndpointProvider(catalog, serviceType) {
				return nil, mutations, blocked("CAPABILITY_NOT_SUPPORTED", "Service does not declare endpoint-provider capability", "command.deploymentId")
			}
			deployment["endpointGroupRef"] = command.EndpointGroupID
			deployment["virtualRouterId"] = command.VirtualRouterID
			deployment["virtualAddresses"] = virtualAddressValues(command.VirtualAddresses)
			candidate.dirty[desiredDocument] = true
			changes = append(changes, commandSummary(command))
		case "ClearEndpointProvider":
			deployment := asMap(deployments[command.DeploymentID])
			if deployment == nil {
				return nil, mutations, blocked("REFERENCE_NOT_FOUND", "Provider clear references a missing deployment", "command.deploymentId")
			}
			delete(deployment, "endpointGroupRef")
			delete(deployment, "virtualRouterId")
			delete(deployment, "virtualAddresses")
			candidate.dirty[desiredDocument] = true
			changes = append(changes, commandSummary(command))
		case "ReconcileDeploymentPlacement", "ReconcileHostScopedDeploymentPlacement":
			if err := candidate.reconcilePlacement(command, deployments, inventory, catalog); err != nil {
				return nil, mutations, err
			}
			mutations.reconciled[command.DeploymentID] = true
			changes = append(changes, commandSummary(command))
		}
	}
	for _, command := range commands {
		if command.Operation != "SetServiceConfigurationValue" && command.Operation != "RemoveServiceConfigurationOverride" {
			continue
		}
		changed, applyErr := candidate.applyConfigurationCommand(command, deployments, catalog)
		if applyErr != nil {
			return nil, mutations, applyErr
		}
		if changed {
			changes = append(changes, commandSummary(command))
		}
	}
	for _, command := range commands {
		if !applicationEditOperation(command.Operation) {
			continue
		}
		if err := candidate.reduceApplicationEdit(command); err != nil {
			return nil, mutations, err
		}
		changes = append(changes, commandSummary(command))
	}
	if profiles := asMap(state["tlsProfiles"]); len(profiles) > 0 && catalog != nil && catalog.Status == "READY" {
		profileIDs, deploymentIDs := make([]string, 0, len(profiles)), make([]string, 0, len(deployments))
		for id := range profiles {
			profileIDs = append(profileIDs, id)
		}
		for id := range deployments {
			deploymentIDs = append(deploymentIDs, id)
		}
		sort.Strings(profileIDs)
		sort.Strings(deploymentIDs)
		for _, id := range deploymentIDs {
			deployment := asMap(deployments[id])
			serviceType, _ := deployment["serviceType"].(string)
			modeID, _ := deployment["mode"].(string)
			service, mode := catalogServiceMode(catalog, serviceType, modeID)
			if service == nil || mode == nil {
				continue
			}
			for _, setting := range service.ConfigurationSettings {
				if setting.ReferenceKind != "TLS_PROFILE" || setting.EditorShape != "TLS_PROFILE" || setting.Kind != "MANAGED" || !settingAllowsScope(&setting, "DEPLOYMENT") {
					continue
				}
				if _, present := asMap(deployment["configuration"])[setting.ID]; present {
					continue
				}
				auto := EditCommand{Operation: "SetServiceConfigurationValue", DeploymentID: id, Scope: "DEPLOYMENT", Setting: setting.ID, Value: profileIDs[0]}
				changed, applyErr := candidate.applyConfigurationCommand(auto, deployments, catalog)
				if applyErr != nil {
					return nil, mutations, applyErr
				}
				if changed {
					changes = append(changes, commandSummary(auto))
				}
			}
		}
	}
	if len(inventory.hosts) > maxManagedEntities || len(deployments) > maxManagedEntities || len(groups) > maxManagedEntities {
		return nil, mutations, blocked("INVALID_EDIT_COMMAND", "Managed entity collection exceeds its limit", "command")
	}
	return changes, mutations, nil
}

func admitCatalogDeployment(catalog *projectlifecycle.ProjectCatalogView, serviceType, mode string) error {
	service, selected := catalogServiceMode(catalog, serviceType, mode)
	if service == nil || selected == nil {
		return blocked("CATALOG_VALUE_UNKNOWN", "Service type or mode is not declared by the project catalog", "command")
	}
	return nil
}

func catalogServiceMode(catalog *projectlifecycle.ProjectCatalogView, serviceType, mode string) (*projectlifecycle.ProjectCatalogService, *projectlifecycle.ProjectCatalogMode) {
	if catalog == nil || catalog.Status != "READY" {
		return nil, nil
	}
	for index := range catalog.Services {
		service := &catalog.Services[index]
		if service.ID != serviceType {
			continue
		}
		for modeIndex := range service.Modes {
			if service.Modes[modeIndex].ID == mode {
				return service, &service.Modes[modeIndex]
			}
		}
		return service, nil
	}
	return nil, nil
}

func catalogEndpointConsumer(catalog *projectlifecycle.ProjectCatalogView, serviceType string) bool {
	if catalog == nil || catalog.Status != "READY" {
		return false
	}
	service, _ := catalogServiceMode(catalog, serviceType, "")
	if service == nil {
		for index := range catalog.Services {
			if catalog.Services[index].ID == serviceType {
				return catalog.Services[index].EndpointConsumer
			}
		}
		return false
	}
	return service.EndpointConsumer
}

func catalogEndpointProvider(catalog *projectlifecycle.ProjectCatalogView, serviceType string) bool {
	if catalog == nil || catalog.Status != "READY" {
		return false
	}
	for index := range catalog.Services {
		if catalog.Services[index].ID == serviceType {
			return catalog.Services[index].EndpointProvider
		}
	}
	return false
}

func virtualAddressValues(values []VirtualAddress) []any {
	result := make([]any, len(values))
	for index, value := range values {
		result[index] = map[string]any{"address": value.Address, "interface": value.Interface}
	}
	return result
}

func (candidate *structuralCandidate) hostDocument(hostID string, create bool) (map[string]any, error) {
	logical := managedHostDocument(hostID)
	if document := candidate.documents[logical]; document != nil {
		placements := asMap(document["platform_deployments"])
		if placements == nil {
			return nil, managedReadError("Managed placement root is missing or malformed", logical)
		}
		return placements, nil
	}
	if !create {
		return nil, nil
	}
	document := map[string]any{"platform_deployments": map[string]any{}}
	candidate.documents[logical] = document
	candidate.existed[logical] = false
	return asMap(document["platform_deployments"]), nil
}

func (candidate *structuralCandidate) reconcilePlacement(command EditCommand, deployments map[string]any, inventory *managedServerInventory, catalog *projectlifecycle.ProjectCatalogView) error {
	deployment := asMap(deployments[command.DeploymentID])
	nonEmpty := len(command.Members) != 0 || len(command.Hosts) != 0
	if nonEmpty && deployment == nil {
		return blocked("REFERENCE_NOT_FOUND", "Placement references a missing deployment", "command.deploymentId")
	}
	if nonEmpty {
		serviceType, _ := deployment["serviceType"].(string)
		modeID, _ := deployment["mode"].(string)
		_, mode := catalogServiceMode(catalog, serviceType, modeID)
		if mode == nil {
			return blocked("CATALOG_VALUE_UNKNOWN", "Deployment mode is not declared by the project catalog", "command.deploymentId")
		}
		expectedKind := "MEMBER_SCOPED"
		roles := make(map[string]bool, len(mode.Roles))
		for _, role := range mode.Roles {
			roles[role] = true
		}
		if command.Operation == "ReconcileHostScopedDeploymentPlacement" {
			expectedKind = "HOST_SCOPED"
		}
		if mode.PlacementKind != expectedKind {
			return blocked("PLACEMENT_KIND_MISMATCH", "Placement form does not match the catalog mode", "command.operation")
		}
		for _, member := range command.Members {
			for _, role := range member.Roles {
				if !roles[role] {
					return blocked("CATALOG_VALUE_UNKNOWN", "Placement role is not declared by the catalog mode", "command.members.roles")
				}
			}
		}
		for _, host := range command.Hosts {
			for _, role := range host.Roles {
				if !roles[role] {
					return blocked("CATALOG_VALUE_UNKNOWN", "Placement role is not declared by the catalog mode", "command.hosts.roles")
				}
			}
		}
	}
	existingMembers := make(map[string]map[string]any)
	existingHosts := make(map[string]map[string]any)
	union := make(map[string]bool, len(candidate.sourceHost)+len(inventory.hosts))
	for hostID := range candidate.sourceHost {
		union[hostID] = true
	}
	for hostID := range inventory.hosts {
		union[hostID] = true
	}
	for hostID := range union {
		placements, err := candidate.hostDocument(hostID, false)
		if err != nil {
			return err
		}
		if placements == nil {
			continue
		}
		current := asMap(placements[command.DeploymentID])
		if current == nil {
			continue
		}
		if members := asMap(current["members"]); members != nil {
			for memberID, raw := range members {
				if member := asMap(raw); member != nil {
					existingMembers[memberID] = deepCopy(member).(map[string]any)
				}
			}
		} else {
			existingHosts[hostID] = deepCopy(current).(map[string]any)
		}
		delete(placements, command.DeploymentID)
		candidate.dirty[managedHostDocument(hostID)] = true
	}
	for _, member := range command.Members {
		if inventory.hosts[member.HostID] == nil || inventory.targets[member.HostID] == nil {
			return blocked("REFERENCE_NOT_FOUND", "Placement references a missing server", "command.members.hostId")
		}
		placements, err := candidate.hostDocument(member.HostID, true)
		if err != nil {
			return err
		}
		entry := asMap(placements[command.DeploymentID])
		if entry == nil {
			entry = map[string]any{"members": map[string]any{}}
			placements[command.DeploymentID] = entry
		}
		members := asMap(entry["members"])
		value := existingMembers[member.MemberID]
		if value == nil {
			value = map[string]any{}
		}
		if len(member.Roles) == 0 {
			delete(value, "roles")
		} else {
			value["roles"] = stringValues(member.Roles)
		}
		members[member.MemberID] = value
		candidate.dirty[managedHostDocument(member.HostID)] = true
	}
	for _, host := range command.Hosts {
		if inventory.hosts[host.HostID] == nil || inventory.targets[host.HostID] == nil {
			return blocked("REFERENCE_NOT_FOUND", "Placement references a missing server", "command.hosts.hostId")
		}
		placements, err := candidate.hostDocument(host.HostID, true)
		if err != nil {
			return err
		}
		value := existingHosts[host.HostID]
		if value == nil {
			value = map[string]any{}
		}
		delete(value, "members")
		if len(host.Roles) == 0 {
			delete(value, "roles")
		} else {
			value["roles"] = stringValues(host.Roles)
		}
		if command.APIVersion == EditCommandAPIVersionV9 || command.APIVersion == EditCommandAPIVersionV10 {
			// v1alpha9 makes priority a required part of each final host-scoped
			// placement entry. Earlier immutable contracts retain their existing
			// preservation behavior for fields they cannot express.
			value["priority"] = host.Priority
		}
		placements[command.DeploymentID] = value
		candidate.dirty[managedHostDocument(host.HostID)] = true
	}
	return nil
}

func stringValues(values []string) []any {
	result := make([]any, len(values))
	for index, value := range values {
		result[index] = value
	}
	return result
}

func (candidate *structuralCandidate) validateFinalReferences(mutations topologyMutationSet, catalog *projectlifecycle.ProjectCatalogView) error {
	if err := candidate.validateApplicationReferences(); err != nil {
		return err
	}
	inventory, err := candidate.inventory()
	if err != nil {
		return err
	}
	state, deployments, groups, err := candidate.desired()
	if err != nil {
		return err
	}
	members := make(map[string]bool)
	placementCount := 0
	deletedDeploymentPlacements := make(map[string][]string)
	for logical, document := range candidate.documents {
		if !strings.HasPrefix(logical, "inventory/host_vars/") {
			continue
		}
		hostID := hostIDFromManagedDocument(logical)
		placements := asMap(document["platform_deployments"])
		if placements == nil {
			return managedReadError("Managed placement root is missing or malformed", logical)
		}
		for deploymentID, raw := range placements {
			if deployments[deploymentID] == nil {
				if mutations.deletedDeployments[deploymentID] {
					placement := asMap(raw)
					if placement == nil {
						return managedReadError("Managed placement is malformed", logical)
					}
					memberRaw, hasMembers := placement["members"]
					_, hasRoles := placement["roles"]
					if hasMembers && hasRoles {
						return managedReadError("Managed placement ambiguously mixes member and host forms", logical)
					}
					if !hasMembers {
						if _, rolesErr := managedRoles(placement["roles"], logical); rolesErr != nil {
							return rolesErr
						}
						deletedDeploymentPlacements[deploymentID] = append(deletedDeploymentPlacements[deploymentID], "узел "+hostID)
					} else {
						memberMap := asMap(memberRaw)
						if memberMap == nil {
							return managedReadError("Managed member placement is malformed", logical)
						}
						for memberID := range memberMap {
							if !identifierPattern.MatchString(memberID) || asMap(memberMap[memberID]) == nil {
								return managedReadError("Managed member placement is malformed", logical)
							}
							if _, rolesErr := managedRoles(asMap(memberMap[memberID])["roles"], logical); rolesErr != nil {
								return rolesErr
							}
							deletedDeploymentPlacements[deploymentID] = append(deletedDeploymentPlacements[deploymentID], "узел "+hostID+", участник "+memberID)
						}
					}
					continue
				}
				return referenceNotFound("deploymentId")
			}
			if inventory.hosts[hostID] == nil || inventory.targets[hostID] == nil {
				if mutations.deletedServers[hostID] {
					return referenceInUse("hostId")
				}
				return referenceNotFound("hostId")
			}
			placement := asMap(raw)
			if placement == nil {
				return managedReadError("Managed placement is malformed", logical)
			}
			memberRaw, hasMembers := placement["members"]
			_, hasRoles := placement["roles"]
			if hasMembers && hasRoles {
				return managedReadError("Managed placement ambiguously mixes member and host forms", logical)
			}
			if !hasMembers {
				placementCount++
				if placementCount > maxManagedPlacements {
					return managedReadError("Managed placement collection exceeds its limit", logical)
				}
				if _, rolesErr := managedRoles(placement["roles"], logical); rolesErr != nil {
					return rolesErr
				}
				continue
			}
			memberMap := asMap(memberRaw)
			if memberMap == nil {
				return managedReadError("Managed member placement is malformed", logical)
			}
			for memberID, rawMember := range memberMap {
				placementCount++
				if placementCount > maxManagedPlacements {
					return managedReadError("Managed placement collection exceeds its limit", logical)
				}
				if !identifierPattern.MatchString(memberID) || asMap(rawMember) == nil {
					return managedReadError("Managed member placement is malformed", logical)
				}
				if _, rolesErr := managedRoles(asMap(rawMember)["roles"], logical); rolesErr != nil {
					return rolesErr
				}
				key := deploymentID + "\x00" + memberID
				if members[key] {
					return managedReadError("Managed member identifier is duplicated within a deployment", logical)
				}
				members[key] = true
			}
		}
	}
	if len(deletedDeploymentPlacements) > 0 {
		return deploymentPlacementInUse(deletedDeploymentPlacements)
	}
	deletedGroupReferences := make([]endpointGroupReference, 0)
	for deploymentID, raw := range deployments {
		deployment := asMap(raw)
		if deployment == nil {
			return managedReadError("Managed deployment is malformed", desiredDocument)
		}
		for _, field := range []string{"endpointGroup", "endpointGroupRef"} {
			if reference, found := deployment[field]; found {
				id, ok := reference.(string)
				if !ok || !identifierPattern.MatchString(id) {
					return managedReadError("Managed endpoint-group reference is malformed", desiredDocument)
				}
				if groups[id] == nil {
					if mutations.deletedGroups[id] {
						deletedGroupReferences = append(deletedGroupReferences, endpointGroupReference{groupID: id, deploymentID: deploymentID, field: field})
						continue
					}
					return referenceNotFound(field)
				}
			}
		}
		if haproxy, found := deployment["haproxy"]; found {
			value := asMap(haproxy)
			if value == nil {
				return managedReadError("Managed deployment reference is malformed", desiredDocument)
			}
			// Legacy input is preserved, but no longer selects a provider.
			if reference, exists := value["deploymentRef"]; exists {
				id, ok := reference.(string)
				if !ok || !identifierPattern.MatchString(id) {
					return managedReadError("Managed deployment reference is malformed", desiredDocument)
				}
			}
		}
		if dependencies, found := deployment["dependencies"]; found {
			values := asMap(dependencies)
			if values == nil {
				return managedReadError("Managed dependency references are malformed", desiredDocument)
			}
			for _, rawDependency := range values {
				dependency := asMap(rawDependency)
				id, ok := dependency["serviceDeployment"].(string)
				if dependency == nil || !ok || !identifierPattern.MatchString(id) {
					return managedReadError("Managed dependency reference is malformed", desiredDocument)
				}
				if deployments[id] == nil {
					if mutations.deletedDeployments[id] {
						return referenceInUse("serviceDeployment")
					}
					return referenceNotFound("serviceDeployment")
				}
			}
		}
	}
	if len(deletedGroupReferences) > 0 {
		return endpointGroupReferencesInUse(deletedGroupReferences)
	}
	if err := validateCertificateScopeReferences(state["certificateScopes"], inventory, deployments, members, mutations); err != nil {
		return err
	}
	if err := validatePKIReferences(state, deployments, mutations); err != nil {
		return err
	}
	tlsProfiles := asMap(state["tlsProfiles"])
	if tlsProfiles == nil {
		tlsProfiles = map[string]any{}
	}
	return candidate.validateCatalogConfigurationReferences(catalog, deployments, tlsProfiles, mutations)
}

func (candidate *structuralCandidate) validateCatalogConfigurationReferences(catalog *projectlifecycle.ProjectCatalogView, deployments, tlsProfiles map[string]any, mutations topologyMutationSet) error {
	validate := func(configuration map[string]any, serviceType, field string) error {
		for settingID, raw := range configuration {
			descriptor, found := catalogConfigurationSetting(catalog, serviceType, settingID)
			if !found || (descriptor.ReferenceKind != "TLS_PROFILE" && descriptor.ReferenceKind != "SERVICE_DEPLOYMENT") {
				continue
			}
			id, ok := raw.(string)
			if !ok || !validDesiredStateIdentifier(id) {
				return managedReadError("Managed configuration reference is malformed", field)
			}
			switch descriptor.ReferenceKind {
			case "TLS_PROFILE":
				if tlsProfiles[id] == nil {
					if mutations.deletedTLSProfiles[id] {
						return referenceInUse("configuration." + settingID)
					}
					return referenceNotFound("configuration." + settingID)
				}
			case "SERVICE_DEPLOYMENT":
				if deployments[id] == nil {
					if mutations.deletedDeployments[id] {
						return referenceInUse("configuration." + settingID)
					}
					return referenceNotFound("configuration." + settingID)
				}
			}
		}
		return nil
	}
	for _, raw := range deployments {
		deployment := asMap(raw)
		serviceType, _ := deployment["serviceType"].(string)
		if configurationRaw, present := deployment["configuration"]; present {
			configuration := asMap(configurationRaw)
			if configuration == nil {
				return managedReadError("Managed configuration is malformed", desiredDocument)
			}
			if err := validate(configuration, serviceType, desiredDocument); err != nil {
				return err
			}
		}
	}
	for logical, document := range candidate.documents {
		if !strings.HasPrefix(logical, "inventory/host_vars/") {
			continue
		}
		placements := asMap(document["platform_deployments"])
		for deploymentID, rawPlacement := range placements {
			deployment := asMap(deployments[deploymentID])
			serviceType, _ := deployment["serviceType"].(string)
			members := asMap(asMap(rawPlacement)["members"])
			for _, rawMember := range members {
				member := asMap(rawMember)
				if configurationRaw, present := member["configuration"]; present {
					configuration := asMap(configurationRaw)
					if configuration == nil {
						return managedReadError("Managed member configuration is malformed", logical)
					}
					if err := validate(configuration, serviceType, logical); err != nil {
						return err
					}
				}
			}
		}
	}
	return nil
}

func validatePKIReferences(state map[string]any, deployments map[string]any, mutations topologyMutationSet) error {
	authorities := asMap(state["certificateAuthorities"])
	profiles := asMap(state["certificateProfiles"])
	tlsProfiles := asMap(state["tlsProfiles"])
	scopes := asMap(state["certificateScopes"])
	if authorities == nil {
		authorities = map[string]any{}
	}
	if profiles == nil {
		profiles = map[string]any{}
	}
	if tlsProfiles == nil {
		tlsProfiles = map[string]any{}
	}
	if scopes == nil {
		scopes = map[string]any{}
	}
	for id, raw := range authorities {
		if !validDesiredStateIdentifier(id) || validPKIEntity("CreateCertificateAuthority", asMap(raw)) != nil {
			return managedReadError("Managed certificate authority is malformed", desiredDocument)
		}
	}
	for id, raw := range profiles {
		profile := asMap(raw)
		if !validDesiredStateIdentifier(id) {
			return managedReadError("Managed certificate profile identifier is malformed", desiredDocument)
		}
		if err := validPKIEntity("CreateCertificateProfile", profile); err != nil {
			return managedReadError("Managed certificate profile is malformed", desiredDocument)
		}
		ref, ok := profile["authorityRef"].(string)
		if profile == nil || !ok || !validDesiredStateIdentifier(ref) {
			return managedReadError("Managed certificate profile is malformed", desiredDocument)
		}
		if authorities[ref] == nil {
			if mutations.deletedAuthorities[ref] {
				return referenceInUse("authorityRef")
			}
			return referenceNotFound("authorityRef")
		}
		_ = id
	}
	for id, raw := range tlsProfiles {
		profile := asMap(raw)
		if !validDesiredStateIdentifier(id) {
			return managedReadError("Managed TLS profile identifier is malformed", desiredDocument)
		}
		if err := validPKIEntity("CreateTLSProfile", profile); err != nil {
			return managedReadError("Managed TLS profile is malformed", desiredDocument)
		}
		ref, ok := profile["certificateProfileRef"].(string)
		if profile == nil || !ok || !validDesiredStateIdentifier(ref) {
			return managedReadError("Managed TLS profile is malformed", desiredDocument)
		}
		if profiles[ref] == nil {
			if mutations.deletedProfiles[ref] {
				return referenceInUse("certificateProfileRef")
			}
			return referenceNotFound("certificateProfileRef")
		}
	}
	for id, raw := range scopes {
		scope := asMap(raw)
		if !validDesiredStateIdentifier(id) {
			return managedReadError("Managed certificate scope identifier is malformed", desiredDocument)
		}
		if err := validPKIEntity("CreateCertificateScope", scope); err != nil {
			return managedReadError("Managed certificate scope is malformed", desiredDocument)
		}
		ref, ok := scope["profile"].(string)
		if scope == nil || !ok || !validDesiredStateIdentifier(ref) {
			return managedReadError("Managed certificate scope is malformed", desiredDocument)
		}
		if profiles[ref] == nil {
			if mutations.deletedProfiles[ref] {
				return referenceInUse("profile")
			}
			return referenceNotFound("profile")
		}
	}
	return nil
}

func validateCertificateScopeReferences(raw any, inventory *managedServerInventory, deployments map[string]any, members map[string]bool, mutations topologyMutationSet) error {
	if raw == nil {
		return nil
	}
	scopes := asMap(raw)
	if scopes == nil {
		return managedReadError("Managed certificate scopes are malformed", desiredDocument)
	}
	for _, rawScope := range scopes {
		scope := asMap(rawScope)
		sources := asMap(scope["sources"])
		if scope == nil || sources == nil {
			return managedReadError("Managed certificate-scope sources are malformed", desiredDocument)
		}
		hostValues, ok := optionalReferenceList(sources, "hosts")
		if !ok || len(hostValues) > maxManagedEntities {
			return managedReadError("Managed certificate-scope host references are malformed", desiredDocument)
		}
		seenHosts := make(map[string]bool, len(hostValues))
		for _, rawHost := range hostValues {
			hostID, ok := rawHost.(string)
			if !ok || !validDesiredStateIdentifier(hostID) || seenHosts[hostID] {
				return managedReadError("Managed certificate-scope host reference is malformed", desiredDocument)
			}
			seenHosts[hostID] = true
			if inventory.hosts[hostID] == nil || inventory.targets[hostID] == nil {
				if mutations.deletedServers[hostID] {
					return referenceInUse("sources.hosts")
				}
				return referenceNotFound("sources.hosts")
			}
		}
		deploymentValues, ok := optionalReferenceList(sources, "serviceDeployments")
		if !ok || len(deploymentValues) > maxManagedEntities {
			return managedReadError("Managed certificate-scope deployment references are malformed", desiredDocument)
		}
		seenDeployments := make(map[string]bool, len(deploymentValues))
		for _, rawDeployment := range deploymentValues {
			deploymentID, ok := rawDeployment.(string)
			if !ok || !validDesiredStateIdentifier(deploymentID) || seenDeployments[deploymentID] {
				return managedReadError("Managed certificate-scope deployment reference is malformed", desiredDocument)
			}
			seenDeployments[deploymentID] = true
			if deployments[deploymentID] == nil {
				if mutations.deletedDeployments[deploymentID] {
					return referenceInUse("sources.serviceDeployments")
				}
				return referenceNotFound("sources.serviceDeployments")
			}
		}
		memberValues, ok := optionalReferenceList(sources, "members")
		if !ok || len(memberValues) > maxManagedPlacements {
			return managedReadError("Managed certificate-scope member references are malformed", desiredDocument)
		}
		seenMembers := make(map[string]bool, len(memberValues))
		for _, rawMember := range memberValues {
			member := asMap(rawMember)
			deploymentID, deploymentOK := member["deploymentId"].(string)
			memberID, memberOK := member["memberId"].(string)
			key := deploymentID + "\x00" + memberID
			if member == nil || len(member) != 2 || !deploymentOK || !memberOK || !validDesiredStateIdentifier(deploymentID) || !validDesiredStateIdentifier(memberID) || seenMembers[key] {
				return managedReadError("Managed certificate-scope member reference is malformed", desiredDocument)
			}
			seenMembers[key] = true
			if !members[key] {
				if mutations.reconciled[deploymentID] || mutations.deletedDeployments[deploymentID] {
					return referenceInUse("sources.members")
				}
				return referenceNotFound("sources.members")
			}
		}
	}
	return nil
}

func optionalReferenceList(value map[string]any, key string) ([]any, bool) {
	raw, found := value[key]
	if !found {
		return []any{}, true
	}
	items := asSlice(raw)
	return items, items != nil
}

func referenceInUse(field string) error {
	return blocked("REFERENCE_IN_USE", "Referenced entity must be cleared before removal", field)
}

type endpointGroupReference struct {
	groupID, deploymentID, field string
}

func endpointGroupReferencesInUse(references []endpointGroupReference) error {
	sort.Slice(references, func(i, j int) bool {
		left, right := references[i], references[j]
		if left.groupID != right.groupID {
			return left.groupID < right.groupID
		}
		if left.deploymentID != right.deploymentID {
			return left.deploymentID < right.deploymentID
		}
		return left.field < right.field
	})
	details := make([]string, 0, len(references))
	for _, reference := range references {
		binding := "«" + reference.groupID + "» назначена потребителю «" + reference.deploymentID + "»"
		if reference.field == "endpointGroupRef" {
			binding = "«" + reference.groupID + "» используется провайдером «" + reference.deploymentID + "»"
		}
		details = append(details, binding)
	}
	return blocked("REFERENCE_IN_USE", "Нельзя удалить группу endpoint: "+strings.Join(details, "; ")+". Сначала очистите эти назначения и повторите проверку.", references[0].field)
}

func deploymentPlacementInUse(placements map[string][]string) error {
	deploymentIDs := make([]string, 0, len(placements))
	for deploymentID := range placements {
		deploymentIDs = append(deploymentIDs, deploymentID)
	}
	sort.Strings(deploymentIDs)
	details := make([]string, 0)
	for _, deploymentID := range deploymentIDs {
		locations := placements[deploymentID]
		sort.Strings(locations)
		details = append(details, "«"+deploymentID+"»: "+strings.Join(locations, "; "))
	}
	message := "Нельзя удалить экземпляр: он всё ещё размещён — " + strings.Join(details, ". ") + ". Сначала удалите эти размещения и повторите проверку."
	return blocked("REFERENCE_IN_USE", message, "deploymentId")
}

func referenceNotFound(field string) error {
	return blocked("REFERENCE_NOT_FOUND", "Final state contains a missing referenced entity", field)
}

func (candidate *structuralCandidate) storedDocuments() ([]storedDocument, error) {
	paths := make([]string, 0, len(candidate.dirty))
	for logical := range candidate.dirty {
		paths = append(paths, logical)
	}
	if candidate.firstSave {
		paths = append(paths, "ansible.cfg")
	}
	sort.Strings(paths)
	documents := make([]storedDocument, 0, len(paths))
	for _, logical := range paths {
		var after []byte
		var err error
		if logical == "ansible.cfg" {
			after = append([]byte(nil), firstSaveAnsibleConfig...)
		} else {
			after, err = deterministicYAML(candidate.documents[logical])
			if err != nil {
				return nil, blocked("INVALID_VALUE", "Edit value cannot be serialized safely", "command")
			}
		}
		before := candidate.originals[logical]
		if bytes.Equal(before, after) {
			continue
		}
		documents = append(documents, storedDocument{LogicalPath: logical, Before: append([]byte(nil), before...), After: after, Existed: candidate.existed[logical]})
	}
	return documents, nil
}

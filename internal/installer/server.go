package installer

import (
	"sort"

	"platform-installer/internal/coreadapter"
)

const managedInventoryDocument = "inventory/hosts.yml"

type managedServerInventory struct {
	document map[string]any
	hosts    map[string]any
	targets  map[string]any
}

func managedServers(candidates map[string]map[string]any, originals map[string][]byte, root string) (*managedServerInventory, error) {
	document := candidates[managedInventoryDocument]
	if document == nil {
		loaded, content, err := loadOwnedDocument(root, managedInventoryDocument)
		if err != nil {
			return nil, err
		}
		document, candidates[managedInventoryDocument], originals[managedInventoryDocument] = loaded, loaded, content
	}
	all := asMap(document["all"])
	hosts := asMap(all["hosts"])
	children := asMap(all["children"])
	targets := asMap(asMap(children["platform_targets"])["hosts"])
	if all == nil || hosts == nil || children == nil || targets == nil {
		return nil, blocked("WRITE_OWNERSHIP_REQUIRED", "Managed inventory roots are missing or malformed", "inventory/hosts.yml")
	}
	return &managedServerInventory{document: document, hosts: hosts, targets: targets}, nil
}

func serverMap(value any) map[string]any { return asMap(value) }

func portWasSupplied(command EditCommand) bool {
	return command.SSHPort != 0 || command.presentFields["sshPort"]
}

func serverFinalExpectation(inventory *managedServerInventory, hostID string) expectation {
	server := serverMap(inventory.hosts[hostID])
	if server == nil {
		return expectation{Operation: "ServerFinal", First: hostID, Value: map[string]any{"exists": false}}
	}
	platformHost := asMap(server["platform_host"])
	value := map[string]any{"exists": true, "address": server["ansible_host"], "type": platformHost["type"], "desiredHostname": platformHost["desiredHostname"]}
	if port, found := server["ansible_port"]; found {
		value["portPresent"] = true
		value["port"] = port
	}
	return expectation{Operation: "ServerFinal", First: hostID, Value: value}
}

func applyServerCommand(command EditCommand, root string, snapshot *coreadapter.Snapshot, candidates map[string]map[string]any, originals map[string][]byte) (expectation, []string, error) {
	inventory, err := managedServers(candidates, originals, root)
	if err != nil {
		return expectation{}, nil, err
	}
	host := serverMap(inventory.hosts[command.HostID])
	switch command.Operation {
	case "CreateServer":
		if host != nil || inventory.targets[command.HostID] != nil {
			return expectation{}, nil, blocked("INVALID_EDIT_COMMAND", "Server identifier already exists", "command.hostId")
		}
		created := map[string]any{
			"ansible_host":  command.Address,
			"platform_host": map[string]any{"type": command.ServerType, "desiredHostname": command.DesiredHostname},
		}
		if portWasSupplied(command) {
			created["ansible_port"] = command.SSHPort
		}
		inventory.hosts[command.HostID] = created
		inventory.targets[command.HostID] = map[string]any{}
		return serverFinalExpectation(inventory, command.HostID), []string{"SERVER_INVENTORY_CHANGED"}, nil
	case "UpdateServer":
		if host == nil || inventory.targets[command.HostID] == nil {
			return expectation{}, nil, blocked("INVALID_EDIT_COMMAND", "Server does not exist in managed inventory", "command.hostId")
		}
		platformHost := asMap(host["platform_host"])
		if platformHost == nil {
			platformHost = map[string]any{}
			host["platform_host"] = platformHost
		}
		if command.Address != "" {
			host["ansible_host"] = command.Address
		}
		if command.ServerType != "" {
			platformHost["type"] = command.ServerType
		}
		if command.DesiredHostname != "" {
			platformHost["desiredHostname"] = command.DesiredHostname
		}
		if portWasSupplied(command) {
			host["ansible_port"] = command.SSHPort
		} else if command.ClearSSHPort {
			delete(host, "ansible_port")
		}
		if command.APIVersion == EditCommandAPIVersionV4 && (platformHost["type"] == nil || platformHost["desiredHostname"] == nil) {
			return expectation{}, nil, blocked("SERVER_METADATA_REQUIRED", "Current server edits require type and desired hostname", "command")
		}
		return serverFinalExpectation(inventory, command.HostID), serverUpdateImpacts(command), nil
	case "DeleteServer":
		if host == nil || inventory.targets[command.HostID] == nil {
			return expectation{}, nil, blocked("INVALID_EDIT_COMMAND", "Server does not exist in managed inventory", "command.hostId")
		}
		delete(inventory.hosts, command.HostID)
		delete(inventory.targets, command.HostID)
		return serverFinalExpectation(inventory, command.HostID), []string{"SERVER_INVENTORY_CHANGED"}, nil
	}
	return expectation{}, nil, blocked("INVALID_EDIT_COMMAND", "Server operation is unsupported", "command.operation")
}

func serverUpdateImpacts(command EditCommand) []string {
	set := map[string]bool{}
	if command.Address != "" || portWasSupplied(command) || command.ClearSSHPort {
		set["SERVER_INVENTORY_CHANGED"] = true
	}
	if command.ServerType != "" {
		set["SERVER_METADATA_CHANGED"] = true
	}
	if command.DesiredHostname != "" {
		set["SERVER_PREPARATION_CHANGED"] = true
	}
	result := make([]string, 0, len(set))
	for value := range set {
		result = append(result, value)
	}
	sort.Strings(result)
	return result
}

func serverReferenceInUse(snapshot *coreadapter.Snapshot, expectations []expectation) bool {
	if snapshot == nil || snapshot.References == nil || snapshot.References["hosts"] == nil {
		return false
	}
	for _, expected := range expectations {
		if expected.Operation != "ServerFinal" {
			continue
		}
		value := asMap(expected.Value)
		if value != nil && value["exists"] == false && len(snapshot.References["hosts"][expected.First]) > 0 {
			return true
		}
	}
	return false
}

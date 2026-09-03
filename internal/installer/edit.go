package installer

import (
	"encoding/json"
	"fmt"
	"os"
	"regexp"
	"sort"
	"strings"

	"platform-installer/internal/coreadapter"
)

var identifierPattern = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{0,62}$`)
var secretKeyPattern = regexp.MustCompile(`(?i)password|passphrase|private.?key|pgpass|token|secret`)

type expectation struct {
	Operation string
	First     string
	Second    string
	Value     any
}

func deepCopy(value any) any {
	switch typed := value.(type) {
	case map[string]any:
		result := make(map[string]any, len(typed))
		for key, item := range typed {
			result[key] = deepCopy(item)
		}
		return result
	case []any:
		result := make([]any, len(typed))
		for index, item := range typed {
			result[index] = deepCopy(item)
		}
		return result
	default:
		return typed
	}
}

func asMap(value any) map[string]any {
	result, _ := value.(map[string]any)
	return result
}

func asSlice(value any) []any {
	result, _ := value.([]any)
	return result
}

func semanticEqual(left, right any) bool {
	leftJSON, leftErr := json.Marshal(left)
	rightJSON, rightErr := json.Marshal(right)
	return leftErr == nil && rightErr == nil && string(leftJSON) == string(rightJSON)
}

func safeValue(value any, key string) error {
	if key != "" && secretKeyPattern.MatchString(key) {
		lower := strings.ToLower(key)
		if !strings.HasSuffix(lower, "secretref") && !strings.HasSuffix(lower, "credentialref") {
			return blocked("SECRET_VALUE_NOT_ALLOWED", "Plaintext secret fields are not accepted", "command.value")
		}
	}
	switch typed := value.(type) {
	case string:
		upper := strings.ToUpper(typed)
		if strings.Contains(upper, "PRIVATE KEY-----") || strings.HasPrefix(upper, "PGPASS=") {
			return blocked("SECRET_VALUE_NOT_ALLOWED", "Secret material is not accepted", "command.value")
		}
	case map[string]any:
		for child, item := range typed {
			if err := safeValue(item, child); err != nil {
				return err
			}
		}
	case []any:
		for _, item := range typed {
			if err := safeValue(item, ""); err != nil {
				return err
			}
		}
	}
	return nil
}

func validateCommand(command EditCommand) error {
	if command.APIVersion != EditCommandAPIVersion || command.Kind != "EditCommand" || command.BaseProjectRevision == "" {
		return blocked("INVALID_EDIT_COMMAND", "EditCommand version, kind, or base revision is invalid", "command")
	}
	if command.Operation == "Batch" {
		if len(command.Commands) < 1 || len(command.Commands) > 16 {
			return blocked("INVALID_EDIT_COMMAND", "Batch must contain 1 through 16 semantic commands", "command.commands")
		}
		for _, child := range command.Commands {
			child.APIVersion = command.APIVersion
			child.Kind = command.Kind
			child.BaseProjectRevision = command.BaseProjectRevision
			if child.Operation == "Batch" {
				return blocked("INVALID_EDIT_COMMAND", "Nested batches are not supported", "command.commands")
			}
			if err := validateCommand(child); err != nil {
				return err
			}
		}
		return nil
	}
	allowed := map[string]bool{
		"CreateServiceDeployment": true, "DeleteServiceDeployment": true,
		"SetServiceConfigurationValue": true, "RemoveServiceConfigurationOverride": true,
		"SetServiceEndpointGroup": true, "ClearServiceEndpointGroup": true,
		"SetHAProxyIntegration": true, "ClearHAProxyIntegration": true,
		"CreateEndpointGroup": true, "UpdateEndpointGroup": true, "DeleteEndpointGroup": true,
		"AssignServiceToHost": true, "RemoveServiceFromHost": true, "SetPlacementProperty": true,
	}
	if !allowed[command.Operation] {
		return blocked("INVALID_EDIT_COMMAND", "Edit operation is unsupported", "command.operation")
	}
	switch command.Operation {
	case "CreateServiceDeployment":
		if !identifierPattern.MatchString(command.DeploymentID) || command.Deployment == nil {
			return blocked("INVALID_EDIT_COMMAND", "Create deployment requires an identifier and deployment object", "command")
		}
	case "DeleteServiceDeployment", "ClearServiceEndpointGroup", "ClearHAProxyIntegration":
		if !identifierPattern.MatchString(command.DeploymentID) {
			return blocked("INVALID_EDIT_COMMAND", "Deployment identifier is required", "command.deploymentId")
		}
	case "SetServiceConfigurationValue", "RemoveServiceConfigurationOverride":
		if !identifierPattern.MatchString(command.DeploymentID) || command.Setting == "" {
			return blocked("INVALID_EDIT_COMMAND", "Configuration edit requires deployment and setting identifiers", "command")
		}
	case "SetServiceEndpointGroup":
		if !identifierPattern.MatchString(command.DeploymentID) || !identifierPattern.MatchString(command.EndpointGroupID) {
			return blocked("INVALID_EDIT_COMMAND", "Endpoint relation requires deployment and endpoint-group identifiers", "command")
		}
	case "SetHAProxyIntegration":
		if !identifierPattern.MatchString(command.DeploymentID) || !identifierPattern.MatchString(command.HAProxyDeploymentID) {
			return blocked("INVALID_EDIT_COMMAND", "HAProxy relation requires two deployment identifiers", "command")
		}
	case "CreateEndpointGroup", "UpdateEndpointGroup":
		if !identifierPattern.MatchString(command.EndpointGroupID) || command.EndpointGroup == nil {
			return blocked("INVALID_EDIT_COMMAND", "Endpoint-group edit requires an identifier and value", "command")
		}
	case "DeleteEndpointGroup":
		if !identifierPattern.MatchString(command.EndpointGroupID) {
			return blocked("INVALID_EDIT_COMMAND", "Endpoint-group identifier is required", "command.endpointGroupId")
		}
	case "AssignServiceToHost", "RemoveServiceFromHost":
		if !identifierPattern.MatchString(command.HostID) || !identifierPattern.MatchString(command.DeploymentID) {
			return blocked("INVALID_EDIT_COMMAND", "Placement edit requires host and deployment identifiers", "command")
		}
	case "SetPlacementProperty":
		if !identifierPattern.MatchString(command.HostID) || !identifierPattern.MatchString(command.DeploymentID) || command.Property == "" {
			return blocked("INVALID_EDIT_COMMAND", "Placement property edit requires host, deployment, and property identifiers", "command")
		}
	}
	for _, value := range []any{command.Value, command.Deployment, command.EndpointGroup, command.Placement, command.Backend} {
		if err := safeValue(value, ""); err != nil {
			return err
		}
	}
	return nil
}

func commandSummary(command EditCommand) SemanticChange {
	entity := command.DeploymentID
	if entity == "" {
		entity = command.EndpointGroupID
	}
	if command.HostID != "" {
		entity = command.HostID + "/" + command.DeploymentID
	}
	property := command.Setting
	if property == "" {
		property = command.Property
	}
	return SemanticChange{Operation: command.Operation, EntityID: entity, Property: property,
		SafeSummary: command.Operation + " " + entity}
}

func loadOwnedDocument(root, logical string) (map[string]any, []byte, error) {
	path, err := safeProjectPath(root, logical, false)
	if err != nil {
		return nil, nil, err
	}
	content, err := os.ReadFile(path)
	if err != nil {
		return nil, nil, err
	}
	document, err := parseManagedYAML(content)
	return document, content, err
}

func desiredState(candidates map[string]map[string]any, originals map[string][]byte, root string) (map[string]any, error) {
	document := candidates[desiredDocument]
	if document == nil {
		loaded, content, err := loadOwnedDocument(root, desiredDocument)
		if err != nil {
			return nil, err
		}
		document = loaded
		candidates[desiredDocument] = document
		originals[desiredDocument] = content
	}
	state := asMap(document["platform_desired_state"])
	if state == nil {
		return nil, blocked("WRITE_OWNERSHIP_REQUIRED", "Installer-owned desired-state root is missing", "platform_desired_state")
	}
	return state, nil
}

func hostPlacements(candidates map[string]map[string]any, originals map[string][]byte, root, hostID string) (map[string]any, error) {
	if !identifierPattern.MatchString(hostID) {
		return nil, blocked("INVALID_EDIT_COMMAND", "Host identifier is invalid", "command.hostId")
	}
	logical := managedHostDocument(hostID)
	document := candidates[logical]
	if document == nil {
		loaded, content, err := loadOwnedDocument(root, logical)
		if err != nil {
			return nil, err
		}
		document = loaded
		candidates[logical] = document
		originals[logical] = content
	}
	placements := asMap(document["platform_deployments"])
	if placements == nil {
		return nil, blocked("WRITE_OWNERSHIP_REQUIRED", "Installer-owned placement root is missing", "platform_deployments")
	}
	return placements, nil
}

func deployment(state map[string]any, deploymentID string) (map[string]any, error) {
	if !identifierPattern.MatchString(deploymentID) {
		return nil, blocked("INVALID_EDIT_COMMAND", "Deployment identifier is invalid", "command.deploymentId")
	}
	value := asMap(asMap(state["serviceDeployments"])[deploymentID])
	if value == nil {
		return nil, blocked("INVALID_EDIT_COMMAND", "Service deployment does not exist", "command.deploymentId")
	}
	return value, nil
}

func catalogSetting(snapshot *coreadapter.Snapshot, serviceType, setting string) bool {
	definition := snapshot.ServiceCatalog[serviceType]
	configuration := asMap(definition["configuration"])
	settings := asMap(configuration["settings"])
	_, found := settings[setting]
	return found
}

func catalogMode(snapshot *coreadapter.Snapshot, serviceType, mode string) bool {
	definition := snapshot.ServiceCatalog[serviceType]
	for _, candidate := range asSlice(definition["modes"]) {
		if candidate == mode {
			return true
		}
	}
	return false
}

func applyOne(command EditCommand, root string, snapshot *coreadapter.Snapshot,
	candidates map[string]map[string]any, originals map[string][]byte) (expectation, []string, error) {
	operation := command.Operation
	if strings.Contains(operation, "ServiceDeployment") || strings.Contains(operation, "Configuration") ||
		strings.Contains(operation, "EndpointGroup") || strings.Contains(operation, "HAProxy") {
		state, err := desiredState(candidates, originals, root)
		if err != nil {
			return expectation{}, nil, err
		}
		deployments := asMap(state["serviceDeployments"])
		groups := asMap(state["endpointGroups"])
		switch operation {
		case "SetServiceConfigurationValue":
			item, err := deployment(state, command.DeploymentID)
			if err != nil {
				return expectation{}, nil, err
			}
			serviceType, _ := item["serviceType"].(string)
			if !catalogSetting(snapshot, serviceType, command.Setting) {
				return expectation{}, nil, blocked("INVALID_VALUE", "Configuration setting is not declared by the catalog", "command.setting")
			}
			configuration := asMap(item["configuration"])
			if configuration == nil {
				configuration = make(map[string]any)
				item["configuration"] = configuration
			}
			if semanticEqual(configuration[command.Setting], command.Value) {
				return expectation{}, nil, nil
			}
			configuration[command.Setting] = deepCopy(command.Value)
			return expectation{operation, command.DeploymentID, command.Setting, command.Value}, []string{"CONFIGURATION_CHANGED"}, nil
		case "RemoveServiceConfigurationOverride":
			item, err := deployment(state, command.DeploymentID)
			if err != nil {
				return expectation{}, nil, err
			}
			serviceType, _ := item["serviceType"].(string)
			if !catalogSetting(snapshot, serviceType, command.Setting) {
				return expectation{}, nil, blocked("INVALID_VALUE", "Configuration setting is not declared by the catalog", "command.setting")
			}
			configuration := asMap(item["configuration"])
			if configuration == nil || configuration[command.Setting] == nil {
				return expectation{}, nil, nil
			}
			delete(configuration, command.Setting)
			return expectation{operation, command.DeploymentID, command.Setting, nil}, []string{"CONFIGURATION_CHANGED"}, nil
		case "CreateServiceDeployment":
			if !identifierPattern.MatchString(command.DeploymentID) || deployments[command.DeploymentID] != nil {
				return expectation{}, nil, blocked("INVALID_EDIT_COMMAND", "Deployment identifier is invalid or already exists", "command.deploymentId")
			}
			value := deepCopy(command.Deployment).(map[string]any)
			serviceType, _ := value["serviceType"].(string)
			mode, _ := value["mode"].(string)
			if !catalogMode(snapshot, serviceType, mode) {
				return expectation{}, nil, blocked("INVALID_VALUE", "Service type or mode is not declared by the catalog", "command.deployment")
			}
			deployments[command.DeploymentID] = value
			return expectation{operation, command.DeploymentID, "", value}, []string{"TOPOLOGY_CHANGED"}, nil
		case "DeleteServiceDeployment":
			if _, err := deployment(state, command.DeploymentID); err != nil {
				return expectation{}, nil, err
			}
			delete(deployments, command.DeploymentID)
			return expectation{operation, command.DeploymentID, "", nil}, []string{"TOPOLOGY_CHANGED"}, nil
		case "SetServiceEndpointGroup", "ClearServiceEndpointGroup":
			item, err := deployment(state, command.DeploymentID)
			if err != nil {
				return expectation{}, nil, err
			}
			if operation == "SetServiceEndpointGroup" {
				if groups[command.EndpointGroupID] == nil {
					return expectation{}, nil, blocked("INVALID_VALUE", "Endpoint group does not exist", "command.endpointGroupId")
				}
				if item["endpointGroup"] == command.EndpointGroupID {
					return expectation{}, nil, nil
				}
				item["endpointGroup"] = command.EndpointGroupID
			} else {
				if item["endpointGroup"] == nil {
					return expectation{}, nil, nil
				}
				delete(item, "endpointGroup")
			}
			return expectation{operation, command.DeploymentID, "endpointGroup", command.EndpointGroupID}, []string{"ENDPOINT_CHANGED", "PKI_INPUT_CHANGED"}, nil
		case "SetHAProxyIntegration", "ClearHAProxyIntegration":
			item, err := deployment(state, command.DeploymentID)
			if err != nil {
				return expectation{}, nil, err
			}
			var value any
			if operation == "SetHAProxyIntegration" {
				if _, err := deployment(state, command.HAProxyDeploymentID); err != nil {
					return expectation{}, nil, blocked("INVALID_VALUE", "HAProxy deployment reference does not exist", "command.haproxyDeploymentId")
				}
				relation := map[string]any{"deploymentRef": command.HAProxyDeploymentID}
				if command.Backend != nil {
					relation["backend"] = deepCopy(command.Backend)
				}
				if semanticEqual(item["haproxy"], relation) {
					return expectation{}, nil, nil
				}
				item["haproxy"] = relation
				value = relation
			} else {
				if item["haproxy"] == nil {
					return expectation{}, nil, nil
				}
				delete(item, "haproxy")
			}
			return expectation{operation, command.DeploymentID, "haproxy", value}, []string{"INTEGRATION_CHANGED"}, nil
		case "CreateEndpointGroup", "UpdateEndpointGroup", "DeleteEndpointGroup":
			if !identifierPattern.MatchString(command.EndpointGroupID) {
				return expectation{}, nil, blocked("INVALID_EDIT_COMMAND", "Endpoint group identifier is invalid", "command.endpointGroupId")
			}
			if operation == "CreateEndpointGroup" {
				if groups[command.EndpointGroupID] != nil {
					return expectation{}, nil, blocked("INVALID_EDIT_COMMAND", "Endpoint group already exists", "command.endpointGroupId")
				}
				groups[command.EndpointGroupID] = deepCopy(command.EndpointGroup)
			} else if operation == "UpdateEndpointGroup" {
				if groups[command.EndpointGroupID] == nil {
					return expectation{}, nil, blocked("INVALID_EDIT_COMMAND", "Endpoint group does not exist", "command.endpointGroupId")
				}
				if semanticEqual(groups[command.EndpointGroupID], command.EndpointGroup) {
					return expectation{}, nil, nil
				}
				groups[command.EndpointGroupID] = deepCopy(command.EndpointGroup)
			} else {
				for _, raw := range deployments {
					item := asMap(raw)
					if item["endpointGroup"] == command.EndpointGroupID || item["endpointGroupRef"] == command.EndpointGroupID {
						return expectation{}, nil, blocked("REFERENCE_IN_USE", "Endpoint group is still referenced", "command.endpointGroupId")
					}
				}
				delete(groups, command.EndpointGroupID)
			}
			return expectation{operation, command.EndpointGroupID, "", deepCopy(command.EndpointGroup)}, []string{"ENDPOINT_CHANGED", "PKI_INPUT_CHANGED"}, nil
		}
	}
	if operation == "AssignServiceToHost" || operation == "RemoveServiceFromHost" || operation == "SetPlacementProperty" {
		stagedDeployments := asMap(asMap(candidates[desiredDocument]["platform_desired_state"])["serviceDeployments"])
		if snapshot.Hosts[command.HostID] == nil ||
			(snapshot.ServiceDeployments[command.DeploymentID] == nil && stagedDeployments[command.DeploymentID] == nil) {
			return expectation{}, nil, blocked("INVALID_EDIT_COMMAND", "Host or deployment does not exist", "command")
		}
		placements, err := hostPlacements(candidates, originals, root, command.HostID)
		if err != nil {
			return expectation{}, nil, err
		}
		if operation == "AssignServiceToHost" {
			if semanticEqual(placements[command.DeploymentID], command.Placement) {
				return expectation{}, nil, nil
			}
			placements[command.DeploymentID] = deepCopy(command.Placement)
			return expectation{operation, command.HostID, command.DeploymentID, deepCopy(command.Placement)}, []string{"TOPOLOGY_CHANGED"}, nil
		}
		if operation == "RemoveServiceFromHost" {
			if placements[command.DeploymentID] == nil {
				return expectation{}, nil, nil
			}
			delete(placements, command.DeploymentID)
			return expectation{operation, command.HostID, command.DeploymentID, nil}, []string{"TOPOLOGY_CHANGED"}, nil
		}
		placement := asMap(placements[command.DeploymentID])
		if placement == nil || placement[command.Property] == nil {
			return expectation{}, nil, blocked("INVALID_VALUE", "Placement property is not already declared", "command.property")
		}
		if semanticEqual(placement[command.Property], command.Value) {
			return expectation{}, nil, nil
		}
		placement[command.Property] = deepCopy(command.Value)
		return expectation{operation, command.HostID, command.DeploymentID,
			map[string]any{"property": command.Property, "value": deepCopy(command.Value)}}, []string{"TOPOLOGY_CHANGED"}, nil
	}
	return expectation{}, nil, blocked("INVALID_EDIT_COMMAND", "Edit operation is unsupported", "command.operation")
}

func applyCommand(command EditCommand, root string, snapshot *coreadapter.Snapshot,
	candidates map[string]map[string]any, originals map[string][]byte) ([]expectation, []SemanticChange, []string, error) {
	commands := []EditCommand{command}
	if command.Operation == "Batch" {
		commands = command.Commands
	}
	var expectations []expectation
	var changes []SemanticChange
	impactSet := make(map[string]bool)
	for _, child := range commands {
		expected, impacts, err := applyOne(child, root, snapshot, candidates, originals)
		if err != nil {
			return nil, nil, nil, err
		}
		if expected.Operation == "" {
			continue
		}
		expectations = append(expectations, expected)
		changes = append(changes, commandSummary(child))
		for _, impact := range impacts {
			impactSet[impact] = true
		}
	}
	impacts := make([]string, 0, len(impactSet))
	for impact := range impactSet {
		impacts = append(impacts, impact)
	}
	sort.Strings(impacts)
	return expectations, changes, impacts, nil
}

func snapshotValue(snapshot *coreadapter.Snapshot, path ...string) any {
	var current any
	switch path[0] {
	case "effectiveConfiguration":
		current = snapshot.EffectiveConfiguration
	case "endpointGroups":
		current = snapshot.EndpointGroups
	case "hosts":
		current = snapshot.Hosts
	default:
		return nil
	}
	for _, key := range path[1:] {
		mapping, ok := current.(map[string]any)
		if !ok {
			return nil
		}
		current = mapping[key]
	}
	return current
}

func proveSnapshot(snapshot *coreadapter.Snapshot, expectations []expectation) bool {
	for _, expected := range expectations {
		deployment := snapshot.ServiceDeployments[expected.First]
		switch expected.Operation {
		case "SetServiceConfigurationValue":
			actual := asMap(snapshotValue(snapshot, "effectiveConfiguration", "services", expected.First, "configuration", expected.Second))
			if actual == nil || !semanticEqual(actual["value"], expected.Value) || actual["source"] != "DEPLOYMENT_OVERRIDE" {
				return false
			}
		case "RemoveServiceConfigurationOverride":
			actual := asMap(snapshotValue(snapshot, "effectiveConfiguration", "services", expected.First, "configuration", expected.Second))
			if actual != nil && actual["source"] == "DEPLOYMENT_OVERRIDE" {
				return false
			}
		case "CreateServiceDeployment":
			if !semanticEqual(deployment, expected.Value) {
				return false
			}
		case "DeleteServiceDeployment":
			if deployment != nil {
				return false
			}
		case "SetServiceEndpointGroup":
			if deployment == nil || deployment["endpointGroup"] != expected.Value {
				return false
			}
		case "ClearServiceEndpointGroup":
			if deployment != nil && deployment["endpointGroup"] != nil {
				return false
			}
		case "SetHAProxyIntegration":
			if deployment == nil || !semanticEqual(deployment["haproxy"], expected.Value) {
				return false
			}
		case "ClearHAProxyIntegration":
			if deployment != nil && deployment["haproxy"] != nil {
				return false
			}
		case "CreateEndpointGroup", "UpdateEndpointGroup":
			if !semanticEqual(snapshot.EndpointGroups[expected.First], expected.Value) {
				return false
			}
		case "DeleteEndpointGroup":
			if snapshot.EndpointGroups[expected.First] != nil {
				return false
			}
		case "AssignServiceToHost":
			placements := asMap(snapshot.Hosts[expected.First]["platformDeployments"])
			if !semanticEqual(placements[expected.Second], expected.Value) {
				return false
			}
		case "RemoveServiceFromHost":
			placements := asMap(snapshot.Hosts[expected.First]["platformDeployments"])
			if placements[expected.Second] != nil {
				return false
			}
		case "SetPlacementProperty":
			placements := asMap(snapshot.Hosts[expected.First]["platformDeployments"])
			placement := asMap(placements[expected.Second])
			value := asMap(expected.Value)
			if placement == nil || !semanticEqual(placement[value["property"].(string)], value["value"]) {
				return false
			}
		}
	}
	return true
}

func expectedState(expectations []expectation) []map[string]any {
	result := make([]map[string]any, 0, len(expectations))
	for _, item := range expectations {
		result = append(result, map[string]any{"operation": item.Operation, "entityId": item.First,
			"property": item.Second, "value": deepCopy(item.Value)})
	}
	return result
}

func decodeJSONValue(data []byte) (any, error) {
	decoder := json.NewDecoder(strings.NewReader(string(data)))
	decoder.UseNumber()
	var value any
	if err := decoder.Decode(&value); err != nil {
		return nil, fmt.Errorf("decode value: %w", err)
	}
	return value, nil
}

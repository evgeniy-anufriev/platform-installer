package installer

import (
	"encoding/json"
	"fmt"
	"math"
	"net/netip"
	"os"
	"regexp"
	"sort"
	"strings"

	"platform-installer/internal/appconfig"
	"platform-installer/internal/coreadapter"
)

var identifierPattern = regexp.MustCompile(`^[a-z0-9][a-z0-9-]{0,62}$`)
var configurationSettingPattern = regexp.MustCompile(`^[A-Za-z][A-Za-z0-9._-]{0,127}$`)
var virtualAddressInterfacePattern = regexp.MustCompile(`^[A-Za-z0-9_.:-]+$`)
var serverAddressPattern = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._:-]{0,252}$`)
var desiredHostnamePattern = regexp.MustCompile(`^[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?$`)
var extensionKeyPattern = regexp.MustCompile(`^x-[A-Za-z0-9][A-Za-z0-9._-]*$`)
var secretKeyPattern = regexp.MustCompile(`(?i)password|passphrase|private.?key|pgpass|token|secret|credential`)
var runtimeRefPattern = regexp.MustCompile(`^runtime:[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`)

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
		if strings.HasSuffix(lower, "secretref") || strings.HasSuffix(lower, "credentialref") {
			text, ok := value.(string)
			if !ok || !runtimeRefPattern.MatchString(text) {
				return blocked("SECRET_REFERENCE_INVALID", "Only opaque runtime secret references are accepted", "command.value")
			}
		} else {
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
	return validateCommandWithInternalBatch(command, false)
}

func isEditCommandV2OrLater(version string) bool {
	return version == EditCommandAPIVersionV2 || version == EditCommandAPIVersionV3 || version == EditCommandAPIVersionV4 || version == EditCommandAPIVersionV5 || version == EditCommandAPIVersionV6 || version == EditCommandAPIVersionV7 || version == EditCommandAPIVersionV8 || version == EditCommandAPIVersionV9
}

func isEditCommandV5OrLater(version string) bool {
	return version == EditCommandAPIVersionV5 || version == EditCommandAPIVersionV6 || version == EditCommandAPIVersionV7 || version == EditCommandAPIVersionV8 || version == EditCommandAPIVersionV9
}

func validateCommandWithInternalBatch(command EditCommand, allowV2Batch bool) error {
	if (command.APIVersion != EditCommandAPIVersion && !isEditCommandV2OrLater(command.APIVersion)) || command.Kind != "EditCommand" || command.BaseProjectRevision == "" || (isEditCommandV2OrLater(command.APIVersion) && !validSHA256(command.BaseProjectRevision)) {
		return blocked("INVALID_EDIT_COMMAND", "EditCommand version, kind, or base revision is invalid", "command")
	}
	if command.Operation == "Batch" {
		if isEditCommandV2OrLater(command.APIVersion) && !allowV2Batch {
			return blocked("INVALID_EDIT_COMMAND", "Batch is an internal review aggregate and is not a public operation", "command.operation")
		}
		if err := validateCommandFields(command, "commands"); err != nil {
			return err
		}
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
	fieldsV2 := map[string][]string{
		"CreateServer": {"hostId", "address", "sshPort"}, "UpdateServer": {"hostId", "address", "sshPort", "clearSSHPort"}, "DeleteServer": {"hostId"},
		"ReconcileDeploymentPlacement": {"deploymentId", "members"},
		"CreateServiceDeployment":      {"deploymentId", "serviceType", "mode"}, "DeleteServiceDeployment": {"deploymentId"},
		"SetServiceConfigurationValue": {"deploymentId", "setting", "value"}, "RemoveServiceConfigurationOverride": {"deploymentId", "setting"},
		"SetServiceEndpointGroup": {"deploymentId", "endpointGroupId"}, "ClearServiceEndpointGroup": {"deploymentId"},
		"SetHAProxyIntegration": {"deploymentId", "haproxyDeploymentId"}, "ClearHAProxyIntegration": {"deploymentId"},
		"CreateEndpointGroup": {"endpointGroupId", "endpointGroup"}, "UpdateEndpointGroup": {"endpointGroupId", "endpointGroup"}, "DeleteEndpointGroup": {"endpointGroupId"},
		"CreateCertificateAuthority": {"entityId", "entity"}, "UpdateCertificateAuthority": {"entityId", "entity"}, "DeleteCertificateAuthority": {"entityId"},
		"CreateCertificateProfile": {"entityId", "entity"}, "UpdateCertificateProfile": {"entityId", "entity"}, "DeleteCertificateProfile": {"entityId"},
		"CreateTLSProfile": {"entityId", "entity"}, "UpdateTLSProfile": {"entityId", "entity"}, "DeleteTLSProfile": {"entityId"},
		"CreateCertificateScope": {"entityId", "entity"}, "UpdateCertificateScope": {"entityId", "entity"}, "DeleteCertificateScope": {"entityId"},
	}
	fieldsV3 := make(map[string][]string, len(fieldsV2))
	for operation, operationFields := range fieldsV2 {
		fieldsV3[operation] = operationFields
	}
	fieldsV3["CreateServer"] = []string{"hostId", "type", "address", "sshPort"}
	fieldsV3["UpdateServer"] = []string{"hostId", "type", "address", "sshPort", "clearSSHPort"}
	// v1alpha4 is deliberately narrow: E1 adds only server CRUD with
	// desiredHostname.  Do not silently advertise the older non-server
	// operations under a contract whose schema does not define them.
	fieldsV4 := map[string][]string{
		"CreateServer": {"hostId", "type", "desiredHostname", "address", "sshPort"},
		"UpdateServer": {"hostId", "type", "desiredHostname", "address", "sshPort", "clearSSHPort"},
		"DeleteServer": {"hostId"},
	}
	fieldsV5 := map[string][]string{
		"CreateServer":                           {"hostId", "type", "desiredHostname", "address", "sshPort"},
		"UpdateServer":                           {"hostId", "type", "desiredHostname", "address", "sshPort", "clearSSHPort"},
		"DeleteServer":                           {"hostId"},
		"CreateServiceDeployment":                {"deploymentId", "serviceType", "mode"},
		"DeleteServiceDeployment":                {"deploymentId"},
		"ReconcileDeploymentPlacement":           {"deploymentId", "members"},
		"ReconcileHostScopedDeploymentPlacement": {"deploymentId", "hosts"},
		"CreateEndpointGroup":                    {"endpointGroupId", "endpointGroup"},
		"UpdateEndpointGroup":                    {"endpointGroupId", "endpointGroup"},
		"DeleteEndpointGroup":                    {"endpointGroupId"},
		"SetServiceEndpointGroup":                {"deploymentId", "endpointGroupId"},
		"ClearServiceEndpointGroup":              {"deploymentId"},
	}
	fieldsV6 := make(map[string][]string, len(fieldsV5)+2)
	for operation, operationFields := range fieldsV5 {
		fieldsV6[operation] = operationFields
	}
	fieldsV6["ReconcileEndpointProvider"] = []string{"deploymentId", "endpointGroupId", "virtualRouterId", "virtualAddresses"}
	fieldsV6["ClearEndpointProvider"] = []string{"deploymentId"}
	fieldsV7 := make(map[string][]string, len(fieldsV6)+12)
	for operation, operationFields := range fieldsV6 {
		fieldsV7[operation] = operationFields
	}
	for _, operation := range []string{"CreateCertificateAuthority", "UpdateCertificateAuthority", "CreateCertificateProfile", "UpdateCertificateProfile", "CreateTLSProfile", "UpdateTLSProfile", "CreateCertificateScope", "UpdateCertificateScope"} {
		fieldsV7[operation] = []string{"entityId", "entity"}
	}
	for _, operation := range []string{"DeleteCertificateAuthority", "DeleteCertificateProfile", "DeleteTLSProfile", "DeleteCertificateScope"} {
		fieldsV7[operation] = []string{"entityId"}
	}
	fieldsV8 := make(map[string][]string, len(fieldsV7)+2)
	for operation, operationFields := range fieldsV7 {
		fieldsV8[operation] = operationFields
	}
	fieldsV8["SetServiceConfigurationValue"] = []string{"deploymentId", "scope", "memberId", "setting", "value"}
	fieldsV8["RemoveServiceConfigurationOverride"] = []string{"deploymentId", "scope", "memberId", "setting"}
	fieldsV9 := make(map[string][]string, len(fieldsV8))
	for operation, operationFields := range fieldsV8 {
		fieldsV9[operation] = operationFields
	}
	fieldsV1 := map[string][]string{
		"CreateServiceDeployment": {"deploymentId", "deployment"}, "DeleteServiceDeployment": {"deploymentId"},
		"SetServiceConfigurationValue": {"deploymentId", "setting", "value"}, "RemoveServiceConfigurationOverride": {"deploymentId", "setting"},
		"SetServiceEndpointGroup": {"deploymentId", "endpointGroupId"}, "ClearServiceEndpointGroup": {"deploymentId"},
		"SetHAProxyIntegration": {"deploymentId", "haproxyDeploymentId", "backend"}, "ClearHAProxyIntegration": {"deploymentId"},
		"CreateEndpointGroup": {"endpointGroupId", "endpointGroup"}, "UpdateEndpointGroup": {"endpointGroupId", "endpointGroup"}, "DeleteEndpointGroup": {"endpointGroupId"},
		"AssignServiceToHost": {"hostId", "deploymentId", "placement"}, "RemoveServiceFromHost": {"hostId", "deploymentId"}, "SetPlacementProperty": {"hostId", "deploymentId", "property", "value"},
	}
	fields := fieldsV1
	if command.APIVersion == EditCommandAPIVersionV2 {
		fields = fieldsV2
	} else if command.APIVersion == EditCommandAPIVersionV3 {
		fields = fieldsV3
	} else if command.APIVersion == EditCommandAPIVersionV4 {
		fields = fieldsV4
	} else if command.APIVersion == EditCommandAPIVersionV5 {
		fields = fieldsV5
	} else if command.APIVersion == EditCommandAPIVersionV6 {
		fields = fieldsV6
	} else if command.APIVersion == EditCommandAPIVersionV7 {
		fields = fieldsV7
	} else if command.APIVersion == EditCommandAPIVersionV8 {
		fields = fieldsV8
	} else if command.APIVersion == EditCommandAPIVersionV9 {
		fields = fieldsV9
	}
	allowedFields, allowed := fields[command.Operation]
	if !allowed {
		return blocked("INVALID_EDIT_COMMAND", "Edit operation is unsupported for this contract version", "command.operation")
	}
	if err := validateCommandFields(command, allowedFields...); err != nil {
		return err
	}
	switch command.Operation {
	case "CreateServer":
		hasSSHPort := command.SSHPort != 0 || command.presentFields["sshPort"]
		versionValid := isEditCommandV2OrLater(command.APIVersion)
		typeValid := command.APIVersion == EditCommandAPIVersionV2 || appconfig.ServerTypeIDPattern.MatchString(command.ServerType)
		desiredHostnameValid := (command.APIVersion != EditCommandAPIVersionV4 && !isEditCommandV5OrLater(command.APIVersion)) || (len(command.DesiredHostname) <= 253 && desiredHostnamePattern.MatchString(command.DesiredHostname))
		if !versionValid || !identifierPattern.MatchString(command.HostID) || !typeValid || !desiredHostnameValid || !validServerAddress(command.Address) || (hasSSHPort && (command.SSHPort < 1 || command.SSHPort > 65535)) {
			return blocked("INVALID_EDIT_COMMAND", "CreateServer requires a valid host, type, address and optional SSH port", "command")
		}
	case "UpdateServer":
		hasSSHPort := command.SSHPort != 0 || command.presentFields["sshPort"]
		hasClearSSHPort := command.ClearSSHPort || command.presentFields["clearSSHPort"]
		versionValid := isEditCommandV2OrLater(command.APIVersion)
		typeValid := command.ServerType == "" || ((command.APIVersion == EditCommandAPIVersionV3 || command.APIVersion == EditCommandAPIVersionV4 || isEditCommandV5OrLater(command.APIVersion)) && appconfig.ServerTypeIDPattern.MatchString(command.ServerType))
		desiredHostnameValid := command.DesiredHostname == "" || ((command.APIVersion == EditCommandAPIVersionV4 || isEditCommandV5OrLater(command.APIVersion)) && len(command.DesiredHostname) <= 253 && desiredHostnamePattern.MatchString(command.DesiredHostname))
		if !versionValid || !typeValid || !desiredHostnameValid || !identifierPattern.MatchString(command.HostID) || (command.Address == "" && !hasSSHPort && !command.ClearSSHPort && command.ServerType == "" && command.DesiredHostname == "") || (command.Address != "" && !validServerAddress(command.Address)) || (hasSSHPort && (command.SSHPort < 1 || command.SSHPort > 65535)) || (hasSSHPort && command.ClearSSHPort) || (hasClearSSHPort && !command.ClearSSHPort) {
			return blocked("INVALID_EDIT_COMMAND", "UpdateServer fields are invalid", "command")
		}
	case "DeleteServer":
		if !isEditCommandV2OrLater(command.APIVersion) || !identifierPattern.MatchString(command.HostID) {
			return blocked("INVALID_EDIT_COMMAND", "DeleteServer requires a valid host", "command.hostId")
		}
	case "ReconcileDeploymentPlacement":
		limit := 1024
		if isEditCommandV5OrLater(command.APIVersion) {
			limit = maxManagedPlacements
		}
		if !isEditCommandV2OrLater(command.APIVersion) || !identifierPattern.MatchString(command.DeploymentID) || len(command.Members) > limit {
			return blocked("INVALID_EDIT_COMMAND", "Deployment placement reconcile is invalid", "command.members")
		}
		memberIDs := make(map[string]bool)
		for _, member := range command.Members {
			rolesRequired := !isEditCommandV5OrLater(command.APIVersion)
			if !identifierPattern.MatchString(member.MemberID) || !identifierPattern.MatchString(member.HostID) || rolesRequired && len(member.Roles) == 0 || len(member.Roles) > maxManagedRoles || memberIDs[member.MemberID] || (isEditCommandV5OrLater(command.APIVersion) && (member.Configuration != nil || len(member.unknownFields) != 0)) {
				return blocked("INVALID_EDIT_COMMAND", "Placement member is invalid or duplicated", "command.members")
			}
			memberIDs[member.MemberID] = true
			roleIDs := make(map[string]bool)
			for _, role := range member.Roles {
				if !identifierPattern.MatchString(role) || roleIDs[role] {
					return blocked("INVALID_EDIT_COMMAND", "Placement role is invalid or duplicated", "command.members.roles")
				}
				roleIDs[role] = true
			}
			if err := safeValue(member.Configuration, "configuration"); err != nil {
				return err
			}
		}
	case "ReconcileHostScopedDeploymentPlacement":
		if !isEditCommandV5OrLater(command.APIVersion) || !identifierPattern.MatchString(command.DeploymentID) || len(command.Hosts) > maxManagedHostDocuments {
			return blocked("INVALID_EDIT_COMMAND", "Host-scoped placement reconcile is invalid", "command.hosts")
		}
		hostIDs := make(map[string]bool)
		for _, host := range command.Hosts {
			if !identifierPattern.MatchString(host.HostID) || len(host.Roles) > maxManagedRoles || hostIDs[host.HostID] || len(host.unknownFields) != 0 || command.APIVersion == EditCommandAPIVersionV9 && (host.Priority < 1 || host.Priority > 254) {
				return blocked("INVALID_EDIT_COMMAND", "Placement host is invalid or duplicated", "command.hosts")
			}
			hostIDs[host.HostID] = true
			roleIDs := make(map[string]bool)
			for _, role := range host.Roles {
				if !identifierPattern.MatchString(role) || roleIDs[role] {
					return blocked("INVALID_EDIT_COMMAND", "Placement role is invalid or duplicated", "command.hosts.roles")
				}
				roleIDs[role] = true
			}
		}
	case "CreateCertificateAuthority", "UpdateCertificateAuthority", "CreateCertificateProfile", "UpdateCertificateProfile", "CreateTLSProfile", "UpdateTLSProfile", "CreateCertificateScope", "UpdateCertificateScope":
		if !isEditCommandV2OrLater(command.APIVersion) || !identifierPattern.MatchString(command.EntityID) || command.Entity == nil {
			return blocked("INVALID_EDIT_COMMAND", "Certificate entity command is invalid", "command.entity")
		}
	case "DeleteCertificateAuthority", "DeleteCertificateProfile", "DeleteTLSProfile", "DeleteCertificateScope":
		if !isEditCommandV2OrLater(command.APIVersion) || !identifierPattern.MatchString(command.EntityID) {
			return blocked("INVALID_EDIT_COMMAND", "Certificate entity identifier is invalid", "command.entityId")
		}
	case "CreateServiceDeployment":
		if !identifierPattern.MatchString(command.DeploymentID) || (command.APIVersion == EditCommandAPIVersion && command.Deployment == nil) || (isEditCommandV2OrLater(command.APIVersion) && (!identifierPattern.MatchString(command.ServiceType) || !identifierPattern.MatchString(command.Mode))) {
			return blocked("INVALID_EDIT_COMMAND", "Create deployment requires an identifier and deployment object", "command")
		}
	case "DeleteServiceDeployment", "ClearServiceEndpointGroup", "ClearHAProxyIntegration":
		if !identifierPattern.MatchString(command.DeploymentID) {
			return blocked("INVALID_EDIT_COMMAND", "Deployment identifier is required", "command.deploymentId")
		}
	case "SetServiceConfigurationValue", "RemoveServiceConfigurationOverride":
		if command.APIVersion != EditCommandAPIVersionV8 && command.APIVersion != EditCommandAPIVersionV9 {
			if !identifierPattern.MatchString(command.DeploymentID) || command.Setting == "" {
				return blocked("INVALID_EDIT_COMMAND", "Configuration edit requires deployment and setting identifiers", "command")
			}
			break
		}
		memberValid := command.Scope == "DEPLOYMENT" && command.MemberID == "" || command.Scope == "MEMBER" && identifierPattern.MatchString(command.MemberID)
		valuePresent := command.presentFields["value"] || command.Value != nil
		if !identifierPattern.MatchString(command.DeploymentID) || len(command.Setting) > 128 || !configurationSettingPattern.MatchString(command.Setting) || !memberValid || command.Operation == "SetServiceConfigurationValue" && (!valuePresent || !configurationPrimitive(command.Value)) || command.Operation == "RemoveServiceConfigurationOverride" && valuePresent {
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
		if !identifierPattern.MatchString(command.EndpointGroupID) || command.EndpointGroup == nil || (isEditCommandV5OrLater(command.APIVersion) && !validEndpointGroup(command.EndpointGroup)) {
			return blocked("INVALID_EDIT_COMMAND", "Endpoint-group edit requires an identifier and value", "command")
		}
	case "DeleteEndpointGroup":
		if !identifierPattern.MatchString(command.EndpointGroupID) {
			return blocked("INVALID_EDIT_COMMAND", "Endpoint-group identifier is required", "command.endpointGroupId")
		}
	case "ReconcileEndpointProvider":
		if (command.APIVersion != EditCommandAPIVersionV6 && command.APIVersion != EditCommandAPIVersionV7 && command.APIVersion != EditCommandAPIVersionV8 && command.APIVersion != EditCommandAPIVersionV9) || !identifierPattern.MatchString(command.DeploymentID) || !identifierPattern.MatchString(command.EndpointGroupID) || command.VirtualRouterID < 1 || command.VirtualRouterID > 255 || len(command.VirtualAddresses) == 0 || len(command.VirtualAddresses) > 64 {
			return blocked("INVALID_EDIT_COMMAND", "Provider reconcile requires a complete bounded provider tuple", "command")
		}
		seen := make(map[string]bool, len(command.VirtualAddresses))
		for _, address := range command.VirtualAddresses {
			ip, err := netip.ParseAddr(address.Address)
			if err != nil || !ip.Is4() || address.Interface == "" || len(address.Interface) > 128 || !virtualAddressInterfacePattern.MatchString(address.Interface) || len(address.unknownFields) != 0 {
				return blocked("INVALID_EDIT_COMMAND", "Provider virtual address is invalid", "command.virtualAddresses")
			}
			key := address.Address + "\x00" + address.Interface
			if seen[key] {
				return blocked("INVALID_EDIT_COMMAND", "Provider virtual address is duplicated", "command.virtualAddresses")
			}
			seen[key] = true
		}
	case "ClearEndpointProvider":
		if (command.APIVersion != EditCommandAPIVersionV6 && command.APIVersion != EditCommandAPIVersionV7 && command.APIVersion != EditCommandAPIVersionV8 && command.APIVersion != EditCommandAPIVersionV9) || !identifierPattern.MatchString(command.DeploymentID) {
			return blocked("INVALID_EDIT_COMMAND", "Provider clear requires a deployment identifier", "command.deploymentId")
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
	if err := safeValue(command.Value, command.Setting); err != nil {
		return err
	}
	if err := safeValue(command.Value, command.Property); err != nil {
		return err
	}
	for _, value := range []any{command.Deployment, command.EndpointGroup, command.Placement, command.Backend, command.Entity, command.Members, command.Hosts, command.VirtualAddresses} {
		if err := safeValue(value, ""); err != nil {
			return err
		}
	}
	return nil
}

func configurationPrimitive(value any) bool {
	switch typed := value.(type) {
	case string, bool, int, int64, uint64:
		return true
	case float64:
		return !math.IsNaN(typed) && !math.IsInf(typed, 0)
	default:
		return false
	}
}

func validEndpointGroup(value map[string]any) bool {
	address := asMap(value["address"])
	if address == nil || len(address) != 2 {
		return false
	}
	domain, domainOK := address["domain"].(string)
	_, wildcardOK := address["wildcard"].(bool)
	if !domainOK || domain == "" || !wildcardOK {
		return false
	}
	for key := range value {
		if key != "address" && !extensionKeyPattern.MatchString(key) {
			return false
		}
	}
	return true
}

func validateCommandFields(command EditCommand, allowed ...string) error {
	if len(command.unknownFields) != 0 {
		return blocked("INVALID_EDIT_COMMAND", "Edit command contains an unknown field", "command."+command.unknownFields[0])
	}
	data, err := json.Marshal(command)
	if err != nil {
		return blocked("INVALID_EDIT_COMMAND", "Edit command cannot be encoded", "command")
	}
	var object map[string]json.RawMessage
	if err := json.Unmarshal(data, &object); err != nil {
		return blocked("INVALID_EDIT_COMMAND", "Edit command cannot be decoded", "command")
	}
	permitted := map[string]bool{"apiVersion": true, "kind": true, "baseProjectRevision": true, "operation": true}
	for _, field := range allowed {
		permitted[field] = true
	}
	for field := range command.presentFields {
		if !permitted[field] {
			return blocked("INVALID_EDIT_COMMAND", "Edit command contains fields from another operation", "command."+field)
		}
	}
	for field := range object {
		if !permitted[field] {
			return blocked("INVALID_EDIT_COMMAND", "Edit command contains fields from another operation", "command."+field)
		}
	}
	return nil
}

func validServerAddress(value string) bool {
	return serverAddressPattern.MatchString(value)
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
	if operation == "CreateServer" || operation == "UpdateServer" || operation == "DeleteServer" {
		return applyServerCommand(command, root, snapshot, candidates, originals)
	}
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
			value := map[string]any{"serviceType": command.ServiceType, "mode": command.Mode}
			if command.APIVersion == EditCommandAPIVersion {
				value = deepCopy(command.Deployment).(map[string]any)
			}
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
		commands = append([]EditCommand(nil), command.Commands...)
		for index := range commands {
			commands[index].APIVersion = command.APIVersion
			commands[index].Kind = command.Kind
			commands[index].BaseProjectRevision = command.BaseProjectRevision
		}
	}
	var expectations []expectation
	serverFinal := make(map[string]expectation)
	deletedServers := make(map[string]bool)
	var changes []SemanticChange
	impactSet := make(map[string]bool)
	for _, child := range commands {
		if child.Operation == "CreateServer" && deletedServers[child.HostID] {
			return nil, nil, nil, blocked("SERVER_RECREATE_IN_SESSION_UNSUPPORTED", "Delete and recreate of one server in a session is not supported", "command.hostId")
		}
		expected, impacts, err := applyOne(child, root, snapshot, candidates, originals)
		if err != nil {
			return nil, nil, nil, err
		}
		if expected.Operation == "" {
			continue
		}
		if expected.Operation == "ServerFinal" {
			serverFinal[expected.First] = expected
			if child.Operation == "DeleteServer" {
				deletedServers[child.HostID] = true
			}
		} else {
			expectations = append(expectations, expected)
		}
		changes = append(changes, commandSummary(child))
		for _, impact := range impacts {
			impactSet[impact] = true
		}
	}
	serverIDs := make([]string, 0, len(serverFinal))
	for hostID := range serverFinal {
		serverIDs = append(serverIDs, hostID)
	}
	sort.Strings(serverIDs)
	for _, hostID := range serverIDs {
		expectations = append(expectations, serverFinal[hostID])
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
		case "ServerFinal":
			value := asMap(expected.Value)
			host := snapshot.Hosts[expected.First]
			if value == nil {
				return false
			}
			if value["exists"] == false {
				if host != nil {
					return false
				}
				continue
			}
			if host == nil || host["ansibleHost"] != value["address"] || host["type"] != value["type"] || host["desiredHostname"] != value["desiredHostname"] {
				return false
			}
			if value["portPresent"] == true && !samePort(host["ansiblePort"], value["port"]) {
				return false
			}
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

func samePort(left, right any) bool {
	leftNumber, leftOK := left.(float64)
	rightNumber, rightOK := right.(int)
	if leftOK && rightOK {
		return leftNumber == float64(rightNumber)
	}
	return semanticEqual(left, right)
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

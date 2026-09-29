package installer

import (
	"encoding/json"
	"math"
	"strings"
	"unicode/utf8"

	"platform-installer/internal/projectlifecycle"
)

const maxConfigurationValueBytes = 64 * 1024

func catalogConfigurationSetting(catalog *projectlifecycle.ProjectCatalogView, serviceType, settingID string) (*projectlifecycle.ProjectCatalogSetting, bool) {
	if catalog == nil || catalog.Status != "READY" {
		return nil, false
	}
	for serviceIndex := range catalog.Services {
		service := &catalog.Services[serviceIndex]
		if service.ID != serviceType {
			continue
		}
		for settingIndex := range service.ConfigurationSettings {
			setting := &service.ConfigurationSettings[settingIndex]
			if setting.ID == settingID {
				return setting, true
			}
		}
		return nil, false
	}
	return nil, false
}

func settingAllowsScope(setting *projectlifecycle.ProjectCatalogSetting, scope string) bool {
	wanted := "deployment"
	if scope == "MEMBER" {
		wanted = "member"
	}
	for _, candidate := range setting.Scopes {
		if candidate == wanted {
			return true
		}
	}
	return false
}

func validateConfigurationValue(setting *projectlifecycle.ProjectCatalogSetting, value any) error {
	encoded, err := json.Marshal(value)
	if err != nil || len(encoded) > maxConfigurationValueBytes {
		return blocked("INVALID_VALUE", "Configuration value is invalid or exceeds its limit", "command.value")
	}
	switch setting.EditorShape {
	case "BOOLEAN":
		if _, ok := value.(bool); !ok {
			return invalidConfigurationValue()
		}
	case "INTEGER":
		integer, ok := configurationInteger(value)
		if !ok || setting.Minimum == nil || setting.Maximum == nil || integer < int64(*setting.Minimum) || integer > int64(*setting.Maximum) {
			return invalidConfigurationValue()
		}
	case "NUMBER":
		number, ok := configurationNumber(value)
		if !ok || setting.Minimum == nil || setting.Maximum == nil || number < *setting.Minimum || number > *setting.Maximum {
			return invalidConfigurationValue()
		}
	case "ENUM":
		for _, allowed := range setting.Enum {
			if configurationEnumEqual(value, allowed) {
				return nil
			}
		}
		return invalidConfigurationValue()
	case "BOUNDED_STRING":
		text, ok := value.(string)
		if !ok || !utf8.ValidString(text) || setting.MinLength == nil || setting.MaxLength == nil {
			return invalidConfigurationValue()
		}
		length := utf8.RuneCountInString(text)
		if length < *setting.MinLength || length > *setting.MaxLength {
			return invalidConfigurationValue()
		}
	case "DNS_DOMAIN":
		text, ok := value.(string)
		if !ok || !utf8.ValidString(text) || !projectlifecycle.ValidDNSDomain(text) {
			return invalidConfigurationValue()
		}
	case "TLS_PROFILE", "SERVICE_DEPLOYMENT":
		text, ok := value.(string)
		if !ok || !validDesiredStateIdentifier(text) {
			return invalidConfigurationValue()
		}
	case "RUNTIME_SECRET_REFERENCE_OBJECT":
		object, ok := value.(map[string]any)
		if !ok || !safeRuntimeSecretReferenceObject(object) || object["passwordSecretRef"] != "runtime:"+setting.RuntimeSecretRequirementRef {
			return invalidConfigurationValue()
		}
		_, usernamePresent := object["username"]
		if setting.RuntimeSecretUsernameRequired != usernamePresent {
			return invalidConfigurationValue()
		}
	default:
		return blocked("SETTING_UNSUPPORTED", "Configuration setting is read-only in this Installer version", "command.setting")
	}
	return nil
}

func invalidConfigurationValue() error {
	return blocked("INVALID_VALUE", "Configuration value does not match the catalog descriptor", "command.value")
}

func configurationNumber(value any) (float64, bool) {
	switch typed := value.(type) {
	case int:
		if typed > 1<<53 || typed < -(1<<53) {
			return 0, false
		}
		return float64(typed), true
	case int64:
		if typed > 1<<53 || typed < -(1<<53) {
			return 0, false
		}
		return float64(typed), true
	case uint64:
		if typed > 1<<53 {
			return 0, false
		}
		return float64(typed), true
	case float64:
		if math.IsNaN(typed) || math.IsInf(typed, 0) || math.Abs(typed) > 1<<53 {
			return 0, false
		}
		return typed, true
	default:
		return 0, false
	}
}

func configurationInteger(value any) (int64, bool) {
	switch typed := value.(type) {
	case int:
		return int64(typed), true
	case int64:
		return typed, true
	case uint64:
		if typed > math.MaxInt64 {
			return 0, false
		}
		return int64(typed), true
	case float64:
		if math.IsNaN(typed) || math.IsInf(typed, 0) || math.Abs(typed) > 1<<53 || math.Trunc(typed) != typed {
			return 0, false
		}
		return int64(typed), true
	default:
		return 0, false
	}
}

func configurationEnumEqual(value, allowed any) bool {
	switch expected := allowed.(type) {
	case string:
		actual, ok := value.(string)
		return ok && actual == expected
	case bool:
		actual, ok := value.(bool)
		return ok && actual == expected
	case int, int64, uint64:
		expectedInteger, expectedOK := configurationInteger(expected)
		actualInteger, actualOK := configurationInteger(value)
		return expectedOK && actualOK && actualInteger == expectedInteger
	case float64:
		actual, ok := configurationNumber(value)
		return ok && actual == expected
	default:
		return allowed == nil && value == nil
	}
}

func (candidate *structuralCandidate) applyConfigurationCommand(command EditCommand, deployments map[string]any, catalog *projectlifecycle.ProjectCatalogView) (bool, error) {
	deployment := asMap(deployments[command.DeploymentID])
	if deployment == nil {
		return false, referenceNotFound("deploymentId")
	}
	serviceType, serviceOK := deployment["serviceType"].(string)
	modeID, modeOK := deployment["mode"].(string)
	if !serviceOK || !modeOK {
		return false, managedReadError("Managed deployment is malformed", desiredDocument)
	}
	if service, mode := catalogServiceMode(catalog, serviceType, modeID); service == nil || mode == nil {
		return false, blocked("CATALOG_VALUE_UNKNOWN", "Deployment service or mode is not declared by the project catalog", "command.deploymentId")
	}
	setting, found := catalogConfigurationSetting(catalog, serviceType, command.Setting)
	if !found {
		return false, blocked("CATALOG_VALUE_UNKNOWN", "Configuration setting is not declared by the project catalog", "command.setting")
	}
	if setting.Kind != "MANAGED" || setting.EditorShape == "UNSUPPORTED" || !settingAllowsScope(setting, command.Scope) {
		return false, blocked("SETTING_UNSUPPORTED", "Configuration setting or scope is read-only in this Installer version", "command.setting")
	}
	if command.Operation == "SetServiceConfigurationValue" {
		if err := validateConfigurationValue(setting, command.Value); err != nil {
			return false, err
		}
	}
	target, logical, err := candidate.configurationTarget(command, deployment)
	if err != nil {
		return false, err
	}
	configuration := asMap(target["configuration"])
	if configuration == nil && target["configuration"] != nil {
		return false, managedReadError("Managed configuration is malformed", logical)
	}
	if command.Operation == "RemoveServiceConfigurationOverride" {
		if configuration == nil {
			return false, nil
		}
		if _, present := configuration[command.Setting]; !present {
			return false, nil
		}
		delete(configuration, command.Setting)
		if len(configuration) == 0 {
			delete(target, "configuration")
		}
		candidate.dirty[logical] = true
		return true, nil
	}
	if configuration == nil {
		configuration = map[string]any{}
		target["configuration"] = configuration
	}
	value := command.Value
	if setting.EditorShape == "INTEGER" {
		// Wails transports JSON numbers as float64. Persist schema integers as
		// integers, not YAML !!float values rejected by Core's integer schema.
		value, _ = configurationInteger(command.Value)
	}
	if existing, present := configuration[command.Setting]; present && semanticEqual(existing, value) {
		return false, nil
	}
	configuration[command.Setting] = deepCopy(value)
	candidate.dirty[logical] = true
	return true, nil
}

func (candidate *structuralCandidate) configurationTarget(command EditCommand, deployment map[string]any) (map[string]any, string, error) {
	if command.Scope == "DEPLOYMENT" {
		return deployment, desiredDocument, nil
	}
	for logical, document := range candidate.documents {
		if !strings.HasPrefix(logical, "inventory/host_vars/") {
			continue
		}
		placements := asMap(document["platform_deployments"])
		placement := asMap(placements[command.DeploymentID])
		members := asMap(placement["members"])
		member := asMap(members[command.MemberID])
		if member != nil {
			return member, logical, nil
		}
	}
	return nil, "command.memberId", referenceNotFound("memberId")
}

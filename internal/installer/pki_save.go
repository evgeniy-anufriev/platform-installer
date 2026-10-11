package installer

import (
	"encoding/json"
	"math"
	"net/netip"
	"regexp"
	"strconv"
)

// desiredStateIdentifierPattern is deliberately separate from the shorter
// Installer command ID grammar. PKI references are desired-state fields and
// must use the grammar published by project/v2alpha1.
var desiredStateIdentifierPattern = regexp.MustCompile(`^[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*$`)

func pkiOperation(operation string) bool {
	switch operation {
	case "CreateCertificateAuthority", "UpdateCertificateAuthority", "DeleteCertificateAuthority", "CreateCertificateProfile", "UpdateCertificateProfile", "DeleteCertificateProfile", "CreateTLSProfile", "UpdateTLSProfile", "DeleteTLSProfile", "CreateCertificateScope", "UpdateCertificateScope", "DeleteCertificateScope":
		return true
	}
	return false
}

func pkiMap(state map[string]any, key string) map[string]any {
	value := asMap(state[key])
	if value == nil {
		value = map[string]any{}
		state[key] = value
	}
	return value
}

func reducePKICommand(state map[string]any, command EditCommand, mutations topologyMutationSet) error {
	var values map[string]any
	var deleted map[string]bool
	switch command.Operation {
	case "CreateCertificateAuthority", "UpdateCertificateAuthority", "DeleteCertificateAuthority":
		values, deleted = pkiMap(state, "certificateAuthorities"), mutations.deletedAuthorities
	case "CreateCertificateProfile", "UpdateCertificateProfile", "DeleteCertificateProfile":
		values, deleted = pkiMap(state, "certificateProfiles"), mutations.deletedProfiles
	case "CreateTLSProfile", "UpdateTLSProfile", "DeleteTLSProfile":
		values, deleted = pkiMap(state, "tlsProfiles"), mutations.deletedTLSProfiles
	case "CreateCertificateScope", "UpdateCertificateScope", "DeleteCertificateScope":
		values = pkiMap(state, "certificateScopes")
	}
	if values == nil {
		return blocked("INVALID_EDIT_COMMAND", "PKI operation is unsupported", "command.operation")
	}
	if command.APIVersion != EditCommandAPIVersionV7 && command.APIVersion != EditCommandAPIVersionV8 && command.APIVersion != EditCommandAPIVersionV9 && command.APIVersion != EditCommandAPIVersionV10 {
		return blocked("EDIT_OPERATION_UNAVAILABLE", "PKI editing requires v1alpha7 or a compatible later contract", "command.apiVersion")
	}
	if command.Operation[:6] == "Create" {
		if values[command.EntityID] != nil {
			return blocked("INVALID_EDIT_COMMAND", "PKI entity already exists", "command.entityId")
		}
		if err := validPKIEntity(command.Operation, command.Entity); err != nil {
			return err
		}
		values[command.EntityID] = deepCopy(command.Entity)
		return nil
	}
	if command.Operation[:6] == "Update" {
		if values[command.EntityID] == nil {
			return blocked("INVALID_EDIT_COMMAND", "PKI entity does not exist", "command.entityId")
		}
		if err := validPKIEntity(command.Operation, command.Entity); err != nil {
			return err
		}
		next := deepCopy(command.Entity).(map[string]any)
		for key, value := range asMap(values[command.EntityID]) {
			if _, supplied := next[key]; extensionKeyPattern.MatchString(key) && !supplied {
				next[key] = deepCopy(value)
			}
		}
		values[command.EntityID] = next
		return nil
	}
	if values[command.EntityID] == nil {
		return blocked("INVALID_EDIT_COMMAND", "PKI entity does not exist", "command.entityId")
	}
	delete(values, command.EntityID)
	if deleted != nil {
		deleted[command.EntityID] = true
	}
	return nil
}

func validPKIEntity(operation string, value map[string]any) error {
	if value == nil {
		return blocked("INVALID_VALUE", "PKI entity is required", "command.entity")
	}
	if operation == "CreateCertificateAuthority" || operation == "UpdateCertificateAuthority" {
		if err := validPKIObjectKeys(value, []string{"mode", "displayName", "commonName", "validityDays"}, "command.entity"); err != nil {
			return err
		}
		if value["mode"] != "MANAGED" {
			return blocked("INVALID_VALUE", "Only MANAGED certificate authorities are supported", "command.entity.mode")
		}
		if name, ok := value["commonName"].(string); !ok || name == "" || len(name) > 128 {
			return blocked("INVALID_VALUE", "Certificate authority common name is invalid", "command.entity.commonName")
		}
		if err := validOptionalString(value, "displayName", 1, 0); err != nil {
			return err
		}
		return validOptionalInteger(value, "validityDays", 1, "command.entity.validityDays")
	}
	if operation == "CreateCertificateProfile" || operation == "UpdateCertificateProfile" {
		if err := validPKIObjectKeys(value, []string{"displayName", "authorityRef", "keyAlgorithm", "keySize", "validityDays", "usages", "sanPolicy", "subject"}, "command.entity"); err != nil {
			return err
		}
		if ref, ok := value["authorityRef"].(string); !ok || !validDesiredStateIdentifier(ref) || asMap(value["sanPolicy"]) == nil {
			return blocked("INVALID_VALUE", "Certificate profile is invalid", "command.entity")
		}
		if err := validOptionalString(value, "displayName", 1, 0); err != nil {
			return err
		}
		if err := validOptionalInteger(value, "keySize", 2048, "command.entity.keySize"); err != nil {
			return err
		}
		if err := validOptionalInteger(value, "validityDays", 1, "command.entity.validityDays"); err != nil {
			return err
		}
		if algorithm, present := value["keyAlgorithm"]; present && algorithm != "RSA" && algorithm != "EC" {
			return blocked("INVALID_VALUE", "Certificate profile key algorithm is invalid", "command.entity.keyAlgorithm")
		}
		if raw, present := value["usages"]; present {
			if err := validPKIEnumList(raw, "command.entity.usages", []string{"serverAuth", "clientAuth"}, maxManagedEntities); err != nil {
				return err
			}
		}
		if err := validClosedBoolMap(asMap(value["sanPolicy"]), []string{"includeHostDns", "includeHostIp", "includeEndpointFqdns", "includeEndpointWildcard", "includeEndpointVip"}, "command.entity.sanPolicy"); err != nil {
			return err
		}
		if raw, present := value["subject"]; present {
			subject := asMap(raw)
			if subject == nil {
				return blocked("INVALID_VALUE", "Certificate subject is invalid", "command.entity.subject")
			}
			return validSubjectDN(subject)
		}
		return nil
	}
	if operation == "CreateTLSProfile" || operation == "UpdateTLSProfile" {
		if err := validPKIObjectKeys(value, []string{"certificateProfileRef", "scope", "storePasswordSecretRef"}, "command.entity"); err != nil {
			return err
		}
		if ref, ok := value["certificateProfileRef"].(string); !ok || !validDesiredStateIdentifier(ref) {
			return blocked("INVALID_VALUE", "TLS profile certificate reference is invalid", "command.entity.certificateProfileRef")
		}
		if ref, ok := value["storePasswordSecretRef"].(string); !ok || !runtimeRefPattern.MatchString(ref) {
			return blocked("SECRET_REFERENCE_INVALID", "TLS profile requires an opaque runtime secret reference", "command.entity.storePasswordSecretRef")
		}
		if err := validOptionalScope(value, "scope", "command.entity.scope"); err != nil {
			return err
		}
		return nil
	}
	if operation != "CreateCertificateScope" && operation != "UpdateCertificateScope" {
		return blocked("INVALID_VALUE", "PKI operation is unsupported", "command.operation")
	}
	if err := validPKIObjectKeys(value, []string{"displayName", "profile", "scope", "sources"}, "command.entity"); err != nil {
		return err
	}
	if ref, ok := value["profile"].(string); !ok || !validDesiredStateIdentifier(ref) || asMap(value["sources"]) == nil {
		return blocked("INVALID_VALUE", "Certificate scope is invalid", "command.entity")
	}
	if err := validOptionalString(value, "displayName", 1, 0); err != nil {
		return err
	}
	if err := validOptionalScope(value, "scope", "command.entity.scope"); err != nil {
		return err
	}
	return validScopeSources(asMap(value["sources"]))
}

func validPKIObjectKeys(value map[string]any, keys []string, field string) error {
	allowed := map[string]bool{}
	for _, key := range keys {
		allowed[key] = true
	}
	for key := range value {
		if !allowed[key] && !extensionKeyPattern.MatchString(key) {
			return blocked("INVALID_VALUE", "PKI entity contains an unknown field", field)
		}
	}
	return nil
}

func validOptionalString(value map[string]any, key string, min, max int) error {
	raw, present := value[key]
	if !present {
		return nil
	}
	text, ok := raw.(string)
	if !ok || (min > 0 && len(text) < min) || (max > 0 && len(text) > max) {
		return blocked("INVALID_VALUE", "PKI string field is invalid", "command.entity."+key)
	}
	return nil
}

func validOptionalInteger(value map[string]any, key string, min int, field string) error {
	raw, present := value[key]
	if !present {
		return nil
	}
	number, ok := pkiInteger(raw)
	if !ok || number < min {
		return blocked("INVALID_VALUE", "PKI integer field is invalid", field)
	}
	return nil
}

func pkiInteger(value any) (int, bool) {
	if number, ok := yamlInteger(value); ok {
		return number, true
	}
	var number float64
	switch typed := value.(type) {
	case float64:
		number = typed
	case json.Number:
		parsed, err := strconv.ParseFloat(string(typed), 64)
		if err != nil {
			return 0, false
		}
		number = parsed
	default:
		return 0, false
	}
	// A decoded float64 has at most 53 exact integer bits. Do not round a JSON
	// number or convert an out-of-range value to the platform int type.
	if math.IsNaN(number) || math.IsInf(number, 0) || math.Trunc(number) != number || number < float64(-maxIntValue()) || number > float64(maxIntValue()) || number > 1<<53 || number < -(1<<53) {
		return 0, false
	}
	return int(number), true
}

func maxIntValue() int {
	return int(^uint(0) >> 1)
}

func validDesiredStateIdentifier(value string) bool {
	return len(value) >= 1 && len(value) <= 128 && desiredStateIdentifierPattern.MatchString(value)
}

func validOptionalScope(value map[string]any, key, field string) error {
	raw, present := value[key]
	if !present {
		return nil
	}
	if raw != "HOST" && raw != "MEMBER" && raw != "DEPLOYMENT" {
		return blocked("INVALID_VALUE", "PKI scope is invalid", field)
	}
	return nil
}

func validClosedBoolMap(value map[string]any, keys []string, field string) error {
	if value == nil {
		return blocked("INVALID_VALUE", "PKI object is invalid", field)
	}
	allowed := map[string]bool{}
	for _, key := range keys {
		allowed[key] = true
	}
	for key, raw := range value {
		if !allowed[key] {
			return blocked("INVALID_VALUE", "PKI object contains an unknown field", field)
		}
		if _, ok := raw.(bool); !ok {
			return blocked("INVALID_VALUE", "PKI policy value is invalid", field)
		}
	}
	return nil
}

func validSubjectDN(value map[string]any) error {
	if value == nil {
		return nil
	}
	limits := map[string]int{"C": 2, "ST": 128, "L": 128, "O": 128, "OU": 128}
	for key, raw := range value {
		limit, allowed := limits[key]
		text, ok := raw.(string)
		if !allowed || !ok || len(text) > limit {
			return blocked("INVALID_VALUE", "Certificate subject is invalid", "command.entity.subject")
		}
	}
	return nil
}

func validPKIEnumList(value any, field string, allowedValues []string, limit int) error {
	values := asSlice(value)
	if values == nil || len(values) > limit {
		return blocked("INVALID_VALUE", "PKI list is invalid", field)
	}
	allowed := map[string]bool{}
	for _, item := range allowedValues {
		allowed[item] = true
	}
	seen := map[string]bool{}
	for _, raw := range values {
		item, ok := raw.(string)
		if !ok || !allowed[item] || seen[item] {
			return blocked("INVALID_VALUE", "PKI list item is invalid", field)
		}
		seen[item] = true
	}
	return nil
}

func validScopeSources(value map[string]any) error {
	if err := validPKIObjectKeys(value, []string{"serviceDeployments", "hosts", "members", "explicitDnsNames", "explicitIpAddresses"}, "command.entity.sources"); err != nil {
		return err
	}
	if raw, present := value["serviceDeployments"]; present {
		if err := validIdentifierList(raw, "command.entity.sources.serviceDeployments", maxManagedEntities); err != nil {
			return err
		}
	}
	if raw, present := value["hosts"]; present {
		if err := validIdentifierList(raw, "command.entity.sources.hosts", maxManagedEntities); err != nil {
			return err
		}
	}
	if raw, present := value["members"]; present {
		if err := validMemberReferenceList(raw); err != nil {
			return err
		}
	}
	if raw, present := value["explicitDnsNames"]; present {
		if err := validStringList(raw, "command.entity.sources.explicitDnsNames", false); err != nil {
			return err
		}
	}
	if raw, present := value["explicitIpAddresses"]; present {
		return validStringList(raw, "command.entity.sources.explicitIpAddresses", true)
	}
	return nil
}

func validIdentifierList(value any, field string, limit int) error {
	values := asSlice(value)
	if values == nil || len(values) > limit {
		return blocked("INVALID_VALUE", "PKI identifier list is invalid", field)
	}
	seen := map[string]bool{}
	for _, raw := range values {
		item, ok := raw.(string)
		if !ok || !validDesiredStateIdentifier(item) || seen[item] {
			return blocked("INVALID_VALUE", "PKI identifier list item is invalid", field)
		}
		seen[item] = true
	}
	return nil
}

func validMemberReferenceList(value any) error {
	values := asSlice(value)
	if values == nil || len(values) > maxManagedPlacements {
		return blocked("INVALID_VALUE", "PKI member list is invalid", "command.entity.sources.members")
	}
	seen := map[string]bool{}
	for _, raw := range values {
		member := asMap(raw)
		deploymentID, deploymentOK := member["deploymentId"].(string)
		memberID, memberOK := member["memberId"].(string)
		key := deploymentID + "\x00" + memberID
		if len(member) != 2 || !deploymentOK || !memberOK || !validDesiredStateIdentifier(deploymentID) || !validDesiredStateIdentifier(memberID) || seen[key] {
			return blocked("INVALID_VALUE", "PKI member reference is invalid", "command.entity.sources.members")
		}
		seen[key] = true
	}
	return nil
}

func validStringList(value any, field string, requireIP bool) error {
	values := asSlice(value)
	if values == nil || len(values) > maxManagedEntities {
		return blocked("INVALID_VALUE", "PKI string list is invalid", field)
	}
	seen := map[string]bool{}
	for _, raw := range values {
		text, ok := raw.(string)
		if !ok || text == "" || seen[text] {
			return blocked("INVALID_VALUE", "PKI string list item is invalid", field)
		}
		if requireIP {
			if _, err := netip.ParseAddr(text); err != nil {
				return blocked("INVALID_VALUE", "Explicit IP address is invalid", field)
			}
		}
		seen[text] = true
	}
	return nil
}

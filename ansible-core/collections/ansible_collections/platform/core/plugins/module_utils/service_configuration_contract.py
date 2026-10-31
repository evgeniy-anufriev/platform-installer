from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import re


SETTING_KINDS = ("MANAGED", "ADVANCED")
SETTING_TYPES = ("string", "integer", "number", "boolean", "object", "array", "null")
SETTING_SCOPES = ("deployment", "member")
VALIDATION_KEYS = {
    "string": {"enum", "minLength", "maxLength", "pattern"},
    "integer": {"enum", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf"},
    "number": {"enum", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf"},
    "boolean": {"enum"},
    "object": {"enum", "required", "properties", "additionalProperties", "unevaluatedProperties", "minProperties", "maxProperties"},
    "array": {"enum", "items", "minItems", "maxItems", "uniqueItems"},
    "null": {"enum"},
}


def _issue(code, path, message):
    return {"code": code, "path": path, "message": message}


def _literal_matches_type(value, expected):
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "null":
        return value is None
    return False


def canonical_settings(definition):
    """Return canonical settings or adapt the alpha legacy mapping.

    The adapter deliberately exposes only information that already existed in
    the legacy mapping/schema pair. It is a read compatibility boundary, not a
    second authored contract.
    """
    definition = definition if isinstance(definition, dict) else {}
    configuration = definition.get("configuration", {})
    settings = configuration.get("settings") if isinstance(configuration, dict) else None
    legacy = definition.get("configurationMapping")
    if isinstance(settings, dict) and isinstance(legacy, dict):
        return {}, [_issue("SERVICE_CONFIGURATION_CONTRACT_CONFLICT", "configuration", "Canonical configuration.settings and legacy configurationMapping cannot coexist")], "conflict"
    if isinstance(settings, dict):
        return copy.deepcopy(settings), [], "canonical"
    if not isinstance(legacy, dict):
        return {}, [_issue("SERVICE_CONFIGURATION_SETTINGS_REQUIRED", "configuration.settings", "Service definition must declare canonical settings or a legacy configurationMapping")], "missing"
    return {
        logical: dict({"kind": "MANAGED", "type": "string", "validation": {}}, **(entry if isinstance(entry, dict) else {}))
        for logical, entry in legacy.items()
    }, [], "legacy"


def validate_settings(settings):
    issues = []
    if not isinstance(settings, dict):
        return [_issue("SERVICE_CONFIGURATION_SETTINGS_INVALID", "configuration.settings", "Configuration settings must be an object")]
    seen_role_variables = set()
    for logical in sorted(settings):
        entry = settings[logical]
        path = "configuration.settings.%s" % logical
        if not isinstance(logical, str) or not logical:
            issues.append(_issue("SERVICE_CONFIGURATION_LOGICAL_ID_INVALID", path, "Logical setting id must be a non-empty string"))
            continue
        if not isinstance(entry, dict):
            issues.append(_issue("SERVICE_CONFIGURATION_SETTING_INVALID", path, "Setting metadata must be an object"))
            continue
        kind = entry.get("kind")
        expected = entry.get("type")
        role_variable = entry.get("roleVariable")
        scopes = entry.get("scopes")
        validation = entry.get("validation", {})
        if kind not in SETTING_KINDS:
            issues.append(_issue("SERVICE_CONFIGURATION_KIND_INVALID", path + ".kind", "Setting kind must be MANAGED or ADVANCED"))
        if expected not in SETTING_TYPES:
            issues.append(_issue("SERVICE_CONFIGURATION_TYPE_INVALID", path + ".type", "Setting type is unsupported"))
        if not isinstance(role_variable, str) or re.match(r"^[a-z][a-z0-9_]*$", role_variable) is None:
            issues.append(_issue("SERVICE_CONFIGURATION_ROLE_VARIABLE_INVALID", path + ".roleVariable", "Setting roleVariable must be a non-empty string"))
        elif role_variable in seen_role_variables:
            issues.append(_issue("SERVICE_CONFIGURATION_ROLE_VARIABLE_DUPLICATE", path + ".roleVariable", "A roleVariable may map to only one logical setting"))
        else:
            seen_role_variables.add(role_variable)
        if not isinstance(scopes, list) or not scopes or any(scope not in SETTING_SCOPES for scope in scopes) or len(set(scopes)) != len(scopes):
            issues.append(_issue("SERVICE_CONFIGURATION_SCOPES_INVALID", path + ".scopes", "Setting scopes must be a unique non-empty deployment/member list"))
        if not isinstance(validation, dict):
            issues.append(_issue("SERVICE_CONFIGURATION_VALIDATION_INVALID", path + ".validation", "Setting validation must be an object"))
        elif expected in SETTING_TYPES:
            unsupported = sorted(set(validation).difference(VALIDATION_KEYS[expected]))
            if unsupported:
                issues.append(_issue("SERVICE_CONFIGURATION_VALIDATION_TYPE_INVALID", path + ".validation", "Validation keywords do not apply to the declared setting type"))
            if "enum" in validation and (not isinstance(validation["enum"], list) or any(not _literal_matches_type(value, expected) for value in validation["enum"])):
                issues.append(_issue("SERVICE_CONFIGURATION_VALIDATION_TYPE_INVALID", path + ".validation.enum", "Validation enum values must match the declared setting type"))
        if kind == "ADVANCED" and expected != "object":
            issues.append(_issue("SERVICE_CONFIGURATION_ADVANCED_TYPE_INVALID", path + ".type", "ADVANCED settings must be object containers"))
    return issues


def generated_schema(definition):
    settings, issues, form = canonical_settings(definition)
    if issues:
        raise ValueError(issues[0]["message"])
    issues = validate_settings(settings)
    if issues:
        raise ValueError(issues[0]["message"])
    metadata = definition.get("metadata", {}) if isinstance(definition, dict) else {}
    service_id = metadata.get("id", "service")
    display_name = metadata.get("displayName", service_id)
    configuration = definition.get("configuration", {}) if isinstance(definition, dict) else {}
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://platform.installer/schemas/services/%s/configuration-v1alpha1.schema.json" % service_id,
        "title": "%s desired configuration" % display_name,
        "type": "object",
        "additionalProperties": configuration.get("additionalProperties", True) if isinstance(configuration, dict) else True,
        "properties": {},
    }
    if isinstance(configuration, dict) and "unevaluatedProperties" in configuration:
        schema["unevaluatedProperties"] = configuration["unevaluatedProperties"]
    for logical in sorted(settings):
        entry = settings[logical]
        property_schema = copy.deepcopy(entry.get("schema", {})) if isinstance(entry.get("schema"), dict) else {"type": entry["type"]}
        property_schema.setdefault("type", entry["type"])
        property_schema.update(copy.deepcopy(entry.get("validation", {})))
        schema["properties"][logical] = property_schema
    return schema


def validate_defaults(definition, defaults, is_literal):
    settings, issues, _ = canonical_settings(definition)
    issues.extend(validate_settings(settings))
    defaults = defaults if isinstance(defaults, dict) else {}
    if issues:
        return issues
    for logical in sorted(settings):
        entry = settings[logical]
        role_variable = entry.get("roleVariable")
        if role_variable not in defaults:
            continue
        value = defaults[role_variable]
        # An empty TLS reference is a required input awaiting project selection,
        # not a business default. Authored overrides still obey minLength.
        if value == "" and entry.get("type") == "string" and isinstance(entry.get("ui"), dict) and entry["ui"].get("x-referenceKind") == "TLS_PROFILE":
            continue
        if not is_literal(value):
            continue
        expected = entry.get("type")
        path = "roles/defaults.%s" % role_variable
        if not _literal_matches_type(value, expected):
            issues.append(_issue("ROLE_DEFAULT_TYPE_INVALID", path, "Literal role default does not match declared setting type"))
            continue
        validation = entry.get("validation", {})
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in validation and value < validation["minimum"]:
                issues.append(_issue("ROLE_DEFAULT_VALIDATION_INVALID", path, "Literal role default is below the declared minimum"))
            if "maximum" in validation and value > validation["maximum"]:
                issues.append(_issue("ROLE_DEFAULT_VALIDATION_INVALID", path, "Literal role default is above the declared maximum"))
        if isinstance(value, str) and "minLength" in validation and len(value) < validation["minLength"]:
            issues.append(_issue("ROLE_DEFAULT_VALIDATION_INVALID", path, "Literal role default is shorter than the declared minimum length"))
    return issues


def apply_managed_overrides(definition, variables, overrides):
    """Apply logical updates to a variable document without discarding pass-through keys.

    This is intentionally a value-level semantic helper. It does not parse or
    serialize YAML, and therefore never claims byte/comment preservation.
    """
    settings, issues, _ = canonical_settings(definition)
    issues.extend(validate_settings(settings))
    if issues:
        return None, issues
    variables = variables if isinstance(variables, dict) else {}
    overrides = overrides if isinstance(overrides, dict) else {}
    result = copy.deepcopy(variables)
    for logical in sorted(overrides):
        entry = settings.get(logical)
        if not isinstance(entry, dict) or not entry.get("roleVariable"):
            issues.append(_issue("SERVICE_CONFIGURATION_PROPERTY_UNKNOWN", logical, "Only declared managed settings may be updated"))
            continue
        result[entry["roleVariable"]] = copy.deepcopy(overrides[logical])
    return (None, issues) if issues else (result, [])

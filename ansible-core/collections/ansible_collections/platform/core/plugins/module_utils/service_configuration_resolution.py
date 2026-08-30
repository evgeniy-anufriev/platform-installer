from __future__ import absolute_import, division, print_function

__metaclass__ = type

import re

try:
    from .project_validation import canonical_digest
except ImportError:
    from project_validation import canonical_digest


API_VERSION = "platform.installer/resolved-service-configuration/v1alpha1"
JINJA_MARKER = re.compile(r"{{|}}|{%|%}|{#|#}")


def _finding(code, field, message, details=None):
    finding = {
        "apiVersion": "platform.installer/finding/v1alpha1",
        "kind": "Finding",
        "code": code,
        "status": "BLOCKED",
        "category": "service-configuration-resolution",
        "field": field,
        "safeMessage": message,
    }
    if details:
        finding["safeDetails"] = details
    return finding


def _literal(value):
    return not (isinstance(value, str) and JINJA_MARKER.search(value))


def _canonical_mapping(mapping):
    return {
        key: mapping[key]
        for key in sorted(mapping)
        if isinstance(key, str)
    }


def _canonical_defaults(role_defaults, mapping):
    return {
        logical: role_defaults.get(entry.get("roleVariable"))
        for logical, entry in sorted(mapping.items())
        if isinstance(entry, dict) and entry.get("roleVariable") in role_defaults
    }


def _service_definition_digest(definition):
    if not isinstance(definition, dict):
        return None
    return definition.get("x-definitionDigest")


def _matches_type(value, expected):
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def _validate_override(logical, value, schema, field):
    """Validate the simple configuration-schema vocabulary used by CORE-03.

    The published offline Draft 2020-12 engine remains the authoritative
    schema validator. This small preflight only creates resolver findings for
    the direct property/type/range contract and never evaluates expressions.
    """
    findings = []
    if not isinstance(schema, dict):
        return findings
    properties = schema.get("properties", {})
    if schema.get("additionalProperties") is False and logical not in properties:
        findings.append(_finding(
            "SERVICE_CONFIGURATION_PROPERTY_UNKNOWN",
            "%s.%s" % (field, logical),
            "Configuration property is not declared by the service schema",
        ))
        return findings
    definition = properties.get(logical, {}) if isinstance(properties, dict) else {}
    expected = definition.get("type") if isinstance(definition, dict) else None
    expected_types = expected if isinstance(expected, list) else [expected]
    if expected and not any(_matches_type(value, item) for item in expected_types):
        findings.append(_finding(
            "SERVICE_CONFIGURATION_TYPE_INVALID",
            "%s.%s" % (field, logical),
            "Configuration property does not match the service schema type",
            {"expected": expected_types},
        ))
        return findings
    if isinstance(definition, dict) and "enum" in definition and value not in definition["enum"]:
        findings.append(_finding(
            "SERVICE_CONFIGURATION_ENUM_INVALID",
            "%s.%s" % (field, logical),
            "Configuration property is not one of the values allowed by the service schema",
        ))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        for keyword, code, message in (
            ("minimum", "SERVICE_CONFIGURATION_MINIMUM_INVALID", "Configuration property is below the service schema minimum"),
            ("maximum", "SERVICE_CONFIGURATION_MAXIMUM_INVALID", "Configuration property is above the service schema maximum"),
        ):
            limit = definition.get(keyword) if isinstance(definition, dict) else None
            if limit is not None and ((keyword == "minimum" and value < limit) or (keyword == "maximum" and value > limit)):
                findings.append(_finding(code, "%s.%s" % (field, logical), message))
    if isinstance(value, str) and isinstance(definition, dict) and len(value) < definition.get("minLength", 0):
        findings.append(_finding(
            "SERVICE_CONFIGURATION_MIN_LENGTH_INVALID",
            "%s.%s" % (field, logical),
            "Configuration string is shorter than the service schema minimum",
        ))
    return findings


def resolve_service_configuration(
    resolved_topology, topology, service_catalog, role_defaults, configuration_schemas=None
):
    """Resolve literal deployment configuration without evaluating Ansible/Jinja.

    role_defaults is keyed by service type and contains the loaded role
    defaults as ordinary data. The mapping is service-package metadata. This
    function never emits role variables and deliberately ignores placements.
    """
    resolved_topology = resolved_topology if isinstance(resolved_topology, dict) else {}
    topology = topology if isinstance(topology, dict) else {}
    service_catalog = service_catalog if isinstance(service_catalog, dict) else {}
    role_defaults = role_defaults if isinstance(role_defaults, dict) else {}
    configuration_schemas = configuration_schemas if isinstance(configuration_schemas, dict) else {}
    definitions = service_catalog.get("definitions", service_catalog)
    desired_deployments = topology.get("serviceDeployments", {})
    resolved_deployments = resolved_topology.get("resolvedTopology", {}).get("serviceDeployments", {})
    services = {}
    findings = []

    for deployment_id in sorted(resolved_deployments):
        resolved = resolved_deployments[deployment_id]
        desired = desired_deployments.get(deployment_id, {})
        service_type = resolved.get("serviceType")
        definition = definitions.get(service_type, {}) if isinstance(definitions, dict) else {}
        mapping = definition.get("configurationMapping", {})
        defaults = role_defaults.get(service_type, {})
        field_prefix = "serviceDeployments.%s.configuration" % deployment_id

        if not isinstance(mapping, dict) or not mapping:
            findings.append(_finding(
                "SERVICE_CONFIGURATION_MAPPING_REQUIRED",
                "catalog.definitions.%s.configurationMapping" % service_type,
                "Service package must declare a logical configuration mapping",
                {"serviceType": service_type},
            ))
            mapping = {}
        if not isinstance(defaults, dict):
            findings.append(_finding(
                "ROLE_DEFAULTS_INVALID",
                "catalog.definitions.%s.roleDefaults" % service_type,
                "Loaded role defaults must be an object",
                {"serviceType": service_type},
            ))
            defaults = {}

        overrides = desired.get("configuration", {}) if isinstance(desired, dict) else {}
        if not isinstance(overrides, dict):
            findings.append(_finding(
                "SERVICE_CONFIGURATION_INVALID",
                field_prefix,
                "Deployment configuration override must be an object",
            ))
            overrides = {}
        members = desired.get("members", {}) if isinstance(desired, dict) else {}
        for member_id in (sorted(members) if isinstance(members, dict) else []):
            member = members[member_id]
            if isinstance(member, dict) and member.get("configuration"):
                findings.append(_finding(
                    "MEMBER_CONFIGURATION_UNSUPPORTED",
                    "serviceDeployments.%s.members.%s.configuration" % (deployment_id, member_id),
                    "Member-specific configuration is not supported by CORE-03",
                    {"deploymentId": deployment_id, "memberId": member_id},
                ))

        for logical in sorted(set(mapping) | set(overrides)):
            entry = mapping.get(logical)
            if not isinstance(entry, dict) or not entry.get("roleVariable"):
                findings.append(_finding(
                    "SERVICE_CONFIGURATION_MAPPING_INVALID",
                    "catalog.definitions.%s.configurationMapping.%s" % (service_type, logical),
                    "Logical configuration property must map to one role variable",
                ))
                continue
            role_variable = entry["roleVariable"]
            if logical in overrides:
                value = overrides[logical]
                if _literal(value):
                    findings.extend(_validate_override(
                        logical,
                        value,
                        configuration_schemas.get(service_type),
                        field_prefix,
                    ))
                    services.setdefault(deployment_id, {}).setdefault("configuration", {})[logical] = {
                        "state": "RESOLVED", "value": value, "source": "OVERRIDE"
                    }
                else:
                    findings.append(_finding(
                        "SERVICE_CONFIGURATION_OVERRIDE_NON_LITERAL",
                        "%s.%s" % (field_prefix, logical),
                        "Deployment configuration overrides must be literal values",
                    ))
                continue
            if role_variable not in defaults:
                findings.append(_finding(
                    "ROLE_DEFAULT_NOT_DECLARED",
                    "%s.%s" % (field_prefix, logical),
                    "Mapped logical configuration has no corresponding role default",
                    {"roleVariable": role_variable},
                ))
                continue
            value = defaults[role_variable]
            if _literal(value):
                services.setdefault(deployment_id, {}).setdefault("configuration", {})[logical] = {
                    "state": "RESOLVED", "value": value, "source": "DEFAULT"
                }
            else:
                services.setdefault(deployment_id, {}).setdefault("configuration", {})[logical] = {
                    "state": "DEFERRED", "reason": "NON_LITERAL_ROLE_DEFAULT", "source": "DEFAULT"
                }

        service = services.setdefault(deployment_id, {})
        service.update({
            "serviceType": service_type,
            "definitionVersion": resolved.get("definitionVersion"),
            "mode": resolved.get("mode"),
        })
        schema = configuration_schemas.get(service_type)
        schema_ref = definition.get("configurationSchema", {}).get("$ref") if isinstance(definition.get("configurationSchema"), dict) else None
        service["inputs"] = {
            "topologyFingerprint": resolved_topology.get("topologyFingerprint"),
            "serviceDefinitionDigest": _service_definition_digest(definition),
            "configurationSchemaDigest": canonical_digest(schema if schema is not None else {"ref": schema_ref}),
            "roleDefaultsDigest": canonical_digest(_canonical_defaults(defaults, mapping)),
            "mappingDigest": canonical_digest(_canonical_mapping(mapping)),
        }

    for service in services.values():
        service["configuration"] = {
            key: service.get("configuration", {})[key]
            for key in sorted(service.get("configuration", {}))
        }
        service["inputs"] = {
            key: value for key, value in service["inputs"].items() if value is not None
        }
    findings.sort(key=lambda item: (item["field"], item["code"]))
    fingerprint_input = {
        "services": {
            deployment_id: {
                "serviceType": service["serviceType"],
                "definitionVersion": service["definitionVersion"],
                "mode": service["mode"],
                "configuration": service["configuration"],
                "inputs": {
                    key: value for key, value in service["inputs"].items()
                    if key != "topologyFingerprint"
                },
            }
            for deployment_id, service in sorted(services.items())
        }
    }
    return {
        "apiVersion": API_VERSION,
        "kind": "ResolvedServiceConfiguration",
        "services": services,
        "configurationFingerprint": canonical_digest(fingerprint_input),
        "findings": findings,
        "status": "BLOCKED" if findings else "PASS",
    }

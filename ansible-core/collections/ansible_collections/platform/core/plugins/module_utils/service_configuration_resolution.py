from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import posixpath
import re

try:
    from .project_validation import canonical_digest
    from .service_configuration_contract import canonical_settings, validate_settings
    from .kafka_schema_registry import configuration_registry_findings
except ImportError:
    from project_validation import canonical_digest
    from service_configuration_contract import canonical_settings, validate_settings
    from kafka_schema_registry import configuration_registry_findings


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


def _merge_mapping_defaults(default_value, override_value):
    """Match Ansible's configured hash merge for one resolved object setting."""
    if not isinstance(default_value, dict) or not isinstance(override_value, dict):
        return override_value
    result = {key: copy.deepcopy(value) for key, value in default_value.items()}
    for key, value in override_value.items():
        result[key] = _merge_mapping_defaults(result[key], value) if key in result else copy.deepcopy(value)
    return result


_EXACT_REFERENCE = re.compile(r"^{{\s*([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)\s*}}$")


def _exact_reference(value):
    if not isinstance(value, str):
        return None
    match = _EXACT_REFERENCE.match(value)
    return match.group(1) if match else None


def _mapping_scopes(entry):
    if not isinstance(entry, dict):
        return []
    scopes = entry.get("scopes", ["deployment"])
    return scopes if isinstance(scopes, list) else []


def _value(state, source, **extra):
    result = {"state": state, "source": source}
    result.update(extra)
    return result


_SECRET_TERMS = ("password", "passphrase", "privatekey", "token", "secret")


def _opaque_variable(name, value, source, path, **identity):
    entry = {
        "state": "OPAQUE",
        "name": name,
        "origin": dict({"source": source, "path": path}, **identity),
    }
    normalized = name.lower().replace("_", "").replace("-", "") if isinstance(name, str) else ""
    if any(term in normalized for term in _SECRET_TERMS):
        entry["redacted"] = True
    elif _literal(value):
        entry["value"] = value
    else:
        entry["expression"] = value
    return entry


def _logical_path(path):
    if not isinstance(path, str) or not path:
        return None
    normalized = posixpath.normpath(path.replace("\\", "/"))
    if normalized in (".", "") or normalized.startswith("/") or normalized.startswith("../") or re.match(r"^[A-Za-z]:", normalized):
        return None
    return normalized


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
    if isinstance(value, str) and JINJA_MARKER.search(value):
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
    resolved_topology, topology, service_catalog, role_defaults, configuration_schemas=None,
    host_contexts=None, variable_documents=None,
):
    """Resolve static deployment/member configuration without being Ansible.

    This deliberately implements only exact variable references. It does not
    evaluate filters, facts, lookups, expressions or host vars. The resulting
    member projections are keyed by deployment/member identity, not by host.
    """
    resolved_topology = resolved_topology if isinstance(resolved_topology, dict) else {}
    topology = topology if isinstance(topology, dict) else {}
    service_catalog = service_catalog if isinstance(service_catalog, dict) else {}
    role_defaults = role_defaults if isinstance(role_defaults, dict) else {}
    configuration_schemas = configuration_schemas if isinstance(configuration_schemas, dict) else {}
    host_contexts = host_contexts if isinstance(host_contexts, dict) else {}
    variable_documents = variable_documents if isinstance(variable_documents, list) else []
    definitions = service_catalog.get("definitions", service_catalog)
    desired_deployments = topology.get("serviceDeployments", {})
    resolved_deployments = resolved_topology.get("resolvedTopology", {}).get("serviceDeployments", {})
    services = {}
    findings = []
    opaque_host_variables = []
    for host_id in sorted(host_contexts):
        values = host_contexts[host_id]
        if not isinstance(values, dict):
            continue
        for name, value in sorted(values.items()):
            opaque_host_variables.append(_opaque_variable(
                name,
                value,
                "HOST_CONTEXT",
                "inventory/host_vars/%s.yml" % host_id,
            ))
    for document in variable_documents:
        if not isinstance(document, dict) or document.get("kind") != "HOST_VARS":
            continue
        variables = document.get("variables")
        path = _logical_path(document.get("logicalPath"))
        host_id = document.get("hostId")
        if not isinstance(variables, dict) or not isinstance(path, str) or not path or not isinstance(host_id, str) or not host_id:
            findings.append(_finding(
                "VARIABLE_DOCUMENT_ORIGIN_INVALID",
                "variableDocuments",
                "HOST_VARS documents require variables, logicalPath and hostId",
            ))
            continue
        for name, value in sorted(variables.items()):
            opaque_host_variables.append(_opaque_variable(
                name, value, "HOST_VARS", path, hostId=host_id,
            ))
    for document in variable_documents:
        if not isinstance(document, dict) or document.get("kind") != "GROUP_VARS":
            continue
        if document.get("deploymentId") and document.get("serviceType"):
            continue
        variables = document.get("variables")
        path = _logical_path(document.get("logicalPath"))
        group_id = document.get("groupId")
        if not isinstance(variables, dict) or not isinstance(path, str) or not path or not isinstance(group_id, str) or not group_id:
            findings.append(_finding(
                "VARIABLE_DOCUMENT_ORIGIN_INVALID",
                "variableDocuments",
                "Unbound GROUP_VARS documents require variables, logicalPath and groupId",
            ))
            continue
        for name, value in sorted(variables.items()):
            opaque_host_variables.append(_opaque_variable(
                name, value, "GROUP_VARS", path, groupId=group_id,
            ))

    for deployment_id in sorted(resolved_deployments):
        resolved = resolved_deployments[deployment_id]
        desired = desired_deployments.get(deployment_id, {})
        service_type = resolved.get("serviceType")
        definition = definitions.get(service_type, {}) if isinstance(definitions, dict) else {}
        metadata = definition.get("metadata", {}) if isinstance(definition, dict) else {}
        service_definition_version = resolved.get("definitionVersion") or (
            metadata.get("version") if isinstance(metadata, dict) else None
        )
        mapping, contract_issues, contract_form = canonical_settings(definition)
        contract_issues.extend(validate_settings(mapping) if contract_form == "canonical" else [])
        defaults = role_defaults.get(service_type, {})
        field_prefix = "serviceDeployments.%s.configuration" % deployment_id

        for issue in contract_issues:
            findings.append(_finding(
                issue["code"],
                "catalog.definitions.%s.%s" % (service_type, issue["path"]),
                issue["message"],
            ))
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
        members = members if isinstance(members, dict) else {}

        document_overrides = {}
        document_origins = {}
        document_opaque_variables = []
        role_to_logical = {
            entry.get("roleVariable"): logical
            for logical, entry in mapping.items()
            if isinstance(entry, dict) and entry.get("roleVariable")
        }
        for document in variable_documents:
            if not isinstance(document, dict):
                continue
            if document.get("deploymentId") != deployment_id or document.get("serviceType") != service_type:
                continue
            if document.get("kind") != "GROUP_VARS":
                continue
            if not isinstance(document.get("variables"), dict):
                findings.append(_finding(
                    "VARIABLE_DOCUMENT_BINDING_INVALID",
                    "variableDocuments",
                    "Managed Ansible variable documents require GROUP_VARS and an object variables payload",
                    {"deploymentId": deployment_id, "serviceType": service_type},
                ))
                continue
            path = _logical_path(document.get("logicalPath"))
            group_id = document.get("groupId")
            if not isinstance(path, str) or not path or not isinstance(group_id, str) or not group_id:
                findings.append(_finding(
                    "VARIABLE_DOCUMENT_ORIGIN_INVALID",
                    "variableDocuments",
                    "Managed Ansible variable documents require logicalPath and groupId",
                ))
                continue
            for name, value in sorted(document["variables"].items()):
                logical = role_to_logical.get(name)
                if logical is None:
                    document_opaque_variables.append(_opaque_variable(
                        name, value, "GROUP_VARS", path, groupId=group_id,
                    ))
                    continue
                if logical in document_overrides or logical in overrides:
                    findings.append(_finding(
                        "MANAGED_VARIABLE_SOURCE_CONFLICT",
                        "%s.%s" % (field_prefix, logical),
                        "A managed setting may have one explicit deployment override source",
                        {"setting": logical},
                    ))
                    continue
                document_overrides[logical] = value
                document_origins[logical] = {
                    "kind": "GROUP_VARS", "logicalPath": path, "groupId": group_id,
                }

        for logical in sorted(mapping):
            entry = mapping.get(logical)
            if not isinstance(entry, dict) or not entry.get("roleVariable"):
                findings.append(_finding(
                    "SERVICE_CONFIGURATION_MAPPING_INVALID",
                    "catalog.definitions.%s.configurationMapping.%s" % (service_type, logical),
                    "Logical configuration property must map to one role variable",
                ))
        schema = configuration_schemas.get(service_type)
        configuration_is_closed = isinstance(schema, dict) and schema.get("additionalProperties") is False
        if configuration_is_closed:
            for logical in sorted(set(overrides).difference(mapping)):
                findings.append(_finding(
                    "SERVICE_CONFIGURATION_PROPERTY_UNKNOWN",
                    "%s.%s" % (field_prefix, logical),
                    "Configuration property is not declared by the service schema",
                ))
        mapped_role_variables = {
            entry.get("roleVariable")
            for entry in mapping.values()
            if isinstance(entry, dict) and entry.get("roleVariable")
        }
        opaque_variables = [
            _opaque_variable(
                role_variable,
                defaults[role_variable],
                "ROLE_DEFAULT",
                "roles/%s/defaults/main.yml" % service_type,
            )
            for role_variable in sorted(defaults)
            if role_variable not in mapped_role_variables
        ]
        opaque_variables.extend(
            _opaque_variable(
                logical,
                value,
                "DEPLOYMENT_CONFIGURATION",
                "%s.%s" % (field_prefix, logical),
            )
            for logical, value in sorted(overrides.items())
            if logical not in mapping and not configuration_is_closed
        )
        opaque_variables.extend(document_opaque_variables)

        def resolve_scope(scope_member=None):
            scope_name = "member" if scope_member is not None else "deployment"
            scope_field_prefix = field_prefix if scope_member is None else "serviceDeployments.%s.members.%s.configuration" % (deployment_id, scope_member.get("id", ""))
            member_overrides = scope_member.get("configuration", {}) if isinstance(scope_member, dict) else {}
            member_overrides = member_overrides if isinstance(member_overrides, dict) else {}
            values = {}
            visiting = []

            def source_for(logical):
                entry = mapping.get(logical)
                if not isinstance(entry, dict) or not entry.get("roleVariable"):
                    return None
                role_variable = entry["roleVariable"]
                default_value = defaults.get(role_variable)
                if scope_name == "member" and logical in member_overrides and "member" in _mapping_scopes(entry):
                    return "MEMBER_OVERRIDE", _merge_mapping_defaults(default_value, member_overrides[logical]), None
                if logical in overrides:
                    return "DEPLOYMENT_OVERRIDE", _merge_mapping_defaults(default_value, overrides[logical]), None
                if logical in document_overrides:
                    return "DEPLOYMENT_OVERRIDE", _merge_mapping_defaults(default_value, document_overrides[logical]), document_origins[logical]
                if role_variable in defaults:
                    return "ROLE_DEFAULT", defaults[role_variable], None
                return None

            def resolve_variable(name):
                if name in mapping:
                    return resolve_setting(name)
                for logical, entry in mapping.items():
                    if isinstance(entry, dict) and entry.get("roleVariable") == name:
                        return resolve_setting(logical)
                if name in defaults:
                    return resolve_raw(name, defaults[name])
                if "." in name:
                    namespace, key = name.split(".", 1)
                    candidate = defaults.get(namespace)
                    if isinstance(candidate, dict) and key in candidate:
                        return resolve_raw(name, candidate[key])
                return {"state": "UNRESOLVED", "reason": "STATIC_REFERENCE_NOT_FOUND", "source": "STATIC_REFERENCE", "reference": name}

            def resolve_raw(name, raw):
                if name in visiting:
                    return {"state": "CYCLIC", "reason": "STATIC_REFERENCE_CYCLE", "source": "STATIC_REFERENCE", "reference": name}
                reference = _exact_reference(raw)
                if reference:
                    visiting.append(name)
                    resolved = resolve_variable(reference)
                    visiting.pop()
                    if resolved.get("state") == "RESOLVED":
                        return _value("RESOLVED", "STATIC_REFERENCE", value=resolved["value"], reference=reference)
                    return dict(resolved, source="STATIC_REFERENCE", reference=reference)
                if _literal(raw):
                    return {"state": "RESOLVED", "value": raw}
                return {"state": "DEFERRED", "reason": "NON_LITERAL_CONFIGURATION", "source": "RUNTIME_DEFERRED", "expression": raw}

            def resolve_setting(logical):
                if logical in values:
                    return values[logical]
                if logical in visiting:
                    return {"state": "CYCLIC", "reason": "STATIC_REFERENCE_CYCLE", "source": "STATIC_REFERENCE", "reference": logical}
                entry = mapping.get(logical)
                if not isinstance(entry, dict) or not entry.get("roleVariable"):
                    return None
                source = source_for(logical)
                if source is None:
                    if contract_form == "canonical":
                        return None
                    findings.append(_finding(
                        "ROLE_DEFAULT_NOT_DECLARED",
                        "%s.%s" % (scope_field_prefix, logical),
                        "Mapped logical configuration has no corresponding role default",
                        {"roleVariable": entry["roleVariable"]},
                    ))
                    return None
                source_name, raw, physical_origin = source
                reference = _exact_reference(raw)
                if reference:
                    visiting.append(logical)
                    resolved = resolve_variable(reference)
                    visiting.pop()
                    if resolved.get("state") == "RESOLVED":
                        result = _value("RESOLVED", "STATIC_REFERENCE", value=resolved["value"], reference=reference, origin=source_name)
                        if physical_origin:
                            result["physicalOrigin"] = physical_origin
                    else:
                        result = dict(resolved, source="STATIC_REFERENCE", reference=reference)
                elif _literal(raw):
                    result = _value("RESOLVED", source_name, value=raw)
                    if physical_origin:
                        result["physicalOrigin"] = physical_origin
                else:
                    result = {
                        "state": "DEFERRED",
                        "reason": "NON_LITERAL_ROLE_DEFAULT" if source_name == "ROLE_DEFAULT" else "NON_LITERAL_CONFIGURATION",
                        "source": "RUNTIME_DEFERRED",
                        "expression": raw,
                    }
                    if physical_origin:
                        result["physicalOrigin"] = physical_origin
                values[logical] = result
                if result.get("state") in ("UNRESOLVED", "CYCLIC"):
                    findings.append(_finding(
                        "STATIC_REFERENCE_NOT_FOUND" if result["state"] == "UNRESOLVED" else "STATIC_REFERENCE_CYCLE",
                        "%s.%s" % (scope_field_prefix, logical),
                        "Static configuration reference could not be resolved" if result["state"] == "UNRESOLVED" else "Static configuration reference is cyclic",
                        {"reference": result.get("reference")},
                    ))
                return result

            for logical in sorted(mapping):
                result = resolve_setting(logical)
                if result is not None:
                    values[logical] = result
            return values

        deployment_configuration = resolve_scope()
        for logical, value in sorted(overrides.items()):
            if logical in mapping:
                findings.extend(_validate_override(logical, value, schema, field_prefix))
        for logical, value in sorted(document_overrides.items()):
            findings.extend(_validate_override(logical, value, schema, field_prefix))
        service = services.setdefault(deployment_id, {})
        service["configuration"] = deployment_configuration
        service["opaqueVariables"] = opaque_variables

        scoped_members = {}
        for member_id in sorted(members):
            member = members[member_id]
            member_configuration = member.get("configuration", {}) if isinstance(member, dict) else {}
            member_opaque_variables = []
            if not isinstance(member_configuration, dict):
                findings.append(_finding(
                    "INVALID_MEMBER_CONFIGURATION",
                    "serviceDeployments.%s.members.%s.configuration" % (deployment_id, member_id),
                    "Member configuration must be an object",
                ))
                member_configuration = {}
            for logical, value in sorted(member_configuration.items()):
                entry = mapping.get(logical)
                if not isinstance(entry, dict) or not entry.get("roleVariable"):
                    if configuration_is_closed:
                        findings.append(_finding(
                            "SERVICE_CONFIGURATION_PROPERTY_UNKNOWN",
                            "serviceDeployments.%s.members.%s.configuration.%s" % (deployment_id, member_id, logical),
                            "Configuration property is not declared by the service schema",
                        ))
                    else:
                        member_opaque_variables.append(_opaque_variable(
                            logical,
                            value,
                            "MEMBER_CONFIGURATION",
                            "serviceDeployments.%s.members.%s.configuration.%s" % (deployment_id, member_id, logical),
                        ))
                elif "member" not in _mapping_scopes(entry):
                    findings.append(_finding(
                        "MEMBER_SCOPE_SETTING_NOT_ALLOWED",
                        "serviceDeployments.%s.members.%s.configuration.%s" % (deployment_id, member_id, logical),
                        "Configuration setting does not allow member scope",
                        {"setting": logical, "allowedScopes": _mapping_scopes(entry)},
                    ))
                if logical in mapping:
                    findings.extend(_validate_override(
                        logical, value, schema,
                        "serviceDeployments.%s.members.%s.configuration" % (deployment_id, member_id),
                    ))
            member_values = resolve_scope(dict(member, id=member_id) if isinstance(member, dict) else {"id": member_id})
            resolved_member = resolved.get("members", {}).get(member_id, {}) if isinstance(resolved, dict) else {}
            host_id = resolved_member.get("host") if isinstance(resolved_member, dict) else None
            context = {"deploymentId": deployment_id, "memberId": member_id, "hostId": host_id}
            member_fingerprint = canonical_digest({"serviceType": service_type, "definitionVersion": service_definition_version, "mode": resolved.get("mode"), "configuration": member_values, "inputs": {"serviceDefinitionDigest": _service_definition_digest(definition), "configurationSchemaDigest": canonical_digest(schema if schema is not None else {}), "roleDefaultsDigest": canonical_digest(_canonical_defaults(defaults, mapping)), "mappingDigest": canonical_digest(_canonical_mapping(mapping))}})
            scoped_members[member_id] = {"variableContext": context, "configuration": member_values, "opaqueVariables": member_opaque_variables, "configurationFingerprint": member_fingerprint, "opaqueVariablesFingerprint": canonical_digest(sorted(member_opaque_variables, key=lambda item: (item["name"], item["origin"]["source"], item["origin"]["path"]))) }
        service["members"] = scoped_members

        service.update({
            "serviceType": service_type,
            "definitionVersion": service_definition_version,
            "mode": resolved.get("mode"),
        })
        schema_ref = definition.get("configurationSchema", {}).get("$ref") if isinstance(definition.get("configurationSchema"), dict) else None
        service["inputs"] = {
            "topologyFingerprint": resolved_topology.get("topologyFingerprint"),
            "serviceDefinitionDigest": _service_definition_digest(definition),
            "configurationSchemaDigest": canonical_digest(schema if schema is not None else {"ref": schema_ref}),
            "roleDefaultsDigest": canonical_digest(_canonical_defaults(defaults, mapping)),
            "mappingDigest": canonical_digest(_canonical_mapping(mapping)),
        }
        service["configurationFingerprint"] = canonical_digest({
            "serviceType": service_type,
            "definitionVersion": service["definitionVersion"],
            "mode": service["mode"],
            "configuration": service["configuration"],
            "members": {member_id: {"configuration": value["configuration"]} for member_id, value in sorted(scoped_members.items())},
            "inputs": {key: value for key, value in service["inputs"].items() if key != "topologyFingerprint"},
        })
        service["opaqueVariablesFingerprint"] = canonical_digest(sorted(service["opaqueVariables"], key=lambda item: (item["name"], item["origin"]["source"], item["origin"]["path"])))

    for service in services.values():
        service["configuration"] = {
            key: service.get("configuration", {})[key]
            for key in sorted(service.get("configuration", {}))
        }
        service["inputs"] = {
            key: value for key, value in service["inputs"].items() if value is not None
        }
    findings.extend(
        _finding(item["code"], item["field"], item["message"])
        for item in configuration_registry_findings(services, resolved_topology)
    )
    findings.sort(key=lambda item: (item["field"], item["code"]))
    fingerprint_input = {
        "services": {
            deployment_id: {
                "serviceType": service["serviceType"],
                "definitionVersion": service["definitionVersion"],
                "mode": service["mode"],
                "configuration": service["configuration"],
                "members": {
                    member_id: {
                        "configuration": value["configuration"],
                    }
                    for member_id, value in sorted(service.get("members", {}).items())
                },
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
        "opaqueVariables": opaque_host_variables,
        "opaqueVariablesFingerprint": canonical_digest({
            "hosts": sorted(opaque_host_variables, key=lambda item: (item["name"], item["origin"]["source"], item["origin"]["path"])),
            "services": {
                deployment_id: {
                    "opaqueVariables": sorted(service.get("opaqueVariables", []), key=lambda item: (item["name"], item["origin"]["source"], item["origin"]["path"])),
                    "members": {
                        member_id: sorted(value.get("opaqueVariables", []), key=lambda item: (item["name"], item["origin"]["source"], item["origin"]["path"]))
                        for member_id, value in sorted(service.get("members", {}).items())
                    },
                }
                for deployment_id, service in sorted(services.items())
            },
        }),
        "configurationFingerprint": canonical_digest(fingerprint_input),
        "findings": findings,
        "status": "BLOCKED" if findings else "PASS",
    }

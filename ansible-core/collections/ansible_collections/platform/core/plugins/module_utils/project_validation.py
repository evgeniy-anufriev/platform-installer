from __future__ import absolute_import, division, print_function

__metaclass__ = type

import hashlib
import json
import os
import re
import tempfile


RESULT_API_VERSION = "platform.installer/validation-result/v1alpha1"
SUPPORTED_PROJECT_API_VERSION = "platform.installer/v2alpha1"
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
SECRET_KEY_TERMS = ("password", "passphrase", "privatekey", "token", "secret")
IDENTIFIER_MAP_FIELDS = {
    "serviceDeployments",
    "members",
    "dependencies",
    "endpointGroups",
    "endpointBindings",
    "certificateProfiles",
    "certificateScopes",
    "secretRequirements",
}


def canonical_digest(value):
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _canonical_fingerprint(value):
    return canonical_digest(value)


def _finding(code, field, message, details=None):
    finding = {
        "apiVersion": "platform.installer/finding/v1alpha1",
        "kind": "Finding",
        "code": code,
        "status": "BLOCKED",
        "category": "project-validation",
        "field": field,
        "safeMessage": message,
    }
    if details:
        finding["safeDetails"] = details
    return finding


def _catalog_definitions(service_catalog):
    definitions = service_catalog.get("definitions", service_catalog)
    return definitions if isinstance(definitions, dict) else {}


def _supported_modes(definition):
    modes = definition.get("modes", {}) if isinstance(definition, dict) else {}
    if isinstance(modes, dict):
        return set(modes.keys())
    if isinstance(modes, list):
        return {
            mode.get("id") if isinstance(mode, dict) else mode
            for mode in modes
            if (isinstance(mode, str) and mode) or (isinstance(mode, dict) and mode.get("id"))
        }
    return set()


def _definition_version(definition):
    if not isinstance(definition, dict):
        return None
    metadata = definition.get("metadata", {})
    return definition.get("definitionVersion") or (
        metadata.get("version") if isinstance(metadata, dict) else None
    )


def _is_digest(value):
    return isinstance(value, str) and DIGEST_PATTERN.match(value) is not None


def _normalized_key(value):
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _is_secret_value_key(key):
    normalized = _normalized_key(key)
    if normalized.endswith("ref"):
        return False
    if normalized == "secretrequirements":
        return False
    return any(term in normalized for term in SECRET_KEY_TERMS)


def _secret_value_fields(value, path="", identifier_map=False):
    fields = []
    if isinstance(value, dict):
        for key in sorted(value, key=lambda item: str(item)):
            child_path = "%s.%s" % (path, key) if path else str(key)
            if isinstance(key, str) and not identifier_map and _is_secret_value_key(key):
                fields.append(child_path)
            child_identifier_map = isinstance(key, str) and key in IDENTIFIER_MAP_FIELDS
            fields.extend(
                _secret_value_fields(value[key], child_path, child_identifier_map)
            )
    elif isinstance(value, list):
        for index, item in enumerate(value):
            child_path = "%s[%d]" % (path, index)
            fields.extend(_secret_value_fields(item, child_path, False))
    return fields


def validate_project(manifest, topology, desired_hosts, service_catalog, inventory_hosts):
    manifest = manifest if isinstance(manifest, dict) else {}
    topology = topology if isinstance(topology, dict) else {}
    service_catalog = service_catalog if isinstance(service_catalog, dict) else {}
    inventory_host_set = set(inventory_hosts or [])
    findings = []

    if manifest.get("apiVersion") != SUPPORTED_PROJECT_API_VERSION:
        findings.append(
            _finding(
                "PROJECT_API_VERSION_UNSUPPORTED",
                "apiVersion",
                "Project apiVersion is missing or unsupported",
                {"supported": [SUPPORTED_PROJECT_API_VERSION]},
            )
        )
    if manifest.get("kind") != "PlatformProject":
        findings.append(
            _finding(
                "PROJECT_KIND_INVALID",
                "kind",
                "Project kind must be PlatformProject",
            )
        )
    metadata = manifest.get("metadata", {})
    if not isinstance(metadata, dict) or not isinstance(metadata.get("id"), str) or not metadata.get("id", "").strip():
        findings.append(
            _finding("PROJECT_ID_REQUIRED", "metadata.id", "Project metadata.id must be a non-empty string")
        )
    if manifest.get("desiredStateContract") != "platform.installer/project-desired-state/v2alpha1":
        findings.append(
            _finding(
                "PROJECT_DESIRED_STATE_CONTRACT_UNSUPPORTED",
                "desiredStateContract",
                "Project desiredStateContract is missing or unsupported",
            )
        )
    catalog_lock = manifest.get("catalogLock", {})
    if not isinstance(catalog_lock, dict):
        findings.append(
            _finding("PROJECT_CATALOG_INVALID", "catalogLock", "Project catalog lock must be an object")
        )
        catalog_lock = {}
    if catalog_lock.get("apiVersion") != "platform.installer/catalog/v1alpha1":
        findings.append(
            _finding(
                "PROJECT_CATALOG_API_VERSION_UNSUPPORTED",
                "catalogLock.apiVersion",
                "Project catalog lock apiVersion is missing or unsupported",
            )
        )
    if not _is_digest(catalog_lock.get("digest")):
        findings.append(
            _finding(
                "PROJECT_CATALOG_DIGEST_INVALID",
                "catalogLock.digest",
                "Project catalog lock must declare a valid SHA256 digest",
            )
        )
    catalog_services = catalog_lock.get("services", {})
    if not isinstance(catalog_services, dict):
        findings.append(
            _finding(
                "PROJECT_CATALOG_SERVICES_INVALID",
                "catalogLock.services",
                "Project catalog services lock must be an object",
            )
        )
        catalog_services = {}
    artifact_lock = manifest.get("artifactLock", {})
    if not isinstance(artifact_lock, dict) or artifact_lock.get("apiVersion") != "platform.installer/artifacts/v1alpha1":
        findings.append(
            _finding(
                "PROJECT_ARTIFACT_LOCK_INVALID",
                "artifactLock",
                "Project artifact lock is missing or has an unsupported apiVersion",
            )
        )
    elif not _is_digest(artifact_lock.get("digest")):
        findings.append(
            _finding(
                "PROJECT_ARTIFACT_DIGEST_INVALID",
                "artifactLock.digest",
                "Project artifact lock must declare a valid SHA256 digest",
            )
        )

    desired_hosts = desired_hosts if isinstance(desired_hosts, dict) else {}

    for field in sorted(
        set(
            _secret_value_fields(topology)
            + _secret_value_fields(desired_hosts, "hosts", True)
        )
    ):
        findings.append(
            _finding(
                "PLAINTEXT_SECRET_FIELD_FORBIDDEN",
                field,
                "Portable desired state must use a runtime secret reference instead of a secret value field",
            )
        )

    if service_catalog.get("apiVersion") != "platform.installer/catalog/v1alpha1" or service_catalog.get("kind") != "ServiceCatalog":
        findings.append(
            _finding(
                "SERVICE_CATALOG_INVALID",
                "catalog",
                "Published service catalog identity is missing or unsupported",
            )
        )
    unsigned_catalog = {
        key: value for key, value in service_catalog.items() if key != "digest"
    }
    computed_catalog_digest = canonical_digest(unsigned_catalog)
    if service_catalog.get("digest") != computed_catalog_digest:
        findings.append(
            _finding(
                "SERVICE_CATALOG_DIGEST_MISMATCH",
                "catalog.digest",
                "Published service catalog digest does not match its canonical content",
                {
                    "computedDigest": computed_catalog_digest,
                    "declaredDigest": service_catalog.get("digest"),
                },
            )
        )
    if catalog_lock.get("digest") != computed_catalog_digest:
        findings.append(
            _finding(
                "PROJECT_CATALOG_DIGEST_MISMATCH",
                "catalogLock.digest",
                "Project catalog lock does not match the canonical published catalog",
                {
                    "catalogDigest": computed_catalog_digest,
                    "lockedDigest": catalog_lock.get("digest"),
                },
            )
        )

    deployments = topology.get("serviceDeployments", {})
    if not isinstance(deployments, dict):
        findings.append(
            _finding(
                "SERVICE_DEPLOYMENTS_INVALID",
                "serviceDeployments",
                "serviceDeployments must be an object keyed by deployment id",
            )
        )
        deployments = {}

    definitions = _catalog_definitions(service_catalog)
    for deployment_id in sorted(deployments):
        deployment = deployments[deployment_id]
        prefix = "serviceDeployments.%s" % deployment_id
        if not isinstance(deployment, dict):
            findings.append(
                _finding("SERVICE_DEPLOYMENT_INVALID", prefix, "Service deployment must be an object")
            )
            continue

        service_type = deployment.get("serviceType")
        definition = definitions.get(service_type)
        if not service_type:
            findings.append(
                _finding(
                    "SERVICE_TYPE_REQUIRED",
                    prefix + ".serviceType",
                    "Service deployment must select a service type",
                )
            )
        elif definition is None:
            findings.append(
                _finding(
                    "SERVICE_DEFINITION_NOT_FOUND",
                    prefix + ".serviceType",
                    "Referenced service definition is not available in the pinned catalog",
                    {"serviceType": service_type},
                )
            )
        else:
            service_lock = catalog_services.get(service_type)
            if not isinstance(service_lock, dict):
                findings.append(
                    _finding(
                        "SERVICE_CATALOG_LOCK_NOT_FOUND",
                        "catalogLock.services.%s" % service_type,
                        "Used service type must be pinned by the project catalog lock",
                        {"serviceType": service_type},
                    )
                )
            else:
                locked_version = service_lock.get("definitionVersion")
                selected_version = deployment.get("definitionVersion")
                catalog_version = _definition_version(definition)
                if not selected_version or selected_version != locked_version or (
                    catalog_version and selected_version != catalog_version
                ):
                    findings.append(
                        _finding(
                            "SERVICE_DEFINITION_VERSION_MISMATCH",
                            prefix + ".definitionVersion",
                            "Deployment, project lock, and catalog definition versions must match",
                            {
                                "catalogVersion": catalog_version,
                                "lockedVersion": locked_version,
                                "selectedVersion": selected_version,
                            },
                        )
                    )
                locked_digest = service_lock.get("digest")
                definition_digest = (
                    definition.get("x-definitionDigest")
                    if isinstance(definition, dict)
                    else None
                )
                if isinstance(definition, dict):
                    unsigned_definition = {
                        key: value
                        for key, value in definition.items()
                        if key not in ("x-definitionDigest", "x-sourceManifest")
                    }
                    computed_definition_digest = canonical_digest(unsigned_definition)
                else:
                    computed_definition_digest = None
                if definition_digest != computed_definition_digest:
                    findings.append(
                        _finding(
                            "SERVICE_DEFINITION_DIGEST_MISMATCH",
                            "catalog.definitions.%s.x-definitionDigest" % service_type,
                            "Service definition digest does not match its canonical content",
                            {
                                "computedDigest": computed_definition_digest,
                                "declaredDigest": definition_digest,
                                "serviceType": service_type,
                            },
                        )
                    )
                if locked_digest != computed_definition_digest:
                    findings.append(
                        _finding(
                            "PROJECT_SERVICE_DEFINITION_DIGEST_MISMATCH",
                            "catalogLock.services.%s.digest" % service_type,
                            "Project service lock does not match the canonical service definition",
                            {
                                "definitionDigest": computed_definition_digest,
                                "lockedDigest": locked_digest,
                                "serviceType": service_type,
                            },
                        )
                    )
            mode = deployment.get("mode")
            modes = _supported_modes(definition)
            if not mode or mode not in modes:
                findings.append(
                    _finding(
                        "SERVICE_MODE_UNSUPPORTED",
                        prefix + ".mode",
                        "Selected service mode is not supported by the service definition",
                        {"serviceType": service_type, "supportedModes": sorted(modes)},
                    )
                )

        members = deployment.get("members", {})
        if not isinstance(members, dict):
            findings.append(
                _finding(
                    "SERVICE_MEMBERS_INVALID",
                    prefix + ".members",
                    "Service members must be an object keyed by member id",
                )
            )
            continue
        mode_definition = {}
        if isinstance(definition, dict) and isinstance(definition.get("modes"), dict):
            mode_definition = definition["modes"].get(deployment.get("mode"), {})
        supported_roles = set(mode_definition.get("memberRoles", [])) if isinstance(mode_definition, dict) else set()
        placed_hosts = []
        for member_id in sorted(members):
            member = members[member_id]
            field = prefix + ".members.%s.host" % member_id
            host = member.get("host") if isinstance(member, dict) else None
            if host:
                placed_hosts.append(host)
            if not host or host not in inventory_host_set:
                findings.append(
                    _finding(
                        "MEMBER_HOST_NOT_FOUND",
                        field,
                        "Explicit member placement must reference a declared inventory host",
                        {"host": host} if host else None,
                    )
                )
            roles = member.get("roles", []) if isinstance(member, dict) else []
            if not isinstance(roles, list):
                findings.append(
                    _finding(
                        "MEMBER_ROLES_INVALID",
                        prefix + ".members.%s.roles" % member_id,
                        "Member roles must be a list of role identifiers",
                    )
                )
                roles = []
            invalid_roles = [role for role in roles if not isinstance(role, str) or not role]
            if invalid_roles:
                findings.append(
                    _finding(
                        "MEMBER_ROLES_INVALID",
                        prefix + ".members.%s.roles" % member_id,
                        "Member roles must contain only non-empty string identifiers",
                    )
                )
            for role in sorted(set(role for role in roles if isinstance(role, str) and role)):
                if supported_roles and role not in supported_roles:
                    findings.append(
                        _finding(
                            "MEMBER_ROLE_UNSUPPORTED",
                            prefix + ".members.%s.roles" % member_id,
                            "Member role is not supported by the selected service mode",
                            {"role": role, "supportedRoles": sorted(supported_roles)},
                        )
                    )
        placement = mode_definition.get("placement", {}) if isinstance(mode_definition, dict) else {}
        member_count = len(members)
        minimum_members = placement.get("minMembers")
        maximum_members = placement.get("maxMembers")
        if isinstance(minimum_members, int) and member_count < minimum_members:
            findings.append(
                _finding(
                    "SERVICE_MEMBER_COUNT_BELOW_MINIMUM",
                    prefix + ".members",
                    "Service deployment has fewer members than the selected mode requires",
                    {"actual": member_count, "minimum": minimum_members},
                )
            )
        if isinstance(maximum_members, int) and member_count > maximum_members:
            findings.append(
                _finding(
                    "SERVICE_MEMBER_COUNT_ABOVE_MAXIMUM",
                    prefix + ".members",
                    "Service deployment has more members than the selected mode permits",
                    {"actual": member_count, "maximum": maximum_members},
                )
            )
        if placement.get("distinctHosts") and len(placed_hosts) != len(set(placed_hosts)):
            findings.append(
                _finding(
                    "PLACEMENT_DISTINCT_HOSTS_REQUIRED",
                    prefix + ".members",
                    "Selected service mode requires every member to use a distinct host",
                )
            )
        role_cardinality = placement.get("roleCardinality", {})
        if isinstance(role_cardinality, dict):
            for role in sorted(role_cardinality):
                constraint = role_cardinality[role]
                if not isinstance(constraint, dict):
                    continue
                actual = sum(
                    1
                    for member in members.values()
                    if isinstance(member, dict)
                    and isinstance(member.get("roles"), list)
                    and role in member["roles"]
                )
                minimum = constraint.get("minimum")
                maximum = constraint.get("maximum")
                if isinstance(minimum, int) and actual < minimum:
                    findings.append(
                        _finding(
                            "SERVICE_ROLE_COUNT_BELOW_MINIMUM",
                            prefix + ".members",
                            "Service deployment has fewer members with a required role than the selected mode permits",
                            {"actual": actual, "minimum": minimum, "role": role},
                        )
                    )
                if isinstance(maximum, int) and actual > maximum:
                    findings.append(
                        _finding(
                            "SERVICE_ROLE_COUNT_ABOVE_MAXIMUM",
                            prefix + ".members",
                            "Service deployment has more members with a role than the selected mode permits",
                            {"actual": actual, "maximum": maximum, "role": role},
                        )
                    )

    findings.sort(key=lambda item: (item["field"], item["code"]))
    blocked = len(findings)
    return {
        "apiVersion": RESULT_API_VERSION,
        "kind": "ProjectValidationResult",
        "status": "BLOCKED" if blocked else "PASS",
        "projectFingerprint": _canonical_fingerprint(
            {
                "manifest": manifest,
                "desiredState": topology,
                "hosts": {key: desired_hosts[key] for key in sorted(desired_hosts)},
            }
        ),
        "summary": {
            "pass": 1 if blocked == 0 else 0,
            "actionRequired": 0,
            "blocked": blocked,
            "warning": 0,
            "unknown": 0,
            "skipped": 0,
        },
        "findings": findings,
    }


def write_validation_artifact(path, result):
    parent = os.path.dirname(path) or "."
    if not os.path.isdir(parent):
        os.makedirs(parent)
    descriptor, temporary_path = tempfile.mkstemp(prefix=".validation-", suffix=".json", dir=parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as artifact:
            json.dump(result, artifact, ensure_ascii=False, sort_keys=True, indent=2)
            artifact.write("\n")
            artifact.flush()
            os.fsync(artifact.fileno())
        os.replace(temporary_path, path)
    except Exception:
        try:
            os.unlink(temporary_path)
        except OSError:
            pass
        raise

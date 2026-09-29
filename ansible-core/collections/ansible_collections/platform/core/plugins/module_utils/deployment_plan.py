"""Deterministic, target-free DeploymentPlan construction for UI-BE-04B."""

from __future__ import absolute_import, division, print_function

import copy
import hashlib
import json
import re

try:
    from .project_validation import DIGEST_PATTERN, canonical_digest
except ImportError:
    from project_validation import DIGEST_PATTERN, canonical_digest


API_VERSION = "platform.installer/plan/v1alpha2"
MANIFEST_API_VERSION = "platform.installer/execution-manifest/v1alpha1"
PLANNING_PROTOCOL = "v1alpha1"
SOURCE_POLICY = "REPOSITORY_THEN_OFFLINE"
_SECRET_INPUT_REF = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_SECRET_INPUT_DEPLOYMENT = re.compile(r"^[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*$")
_SECRET_INPUT_PURPOSES = {
    "SERVICE_ADMIN_TOKEN": "INITIALIZED",
    "SERVICE_UNSEAL_SHARES": "SEALED",
}
_SECRET_INPUT_OPERATIONS = ["SERVICE_APPLY", "SERVICE_VERIFY"]
_SECRET_INPUT_OPERATIONS_BY_PURPOSE = {
    "SERVICE_ADMIN_TOKEN": _SECRET_INPUT_OPERATIONS,
    "SERVICE_UNSEAL_SHARES": ["SERVICE_APPLY"],
}


def _digest(value):
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _finding(code, field, message):
    return {
        "apiVersion": "platform.installer/finding/v1alpha1",
        "kind": "Finding",
        "code": code,
        "status": "BLOCKED",
        "category": "deployment-plan",
        "field": field,
        "safeMessage": message,
    }


def _safe_findings(items):
    result = []
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict):
            result.append(copy.deepcopy(item))
    return sorted(result, key=lambda item: (item.get("field", ""), item.get("code", ""), item.get("safeMessage", "")))


def _runtime_release(value):
    value = value if isinstance(value, dict) else {}
    result = {
        "bundleDigest": value.get("bundleDigest"),
        "coreVersion": value.get("coreVersion"),
        "catalogDigest": value.get("catalogDigest"),
        "planningProtocol": value.get("planningProtocol", PLANNING_PROTOCOL),
    }
    if any(not isinstance(item, str) or not item for item in result.values()):
        raise ValueError("DEPLOYMENT_PLAN_RUNTIME_RELEASE_INVALID")
    if not result["bundleDigest"].startswith("sha256:") or not result["catalogDigest"].startswith("sha256:"):
        raise ValueError("DEPLOYMENT_PLAN_RUNTIME_RELEASE_INVALID")
    return result


def _artifact_requirements(deployments, definitions):
    requirements = []
    for deployment_id, deployment in sorted(deployments.items()):
        service_type = deployment.get("serviceType") if isinstance(deployment, dict) else None
        definition = definitions.get(service_type, {}) if isinstance(definitions, dict) else {}
        for artifact in definition.get("artifacts", []) if isinstance(definition, dict) else []:
            if isinstance(artifact, dict) and all(isinstance(artifact.get(key), str) and artifact[key] for key in ("id", "version", "digest")):
                requirements.append({
                    "id": "%s:%s" % (deployment_id, artifact["id"]),
                    "serviceDeployment": deployment_id,
                    "serviceType": service_type,
                    "requirementId": artifact["id"],
                    "name": artifact.get("name", artifact["id"]),
                    "os": artifact.get("os", ""),
                    "architecture": artifact.get("architecture", ""),
                    "version": artifact["version"],
                    "digest": artifact["digest"],
                    "requiredOffline": bool(artifact.get("requiredOffline", True)),
                })
        for requirement in definition.get("runtimeRequirements", []) if isinstance(definition, dict) else []:
            if isinstance(requirement, dict) and all(isinstance(requirement.get(key), str) and requirement[key] for key in ("id", "name", "os", "architecture")):
                declaration = "%s\x00%s\x00%s\x00%s" % (requirement["id"], requirement["name"], requirement.get("version", ""), requirement["architecture"])
                requirements.append({
                    "id": "%s:%s" % (deployment_id, requirement["id"]),
                    "serviceDeployment": deployment_id,
                    "serviceType": service_type,
                    "requirementId": requirement["id"],
                    "name": requirement["name"],
                    "version": requirement.get("version", ""),
                    "os": requirement["os"],
                    "architecture": requirement["architecture"],
                    "digest": _digest(declaration),
                    "requiredOffline": bool(requirement.get("requiredOffline", False)),
                })
    return requirements


def _source_finding(code, requirement, message):
    return _finding(code, "artifactRequirements.%s" % requirement.get("id", "unknown"), message)


def _source_identity(value):
    return tuple(value.get(key) for key in ("serviceType", "requirementId", "name", "version", "os", "architecture", "digest"))


def _bundle_source_index(value):
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 256:
        raise ValueError("DEPLOYMENT_PLAN_BUNDLE_SOURCE_INDEX_INVALID")
    result = []
    seen = set()
    for source in value:
        if not isinstance(source, dict) or set(source) != {"serviceType", "requirementId", "name", "version", "os", "architecture", "digest", "ref", "sha256", "size", "type"}:
            raise ValueError("DEPLOYMENT_PLAN_BUNDLE_SOURCE_INDEX_INVALID")
        if any(not isinstance(source.get(key), str) or not source[key] for key in ("serviceType", "requirementId", "name", "version", "os", "architecture", "digest", "ref", "sha256", "type")) or not isinstance(source.get("size"), int) or isinstance(source.get("size"), bool) or source["size"] < 0:
            raise ValueError("DEPLOYMENT_PLAN_BUNDLE_SOURCE_INDEX_INVALID")
        if DIGEST_PATTERN.fullmatch(source["digest"]) is None or DIGEST_PATTERN.fullmatch(source["sha256"]) is None or source["digest"] != source["sha256"] or not source["ref"].startswith("runtime/artifacts/") or ".." in source["ref"].split("/") or source["type"] not in ("archive", "package", "file"):
            raise ValueError("DEPLOYMENT_PLAN_BUNDLE_SOURCE_INDEX_INVALID")
        key = _source_identity(source) + (source["ref"], source["sha256"], source["size"], source["type"])
        if key in seen:
            raise ValueError("DEPLOYMENT_PLAN_BUNDLE_SOURCE_INDEX_INVALID")
        seen.add(key)
        result.append(copy.deepcopy(source))
    return sorted(result, key=lambda item: _source_identity(item) + (item["ref"],))


def _artifact_source_authorities(requirements, sources, bundle_digest):
    by_identity = {}
    for source in sources:
        by_identity.setdefault(_source_identity(source), []).append(source)
    authorities, findings = [], []
    for requirement in requirements:
        matches = by_identity.get(_source_identity(requirement), [])
        if len(matches) > 1:
            findings.append(_source_finding("ARTIFACT_SOURCE_AMBIGUOUS", requirement, "Offline bundle contains ambiguous artifact sources"))
            continue
        offline = None
        if matches:
            source = matches[0]
            offline = {"kind": "OFFLINE_BUNDLE", "bundleDigest": bundle_digest, "ref": source["ref"], "sha256": source["sha256"], "size": source["size"], "type": source["type"]}
        if requirement["requiredOffline"] and offline is None:
            findings.append(_source_finding("ARTIFACT_SOURCE_OFFLINE_REQUIRED", requirement, "Required offline bundle artifact is unavailable"))
            continue
        authorities.append({
            "apiVersion": "platform.installer/artifact-source-authority/v1alpha1",
            "kind": "ArtifactSourceAuthority",
            "requirement": copy.deepcopy(requirement),
            "sourcePolicy": SOURCE_POLICY,
            "repository": {"kind": "REPOSITORY"},
            "offlineBundle": offline,
        })
    return authorities, findings


def _service_dependencies(deployment_id, deployment, definitions, deployments):
    definition = definitions.get(deployment.get("serviceType"), {}) if isinstance(deployment, dict) and isinstance(definitions, dict) else {}
    required = definition.get("dependencies", []) if isinstance(definition, dict) else []
    result = []
    for dependency in required if isinstance(required, list) else []:
        capability = dependency.get("capability") if isinstance(dependency, dict) else None
        if not isinstance(capability, str):
            continue
        providers = []
        for candidate_id, candidate in sorted(deployments.items()):
            candidate_definition = definitions.get(candidate.get("serviceType"), {}) if isinstance(candidate, dict) else {}
            if capability in (candidate_definition.get("capabilities", []) if isinstance(candidate_definition, dict) else []):
                providers.append("apply:%s" % candidate_id)
        result.extend(providers)
    # A provider must not activate a backend before its explicitly related
    # source has completed apply. This is generic relation ordering, not a
    # service-type rule or a second endpoint model.
    for source_id, source in sorted(deployments.items()):
        relation = source.get("haproxy") if isinstance(source, dict) else None
        if source_id != deployment_id and isinstance(relation, dict) and relation.get("deploymentRef") == deployment_id:
            result.append("apply:%s" % source_id)
    return sorted(set(result))


def _ordered_apply_actions(actions):
    """Keep public plan and sequential controller order consistent with dependencies."""
    pending = {item["id"]: item for item in actions}
    ordered, completed = [], set()
    while pending:
        ready = sorted(key for key, item in pending.items()
                       if all(dep not in pending or dep in completed
                              for dep in item.get("dependsOn", [])))
        if not ready:
            raise ValueError("EXECUTION_DEPENDENCY_CYCLE")
        for key in ready:
            ordered.append(pending.pop(key))
            completed.add(key)
    return ordered


def _pki_consumers(snapshot):
    identities = ((snapshot.get("pki") or {}).get("certificateIdentities", []) if isinstance(snapshot, dict) else [])
    deployments = set()
    for identity in identities if isinstance(identities, list) else []:
        for consumer in identity.get("consumers", []) if isinstance(identity, dict) else []:
            if isinstance(consumer, dict) and isinstance(consumer.get("deploymentId"), str):
                deployments.add(consumer["deploymentId"])
    return sorted(deployments)


_PKI_STORE_PASSWORD_REQUIREMENT_REF = "pki-store-password"
_PKI_STORE_PASSWORD_PURPOSE = "PKI_STORE_PASSWORD"
_PKI_STORE_PASSWORD_RUNTIME_REF = "runtime:pki-store-password"
_RUNTIME_SECRET_REQUIREMENT = re.compile(r"[a-z][a-z0-9-]{0,63}")


def _pki_store_password_requirements(pki_materialization):
    """Return the public-safe requirement and private runtime binding.

    The resolved materialization result is an internal Core input.  It never
    becomes part of ProjectSnapshot or the public plan beyond the fixed safe
    requirement convention below.
    """
    values = pki_materialization.get("materializationPlans", []) if isinstance(pki_materialization, dict) else []
    if not isinstance(values, list):
        raise ValueError("DEPLOYMENT_PLAN_PKI_MATERIALIZATION_INVALID")
    hosts, unsupported = set(), False
    for value in values:
        if not isinstance(value, dict):
            raise ValueError("DEPLOYMENT_PLAN_PKI_MATERIALIZATION_INVALID")
        reference = value.get("storePasswordSecretRef")
        if reference is None:
            continue
        if not isinstance(reference, str) or not reference:
            raise ValueError("DEPLOYMENT_PLAN_PKI_MATERIALIZATION_INVALID")
        if reference != _PKI_STORE_PASSWORD_RUNTIME_REF:
            unsupported = True
            continue
        host_id = value.get("hostId")
        if not isinstance(host_id, str) or not host_id:
            raise ValueError("DEPLOYMENT_PLAN_PKI_MATERIALIZATION_INVALID")
        hosts.add(host_id)
    if unsupported:
        return [], [], [_finding("PKI_STORE_PASSWORD_REFERENCE_UNSUPPORTED", "pki", "PKI store-password runtime reference is unsupported for Installer execution")]
    if not hosts:
        return [], [], []
    public = {"requirementRef": _PKI_STORE_PASSWORD_REQUIREMENT_REF, "purpose": _PKI_STORE_PASSWORD_PURPOSE, "hosts": sorted(hosts)}
    private = {"requirementRef": _PKI_STORE_PASSWORD_REQUIREMENT_REF, "purpose": _PKI_STORE_PASSWORD_PURPOSE, "hosts": sorted(hosts), "runtimeReference": _PKI_STORE_PASSWORD_RUNTIME_REF}
    return [public], [private], []


def _service_runtime_secret_requirements(deployments, definitions, hosts):
    """Collect only catalog-declared runtime secret references.

    This intentionally knows no service or setting name.  The trusted closed
    manifest extension, the final desired configuration and the setting's
    closed object schema jointly prove the one runtime reference.
    """
    public, private, findings = [], [], []
    for deployment_id, deployment in sorted(deployments.items()):
        service_type = deployment.get("serviceType") if isinstance(deployment, dict) else None
        definition = definitions.get(service_type) if isinstance(definitions, dict) else None
        settings = ((definition.get("configuration") or {}).get("settings") if isinstance(definition, dict) else None)
        values = deployment.get("configuration") if isinstance(deployment, dict) else None
        if not isinstance(settings, dict) or not isinstance(values, dict):
            continue
        for setting_id, setting in sorted(settings.items()):
            ui = setting.get("ui") if isinstance(setting, dict) else None
            extension = ui.get("x-runtimeSecretRequirement") if isinstance(ui, dict) else None
            if extension is None:
                continue
            if (not isinstance(extension, dict) or set(extension) != {"requirementRef", "purpose"} or
                    not isinstance(extension.get("requirementRef"), str) or _RUNTIME_SECRET_REQUIREMENT.fullmatch(extension["requirementRef"]) is None or
                    extension.get("purpose") != "SERVICE_PASSWORD"):
                findings.append(_finding("RUNTIME_SECRET_REQUIREMENT_INVALID", "catalog.definitions.%s.configuration.settings.%s" % (service_type, setting_id), "Runtime secret requirement metadata is invalid"))
                continue
            schema = setting.get("schema") if isinstance(setting, dict) else None
            required = schema.get("required") if isinstance(schema, dict) else None
            properties = schema.get("properties") if isinstance(schema, dict) else None
            value = values.get(setting_id)
            if (not isinstance(schema, dict) or schema.get("type") != "object" or schema.get("additionalProperties") is not False or
                    not isinstance(required, list) or "passwordSecretRef" not in required or not isinstance(properties, dict) or
                    not isinstance(properties.get("passwordSecretRef"), dict) or properties["passwordSecretRef"].get("type") != "string"):
                findings.append(_finding("RUNTIME_SECRET_REQUIREMENT_SCHEMA_INVALID", "catalog.definitions.%s.configuration.settings.%s" % (service_type, setting_id), "Runtime secret requirement setting schema is incompatible"))
                continue
            if value is None:
                continue
            reference = value.get("passwordSecretRef") if isinstance(value, dict) else None
            if not isinstance(reference, str) or re.fullmatch(r"runtime:[a-z][a-z0-9-]{0,127}", reference) is None:
                findings.append(_finding("RUNTIME_SECRET_REFERENCE_INVALID", "serviceDeployments.%s.configuration.%s" % (deployment_id, setting_id), "Runtime secret reference is invalid"))
                continue
            item = {"requirementRef": extension["requirementRef"], "purpose": "SERVICE_PASSWORD", "hosts": sorted(hosts)}
            public.append(item)
            private.append(dict(item, runtimeReference=reference, serviceDeployment=deployment_id))
    refs, runtime_refs = set(), set()
    for item in private:
        if item["requirementRef"] in refs or item["runtimeReference"] in runtime_refs:
            findings.append(_finding("RUNTIME_SECRET_REQUIREMENT_DUPLICATE", "serviceDeployments", "Runtime secret requirements must be unique"))
            return [], [], findings
        refs.add(item["requirementRef"]); runtime_refs.add(item["runtimeReference"])
    return public, private, findings


def _secret_input_requirement_ref(service_deployment, manifest_requirement_ref, purpose):
    """Return the public opaque ref for a typed service input."""
    encoded = json.dumps([service_deployment, manifest_requirement_ref, purpose], ensure_ascii=False,
                         sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "si-" + hashlib.sha256(encoded).hexdigest()[:40]


def _service_input_requirements(deployments, definitions, resolved_topology):
    """Project the closed manifest x-secretInputs extension without values.

    This is metadata-only: target conditions are evaluated by the service at
    execution time, never by target-free planning.
    """
    public, private, findings = [], [], []
    resolved = resolved_topology.get("serviceDeployments", {}) if isinstance(resolved_topology, dict) else {}
    if not isinstance(resolved, dict):
        resolved = {}
    for deployment_id, deployment in sorted(deployments.items()):
        service_type = deployment.get("serviceType") if isinstance(deployment, dict) else None
        definition = definitions.get(service_type) if isinstance(definitions, dict) else None
        extension = definition.get("x-secretInputs") if isinstance(definition, dict) else None
        if extension is None:
            continue
        field = "catalog.definitions.%s.x-secretInputs" % (service_type or "unknown")
        if not isinstance(deployment_id, str) or len(deployment_id) > 128 or _SECRET_INPUT_DEPLOYMENT.fullmatch(deployment_id) is None or not isinstance(extension, dict) or set(extension) != {"apiVersion", "inputs"} or extension.get("apiVersion") != "ServiceSecretInputs/v1alpha1" or not isinstance(extension.get("inputs"), list) or not 1 <= len(extension["inputs"]) <= 16:
            findings.append(_finding("SERVICE_SECRET_INPUT_METADATA_INVALID", field, "Service secret input metadata is invalid"))
            continue
        placement = resolved.get(deployment_id, {})
        members = placement.get("members", {}) if isinstance(placement, dict) else None
        hosts = sorted({member.get("host") for member in members.values()
                        if isinstance(member, dict) and isinstance(member.get("host"), str) and member.get("host")}
                       ) if isinstance(members, dict) else []
        if not hosts or len(hosts) > 256:
            findings.append(_finding("SERVICE_SECRET_INPUT_PLACEMENT_INVALID", "serviceDeployments.%s" % deployment_id, "Service secret input placement is unavailable"))
            continue
        seen = set()
        for item in extension["inputs"]:
            if not isinstance(item, dict) or set(item) != {"requirementRef", "purpose", "displayLabel", "requiredWhen", "operations"}:
                findings.append(_finding("SERVICE_SECRET_INPUT_METADATA_INVALID", field, "Service secret input metadata is invalid"))
                continue
            manifest_ref, purpose = item.get("requirementRef"), item.get("purpose")
            if (not isinstance(manifest_ref, str) or _SECRET_INPUT_REF.fullmatch(manifest_ref) is None or
                    not isinstance(purpose, str) or purpose not in _SECRET_INPUT_PURPOSES or item.get("requiredWhen") != _SECRET_INPUT_PURPOSES.get(purpose) or
                    not isinstance(item.get("displayLabel"), str) or not item["displayLabel"] or len(item["displayLabel"].encode("utf-8")) > 256 or
                    item.get("operations") != _SECRET_INPUT_OPERATIONS_BY_PURPOSE.get(purpose) or (manifest_ref, purpose) in seen):
                findings.append(_finding("SERVICE_SECRET_INPUT_METADATA_INVALID", field, "Service secret input metadata is invalid"))
                continue
            seen.add((manifest_ref, purpose))
            requirement_ref = _secret_input_requirement_ref(deployment_id, manifest_ref, purpose)
            descriptor = {"requirementRef": requirement_ref, "purpose": purpose,
                          "serviceDeployment": deployment_id, "displayLabel": item["displayLabel"],
                          "hosts": hosts, "requiredWhen": item["requiredWhen"],
                          "operations": list(item["operations"])}
            public.append({key: descriptor[key] for key in ("requirementRef", "purpose", "serviceDeployment", "displayLabel", "hosts", "requiredWhen", "operations")})
            private.append(dict(
                {key: descriptor[key] for key in ("requirementRef", "purpose", "serviceDeployment", "hosts", "requiredWhen", "operations")},
                manifestRequirementRef=manifest_ref,
            ))
    keys = [(item["serviceDeployment"], item["manifestRequirementRef"], item["purpose"]) for item in private]
    refs = [item["requirementRef"] for item in private]
    if len(set(keys)) != len(keys) or len(set(refs)) != len(refs):
        findings.append(_finding("SERVICE_SECRET_INPUT_DUPLICATE", "serviceDeployments", "Service secret input requirements must be unique"))
    if len(public) > 16:
        findings.append(_finding("SERVICE_SECRET_INPUT_LIMIT_EXCEEDED", "serviceDeployments", "Service secret input requirements exceed the supported limit"))
    return public, private, findings


def build_runtime_secret_descriptors(snapshot, catalog, pki_materialization=None):
    """Build the closed safe v1alpha2 descriptor response from trusted Core data."""
    if not isinstance(snapshot, dict) or not isinstance(catalog, dict):
        raise ValueError("RUNTIME_SECRET_DESCRIPTORS_INPUT_INVALID")
    deployments = snapshot.get("serviceDeployments", {})
    definitions = catalog.get("definitions", {})
    hosts = sorted(snapshot.get("hosts", {}).keys()) if isinstance(snapshot.get("hosts"), dict) else []
    password_public, password_private, findings = _service_runtime_secret_requirements(deployments, definitions, hosts)
    _, pki_private, pki_findings = _pki_store_password_requirements(pki_materialization)
    findings.extend(pki_findings)
    typed_public, _, typed_findings = _service_input_requirements(
        deployments, definitions,
        (snapshot.get("topology") or {}).get("resolved", {}) if isinstance(snapshot.get("topology"), dict) else {},
    )
    findings.extend(typed_findings)
    if findings:
        raise ValueError("RUNTIME_SECRET_DESCRIPTORS_BLOCKED")
    labels = {}
    for deployment_id, deployment in deployments.items() if isinstance(deployments, dict) else []:
        definition = definitions.get(deployment.get("serviceType"), {}) if isinstance(deployment, dict) else {}
        settings = ((definition.get("configuration") or {}).get("settings") or {}) if isinstance(definition, dict) else {}
        for setting in settings.values() if isinstance(settings, dict) else []:
            ui = setting.get("ui") if isinstance(setting, dict) else None
            extension = ui.get("x-runtimeSecretRequirement") if isinstance(ui, dict) else None
            if isinstance(extension, dict) and isinstance(extension.get("requirementRef"), str):
                labels[(deployment_id, extension["requirementRef"])] = ui.get("label")
    descriptors = []
    for item in pki_private:
        descriptors.append({"requirementRef": item["requirementRef"], "purpose": item["purpose"],
                            "serviceDeployment": None, "displayLabel": "PKI store password",
                            "hosts": item["hosts"], "requiredWhen": "ALWAYS",
                            "operations": list(_SECRET_INPUT_OPERATIONS)})
    for item in password_private:
        label = labels.get((item["serviceDeployment"], item["requirementRef"]))
        if not isinstance(label, str) or not label or len(label.encode("utf-8")) > 256:
            raise ValueError("RUNTIME_SECRET_DESCRIPTORS_BLOCKED")
        descriptors.append({"requirementRef": item["requirementRef"], "purpose": item["purpose"],
                            "serviceDeployment": item["serviceDeployment"], "displayLabel": label,
                            "hosts": item["hosts"], "requiredWhen": "ALWAYS",
                            "operations": list(_SECRET_INPUT_OPERATIONS)})
    descriptors.extend(typed_public)
    descriptors.sort(key=lambda item: (item["serviceDeployment"] or "", item["requirementRef"]))
    identity = snapshot.get("project", {}).get("id") if isinstance(snapshot.get("project"), dict) else None
    revision = snapshot.get("projectRevision")
    if (not isinstance(identity, str) or not identity or not isinstance(revision, str) or
            DIGEST_PATTERN.fullmatch(revision) is None or len(descriptors) > 16 or
            any(len(item["hosts"]) > 256 for item in descriptors)):
        raise ValueError("RUNTIME_SECRET_DESCRIPTORS_BLOCKED")
    fields = ("requirementRef", "purpose", "serviceDeployment", "hosts", "requiredWhen", "operations")
    return {"apiVersion": "BuildRuntimeSecretDescriptors/v1alpha2", "projectIdentity": identity,
            "projectRevision": revision, "descriptors": descriptors,
            "descriptorSetFingerprint": canonical_digest([{key: item[key] for key in fields} for item in descriptors])}


def _execution_role_variables(deployment_id, definition, prefix, execution_configuration, targets,
                              resolved_deployment=None, hosts=None, member_list_variable=None):
    """Project Core-resolved settings into one private host-scoped operation map."""
    services = execution_configuration.get("services", {}) if isinstance(execution_configuration, dict) else {}
    service = services.get(deployment_id) if isinstance(services, dict) else None
    if not isinstance(service, dict):
        return None
    settings = ((definition.get("configuration") or {}).get("settings") or {}) if isinstance(definition, dict) else {}
    if not isinstance(settings, dict) or not isinstance(service.get("mode"), str):
        raise ValueError("EXECUTION_CONFIGURATION_INVALID")
    deployment_values = service.get("configuration", {})
    members = service.get("members", {})
    if not isinstance(deployment_values, dict) or not isinstance(members, dict):
        raise ValueError("EXECUTION_CONFIGURATION_INVALID")
    client_listener = definition.get("x-backendClientListener") if isinstance(definition, dict) else None
    member_port_variable = None
    if client_listener is not None:
        port_setting = settings.get("port")
        if (not isinstance(client_listener, dict) or
                not isinstance(port_setting, dict) or
                "member" not in port_setting.get("scopes", []) or
                member_list_variable is None):
            raise ValueError("EXECUTION_CONFIGURATION_INVALID")
        member_port_variable = port_setting.get("roleVariable")
        if not isinstance(member_port_variable, str) or not member_port_variable.startswith(prefix):
            raise ValueError("EXECUTION_CONFIGURATION_INVALID")

    def role_values(values):
        if not isinstance(values, dict):
            raise ValueError("EXECUTION_CONFIGURATION_INVALID")
        result = {prefix + "mode": service["mode"]}
        for logical, resolved in values.items():
            entry = settings.get(logical)
            role_variable = entry.get("roleVariable") if isinstance(entry, dict) else None
            if not isinstance(role_variable, str) or not role_variable.startswith(prefix):
                raise ValueError("EXECUTION_CONFIGURATION_INVALID")
            if not isinstance(resolved, dict) or resolved.get("state") != "RESOLVED" or "value" not in resolved:
                raise ValueError("EXECUTION_CONFIGURATION_INVALID")
            result[role_variable] = copy.deepcopy(resolved["value"])
        return result

    if not isinstance(targets, list) or not targets or any(not isinstance(host, str) or not host for host in targets):
        raise ValueError("EXECUTION_CONFIGURATION_INVALID")
    by_host = {host: role_values(deployment_values) for host in sorted(set(targets))}
    for member_id, member in sorted(members.items()):
        context = member.get("variableContext", {}) if isinstance(member, dict) else {}
        host_id = context.get("hostId") if isinstance(context, dict) else None
        values = member.get("configuration") if isinstance(member, dict) else None
        if not isinstance(member_id, str) or not isinstance(host_id, str) or not host_id:
            raise ValueError("EXECUTION_CONFIGURATION_INVALID")
        variables = role_values(values)
        if host_id not in by_host:
            raise ValueError("EXECUTION_CONFIGURATION_INVALID")
        # A package-declared client port is represented per member in the
        # existing member list. Other settings keep the host-conflict guard.
        if member_port_variable is not None:
            variables[member_port_variable] = by_host[host_id][member_port_variable]
        if by_host[host_id] != role_values(deployment_values) and by_host[host_id] != variables:
            raise ValueError("EXECUTION_CONFIGURATION_HOST_CONFLICT")
        by_host[host_id] = variables
    if member_list_variable is not None:
        if (not isinstance(member_list_variable, str) or not member_list_variable.startswith(prefix) or
                not isinstance(resolved_deployment, dict) or not isinstance(hosts, dict)):
            raise ValueError("EXECUTION_CONFIGURATION_INVALID")
        resolved_members = resolved_deployment.get("members")
        if not isinstance(resolved_members, dict) or not resolved_members:
            raise ValueError("EXECUTION_CONFIGURATION_INVALID")
        instances = []
        for member_id, member in sorted(resolved_members.items()):
            host_id = member.get("host") if isinstance(member, dict) else None
            roles = member.get("roles") if isinstance(member, dict) else None
            host = hosts.get(host_id) if isinstance(host_id, str) else None
            address = host.get("ansibleHost") if isinstance(host, dict) else None
            if (not isinstance(member_id, str) or not member_id or not isinstance(host_id, str) or not host_id or
                    not isinstance(address, str) or not address or not isinstance(roles, list) or
                    not roles or any(not isinstance(role, str) or not role for role in roles)):
                raise ValueError("EXECUTION_CONFIGURATION_INVALID")
            instance = {"id": member_id, "host": host_id, "hostname": host_id,
                        "address": address, "roles": sorted(roles)}
            if member_port_variable is not None:
                port_value = members.get(member_id, {}).get("configuration", {}).get("port")
                if isinstance(port_value, dict) and port_value.get("source") == "MEMBER_OVERRIDE":
                    explicit_port = port_value.get("value")
                    if isinstance(explicit_port, bool) or not isinstance(explicit_port, int) or not 1 <= explicit_port <= 65535:
                        raise ValueError("EXECUTION_CONFIGURATION_INVALID")
                    instance["port"] = explicit_port
            instances.append(instance)
        for values in by_host.values():
            values[member_list_variable] = copy.deepcopy(instances)
    return {host_id: by_host[host_id] for host_id in sorted(by_host)}


def _runtime_secret_outputs(manifest_operations, deployments, definitions):
    """Copy trusted closed output declarations into the private manifest.

    Output source paths are not accepted from catalog data. The execution
    controller uses the established project/secrets/<deploymentId> convention.
    """
    apply_deployments = {
        item.get("serviceDeployment") for item in manifest_operations
        if isinstance(item, dict) and item.get("operation") == "SERVICE_APPLY"
    }
    result = []
    for deployment_id in sorted(apply_deployments):
        deployment = deployments.get(deployment_id)
        service_type = deployment.get("serviceType") if isinstance(deployment, dict) else None
        definition = definitions.get(service_type) if isinstance(service_type, str) else None
        declaration = definition.get("x-secretOutputs") if isinstance(definition, dict) else None
        if declaration is None:
            continue
        if (not isinstance(declaration, dict) or set(declaration) != {"protocol", "entries"} or
                declaration.get("protocol") != "SecretOutputDelivery/v1alpha1" or
                declaration.get("entries") != ["admin-token", "unseal-shares"]):
            raise ValueError("SECRET_OUTPUT_DECLARATION_INVALID")
        result.append({"protocol": declaration["protocol"], "serviceDeployment": deployment_id,
                       "entries": list(declaration["entries"])})
    return result


def build_deployment_plan(snapshot, service_catalog, runtime_release, created_at="1970-01-01T00:00:00Z", bundle_artifact_sources=None, pki_materialization=None, execution_configuration=None):
    """Return a public plan and private manifest from already resolved Core data."""
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    catalog = service_catalog.get("platform_service_catalog", service_catalog) if isinstance(service_catalog, dict) else {}
    definitions = catalog.get("definitions", {}) if isinstance(catalog, dict) else {}
    release = _runtime_release(runtime_release)
    project = snapshot.get("project", {}) if isinstance(snapshot.get("project"), dict) else {}
    identity = project.get("id")
    explicit_identity = project.get("identitySource") == "PROJECT_MANIFEST"
    deployments = snapshot.get("serviceDeployments", {}) if isinstance(snapshot.get("serviceDeployments"), dict) else {}
    findings = _safe_findings(snapshot.get("findings"))
    if not explicit_identity or not isinstance(identity, str) or not identity:
        findings.append(_finding("PROJECT_IDENTITY_REQUIRED", "project.metadata.id", "Installer-managed execution requires project.yml metadata.id"))
    if snapshot.get("validation", {}).get("status") != "PASS":
        findings.append(_finding("PROJECT_VALIDATION_BLOCKED", "validation", "Authoritative project validation is blocked"))
    artifact_requirements = _artifact_requirements(deployments, definitions)
    source_authorities, source_findings = _artifact_source_authorities(artifact_requirements, _bundle_source_index(bundle_artifact_sources), release["bundleDigest"])
    findings.extend(source_findings)
    pki_public, pki_private, pki_secret_findings = _pki_store_password_requirements(pki_materialization)
    service_public, service_private, service_secret_findings = _service_runtime_secret_requirements(deployments, definitions, sorted(snapshot.get("hosts", {}).keys()) if isinstance(snapshot.get("hosts"), dict) else [])
    service_input_public, service_input_private, service_input_findings = _service_input_requirements(
        deployments, definitions,
        (snapshot.get("topology") or {}).get("resolved", {}) if isinstance(snapshot.get("topology"), dict) else {},
    )
    required_credentials = pki_public + service_public + [
        {key: item[key] for key in ("requirementRef", "purpose", "hosts")}
        for item in service_input_public
    ]
    runtime_secret_requirements = pki_private + service_private
    if len({item["requirementRef"] for item in runtime_secret_requirements + service_input_private}) != len(runtime_secret_requirements) + len(service_input_private) or len({item["runtimeReference"] for item in runtime_secret_requirements if "runtimeReference" in item}) != len([item for item in runtime_secret_requirements if "runtimeReference" in item]):
        service_secret_findings.append(_finding("RUNTIME_SECRET_REQUIREMENT_DUPLICATE", "runtimeSecrets", "Runtime secret requirements must be unique"))
    findings.extend(pki_secret_findings + service_secret_findings + service_input_findings)
    required_credentials.sort(key=lambda item: item["requirementRef"])
    if len({item["requirementRef"] for item in required_credentials}) != len(required_credentials):
        findings.append(_finding("RUNTIME_SECRET_REQUIREMENT_DUPLICATE", "runtimeSecrets", "Runtime secret requirements must be unique"))
    runtime_secret_requirements.sort(key=lambda item: (item.get("serviceDeployment") or "", item["requirementRef"]))
    findings = _safe_findings(findings)
    executable = not findings
    artifact_digest = canonical_digest(artifact_requirements)
    targets = sorted(snapshot.get("hosts", {}).keys()) if isinstance(snapshot.get("hosts"), dict) else []
    pki_consumers = _pki_consumers(snapshot)
    actions = []
    if pki_consumers:
        actions.append({"id": "pki:apply", "type": "PKI_APPLY", "targets": targets, "dependsOn": [], "mutating": True, "reboot": "NONE", "summary": "Materialize approved PKI inputs"})
    apply_actions = []
    for deployment_id, deployment in sorted(deployments.items()):
        dependencies = _service_dependencies(deployment_id, deployment, definitions, deployments)
        if deployment_id in pki_consumers:
            dependencies.append("pki:apply")
        apply_actions.append({"id": "apply:%s" % deployment_id, "type": "SERVICE_APPLY", "serviceDeployment": deployment_id, "targets": targets, "dependsOn": sorted(set(dependencies)), "mutating": True, "reboot": "NONE", "summary": "Apply service deployment %s" % deployment_id})
    apply_actions = _ordered_apply_actions(apply_actions)
    verify_actions = [{"id": "verify:%s" % deployment_id, "type": "SERVICE_VERIFY", "serviceDeployment": deployment_id, "targets": targets, "dependsOn": ["apply:%s" % deployment_id], "mutating": False, "reboot": "NONE", "summary": "Verify service deployment %s" % deployment_id} for deployment_id in sorted(deployments)]
    phases = []
    if actions:
        phases.append({"id": "pki", "order": len(phases), "actions": actions})
    phases.append({"id": "apply", "order": len(phases), "actions": apply_actions})
    phases.append({"id": "verify", "order": len(phases), "actions": verify_actions})
    semantic = {
        "apiVersion": API_VERSION,
        "planningProtocol": release["planningProtocol"],
        "projectIdentity": identity if explicit_identity else None,
        "projectRevision": snapshot.get("projectRevision"),
        "catalogDigest": catalog.get("digest"),
        "runtimeRelease": release,
        "artifactRequirements": artifact_requirements,
        "requiredCredentials": required_credentials,
        "phases": phases,
        "acknowledgements": [],
        "status": "EXECUTABLE" if executable else "BLOCKED",
    }
    plan_fingerprint = canonical_digest(semantic)
    plan = {
        "apiVersion": API_VERSION,
        "kind": "DeploymentPlan",
        "id": "plan-" + plan_fingerprint.split(":", 1)[1][:24],
        "createdAt": created_at,
        "projectIdentity": identity if explicit_identity else None,
        "projectRevision": snapshot.get("projectRevision"),
        "planner": {"coreVersion": release["coreVersion"], "planningProtocol": release["planningProtocol"]},
        "runtimeRelease": release,
        "fingerprints": {"project": snapshot.get("projectRevision"), "catalog": catalog.get("digest"), "artifacts": artifact_digest, "core": _digest(release["coreVersion"] + "\x00" + release["planningProtocol"]), "plan": plan_fingerprint},
        "status": "EXECUTABLE" if executable else "BLOCKED",
        "readiness": "REQUIRES_PREPARATION" if executable else "BLOCKED",
        "artifactRequirements": artifact_requirements,
        "phases": phases,
        "requiredCredentials": required_credentials,
        "acknowledgements": [],
        "findings": findings,
    }
    manifest = None
    if executable:
        manifest_operations = []
        authority_deployments = set(item["requirement"]["serviceDeployment"] for item in source_authorities)
        for phase in phases:
            for action in phase["actions"]:
                deployment = deployments.get(action.get("serviceDeployment"), {})
                definition = definitions.get(deployment.get("serviceType"), {}) if isinstance(deployment, dict) else {}
                entrypoint = "apply" if action["type"] == "SERVICE_APPLY" else "verify"
                role_entrypoint = ((definition.get("roleEntrypoints") or {}).get(entrypoint) or {}) if isinstance(definition, dict) else {}
                prefix = role_entrypoint.get("variablesPrefix") if isinstance(role_entrypoint, dict) else None
                item = {"operationId": action["id"], "phaseId": phase["id"], "operation": action["type"], "serviceDeployment": action.get("serviceDeployment"), "serviceType": deployment.get("serviceType") if isinstance(deployment, dict) else None, "requiresArtifactSources": action.get("serviceDeployment") in authority_deployments}
                if action["type"] in ("SERVICE_APPLY", "SERVICE_VERIFY"):
                    if isinstance(prefix, str) and re.fullmatch(r"platform_[a-z0-9_]{1,96}_", prefix) is not None:
                        item["roleVariablesPrefix"] = prefix
                        topology = snapshot.get("topology", {}) if isinstance(snapshot.get("topology"), dict) else {}
                        resolved = topology.get("resolved", {}) if isinstance(topology.get("resolved"), dict) else {}
                        resolved_deployments = resolved.get("serviceDeployments", {}) if isinstance(resolved.get("serviceDeployments"), dict) else {}
                        variables = _execution_role_variables(
                            action.get("serviceDeployment"), definition, prefix, execution_configuration,
                            action.get("targets"), resolved_deployments.get(action.get("serviceDeployment")),
                            snapshot.get("hosts"), role_entrypoint.get("x-memberListVariable"),
                        )
                        if variables is not None:
                            item["roleVariablesByHost"] = variables
                manifest_operations.append(item)
        runtime_secret_outputs = _runtime_secret_outputs(manifest_operations, deployments, definitions)
        # Materialization plans are Core-derived, private execution inputs.  A
        # controller starts each approved Ansible operation in a fresh process,
        # so PKI-consuming service operations must receive the same plans that
        # the preceding PKI operation resolved.  They are deliberately bound
        # only into the digest-protected private manifest, never the portable
        # project, public DeploymentPlan, UI projection, journal or result.
        materialization_plans = pki_materialization.get("materializationPlans", []) if isinstance(pki_materialization, dict) else []
        # The descriptor fingerprint has one closed shape.  PKI has no
        # service deployment and therefore uses the explicit null value rather
        # than a second, ambiguously shaped descriptor form.
        descriptor_set = [
            {key: item.get(key) for key in ("requirementRef", "purpose", "serviceDeployment", "hosts")}
            for item in runtime_secret_requirements
        ] + [
            {key: item.get(key) for key in ("requirementRef", "purpose", "serviceDeployment", "hosts", "requiredWhen", "operations")}
            for item in service_input_private
        ] + [
            {key: item.get(key) for key in ("protocol", "serviceDeployment", "entries")}
            for item in runtime_secret_outputs
        ]
        manifest = {"apiVersion": MANIFEST_API_VERSION, "kind": "ExecutionManifest", "projectIdentity": identity, "projectRevision": snapshot.get("projectRevision"), "planFingerprint": plan_fingerprint, "runtimeRelease": release, "operations": manifest_operations, "artifactRequirements": artifact_requirements, "artifactSourceAuthorities": source_authorities, "requiredCredentials": required_credentials, "runtimeSecretRequirements": runtime_secret_requirements, "runtimeSecretInputs": service_input_private, "runtimeSecretOutputs": runtime_secret_outputs, "runtimeSecretDescriptorSetFingerprint": canonical_digest(descriptor_set), "pkiMaterializationPlans": materialization_plans}
    return {"deploymentPlan": plan, "executionManifest": manifest, "executionManifestDigest": canonical_digest(manifest) if manifest else None}

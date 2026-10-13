"""Deterministic, target-free DeploymentPlan construction for UI-BE-04B."""

from __future__ import absolute_import, division, print_function

import copy
import hashlib
import json
import re

try:
    from .artifact_authority import assemble_authority
except ImportError:
    from artifact_authority import assemble_authority

try:
    from .project_validation import DIGEST_PATTERN, canonical_digest
    from .service_integration_resolution import haproxy_provider_hosts
    from .application_plan import application_execution_model, application_operation, PLAN_VERSION as APPLICATION_PLAN_VERSION, MANIFEST_VERSION as APPLICATION_MANIFEST_VERSION
except ImportError:
    from project_validation import DIGEST_PATTERN, canonical_digest
    from service_integration_resolution import haproxy_provider_hosts
    from application_plan import application_execution_model, application_operation, PLAN_VERSION as APPLICATION_PLAN_VERSION, MANIFEST_VERSION as APPLICATION_MANIFEST_VERSION


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
        authorities.append(assemble_authority(requirement, offline))
    return authorities, findings


def _service_dependencies(deployment_id, deployment, definitions, deployments, placements):
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
    # Base HAProxy does not consume future source backends. The existing
    # source-owned integration needs its selected providers prepared first.
    providers = haproxy_provider_hosts({"serviceDeployments": deployments}, placements, deployment)
    result.extend("apply:%s" % provider_id for provider_id in providers)
    return sorted(set(result))


def _validated_deployment_order(deployments, deployment_order):
    if (not isinstance(deployment_order, list) or len(deployment_order) > 256 or
            any(not isinstance(item, str) or not item or len(item) > 128 for item in deployment_order) or
            len(deployment_order) != len(set(deployment_order)) or
            set(deployment_order) != set(deployments)):
        raise ValueError("DEPLOYMENT_ORDER_INVALID")
    return list(deployment_order)


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


def _deployment_targets(snapshot, deployment_ids, known_hosts):
    """Copy validated inventory placement into per-deployment action targets."""
    if not deployment_ids:
        return {}, []
    topology = snapshot.get("topology") if isinstance(snapshot, dict) else None
    placements = topology.get("placementsByHost") if isinstance(topology, dict) else None
    selected = {deployment_id: set() for deployment_id in deployment_ids}
    if not isinstance(placements, dict):
        return {}, [_finding("SERVICE_TARGETS_UNAVAILABLE", "topology.placementsByHost", "Service placement is unavailable")]
    findings = []
    for host_id, host_placements in placements.items():
        if (not isinstance(host_id, str) or host_id not in known_hosts or
                not isinstance(host_placements, dict)):
            findings.append(_finding("SERVICE_TARGETS_UNAVAILABLE", "topology.placementsByHost", "Service placement is invalid"))
            continue
        for deployment_id in host_placements:
            if deployment_id in selected:
                selected[deployment_id].add(host_id)
    for deployment_id in deployment_ids:
        if not selected[deployment_id]:
            findings.append(_finding("SERVICE_TARGETS_UNAVAILABLE", "serviceDeployments.%s" % deployment_id, "Service has no selected target hosts"))
    return {key: sorted(value) for key, value in selected.items()}, findings


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
    result = {"apiVersion": "BuildRuntimeSecretDescriptors/v1alpha2", "projectIdentity": identity,
            "projectRevision": revision, "descriptors": descriptors,
            "descriptorSetFingerprint": canonical_digest([{key: item[key] for key in fields} for item in descriptors])}
    if snapshot.get('apiVersion') == 'platform.installer/project-snapshot/v2alpha1':
        model = application_execution_model(snapshot)
        app_inputs = [dict({key: item[key] for key in ('requirementRef', 'purpose', 'providerDeployment',
                                                     'applicationLibraries', 'hosts', 'operations')},
                           sourceRef=item['runtimeReference'], displayLabel=item['runtimeReference'])
                      for item in model['runtimeSecretRequirements']]
        if len(app_inputs) + len(descriptors) > 16 or any(len(item['hosts']) > 256 for item in app_inputs):
            raise ValueError('RUNTIME_SECRET_DESCRIPTORS_BLOCKED')
        result.update(apiVersion='BuildRuntimeSecretDescriptors/v1alpha3', applicationInputs=app_inputs)
        result['descriptorSetFingerprint'] = canonical_digest(dict(
            serviceInputs=[{key: item[key] for key in fields} for item in descriptors], applicationInputs=app_inputs))
    return result


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
    member_data_setting = definition.get("x-memberDataDirectorySetting") if isinstance(definition, dict) else None
    member_data_variable = None
    if member_data_setting is not None:
        data_entry = settings.get(member_data_setting)
        if (not isinstance(member_data_setting, str) or not isinstance(data_entry, dict) or
                "member" not in data_entry.get("scopes", []) or member_list_variable is None):
            raise ValueError("EXECUTION_CONFIGURATION_INVALID")
        member_data_variable = data_entry.get("roleVariable")
        if not isinstance(member_data_variable, str) or not member_data_variable.startswith(prefix):
            raise ValueError("EXECUTION_CONFIGURATION_INVALID")
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

    def role_values(values, member_scope=False):
        if not isinstance(values, dict):
            raise ValueError("EXECUTION_CONFIGURATION_INVALID")
        result = {prefix + "mode": service["mode"]}
        for logical, resolved in values.items():
            entry = settings.get(logical)
            role_variable = entry.get("roleVariable") if isinstance(entry, dict) else None
            if not isinstance(role_variable, str) or not role_variable.startswith(prefix):
                raise ValueError("EXECUTION_CONFIGURATION_INVALID")
            if member_scope and role_variable == member_data_variable:
                continue
            if not isinstance(resolved, dict):
                raise ValueError("EXECUTION_CONFIGURATION_INVALID")
            # A read-only Core projection of a role default is not an override.
            # Leave it to normal Ansible role/inventory precedence at execution.
            if (resolved.get("state") == "RESOLVED" and
                    (resolved.get("source") == "ROLE_DEFAULT" or
                     (resolved.get("source") == "STATIC_REFERENCE" and resolved.get("origin") == "ROLE_DEFAULT"))):
                continue
            if (resolved.get("state") == "DEFERRED" and
                    resolved.get("reason") == "NON_LITERAL_ROLE_DEFAULT"):
                continue
            if resolved.get("state") != "RESOLVED" or "value" not in resolved:
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
        variables = role_values(values, member_scope=True)
        if host_id not in by_host:
            raise ValueError("EXECUTION_CONFIGURATION_INVALID")
        # A package-declared client port is represented per member in the
        # existing member list. Other settings keep the host-conflict guard.
        if member_port_variable is not None:
            if member_port_variable in by_host[host_id]:
                variables[member_port_variable] = by_host[host_id][member_port_variable]
            else:
                variables.pop(member_port_variable, None)
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
            if member_data_setting is not None:
                data_value = members.get(member_id, {}).get("configuration", {}).get(member_data_setting)
                if isinstance(data_value, dict) and data_value.get("source") == "MEMBER_OVERRIDE":
                    data_path = data_value.get("value")
                    if not isinstance(data_path, str) or not data_path.startswith("/"):
                        raise ValueError("EXECUTION_CONFIGURATION_INVALID")
                    instance["data_directory"] = data_path
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


def build_deployment_plan(snapshot, service_catalog, runtime_release, created_at="1970-01-01T00:00:00Z", bundle_artifact_sources=None, pki_materialization=None, execution_configuration=None, execution_connections=None, pki_reissue=None, deployment_order=None, application_image_lock=None, application_vault_sources=None):
    """Return a public plan and private manifest from already resolved Core data."""
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    if snapshot.get('apiVersion') not in (None, 'platform.installer/project-snapshot/v1alpha1',
                                         'platform.installer/project-snapshot/v2alpha1'):
        raise ValueError('PROJECT_SNAPSHOT_VERSION_UNSUPPORTED')
    application_aware = snapshot.get('apiVersion') == 'platform.installer/project-snapshot/v2alpha1'
    application_model = application_execution_model(snapshot, application_image_lock) if application_aware else None
    plan_version = APPLICATION_PLAN_VERSION if application_aware else API_VERSION
    catalog = service_catalog.get("platform_service_catalog", service_catalog) if isinstance(service_catalog, dict) else {}
    definitions = catalog.get("definitions", {}) if isinstance(catalog, dict) else {}
    release = _runtime_release(runtime_release)
    project = snapshot.get("project", {}) if isinstance(snapshot.get("project"), dict) else {}
    identity = project.get("id")
    explicit_identity = project.get("identitySource") == "PROJECT_MANIFEST"
    deployments = snapshot.get("serviceDeployments", {}) if isinstance(snapshot.get("serviceDeployments"), dict) else {}
    deployment_order = _validated_deployment_order(deployments, deployment_order)
    findings = _safe_findings(snapshot.get("findings"))
    if application_aware:
        findings.extend(application_model['findings'])
        sources = {} if application_vault_sources is None else application_vault_sources
        vaults = {item['providerDeployment'] for item in application_model['runtimeSecretRequirements']
                  if item['purpose'] == 'APPLICATION_VAULT_ADMIN_TOKEN'}
        if (not isinstance(sources, dict) or set(sources) - vaults or
                any(value not in ('RUNTIME_INPUT', 'CURRENT_RUN_BOOTSTRAP') for value in sources.values())):
            raise ValueError('APPLICATION_VAULT_SOURCE_INVALID')
        for item in application_model['runtimeSecretRequirements']:
            item['source'] = sources.get(item['providerDeployment'], 'RUNTIME_INPUT')
            if item['source'] == 'CURRENT_RUN_BOOTSTRAP':
                provider = item['providerDeployment']
                definition = definitions.get(deployments.get(provider, {}).get('serviceType'), {})
                if definition.get('x-secretOutputs') != {'protocol': 'SecretOutputDelivery/v1alpha1', 'entries': ['admin-token', 'unseal-shares']}:
                    findings.append(_finding('APPLICATION_BOOTSTRAP_PROVIDER_INVALID', 'applicationLibraries',
                                             'Bootstrap source must be a Vault deployment of this plan'))
    if not explicit_identity or not isinstance(identity, str) or not identity:
        findings.append(_finding("PROJECT_IDENTITY_REQUIRED", "project.metadata.id", "Installer-managed execution requires project.yml metadata.id"))
    if snapshot.get("validation", {}).get("status") != "PASS":
        findings.append(_finding("PROJECT_VALIDATION_BLOCKED", "validation", "Authoritative project validation is blocked"))
    artifact_requirements = _artifact_requirements(deployments, definitions)
    source_authorities, source_findings = _artifact_source_authorities(artifact_requirements, _bundle_source_index(bundle_artifact_sources), release["bundleDigest"])
    if application_model:
        artifact_requirements.extend(application_model['artifactRequirements'])
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
    if application_model:
        required_credentials.extend({key: item[key] for key in ('requirementRef', 'purpose', 'hosts')}
                                    for item in application_model['runtimeSecretRequirements'] if item['source'] == 'RUNTIME_INPUT')
        if len(service_private) + len(application_model['runtimeSecretRequirements']) > 16:
            findings.append(_finding('RUNTIME_SECRET_REQUIREMENTS_LIMIT', 'applicationLibraries',
                                     'The current runtime secret lease admits at most 16 values'))
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
    deployment_targets, target_findings = _deployment_targets(snapshot, sorted(deployments), set(targets))
    findings.extend(target_findings)
    executable = not findings
    pki_consumers = _pki_consumers(snapshot)
    reissue = pki_reissue if pki_reissue is not None else []
    if not isinstance(reissue, list) or len(reissue) > 256:
        raise ValueError("PKI_REISSUE_SCOPE_INVALID")
    request_ids = [item.get("requestId") for item in reissue if isinstance(item, dict)]
    requests = pki_materialization.get("requests", []) if isinstance(pki_materialization, dict) else []
    request_by_id = {item.get("id"): item for item in requests if isinstance(item, dict)}
    desired_by_id = {key: item.get("certificateRequestFingerprint") for key, item in request_by_id.items()}
    if len(request_ids) != len(reissue) or any(not isinstance(item, str) or item not in request_by_id for item in request_ids) or request_ids != sorted(set(request_ids)) or any(
            set(item) != {"requestId", "expectedOldFingerprint", "desiredFingerprint", "recoveryFingerprint", "authorityId", "authorityFingerprint"} or
            desired_by_id.get(item["requestId"]) != item["desiredFingerprint"] or
            request_by_id[item["requestId"]].get("authorityId") != item["authorityId"] or
            request_by_id[item["requestId"]].get("authorityFingerprint") != item["authorityFingerprint"] or
            not isinstance(item["desiredFingerprint"], str) or DIGEST_PATTERN.fullmatch(item["desiredFingerprint"]) is None or
            (item["expectedOldFingerprint"] is not None and
             (not isinstance(item["expectedOldFingerprint"], str) or DIGEST_PATTERN.fullmatch(item["expectedOldFingerprint"]) is None)) or
            (item["recoveryFingerprint"] is not None and item["recoveryFingerprint"] != item["desiredFingerprint"]) or
            (item["expectedOldFingerprint"] is None and item["recoveryFingerprint"] is None)
            for item in reissue):
        raise ValueError("PKI_REISSUE_SCOPE_INVALID")
    materialization_plans = pki_materialization.get("materializationPlans", []) if isinstance(pki_materialization, dict) else []
    target_values = {item.get("hostId") for item in materialization_plans if isinstance(item, dict)
                     and item.get("requestId") in request_ids}
    covered_requests = {item.get("requestId") for item in materialization_plans if isinstance(item, dict)
                        and item.get("requestId") in request_ids}
    if reissue and (not pki_consumers or not target_values or covered_requests != set(request_ids) or
                    any(not isinstance(host, str) or host not in targets for host in target_values)):
        raise ValueError("PKI_REISSUE_SCOPE_INVALID")
    scope_labels = []
    for request_id in request_ids:
        consumers = request_by_id[request_id].get("consumers")
        if not isinstance(consumers, list) or not consumers or len(consumers) > 4096:
            raise ValueError("PKI_REISSUE_SCOPE_INVALID")
        deployments_for_request, hosts_for_request = set(), set()
        for consumer in consumers:
            if not isinstance(consumer, dict) or consumer.get("deploymentId") not in deployments or consumer.get("hostId") not in targets:
                raise ValueError("PKI_REISSUE_SCOPE_INVALID")
            deployments_for_request.add(consumer["deploymentId"])
            hosts_for_request.add(consumer["hostId"])
        plan_hosts = {item.get("hostId") for item in materialization_plans if isinstance(item, dict) and item.get("requestId") == request_id}
        if hosts_for_request != plan_hosts:
            raise ValueError("PKI_REISSUE_SCOPE_INVALID")
        scope_labels.append("%s (сервисы: %s; серверы: %s)" %
                            (request_id, ", ".join(sorted(deployments_for_request)), ", ".join(sorted(hosts_for_request))))
    reissue_summary = "Перевыпустить сертификаты: " + "; ".join(scope_labels)
    if reissue and len(reissue_summary.encode("utf-8")) > 512:
        # Repeated consumers across per-host requests must not make a valid
        # scope unrepresentable. Retain the complete deployment/host scope;
        # exact request identities remain bound in the execution manifest.
        scope_deployments = sorted({consumer["deploymentId"] for request_id in request_ids
                                    for consumer in request_by_id[request_id]["consumers"]})
        scope_hosts = sorted({consumer["hostId"] for request_id in request_ids
                             for consumer in request_by_id[request_id]["consumers"]})
        reissue_summary = "Перевыпустить сертификаты (%s запросов; сервисы: %s; серверы: %s)" % (
            len(request_ids), ", ".join(scope_deployments), ", ".join(scope_hosts))
        if len(reissue_summary.encode("utf-8")) > 512:
            raise ValueError("PKI_REISSUE_SCOPE_TOO_LARGE")
    reissue_targets = sorted(target_values)
    actions = []
    if pki_consumers:
        if reissue:
            actions.append({"id": "pki:reissue", "type": "PKI_REISSUE", "targets": reissue_targets, "dependsOn": [], "mutating": True, "reboot": "NONE", "summary": reissue_summary})
        actions.append({"id": "pki:apply", "type": "PKI_APPLY", "targets": targets, "dependsOn": ["pki:reissue"] if reissue else [], "mutating": True, "reboot": "NONE", "summary": "Materialize approved PKI inputs"})
    service_actions = []
    deployment_positions = {deployment_id: index for index, deployment_id in enumerate(deployment_order)}
    for deployment_id in deployment_order:
        deployment = deployments[deployment_id]
        dependencies = _service_dependencies(deployment_id, deployment, definitions, deployments,
                                             (snapshot.get("topology") or {}).get("placementsByHost", {}))
        prior_dependencies = []
        for dependency in dependencies:
            provider_id = dependency[len("apply:"):] if dependency.startswith("apply:") else dependency
            if provider_id not in deployment_positions or deployment_positions[provider_id] >= deployment_positions[deployment_id]:
                findings.append(_finding(
                    "EXECUTION_ORDER_DEPENDENCY_CONFLICT", "deploymentOrder",
                    "Порядок установки конфликтует с обязательной зависимостью %s → %s." % (deployment_id, provider_id)))
            prior_dependencies.append("verify:%s" % provider_id)
        if deployment_id in pki_consumers:
            prior_dependencies.append("pki:apply")
        service_actions.append({"id": "apply:%s" % deployment_id, "type": "SERVICE_APPLY", "serviceDeployment": deployment_id, "targets": deployment_targets.get(deployment_id, []), "dependsOn": sorted(set(prior_dependencies)), "mutating": True, "reboot": "NONE", "summary": "Apply service deployment %s" % deployment_id})
        service_actions.append({"id": "verify:%s" % deployment_id, "type": "SERVICE_VERIFY", "serviceDeployment": deployment_id, "targets": deployment_targets.get(deployment_id, []), "dependsOn": ["apply:%s" % deployment_id], "mutating": False, "reboot": "NONE", "summary": "Verify service deployment %s" % deployment_id})
    findings = _safe_findings(findings)
    executable = not findings
    phases = []
    if actions:
        phases.append({"id": "pki", "order": len(phases), "actions": actions})
    phases.append({"id": "services", "order": len(phases), "actions": service_actions})
    if application_model and application_model['actions']:
        application_model['actions'][0]['dependsOn'] = sorted(action['id'] for action in service_actions
                                                             if action['type'] == 'SERVICE_VERIFY')
        if not service_actions:
            findings.append(_finding('APPLICATION_INFRASTRUCTURE_BARRIER_REQUIRED', 'applicationLibraries',
                                     'A mixed plan requires infrastructure Apply and Verify'))
            executable = False
        phases.append(dict(id='applications', order=len(phases), actions=application_model['actions']))
    semantic = {
        "apiVersion": plan_version,
        "planningProtocol": release["planningProtocol"],
        "projectIdentity": identity if explicit_identity else None,
        "projectRevision": snapshot.get("projectRevision"),
        "catalogDigest": catalog.get("digest"),
        "runtimeRelease": release,
        "artifactRequirements": artifact_requirements,
        "requiredCredentials": required_credentials,
        "pkiReissueEvidenceDigest": canonical_digest(reissue) if reissue else None,
        "phases": phases,
        "acknowledgements": [],
        "status": "EXECUTABLE" if executable else "BLOCKED",
    }
    if application_model:
        semantic['applicationFingerprint'] = application_model['semanticFingerprint']
        semantic['applicationSecretRequirements'] = application_model['runtimeSecretRequirements']
    plan_fingerprint = canonical_digest(semantic)
    plan = {
        "apiVersion": plan_version,
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
                if action['type'] in ('APPLICATION_LIBRARIES_APPLY', 'APPLICATION_LIBRARIES_VERIFY'):
                    manifest_operations.append(application_operation(action, application_model))
                    continue
                deployment = deployments.get(action.get("serviceDeployment"), {})
                definition = definitions.get(deployment.get("serviceType"), {}) if isinstance(deployment, dict) else {}
                entrypoint = "apply" if action["type"] == "SERVICE_APPLY" else "verify"
                role_entrypoint = ((definition.get("roleEntrypoints") or {}).get(entrypoint) or {}) if isinstance(definition, dict) else {}
                prefix = role_entrypoint.get("variablesPrefix") if isinstance(role_entrypoint, dict) else None
                item = {"operationId": action["id"], "phaseId": phase["id"], "operation": action["type"], "serviceDeployment": action.get("serviceDeployment"), "serviceType": deployment.get("serviceType") if isinstance(deployment, dict) else None, "requiresArtifactSources": action.get("serviceDeployment") in authority_deployments}
                if action["type"] == "PKI_REISSUE":
                    item["reissueRequests"] = [dict(value) for value in reissue]
                if action["type"] in ("SERVICE_APPLY", "SERVICE_VERIFY"):
                    item["targets"] = list(action["targets"])
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
        if application_model:
            manifest['apiVersion'] = APPLICATION_MANIFEST_VERSION
            manifest['applicationSecretRequirements'] = application_model['runtimeSecretRequirements']
            manifest['runtimeSecretDescriptorSetFingerprint'] = canonical_digest(
                dict(serviceDescriptors=descriptor_set, applicationDescriptors=application_model['runtimeSecretRequirements']))
        if execution_connections is not None:
            # Bind SSH trust only for hosts that an action in this exact plan
            # can contact. The target-free snapshot contains every inventory
            # target, which may be broader than service placement for this
            # plan; passing it through would require approval for unrelated
            # servers and disagree with Go's plan-scoped approval set.
            plan_target_ids = sorted({
                host_id
                for phase in phases
                for action in phase.get("actions", [])
                for host_id in action.get("targets", [])
            })
            manifest["targetConnections"] = {
                host_id: execution_connections[host_id]
                for host_id in plan_target_ids
                if host_id in execution_connections
            }
    result = {"deploymentPlan": plan, "executionManifest": manifest, "executionManifestDigest": canonical_digest(manifest) if manifest else None}
    if application_model and not manifest:
        # Private preparation data for A8, never registered as an executable manifest.
        result['applicationExecution'] = dict(
            apiVersion=APPLICATION_MANIFEST_VERSION,
            operations=[application_operation(action, application_model) for action in application_model['actions']],
            applicationSecretRequirements=application_model['runtimeSecretRequirements'])
    return result

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import hashlib
import os
import re

try:
    from .project_validation import canonical_digest
    from .service_integration_resolution import service_integration_relations
except ImportError:
    from project_validation import canonical_digest
    from service_integration_resolution import service_integration_relations


API_VERSION = "platform.installer/project-snapshot/v1alpha1"
GENERATED_PATH = "inventory/group_vars/all/platform-state.yml"
_SECRET_KEY = re.compile(r"password|passphrase|private.?key|token|secret", re.I)


def _logical(path):
    return path.replace("\\", "/")


def project_documents(project_root, installer_owned_paths=None):
    """Fingerprint canonical project bytes without parsing or rewriting them."""
    root = os.path.realpath(project_root)
    owned = set(_logical(item) for item in (installer_owned_paths or []))
    candidates = ["project.yml", "ansible.cfg", "inventory/hosts.yml"]
    try:
        from .application_libraries import package_inputs
    except ImportError:
        from application_libraries import package_inputs
    candidates.extend(package_inputs(root))
    for directory in ("inventory/group_vars", "inventory/host_vars"):
        absolute = os.path.join(root, directory.replace("/", os.sep))
        if not os.path.isdir(absolute):
            continue
        for current, dirs, files in os.walk(absolute):
            if any(os.path.islink(os.path.join(current, item)) for item in dirs):
                raise ValueError("Canonical project variable directories must not contain symlinks")
            dirs[:] = sorted(item for item in dirs if not os.path.islink(os.path.join(current, item)))
            for name in sorted(files):
                if os.path.splitext(name)[1].lower() in (".yml", ".yaml", ".json"):
                    candidates.append(_logical(os.path.relpath(os.path.join(current, name), root)))
    documents = []
    revision_parts = []
    for logical_path in sorted(set(candidates)):
        absolute = os.path.join(root, logical_path.replace("/", os.sep))
        if os.path.islink(absolute):
            raise ValueError("Canonical project documents must not be symlinks")
        if not os.path.isfile(absolute):
            continue
        with open(absolute, "rb") as stream:
            content = stream.read()
        generated = logical_path == GENERATED_PATH
        digest = "sha256:" + hashlib.sha256(content).hexdigest()
        documents.append({
            "logicalPath": logical_path,
            "digest": digest,
            "ownership": "GENERATED_READ_ONLY" if generated else (
                "INSTALLER_OWNED" if logical_path in owned else "USER_OWNED_READ_ONLY"
            ),
            "revisionIncluded": not generated,
        })
        if not generated:
            revision_parts.append(logical_path.encode("utf-8") + b"\0" + digest.encode("ascii") + b"\0")
    revision = "sha256:" + hashlib.sha256(b"".join(revision_parts)).hexdigest()
    return documents, revision


def redact(value, key=None):
    """Defence-in-depth redaction for every value crossing the query boundary."""
    if key and _SECRET_KEY.search(str(key)) and not str(key).lower().endswith(("secretref", "credentialref")):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {item: redact(value[item], item) for item in sorted(value)}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def _catalog_view(catalog):
    definitions = catalog.get("definitions", {}) if isinstance(catalog, dict) else {}
    result = {}
    for service_type, definition in sorted(definitions.items()):
        if not isinstance(definition, dict):
            continue
        if definition.get("x-conformanceOnly") is True:
            continue
        metadata = definition.get("metadata", {}) if isinstance(definition, dict) else {}
        result[service_type] = {
            "definitionVersion": metadata.get("version"),
            "displayName": metadata.get("displayName", service_type),
            "description": metadata.get("description"),
            "modes": sorted((definition.get("modes") or {}).keys()),
            "topology": definition.get("modes", {}),
            "capabilities": sorted(definition.get("capabilities") or []),
            "configuration": definition.get("configuration", {}),
            "endpoint": definition.get("endpoint"),
            "endpointProvider": definition.get("endpointProvider"),
            "compatibilityRef": definition.get("compatibilityRef"),
            "definitionDigest": definition.get("x-definitionDigest"),
        }
    return result


def _configuration_view(configuration, desired_state_path, role_default_paths, ownership):
    result = redact(configuration)
    for deployment_id, service in result.get("services", {}).items():
        service_type = service.get("serviceType")
        for setting_name, setting in service.get("configuration", {}).items():
            source = setting.get("source") if isinstance(setting, dict) else None
            logical_path = "serviceDeployments.%s.configuration.%s" % (deployment_id, setting_name)
            if source == "ROLE_DEFAULT":
                setting["physicalOrigin"] = {"kind": "ROLE_DEFAULT", "logicalPath": role_default_paths.get(service_type)}
                setting["editPolicy"] = "OVERRIDE"
                setting["semanticSource"] = "ROLE_DEFAULT"
                setting["logicalPath"] = logical_path
                if desired_state_path:
                    setting["overrideTarget"] = {"intendedDocument": desired_state_path, "logicalPath": logical_path}
            elif source == "DEPLOYMENT_OVERRIDE":
                setting["physicalOrigin"] = ({"kind": "GROUP_VARS", "logicalPath": desired_state_path}
                                             if desired_state_path else {"kind": "UNKNOWN"})
                setting["editPolicy"] = ("FUTURE_EDITABLE" if ownership.get(desired_state_path) == "INSTALLER_OWNED"
                                         else "READ_ONLY_UNRESOLVED" if not desired_state_path else "READ_ONLY")
                setting["semanticSource"] = "USER_PROJECT_VALUE"
                setting["logicalPath"] = logical_path
            else:
                setting.setdefault("editPolicy", "READ_ONLY_UNRESOLVED")
                setting.setdefault("semanticSource", source or "DERIVED")
                setting.setdefault("physicalOrigin", {"kind": "UNKNOWN"})
        for member in service.get("members", {}).values():
            for setting in member.get("configuration", {}).values():
                if isinstance(setting, dict) and setting.get("source") == "MEMBER_OVERRIDE":
                    setting["physicalOrigin"] = {"kind": "INVENTORY", "logicalPath": "inventory/hosts.yml"}
                    setting["editPolicy"] = "READ_ONLY"
                    setting["semanticSource"] = "USER_PROJECT_VALUE"
    return result


def _integration_view(desired_state, catalog, endpoint_result, haproxy_result, dns_result, hosts):
    deployments = desired_state.get("serviceDeployments", {}) if isinstance(desired_state, dict) else {}
    definitions = catalog.get("definitions", {}) if isinstance(catalog, dict) else {}
    providers = {}
    for deployment_id, deployment in sorted(deployments.items()):
        definition = definitions.get(deployment.get("serviceType"), {}) if isinstance(deployment, dict) else {}
        group_id = deployment.get("endpointGroupRef") if isinstance(deployment, dict) else None
        if group_id and isinstance(definition.get("endpointProvider"), dict):
            providers.setdefault(group_id, []).append({
                "deploymentId": deployment_id,
                "virtualAddresses": deployment.get("virtualAddresses", []),
                "status": "STATIC_VALID",
            })
    relations = service_integration_relations(desired_state, set(
        item.get("serviceType") for item in deployments.values() if isinstance(item, dict)
    ), inventory_deployments={host: value.get("platformDeployments", {}) for host, value in hosts.items()})
    for relation in relations:
        relation["endpoint"] = endpoint_result.get("endpoints", {}).get(relation["sourceDeploymentId"])
        relation["addressProviders"] = providers.get(relation.get("endpointGroupId"), [])
    return {
        "relations": relations,
        "addressProvidersByEndpointGroup": providers,
        "haproxyBackends": haproxy_result.get("backends", {}),
        "dnsZones": dns_result.get("zones", {}),
    }


def build_project_snapshot(project_id, project_name, documents, project_revision, catalog,
                           hosts, desired_state, topology_result, configuration_result,
                           endpoint_result, pki_result, haproxy_result,
                           dns_result, desired_state_path, role_default_paths, core_version="0.1.0", identity_source="PROJECT_MANIFEST", references=None):
    ownership = {item["logicalPath"]: item["ownership"] for item in documents}
    results = (topology_result, configuration_result, endpoint_result, pki_result, haproxy_result, dns_result)
    findings = []
    for item in results:
        findings.extend(item.get("findings", []) if isinstance(item, dict) else [])
    unique = {}
    for finding in findings:
        key = (finding.get("field", ""), finding.get("code", ""), finding.get("safeMessage", ""))
        unique[key] = finding
    findings = [unique[key] for key in sorted(unique)]
    blocking_findings = [item for item in findings if item.get("status") != "WARNING"]
    blocked = bool(blocking_findings)
    topology = topology_result.get("resolvedTopology") if topology_result.get("status") == "PASS" else None
    configuration = _configuration_view(configuration_result, desired_state_path, role_default_paths, ownership)
    requests = pki_result.get("requests", []) if pki_result.get("status") == "PASS" else []
    identities = [{key: item[key] for key in (
        "id", "scope", "tlsProfileId", "dnsNames", "ipAddresses", "consumers",
        "certificateRequestFingerprint") if key in item} for item in requests]
    deployments = desired_state.get("serviceDeployments", {}) if isinstance(desired_state, dict) else {}
    readiness = {}
    for deployment_id in sorted(deployments):
        affected = any(deployment_id in finding.get("field", "") for finding in blocking_findings)
        readiness[deployment_id] = {
            "status": "BLOCKED" if affected else "REQUIRES_PREPARATION",
            "runtime": "NOT_CHECKED",
        }
    validation = {
        "apiVersion": "platform.installer/validation-result/v1alpha1",
        "kind": "ValidationResult",
        "status": "BLOCKED" if blocked else "PASS",
        "summary": {"blocked": len(blocking_findings), "warning": len(findings) - len(blocking_findings), "pass": 0 if blocked else 1},
        "findings": findings,
    }
    snapshot = {
        "apiVersion": API_VERSION,
        "kind": "ProjectSnapshot",
        "status": "PARTIAL" if blocked else "PASS",
        "partial": blocked,
        "project": {"id": project_id, "name": project_name, "identitySource": identity_source},
        "projectRevision": project_revision,
        "catalogRevision": catalog.get("digest"),
        "coreVersion": core_version,
        "documents": documents,
        "hosts": {key: hosts[key] for key in sorted(hosts)},
        "references": redact(references if isinstance(references, dict) else {"hosts": {}}),
        "serviceCatalog": _catalog_view(catalog),
        "serviceDeployments": redact(deployments),
        "effectiveConfiguration": configuration,
        "endpointGroups": redact(desired_state.get("endpointGroups", {})),
        "topology": {"resolved": topology, "placementsByHost": {
            host_id: hosts[host_id].get("platformDeployments", {}) for host_id in sorted(hosts)
        }} if topology is not None else None,
        "endpoints": redact({
            "deployments": endpoint_result.get("endpoints", {}),
            "hosts": endpoint_result.get("hostEndpoints", {}),
        }),
        "integrations": redact(_integration_view(
            desired_state, catalog, endpoint_result, haproxy_result, dns_result, hosts,
        )),
        "pki": {"status": pki_result.get("status"), "certificateIdentities": redact(identities)},
        "validation": validation,
        "readiness": {"status": "BLOCKED" if blocked else "REQUIRES_PREPARATION", "services": readiness},
        "findings": findings,
    }
    snapshot["snapshotFingerprint"] = canonical_digest(snapshot)
    return redact(snapshot)

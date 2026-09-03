from __future__ import absolute_import, division, print_function

__metaclass__ = type

try:
    from .project_validation import canonical_digest
except ImportError:
    from project_validation import canonical_digest


BACKEND_FIELDS = set(("balance", "check", "fall", "rise", "ssl", "sslVerify"))


def _finding(code, field, message):
    return {"apiVersion": "platform.installer/finding/v1alpha1", "kind": "Finding",
            "code": code, "status": "BLOCKED", "category": "haproxy-resolution",
            "field": field, "safeMessage": message}


def _definitions(catalog):
    value = catalog.get("definitions", catalog) if isinstance(catalog, dict) else {}
    return value if isinstance(value, dict) else {}


def _catalog_default_port(definition):
    listeners = definition.get("listeners", {}) if isinstance(definition, dict) else {}
    candidates = [
        value.get("defaultPort")
        for value in listeners.values()
        if isinstance(value, dict) and value.get("scope") == "deployment"
        and isinstance(value.get("defaultPort"), int)
    ]
    return candidates[0] if len(candidates) == 1 else None


def normalize_backend_settings(defaults, override, field):
    defaults = defaults if isinstance(defaults, dict) else {}
    override = override if isinstance(override, dict) else {}
    findings = []
    for layer, name in ((defaults, "defaults"), (override, "backend")):
        unknown = sorted(set(layer).difference(BACKEND_FIELDS))
        for key in unknown:
            findings.append(_finding("HAPROXY_BACKEND_PROPERTY_UNKNOWN", field + "." + name + "." + key, "BackendSettings contains an unsupported property"))
    effective = dict(defaults)
    effective.update(override)
    if effective.get("ssl") is False:
        effective.pop("sslVerify", None)
    if effective.get("check") is False:
        effective.pop("fall", None)
        effective.pop("rise", None)
    if not isinstance(effective.get("balance"), str) or effective.get("balance") not in ("roundrobin", "leastconn", "source"):
        findings.append(_finding("HAPROXY_BACKEND_BALANCE_INVALID", field, "Effective BackendSettings balance must be roundrobin, leastconn or source"))
    for key in ("ssl", "check"):
        if not isinstance(effective.get(key), bool):
            findings.append(_finding("HAPROXY_BACKEND_%s_INVALID" % key.upper(), field, "Effective BackendSettings %s must be boolean" % key))
    if effective.get("ssl") is True and effective.get("sslVerify") not in ("required", "none"):
        findings.append(_finding("HAPROXY_BACKEND_SSL_VERIFY_REQUIRED", field, "TLS backend settings require sslVerify"))
    if effective.get("ssl") is False and "sslVerify" in effective:
        findings.append(_finding("HAPROXY_BACKEND_SSL_VERIFY_FORBIDDEN", field, "sslVerify is valid only when ssl is true"))
    if effective.get("check") is True:
        for key in ("fall", "rise"):
            if not isinstance(effective.get(key), int) or not 1 <= effective[key] <= 20:
                findings.append(_finding("HAPROXY_BACKEND_%s_REQUIRED" % key.upper(), field, "Health checks require %s between 1 and 20" % key))
    if effective.get("check") is False and ("fall" in effective or "rise" in effective):
        findings.append(_finding("HAPROXY_BACKEND_CHECK_DEPENDENCY_FORBIDDEN", field, "fall and rise are valid only when check is true"))
    return effective, findings


def resolve_haproxy_backends(topology, service_catalog, inventory_hosts, inventory_deployments,
                             resolved_endpoints, backend_defaults=None, resolved_configuration=None):
    topology = topology if isinstance(topology, dict) else {}
    deployments = topology.get("serviceDeployments", {}) if isinstance(topology.get("serviceDeployments"), dict) else {}
    definitions = _definitions(service_catalog)
    inventory_hosts = inventory_hosts if isinstance(inventory_hosts, dict) else {}
    inventory_deployments = inventory_deployments if isinstance(inventory_deployments, dict) else {}
    endpoint_map = resolved_endpoints.get("endpoints", {}) if isinstance(resolved_endpoints, dict) else {}
    findings, resolved = [], {}
    for target_id, target in sorted(deployments.items()):
        relation = target.get("haproxy") if isinstance(target, dict) else None
        if relation is None:
            continue
        field = "serviceDeployments.%s.haproxy" % target_id
        if not isinstance(relation, dict) or set(relation).difference(("deploymentRef", "backend")):
            findings.append(_finding("HAPROXY_INTEGRATION_INVALID", field, "HAProxy integration must contain only deploymentRef and backend"))
            continue
        haproxy_id = relation.get("deploymentRef")
        proxy = deployments.get(haproxy_id)
        if not isinstance(proxy, dict):
            findings.append(_finding("HAPROXY_DEPLOYMENT_NOT_FOUND", field + ".deploymentRef", "HAProxy deployment reference is not defined"))
            continue
        if proxy.get("serviceType") != "haproxy":
            findings.append(_finding("HAPROXY_DEPLOYMENT_TYPE_INVALID", field + ".deploymentRef", "HAProxy deployment reference must select serviceType haproxy"))
            continue
        definition = definitions.get(target.get("serviceType"), {})
        if not isinstance(definition.get("endpoint"), dict):
            findings.append(_finding("HAPROXY_TARGET_ENDPOINT_UNSUPPORTED", field, "HAProxy target service must support generic endpoints"))
        if not target.get("endpointGroup") or not proxy.get("endpointGroup"):
            findings.append(_finding("HAPROXY_ENDPOINT_GROUP_REQUIRED", field, "HAProxy target and deployment require endpointGroup"))
        elif target.get("endpointGroup") != proxy.get("endpointGroup"):
            findings.append(_finding("HAPROXY_ENDPOINT_GROUP_MISMATCH", field, "HAProxy target and deployment must use the same endpoint group"))
        configuration = target.get("configuration", {}) if isinstance(target.get("configuration"), dict) else {}
        port = configuration.get("port")
        if not isinstance(port, int):
            effective = (((resolved_configuration or {}).get("services", {}).get(target_id, {})
                          .get("configuration", {}).get("port", {})))
            port = effective.get("value") if isinstance(effective, dict) else None
        if not isinstance(port, int):
            port = _catalog_default_port(definition)
        if not isinstance(port, int) or not 1 <= port <= 65535:
            findings.append(_finding("HAPROXY_BACKEND_PORT_UNRESOLVED", "serviceDeployments.%s.configuration.port" % target_id, "HAProxy target requires a valid configuration.port"))
        defaults = (backend_defaults or {}).get(target.get("serviceType"), {})
        effective, setting_findings = normalize_backend_settings(defaults, relation.get("backend", {}), field)
        findings.extend(setting_findings)
        if findings:
            continue
        targets = []
        for host_id, placements in sorted(inventory_deployments.items()):
            if isinstance(placements, dict) and target_id in placements:
                values = inventory_hosts.get(host_id, {}) if isinstance(inventory_hosts.get(host_id), dict) else {}
                targets.append({"hostId": host_id, "address": values.get("ansible_host", host_id), "port": port, "serverName": host_id})
        for member_id, member in sorted((target.get("members", {}) if isinstance(target.get("members"), dict) else {}).items()):
            host_id = member.get("host") if isinstance(member, dict) else None
            if isinstance(host_id, str):
                values = inventory_hosts.get(host_id, {}) if isinstance(inventory_hosts.get(host_id), dict) else {}
                targets.append({"hostId": host_id, "address": values.get("ansible_host", host_id), "port": port, "serverName": host_id})
        targets = sorted({item["hostId"]: item for item in targets}.values(), key=lambda item: item["hostId"])
        if not targets:
            findings.append(_finding("HAPROXY_BACKEND_TARGETS_UNRESOLVED", field, "HAProxy target has no resolved host placements"))
            continue
        endpoint_group_id = target.get("endpointGroup")
        record = {"targetDeploymentId": target_id, "backendName": "%s-%s" % (target_id, endpoint_group_id),
                  "configFileName": "30-backend-%s-%s.cfg" % (target_id, endpoint_group_id),
                  "endpoint": endpoint_map.get(target_id, {}), "settings": effective, "targets": targets}
        record["fingerprint"] = canonical_digest(record)
        resolved.setdefault(haproxy_id, []).append(record)
    if findings:
        resolved = {}
    return {"apiVersion": "platform.installer/resolved-haproxy-backend/v1alpha1", "kind": "ResolvedHAProxyBackends",
            "backends": {key: sorted(value, key=lambda item: item["backendName"]) for key, value in sorted(resolved.items())},
            "fingerprint": canonical_digest(resolved), "findings": sorted(findings, key=lambda item: (item["field"], item["code"])),
            "status": "BLOCKED" if findings else "PASS"}

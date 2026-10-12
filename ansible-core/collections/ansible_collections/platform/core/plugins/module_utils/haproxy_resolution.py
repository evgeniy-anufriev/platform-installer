from __future__ import absolute_import, division, print_function

__metaclass__ = type

import re
import ipaddress

try:
    from .project_validation import canonical_digest
    from .service_integration_resolution import haproxy_provider_hosts
except ImportError:
    from project_validation import canonical_digest
    from service_integration_resolution import haproxy_provider_hosts


BACKEND_FIELDS = set(("balance", "check", "fall", "rise", "ssl", "sslVerify",
                      "checkInterval", "httpCheck", "maxconn", "timeoutConnect", "timeoutServer"))


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


def _valid_port(value):
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 65535


def _valid_endpoint_target(target):
    if not isinstance(target, dict) or not _valid_port(target.get('port')):
        return False
    try:
        return (ipaddress.ip_address(target.get('address')).version == 4 and
                isinstance(target.get('serverName'), str) and
                re.fullmatch(r'[a-zA-Z0-9_.-]{1,128}', target['serverName']) is not None)
    except (ValueError, TypeError):
        return False


def _member_client_allocation(definition):
    descriptor = definition.get("x-backendClientListener") if isinstance(definition, dict) else None
    if descriptor is None:
        return None
    if not isinstance(descriptor, dict) or set(descriptor) != {"listener", "allocation"}:
        raise ValueError("HAPROXY_CLIENT_LISTENER_DESCRIPTOR_INVALID")
    listener_name = descriptor.get("listener")
    listeners = definition.get("listeners")
    if not isinstance(listener_name, str) or not isinstance(listeners, dict):
        raise ValueError("HAPROXY_CLIENT_LISTENER_DESCRIPTOR_INVALID")
    listener = listeners.get(listener_name)
    allocation = descriptor["allocation"]
    settings = (definition.get("configuration") or {}).get("settings", {})
    port_setting = settings.get("port") if isinstance(settings, dict) else None
    if (not isinstance(listener, dict) or listener.get("scope") != "member" or
            not _valid_port(listener.get("defaultPort")) or
            not isinstance(allocation, dict) or set(allocation) != {"kind", "stride"} or
            allocation.get("kind") != "HOST_LOCAL_ORDINAL" or
            not _valid_port(allocation.get("stride")) or
            not isinstance(port_setting, dict) or
            "member" not in port_setting.get("scopes", [])):
        raise ValueError("HAPROXY_CLIENT_LISTENER_DESCRIPTOR_INVALID")
    return allocation["stride"]


def _inventory_members_for_deployment(inventory_deployments, deployment_id):
    """Build the ephemeral member view from inventory-owned placements."""
    members = {}
    duplicate_ids = set()
    source = inventory_deployments if isinstance(inventory_deployments, dict) else {}
    for host_id in sorted(source):
        placements = source.get(host_id)
        placement = placements.get(deployment_id) if isinstance(placements, dict) else None
        candidate_members = placement.get("members") if isinstance(placement, dict) else None
        if not isinstance(candidate_members, dict):
            continue
        for member_id, member in sorted(candidate_members.items()):
            if member_id in members:
                duplicate_ids.add(member_id)
                continue
            if not isinstance(member, dict):
                continue
            projected = dict(member)
            # Inventory ownership is authoritative for the target host.
            projected["host"] = host_id
            members[member_id] = projected
    return members, sorted(duplicate_ids)


def _safe_dns_name(value):
    return (isinstance(value, str) and 1 <= len(value) <= 253 and
            all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                for label in value.split(".")))


def _request_dns_covers_name(dns_names, expected_name):
    """Accept an exact SAN or a wildcard covering exactly one DNS label."""
    if not isinstance(dns_names, list) or not _safe_dns_name(expected_name):
        return False
    for candidate in dns_names:
        if candidate == expected_name:
            return True
        if isinstance(candidate, str) and candidate.startswith("*.") and _safe_dns_name(candidate[2:]):
            suffix = candidate[1:]
            if expected_name.endswith(suffix) and "." not in expected_name[:-len(suffix)]:
                return True
    return False


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
    for key in ('checkInterval', 'timeoutConnect', 'timeoutServer'):
        if key in effective:
            value = effective[key]
            match = re.fullmatch(r'([1-9][0-9]*)(ms|s)', value) if isinstance(value, str) else None
            millis = int(match[1]) * (1000 if match[2] == 's' else 1) if match else 0
            if not 100 <= millis <= (60000 if key == 'checkInterval' else 300000):
                findings.append(_finding('HAPROXY_BACKEND_DURATION_INVALID', field + '.' + key, 'Invalid bounded duration'))
    if 'maxconn' in effective and (type(effective['maxconn']) is not int or not 1 <= effective['maxconn'] <= 100000):
        findings.append(_finding('HAPROXY_BACKEND_MAXCONN_INVALID', field, 'Invalid maxconn'))
    if 'httpCheck' in effective:
        check = effective['httpCheck']
        if (not isinstance(check, dict) or set(check) != {'method', 'path', 'expectedStatus'} or
                check.get('method') not in {'GET', 'HEAD'} or
                not isinstance(check.get('path'), str) or not re.fullmatch(r'/[^\s\x00-\x1f\x7f]{0,2047}', check['path']) or
                type(check.get('expectedStatus')) is not int or not 100 <= check['expectedStatus'] <= 599 or
                effective.get('check') is not True):
            findings.append(_finding('HAPROXY_BACKEND_HTTP_CHECK_INVALID', field, 'Invalid HTTP health check'))
    return effective, findings


def resolve_haproxy_backends(topology, service_catalog, inventory_hosts, inventory_deployments,
                             resolved_endpoints, backend_defaults=None, resolved_configuration=None,
                             pki_requests=None, target_deployment_ids=None, endpoint_sources=None):
    topology = topology if isinstance(topology, dict) else {}
    deployments = topology.get("serviceDeployments", {}) if isinstance(topology.get("serviceDeployments"), dict) else {}
    definitions = _definitions(service_catalog)
    inventory_hosts = inventory_hosts if isinstance(inventory_hosts, dict) else {}
    inventory_deployments = inventory_deployments if isinstance(inventory_deployments, dict) else {}
    endpoint_map = resolved_endpoints.get("endpoints", {}) if isinstance(resolved_endpoints, dict) else {}
    selected_ids = set(target_deployment_ids) if isinstance(target_deployment_ids, list) else None
    findings, resolved = [], {}
    for target_id, target in sorted(deployments.items()):
        if selected_ids is not None and target_id not in selected_ids:
            continue
        proxy_hosts = haproxy_provider_hosts(topology, inventory_deployments, target)
        if not proxy_hosts:
            continue
        relation = target.get("haproxy", {})
        field = "serviceDeployments.%s.haproxy" % target_id
        if not isinstance(relation, dict) or set(relation).difference(("deploymentRef", "backend")):
            findings.append(_finding("HAPROXY_INTEGRATION_INVALID", field, "HAProxy integration must contain only deploymentRef and backend"))
            continue
        definition = definitions.get(target.get("serviceType"), {})
        if not isinstance(definition.get("endpoint"), dict):
            findings.append(_finding("HAPROXY_TARGET_ENDPOINT_UNSUPPORTED", field, "HAProxy target service must support generic endpoints"))
        try:
            member_stride = _member_client_allocation(definition)
        except ValueError:
            findings.append(_finding("HAPROXY_CLIENT_LISTENER_DESCRIPTOR_INVALID", field, "Client listener metadata is invalid"))
            continue
        configuration = target.get("configuration", {}) if isinstance(target.get("configuration"), dict) else {}
        port = configuration.get("port")
        if not _valid_port(port):
            effective = (((resolved_configuration or {}).get("services", {}).get(target_id, {})
                          .get("configuration", {}).get("port", {})))
            port = effective.get("value") if isinstance(effective, dict) else None
        if not _valid_port(port):
            if member_stride is not None:
                port = definition["listeners"][definition["x-backendClientListener"]["listener"]]["defaultPort"]
            else:
                port = _catalog_default_port(definition)
        if not _valid_port(port):
            findings.append(_finding("HAPROXY_BACKEND_PORT_UNRESOLVED", "serviceDeployments.%s.configuration.port" % target_id, "HAProxy target requires a valid configuration.port"))
        package_defaults = definition.get("x-haproxyBackendDefaults", {})
        if not isinstance(package_defaults, dict):
            findings.append(_finding("HAPROXY_BACKEND_DEFAULTS_INVALID", field, "Service package backend defaults must be a mapping"))
            continue
        defaults = dict(package_defaults)
        defaults.update((backend_defaults or {}).get(target.get("serviceType"), {}))
        effective, setting_findings = normalize_backend_settings(defaults, relation.get("backend", {}), field)
        findings.extend(setting_findings)
        if findings:
            continue
        targets = []
        if member_stride is None:
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
        else:
            host_counts, used = {}, set()
            members = target.get("members", {}) if isinstance(target.get("members"), dict) else {}
            if not members:
                members, duplicate_member_ids = _inventory_members_for_deployment(
                    inventory_deployments, target_id
                )
                if duplicate_member_ids:
                    findings.append(_finding(
                        "HAPROXY_BACKEND_TARGETS_UNRESOLVED",
                        field,
                        "Inventory-owned deployment members are duplicated",
                    ))
            for member_id, member in sorted(members.items()):
                host_id = member.get("host") if isinstance(member, dict) else None
                if not isinstance(host_id, str) or host_id not in inventory_hosts:
                    findings.append(_finding("HAPROXY_BACKEND_TARGETS_UNRESOLVED", field, "Member host cannot be resolved"))
                    break
                member_config = member.get("configuration", {}) if isinstance(member.get("configuration"), dict) else {}
                explicit = member_config.get("port")
                if explicit is None:
                    resolved_member = (((resolved_configuration or {}).get("services", {}).get(target_id, {})
                                        .get("members", {}).get(member_id, {}).get("configuration", {}).get("port")))
                    if isinstance(resolved_member, dict) and resolved_member.get("source") == "MEMBER_OVERRIDE":
                        explicit = resolved_member.get("value")
                member_port = explicit if explicit is not None else port + member_stride * host_counts.get(host_id, 0)
                if not _valid_port(member_port) or (host_id, member_port) in used:
                    findings.append(_finding("HAPROXY_BACKEND_PORT_COLLISION", field, "Member client ports collide or exceed valid range"))
                    break
                host_counts[host_id] = host_counts.get(host_id, 0) + 1
                used.add((host_id, member_port))
                values = inventory_hosts[host_id]
                targets.append({"hostId": host_id, "memberId": member_id,
                                "address": values.get("ansible_host", host_id) if isinstance(values, dict) else host_id,
                                "port": member_port, "serverName": member_id})
            if findings:
                continue
        if not targets:
            findings.append(_finding("HAPROXY_BACKEND_TARGETS_UNRESOLVED", field, "HAProxy target has no resolved host placements"))
            continue
        endpoint_group_id = target.get("endpointGroup")
        expected_name = None
        if member_stride is not None and effective.get("ssl") is True and effective.get("sslVerify") == "required":
            endpoint = endpoint_map.get(target_id, {})
            expected_name = endpoint.get("fqdn") if isinstance(endpoint, dict) else None
            if not _safe_dns_name(expected_name):
                findings.append(_finding("HAPROXY_BACKEND_TLS_IDENTITY_UNRESOLVED", field, "Backend TLS identity is unavailable"))
                continue
            if pki_requests is not None:
                for member_target in targets:
                    matched = any(
                        isinstance(request, dict) and
                        _request_dns_covers_name(request.get("dnsNames"), expected_name) and
                        any(isinstance(consumer, dict) and
                            consumer.get("deploymentId") == target_id and
                            consumer.get("memberId") == member_target["memberId"] and
                            consumer.get("hostId") == member_target["hostId"]
                            for consumer in request.get("consumers", []))
                        for request in pki_requests
                    )
                    if not matched:
                        findings.append(_finding("HAPROXY_BACKEND_TLS_IDENTITY_UNRESOLVED", field, "Backend certificate request lacks the endpoint DNS identity"))
                        break
                if findings:
                    continue
        record = {"targetDeploymentId": target_id, "backendName": "%s-%s" % (target_id, endpoint_group_id),
                  "configFileName": "30-backend-%s-%s.cfg" % (target_id, endpoint_group_id),
                  "endpoint": endpoint_map.get(target_id, {}), "settings": effective, "targets": targets}
        if expected_name is not None:
            record["expectedServerName"] = expected_name
        for haproxy_id, provider_hosts in sorted(proxy_hosts.items()):
            provider_record = dict(record, providerHostIds=provider_hosts)
            provider_record["fingerprint"] = canonical_digest(provider_record)
            resolved.setdefault(haproxy_id, []).append(provider_record)
    for source_id, source in sorted((endpoint_sources or {}).items()):
        if selected_ids is not None and source_id not in selected_ids:
            continue
        endpoint = endpoint_map.get(source_id, {})
        group_id = endpoint.get('endpointGroupId')
        proxy_hosts = haproxy_provider_hosts(topology, inventory_deployments, {'endpointGroup': group_id})
        effective, errors = normalize_backend_settings({}, source.get('settings', {}), 'endpointSources.' + source_id)
        findings.extend(errors)
        targets = source.get('targets', [])
        if not targets or not isinstance(targets, list) or any(not _valid_endpoint_target(t) for t in targets):
            findings.append(_finding('HAPROXY_BACKEND_TARGETS_UNRESOLVED', 'endpointSources.' + source_id, 'Invalid endpoint targets'))
        if not endpoint:
            findings.append(_finding('HAPROXY_TARGET_ENDPOINT_UNSUPPORTED', 'endpointSources.' + source_id, 'Endpoint source is unresolved'))
        record = {'targetDeploymentId': source_id, 'backendName': source_id + '-' + str(group_id),
                  'configFileName': '30-backend-' + source_id + '-' + str(group_id) + '.cfg',
                  'endpoint': endpoint, 'settings': effective, 'targets': targets}
        if source.get('probe'):
            record['probe'] = source['probe']
        if effective.get('ssl'):
            if effective.get('sslVerify') != 'required':
                findings.append(_finding('HAPROXY_BACKEND_SSL_VERIFY_REQUIRED', 'endpointSources.' + source_id, 'Endpoint TLS requires verified identity'))
            record['expectedServerName'] = endpoint.get('fqdn')
        for provider_id, provider_hosts in sorted(proxy_hosts.items()):
            value = dict(record, providerHostIds=provider_hosts)
            value['fingerprint'] = canonical_digest(value)
            resolved.setdefault(provider_id, []).append(value)
    if findings:
        resolved = {}
    return {"apiVersion": "platform.installer/resolved-haproxy-backend/v1alpha1", "kind": "ResolvedHAProxyBackends",
            "backends": {key: sorted(value, key=lambda item: item["backendName"]) for key, value in sorted(resolved.items())},
            "fingerprint": canonical_digest(resolved), "findings": sorted(findings, key=lambda item: (item["field"], item["code"])),
            "status": "BLOCKED" if findings else "PASS"}

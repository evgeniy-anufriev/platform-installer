from __future__ import absolute_import, division, print_function

__metaclass__ = type

"""Pure NET-03 authoritative DNS projection.

This module deliberately accepts only canonical desired/inventory inputs.  It
does not read BIND configuration, generated state, facts, or the network.
"""

import ipaddress

try:
    from .project_validation import canonical_digest
    from .service_endpoint_resolution import DNS_DOMAIN, DNS_LABEL, resolve_service_endpoints
except ImportError:
    from project_validation import canonical_digest
    from service_endpoint_resolution import DNS_DOMAIN, DNS_LABEL, resolve_service_endpoints


API_VERSION = "platform.installer/resolved-dns-zone/v1alpha1"


def _finding(code, field, message, details=None):
    value = {
        "apiVersion": "platform.installer/finding/v1alpha1", "kind": "Finding",
        "code": code, "status": "BLOCKED", "category": "dns-resolution",
        "field": field, "safeMessage": message,
    }
    if details:
        value["safeDetails"] = details
    return value


def _definitions(catalog):
    value = catalog.get("definitions", catalog) if isinstance(catalog, dict) else {}
    return value if isinstance(value, dict) else {}


def _ipv4(value):
    try:
        parsed = ipaddress.ip_address(value)
        return str(parsed) if parsed.version == 4 else None
    except ValueError:
        return None


def _inside(name, zone):
    return name == zone or name.endswith("." + zone)


def _record(owner, record_type, values):
    return {"owner": owner + ".", "type": record_type, "values": sorted(values)}


def _provider_addresses(deployments, definitions, endpoint_group, findings):
    providers = []
    for deployment_id, deployment in sorted(deployments.items()):
        definition = definitions.get(deployment.get("serviceType")) if isinstance(deployment, dict) else None
        if not isinstance(deployment, dict) or not isinstance(definition, dict):
            continue
        if not isinstance(definition.get("endpointProvider"), dict) or deployment.get("endpointGroupRef") != endpoint_group:
            continue
        addresses = []
        for index, item in enumerate(deployment.get("virtualAddresses", [])):
            address = _ipv4(item.get("address")) if isinstance(item, dict) else None
            if address is None:
                findings.append(_finding("DNS_PROVIDER_ADDRESS_INVALID", "serviceDeployments.%s.virtualAddresses.%d.address" % (deployment_id, index), "Endpoint address provider must expose an IPv4 virtual address"))
            else:
                addresses.append(address)
        providers.append((deployment_id, sorted(set(addresses))))
    if len(providers) != 1:
        return None, providers
    return providers[0][1], providers


def resolve_dns_zones(desired_state, service_catalog, inventory_hosts, inventory_deployments):
    """Return deterministic BIND zones for all declared BIND deployments."""
    desired_state = desired_state if isinstance(desired_state, dict) else {}
    deployments = desired_state.get("serviceDeployments", {})
    deployments = deployments if isinstance(deployments, dict) else {}
    groups = desired_state.get("endpointGroups", {})
    groups = groups if isinstance(groups, dict) else {}
    definitions = _definitions(service_catalog)
    inventory_hosts = inventory_hosts if isinstance(inventory_hosts, dict) else {}
    inventory_deployments = inventory_deployments if isinstance(inventory_deployments, dict) else {}
    findings, zones = [], {}

    endpoint_projection = resolve_service_endpoints(desired_state, service_catalog)
    findings.extend(endpoint_projection.get("findings", []))
    endpoints = endpoint_projection.get("endpoints", {}) if endpoint_projection.get("status") == "PASS" else {}

    # Host records are mandatory for every canonical project host, even when a
    # malformed DNS participant would otherwise short-circuit a zone.
    for host_id, host in sorted(inventory_hosts.items()):
        if not isinstance(host_id, str) or not DNS_LABEL.match(host_id):
            findings.append(_finding("DNS_HOST_ID_INVALID", "inventory.%s" % host_id, "Project host id must be a lowercase DNS label"))
        address = _ipv4(host.get("ansible_host")) if isinstance(host, dict) else None
        if address is None:
            findings.append(_finding("DNS_HOST_ADDRESS_UNRESOLVED", "inventory.%s.ansible_host" % host_id, "Every project host requires a deterministic IPv4 inventory address"))

    for deployment_id, deployment in sorted(deployments.items()):
        if not isinstance(deployment, dict) or deployment.get("serviceType") != "bind":
            continue
        prefix = "serviceDeployments.%s" % deployment_id
        configuration = deployment.get("configuration", {}) if isinstance(deployment.get("configuration"), dict) else {}
        zone = configuration.get("zone")
        ttl = configuration.get("defaultTtl")
        if not isinstance(zone, str) or not DNS_DOMAIN.match(zone):
            findings.append(_finding("DNS_ZONE_INVALID", prefix + ".configuration.zone", "Managed DNS zone must be a lowercase fully qualified domain"))
            continue
        if not isinstance(ttl, int) or ttl < 1 or ttl > 2147483647:
            findings.append(_finding("DNS_DEFAULT_TTL_INVALID", prefix + ".configuration.defaultTtl", "Managed DNS defaultTtl must be a positive integer"))
            continue

        participants = []
        for host_id, host_deployments in sorted(inventory_deployments.items()):
            local = host_deployments.get(deployment_id) if isinstance(host_deployments, dict) else None
            if not isinstance(local, dict):
                continue
            roles = local.get("roles", [])
            if not isinstance(roles, list) or any(role not in ("primary", "secondary") for role in roles) or len(roles) != 1:
                findings.append(_finding("DNS_PARTICIPANT_ROLE_INVALID", "platform_deployments.%s.%s.roles" % (host_id, deployment_id), "BIND participant must have exactly one supported role: primary or secondary"))
                continue
            address = _ipv4((inventory_hosts.get(host_id) or {}).get("ansible_host"))
            if address is None:
                findings.append(_finding("DNS_HOST_ADDRESS_UNRESOLVED", "inventory.%s.ansible_host" % host_id, "DNS participant requires a deterministic IPv4 inventory address"))
                continue
            participants.append({"hostId": host_id, "address": address, "role": roles[0], "fqdn": "%s.%s" % (host_id, zone)})
        primaries = [item for item in participants if item["role"] == "primary"]
        secondaries = [item for item in participants if item["role"] == "secondary"]
        if len(primaries) != 1:
            findings.append(_finding("DNS_PRIMARY_COUNT_INVALID", prefix, "BIND deployment requires exactly one primary participant", {"actual": len(primaries)}))
        if not secondaries:
            findings.append(_finding("DNS_SECONDARY_REQUIRED", prefix, "BIND deployment requires at least one secondary participant"))
        if len(primaries) != 1 or not secondaries:
            continue

        records, owners = [], {}
        for host_id, host in sorted(inventory_hosts.items()):
            address = _ipv4(host.get("ansible_host")) if isinstance(host, dict) else None
            if not isinstance(host_id, str) or not DNS_LABEL.match(host_id) or address is None:
                continue
            owner = "%s.%s" % (host_id, zone)
            owners[owner] = {address}

        endpoint_groups = sorted(set(item.get("endpointGroupId") for item in endpoints.values() if isinstance(item, dict)))
        provider_values = {}
        for group_id in endpoint_groups:
            group = groups.get(group_id, {})
            domain = (group.get("address") or {}).get("domain") if isinstance(group, dict) else None
            if not isinstance(domain, str) or not _inside(domain, zone):
                findings.append(_finding("DNS_ENDPOINT_GROUP_OUTSIDE_ZONE", "endpointGroups.%s.address.domain" % group_id, "Endpoint group domain must equal or descend from the managed zone", {"zone": zone}))
                continue
            addresses, providers = _provider_addresses(deployments, definitions, group_id, findings)
            if len(providers) == 0:
                findings.append(_finding("DNS_ENDPOINT_ADDRESS_UNRESOLVED", "endpointGroups.%s" % group_id, "Endpoint group has endpoint services but no active address provider"))
                continue
            if len(providers) > 1:
                findings.append(_finding("DNS_ENDPOINT_PROVIDER_AMBIGUOUS", "endpointGroups.%s" % group_id, "Endpoint group has more than one active address provider", {"deployments": [item[0] for item in providers]}))
                continue
            provider_values[group_id] = addresses

        for endpoint_id, endpoint in sorted(endpoints.items()):
            group_id = endpoint.get("endpointGroupId")
            addresses = provider_values.get(group_id)
            if not addresses:
                continue
            owner = endpoint["fqdn"]
            if owner in owners and owners[owner] != set(addresses):
                findings.append(_finding("DNS_RECORD_COLLISION", "serviceDeployments.%s.endpointGroup" % endpoint_id, "Endpoint DNS name collides with an incompatible host record", {"fqdn": owner}))
                continue
            owners[owner] = set(addresses)
            group = groups[group_id]
            if (group.get("address") or {}).get("wildcard") is True:
                wildcard = "*.%s" % (group["address"]["domain"])
                if wildcard in owners and owners[wildcard] != set(addresses):
                    findings.append(_finding("DNS_RECORD_COLLISION", "endpointGroups.%s.address.wildcard" % group_id, "Wildcard DNS name has incompatible address ownership", {"fqdn": wildcard}))
                else:
                    owners[wildcard] = set(addresses)

        if findings:
            continue
        for owner, addresses in sorted(owners.items()):
            records.append(_record(owner, "A", addresses))
        ns_hosts = sorted(item["fqdn"] for item in participants)
        primary = primaries[0]
        logical = {
            "zone": zone, "defaultTtl": ttl, "mname": primary["fqdn"], "rname": "hostmaster.%s" % zone,
            "nameservers": ns_hosts, "primary": primary,
            "secondaries": sorted(secondaries, key=lambda item: item["hostId"]), "records": records,
        }
        logical["contentFingerprint"] = canonical_digest(logical)
        zones[deployment_id] = logical

    if findings:
        zones = {}
    return {"apiVersion": API_VERSION, "kind": "ResolvedDnsZones", "status": "BLOCKED" if findings else "PASS", "zones": zones, "findings": sorted(findings, key=lambda item: (item["field"], item["code"]))}

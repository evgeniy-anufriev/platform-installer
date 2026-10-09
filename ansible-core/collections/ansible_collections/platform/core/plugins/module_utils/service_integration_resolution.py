from __future__ import absolute_import, division, print_function

__metaclass__ = type

try:
    from .project_validation import canonical_digest
except ImportError:
    from project_validation import canonical_digest


def haproxy_provider_hosts(desired_state, inventory_deployments, source):
    """Select desired HAProxy placements through the endpoint's Keepalived hosts."""
    deployments = desired_state.get("serviceDeployments", {})
    group_id = source.get("endpointGroup") if isinstance(source, dict) else None
    if not group_id or source.get("serviceType") == "haproxy":
        return {}
    placements = inventory_deployments if isinstance(inventory_deployments, dict) else {}
    keepalived_ids = {key for key, value in deployments.items()
                      if isinstance(value, dict) and value.get("serviceType") == "keepalived"
                      and value.get("endpointGroupRef") == group_id}
    vip_hosts = {host for host, values in placements.items()
                 if isinstance(values, dict) and keepalived_ids.intersection(values)}
    return {key: sorted(host for host in vip_hosts
                        if key in placements[host])
            for key, value in sorted(deployments.items())
            if isinstance(value, dict) and value.get("serviceType") == "haproxy"
            and value.get("endpointGroup") == group_id
            and any(key in placements[host] for host in vip_hosts)}


def service_integration_relations(desired_state, source_service_types=None, source_deployment_id=None,
                                  inventory_deployments=None):
    """Return deterministic source-to-provider relations from canonical state."""
    desired_state = desired_state if isinstance(desired_state, dict) else {}
    deployments = desired_state.get("serviceDeployments", {})
    deployments = deployments if isinstance(deployments, dict) else {}
    groups = desired_state.get("endpointGroups", {})
    groups = groups if isinstance(groups, dict) else {}
    source_service_types = set(source_service_types or [])
    relations = []

    for source_id, source in sorted(deployments.items()):
        if source_deployment_id is not None and source_id != source_deployment_id:
            continue
        if not isinstance(source, dict) or source.get("serviceType") not in source_service_types:
            if source_deployment_id is None or not isinstance(source, dict):
                continue
        dns_deployments = set()
        endpoint_group_id = source.get("endpointGroup")
        endpoint_group = groups.get(endpoint_group_id)
        address = endpoint_group.get("address") if isinstance(endpoint_group, dict) else {}
        domain = address.get("domain") if isinstance(address, dict) else None
        if isinstance(domain, str):
            for provider_id, provider in sorted(deployments.items()):
                configuration = provider.get("configuration", {}) if isinstance(provider, dict) else {}
                zone = configuration.get("zone") if isinstance(configuration, dict) else None
                if (isinstance(provider, dict) and provider.get("serviceType") == "bind"
                        and isinstance(zone, str) and (domain == zone or domain.endswith("." + zone))):
                    dns_deployments.add(provider_id)
        proxy_hosts = haproxy_provider_hosts(desired_state, inventory_deployments, source)
        if dns_deployments or proxy_hosts or (endpoint_group_id and source.get("serviceType") != "haproxy"):
            relations.append({
                "sourceDeploymentId": source_id,
                "endpointGroupId": endpoint_group_id,
                "dnsDeploymentIds": sorted(dns_deployments),
                "haproxyDeploymentIds": sorted(proxy_hosts),
                "haproxyHostsByDeployment": proxy_hosts,
            })
    return relations


def resolve_service_integrations(desired_state, source_service_types=None, source_deployment_id=None,
                                 inventory_deployments=None):
    """Resolve provider deployments implied by successful source lifecycles.

    This intentionally returns only provider deployment identifiers. Providers
    rebuild their complete models from canonical desired state themselves.
    """
    desired_state = desired_state if isinstance(desired_state, dict) else {}
    deployments = desired_state.get("serviceDeployments", {})
    deployments = deployments if isinstance(deployments, dict) else {}
    findings = []
    if source_deployment_id is not None and source_deployment_id not in deployments:
        findings.append({
            "apiVersion": "platform.installer/finding/v1alpha1", "kind": "Finding",
            "code": "SERVICE_INTEGRATION_SOURCE_NOT_FOUND", "status": "BLOCKED",
            "category": "service-integration", "field": "serviceDeployments.%s" % source_deployment_id,
            "safeMessage": "Selected source service deployment does not exist",
        })
    relations = service_integration_relations(desired_state, source_service_types, source_deployment_id,
                                             inventory_deployments)
    dns_deployments = set()
    haproxy_deployments = set()
    for relation in relations:
        dns_deployments.update(relation["dnsDeploymentIds"])
        haproxy_deployments.update(relation["haproxyDeploymentIds"])

    result = {
        "sources": relations,
        "dnsDeployments": sorted(dns_deployments),
        "haproxyDeployments": sorted(haproxy_deployments),
        "haproxyHosts": sorted({host for relation in relations
                                for hosts in relation["haproxyHostsByDeployment"].values() for host in hosts}),
        "missingHAProxySources": sorted(relation["sourceDeploymentId"] for relation in relations
                                        if relation["endpointGroupId"] and not relation["haproxyDeploymentIds"]
                                        and deployments[relation["sourceDeploymentId"]].get("serviceType") != "haproxy"),
    }
    result["fingerprint"] = canonical_digest(result)
    return {
        "apiVersion": "platform.installer/resolved-service-integrations/v1alpha2",
        "kind": "ResolvedServiceIntegrations",
        "status": "BLOCKED" if findings else "PASS",
        "integrations": result,
        "findings": findings,
    }

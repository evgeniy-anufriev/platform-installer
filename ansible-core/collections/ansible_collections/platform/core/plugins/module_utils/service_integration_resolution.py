from __future__ import absolute_import, division, print_function

__metaclass__ = type

try:
    from .project_validation import canonical_digest
except ImportError:
    from project_validation import canonical_digest


def service_integration_relations(desired_state, source_service_types=None):
    """Return deterministic source-to-provider relations from canonical state."""
    desired_state = desired_state if isinstance(desired_state, dict) else {}
    deployments = desired_state.get("serviceDeployments", {})
    deployments = deployments if isinstance(deployments, dict) else {}
    groups = desired_state.get("endpointGroups", {})
    groups = groups if isinstance(groups, dict) else {}
    source_service_types = set(source_service_types or [])
    relations = []

    for source_id, source in sorted(deployments.items()):
        if not isinstance(source, dict) or source.get("serviceType") not in source_service_types:
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
        relation = source.get("haproxy")
        haproxy_deployment = None
        if (source.get("serviceType") != "haproxy" and isinstance(relation, dict)
                and isinstance(relation.get("deploymentRef"), str)):
            haproxy_deployment = relation["deploymentRef"]
        if dns_deployments or haproxy_deployment:
            relations.append({
                "sourceDeploymentId": source_id,
                "endpointGroupId": endpoint_group_id,
                "dnsDeploymentIds": sorted(dns_deployments),
                "haproxyDeploymentId": haproxy_deployment,
            })
    return relations


def resolve_service_integrations(desired_state, source_service_types=None):
    """Resolve provider deployments implied by successful source lifecycles.

    This intentionally returns only provider deployment identifiers. Providers
    rebuild their complete models from canonical desired state themselves.
    """
    relations = service_integration_relations(desired_state, source_service_types)
    dns_deployments = set()
    haproxy_deployments = set()
    for relation in relations:
        dns_deployments.update(relation["dnsDeploymentIds"])
        if relation["haproxyDeploymentId"]:
            haproxy_deployments.add(relation["haproxyDeploymentId"])

    result = {
        "dnsDeployments": sorted(dns_deployments),
        "haproxyDeployments": sorted(haproxy_deployments),
    }
    result["fingerprint"] = canonical_digest(result)
    return {
        "apiVersion": "platform.installer/resolved-service-integrations/v1alpha1",
        "kind": "ResolvedServiceIntegrations",
        "status": "PASS",
        "integrations": result,
    }

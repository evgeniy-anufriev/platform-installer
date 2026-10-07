from __future__ import absolute_import, division, print_function

__metaclass__ = type

import re

try:
    from .project_validation import canonical_digest
except ImportError:
    from project_validation import canonical_digest


API_VERSION = "platform.installer/resolved-service-endpoint/v1alpha1"
DNS_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
DNS_DOMAIN = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


def _finding(code, field, message, details=None):
    result = {
        "apiVersion": "platform.installer/finding/v1alpha1",
        "kind": "Finding",
        "code": code,
        "status": "BLOCKED",
        "category": "service-endpoint-resolution",
        "field": field,
        "safeMessage": message,
    }
    if details:
        result["safeDetails"] = details
    return result


def _definitions(catalog):
    catalog = catalog if isinstance(catalog, dict) else {}
    values = catalog.get("definitions", catalog)
    return values if isinstance(values, dict) else {}


def resolve_service_endpoints(topology, service_catalog, resolved_service_configuration=None, inventory_deployments=None, deployment_ids=None):
    """Derive generic client endpoint identity from desired topology.

    Transport ports and routing are deliberately deferred to NET-03. This function
    has no filesystem, inventory, target, generated-state or secret access.
    """
    topology = topology if isinstance(topology, dict) else {}
    deployments = topology.get("serviceDeployments", {}) if isinstance(topology.get("serviceDeployments"), dict) else {}
    groups = topology.get("endpointGroups", {}) if isinstance(topology.get("endpointGroups"), dict) else {}
    definitions = _definitions(service_catalog)
    findings, endpoints, host_endpoints = [], {}, {}
    inventory_deployments = inventory_deployments if isinstance(inventory_deployments, dict) else {}
    selected_ids = set(deployment_ids) if isinstance(deployment_ids, list) else None

    for deployment_id, deployment in sorted(deployments.items()):
        if selected_ids is not None and deployment_id not in selected_ids:
            continue
        if not isinstance(deployment, dict) or "endpointGroup" not in deployment:
            continue
        prefix = "serviceDeployments.%s" % deployment_id
        group_id = deployment.get("endpointGroup")
        group = groups.get(group_id)
        if not isinstance(group, dict):
            findings.append(_finding("ENDPOINT_GROUP_NOT_FOUND", prefix + ".endpointGroup", "Endpoint group reference is not defined"))
            continue
        address = group.get("address") if isinstance(group.get("address"), dict) else {}
        domain = address.get("domain")
        if not isinstance(domain, str) or not DNS_DOMAIN.match(domain):
            findings.append(_finding("ENDPOINT_GROUP_DOMAIN_INVALID", "endpointGroups.%s.address.domain" % group_id, "Endpoint group domain must be a lowercase fully qualified DNS suffix"))
            continue
        if not isinstance(deployment_id, str) or not DNS_LABEL.match(deployment_id):
            findings.append(_finding("ENDPOINT_DEPLOYMENT_ID_NOT_DNS_LABEL", prefix, "Endpoint-enabled service deployment id must be a lowercase DNS label"))
            continue
        service_type = deployment.get("serviceType")
        definition = definitions.get(service_type)
        endpoint = definition.get("endpoint") if isinstance(definition, dict) else None
        if not isinstance(endpoint, dict):
            findings.append(_finding("ENDPOINT_SERVICE_UNSUPPORTED", prefix + ".endpointGroup", "Service package does not support a generic client endpoint", {"serviceType": service_type}))
            continue
        fqdn = "%s.%s" % (deployment_id, domain)
        record = {
            "scope": "deployment",
            "serviceDeploymentId": deployment_id,
            "serviceType": service_type,
            "endpointGroupId": group_id,
            "fqdn": fqdn,
            "sanDnsNames": [fqdn],
            "wildcardDnsNames": (["*.%s" % domain] if address.get("wildcard") is True else []),
        }
        record["endpointFingerprint"] = canonical_digest(record)
        endpoints[deployment_id] = record

        # A host endpoint is an inventory opt-in, never a second desired-state
        # entity.  It is intentionally generic so DNS, PKI and future services
        # consume one endpoint projection rather than service-specific logic.
        for host_id, placements in sorted(inventory_deployments.items()):
            placement = placements.get(deployment_id) if isinstance(placements, dict) else None
            field = "platform_deployments.%s.%s.hostEndpoint" % (host_id, deployment_id)
            if not isinstance(placement, dict) or "hostEndpoint" not in placement:
                continue
            if not isinstance(placement.get("hostEndpoint"), bool):
                findings.append(_finding("HOST_ENDPOINT_INVALID", field, "hostEndpoint must be a boolean"))
                continue
            if not placement["hostEndpoint"]:
                continue
            if not isinstance(host_id, str) or not DNS_LABEL.match(host_id):
                findings.append(_finding("HOST_ENDPOINT_HOST_ID_NOT_DNS_LABEL", field, "Host id used for hostEndpoint must be a lowercase DNS label"))
                continue
            if address.get("wildcard") is not True:
                findings.append(_finding("HOST_ENDPOINT_WILDCARD_REQUIRED", field, "hostEndpoint requires an endpoint group with wildcard DNS enabled"))
                continue
            host_fqdn = "%s-%s.%s" % (deployment_id, host_id, domain)
            key = "%s--%s" % (deployment_id, host_id)
            host_record = {
                "scope": "host", "serviceDeploymentId": deployment_id,
                "serviceType": service_type, "hostId": host_id,
                "endpointGroupId": group_id, "fqdn": host_fqdn,
                "sanDnsNames": [host_fqdn],
                "wildcardDnsNames": ["*.%s" % domain],
            }
            host_record["endpointFingerprint"] = canonical_digest(host_record)
            host_endpoints[key] = host_record

    fqdn_owner = {}
    for deployment_id, endpoint in sorted(endpoints.items()):
        fqdn = endpoint["fqdn"]
        if fqdn in fqdn_owner:
            findings.append(_finding("ENDPOINT_FQDN_COLLISION", "serviceDeployments.%s.endpointGroup" % deployment_id, "Resolved endpoint FQDN collides with another service deployment", {"fqdn": fqdn, "otherDeploymentId": fqdn_owner[fqdn]}))
        else:
            fqdn_owner[fqdn] = deployment_id
    for key, endpoint in sorted(host_endpoints.items()):
        fqdn = endpoint["fqdn"]
        if fqdn in fqdn_owner:
            findings.append(_finding("HOST_ENDPOINT_FQDN_COLLISION", "platform_deployments.%s.%s.hostEndpoint" % (endpoint["hostId"], endpoint["serviceDeploymentId"]), "Resolved host endpoint FQDN collides with another endpoint", {"fqdn": fqdn, "otherEndpoint": fqdn_owner[fqdn]}))
        else:
            fqdn_owner[fqdn] = key
    if findings:
        endpoints, host_endpoints = {}, {}
    fingerprint = canonical_digest({"endpoints": endpoints, "hostEndpoints": host_endpoints})
    return {
        "apiVersion": API_VERSION,
        "kind": "ResolvedServiceEndpoints",
        "endpoints": endpoints,
        "hostEndpoints": host_endpoints,
        "endpointFingerprint": fingerprint,
        "findings": sorted(findings, key=lambda item: (item["field"], item["code"])),
        "status": "BLOCKED" if findings else "PASS",
    }

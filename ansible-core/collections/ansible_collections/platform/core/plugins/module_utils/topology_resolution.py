from __future__ import absolute_import, division, print_function

__metaclass__ = type

try:
    from .project_validation import canonical_digest, validate_project
except ImportError:
    from project_validation import canonical_digest, validate_project


TOPOLOGY_FIELDS = ("serviceType", "definitionVersion", "mode", "members")


def _canonical_roles(roles):
    return sorted(role for role in roles if isinstance(role, str))


def _canonical_member(member):
    return {
        "host": member.get("host"),
        "roles": _canonical_roles(member.get("roles", [])),
    }


def canonical_topology(topology):
    """Return only the explicit topology fields in stable identifier order."""
    deployments = topology.get("serviceDeployments", {})
    canonical_deployments = {}
    for deployment_id in sorted(deployments):
        deployment = deployments[deployment_id]
        if not isinstance(deployment, dict):
            continue
        members = deployment.get("members", {})
        canonical_deployments[deployment_id] = {
            field: (
                {
                    member_id: _canonical_member(members[member_id])
                    for member_id in sorted(members)
                }
                if field == "members"
                else deployment.get(field)
            )
            for field in TOPOLOGY_FIELDS
            if field in deployment
        }
    return {"serviceDeployments": canonical_deployments}


def _used_definition_digests(topology, service_catalog):
    definitions = service_catalog.get("definitions", service_catalog)
    deployments = topology.get("serviceDeployments", {})
    used_types = sorted(
        set(
            deployment.get("serviceType")
            for deployment in deployments.values()
            if isinstance(deployment, dict) and deployment.get("serviceType")
        )
    )
    return {
        service_type: definitions[service_type].get("x-definitionDigest")
        for service_type in used_types
        if isinstance(definitions.get(service_type), dict)
    }


def resolve_topology(manifest, topology, inventory_hosts, service_catalog):
    """Resolve explicit topology without filesystem, Ansible or host-var knowledge.

    CORE-01 remains responsible for project/catalog/reference and manifest
    constraint validation. This function only canonicalizes the validated
    topology and fingerprints it with digests of definitions actually used.
    """
    validation = validate_project(
        manifest=manifest,
        topology=topology,
        desired_hosts={},
        service_catalog=service_catalog,
        inventory_hosts=inventory_hosts,
    )
    if validation["findings"]:
        return {
            "status": "BLOCKED",
            "findings": validation["findings"],
        }

    resolved = canonical_topology(topology)
    definition_digests = _used_definition_digests(topology, service_catalog)
    fingerprint_input = {
        "resolvedTopology": resolved,
        "serviceDefinitionDigests": definition_digests,
    }
    return {
        "status": "PASS",
        "resolvedTopology": resolved,
        "serviceDefinitionDigests": definition_digests,
        "topologyFingerprint": canonical_digest(fingerprint_input),
        "findings": [],
    }

from __future__ import absolute_import, division, print_function

__metaclass__ = type

try:
    from .project_validation import canonical_digest, validate_project
    from .project_state import (
        canonical_inventory_members,
        canonical_placements,
        select_desired_state,
        synthesize_ansible_manifest,
        topology_with_inventory_members,
    )
except ImportError:
    from project_validation import canonical_digest, validate_project
    from project_state import canonical_inventory_members, canonical_placements, select_desired_state, synthesize_ansible_manifest, topology_with_inventory_members


TOPOLOGY_FIELDS = ("serviceType", "mode", "identity", "members")


def _with_placement_hosts(topology, placements):
    """Compatibility validation view; placement remains inventory-owned."""
    if placements is None:
        return topology
    result = dict(topology)
    deployments = topology.get("serviceDeployments", {}) if isinstance(topology, dict) else {}
    result_deployments = {}
    for deployment_id, deployment in deployments.items():
        copied = dict(deployment) if isinstance(deployment, dict) else deployment
        if isinstance(copied, dict):
            members = copied.get("members", {})
            copied_members = {}
            for member_id, member in members.items() if isinstance(members, dict) else []:
                copied_member = dict(member) if isinstance(member, dict) else member
                if isinstance(copied_member, dict) and (deployment_id, member_id) in placements:
                    copied_member["host"] = placements[(deployment_id, member_id)]
                copied_members[member_id] = copied_member
            copied["members"] = copied_members
        result_deployments[deployment_id] = copied
    result["serviceDeployments"] = result_deployments
    return result


def _canonical_roles(roles):
    return sorted(role for role in roles if isinstance(role, str))


def _canonical_member(member, host=None):
    return {
        "host": host if host is not None else member.get("host"),
        "roles": _canonical_roles(member.get("roles", [])),
        "identity": member.get("identity", {}),
    }


def canonical_topology(topology, placements=None):
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
                    member_id: _canonical_member(
                        members[member_id],
                        placements.get((deployment_id, member_id)) if placements is not None else None,
                    )
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


def resolve_topology(manifest, topology, inventory_hosts, service_catalog, placement_by_host=None, inventory_deployments_by_host=None, ansible_desired_state=None):
    """Resolve explicit topology without filesystem, Ansible or host-var knowledge.

    CORE-01 remains responsible for project/catalog/reference and manifest
    constraint validation. This function only canonicalizes the validated
    topology and fingerprints it with digests of definitions actually used.
    """
    desired_state, state_findings = select_desired_state(manifest, topology, ansible_desired_state)
    effective_manifest = manifest
    if ansible_desired_state and not isinstance(manifest.get("desiredState"), dict):
        effective_manifest = synthesize_ansible_manifest(desired_state, service_catalog)
    placements = None
    placement_findings = []
    host_scoped_deployments = {}
    if inventory_deployments_by_host is not None:
        inventory_members, inventory_findings = canonical_inventory_members(
            inventory_deployments_by_host, inventory_hosts
        )
        deployments = desired_state.get("serviceDeployments", {})
        for host_id, host_deployments in sorted((inventory_deployments_by_host or {}).items()):
            if not isinstance(host_deployments, dict):
                continue
            for deployment_id, host_configuration in sorted(host_deployments.items()):
                if isinstance(host_configuration, dict) and "members" not in host_configuration:
                    host_scoped_deployments.setdefault(deployment_id, {})[host_id] = dict(host_configuration)
        for deployment_id, deployment in (sorted(deployments.items()) if isinstance(deployments, dict) else []):
            if isinstance(deployment, dict) and "members" in deployment:
                placement_findings.append({
                    "apiVersion": "platform.installer/finding/v1alpha1", "kind": "Finding",
                    "code": "PERSISTED_MEMBERS_NOT_ALLOWED", "status": "BLOCKED",
                    "category": "project-state", "field": "serviceDeployments.%s.members" % deployment_id,
                    "safeMessage": "Ansible desired state must not duplicate inventory-owned service members",
                })
        for deployment_id, member_id in sorted(inventory_members):
            if deployment_id not in deployments:
                placement_findings.append({
                    "apiVersion": "platform.installer/finding/v1alpha1", "kind": "Finding",
                    "code": "INVENTORY_DEPLOYMENT_NOT_FOUND", "status": "BLOCKED",
                    "category": "project-state", "field": "platform_deployments.%s.%s" % (inventory_members[(deployment_id, member_id)]["host"], deployment_id),
                    "safeMessage": "Inventory member references an unknown deployment",
                })
        for deployment_id in sorted(host_scoped_deployments):
            if deployment_id not in deployments:
                placement_findings.append({
                    "apiVersion": "platform.installer/finding/v1alpha1", "kind": "Finding",
                    "code": "INVENTORY_DEPLOYMENT_NOT_FOUND", "status": "BLOCKED",
                    "category": "project-state", "field": "platform_deployments.%s" % deployment_id,
                    "safeMessage": "Inventory host-scoped deployment references an unknown deployment",
                })
        desired_state = topology_with_inventory_members(desired_state, inventory_members)
        for deployment_id in host_scoped_deployments:
            if isinstance(desired_state.get("serviceDeployments", {}).get(deployment_id), dict):
                desired_state["serviceDeployments"][deployment_id].pop("members", None)
        placements = {key: member["host"] for key, member in inventory_members.items()}
        placement_findings.extend(inventory_findings)
    elif placement_by_host is not None:
        placements, placement_findings = canonical_placements(placement_by_host, inventory_hosts)
        deployments = desired_state.get("serviceDeployments", {})
        if isinstance(deployments, dict):
            for deployment_id in sorted(deployments):
                members = deployments[deployment_id].get("members", {}) if isinstance(deployments[deployment_id], dict) else {}
                for member_id in sorted(members) if isinstance(members, dict) else []:
                    key = (deployment_id, member_id)
                    host = placements.get(key)
                    if host is None:
                        placement_findings.append({
                            "apiVersion": "platform.installer/finding/v1alpha1", "kind": "Finding",
                            "code": "MEMBER_PLACEMENT_UNASSIGNED", "status": "BLOCKED",
                            "category": "project-state", "field": "serviceDeployments.%s.members.%s" % key,
                            "safeMessage": "Logical member has no inventory placement",
                        })
                    elif isinstance(members[member_id], dict) and members[member_id].get("host") and members[member_id]["host"] != host:
                        placement_findings.append({
                            "apiVersion": "platform.installer/finding/v1alpha1", "kind": "Finding",
                            "code": "LEGACY_MEMBER_HOST_CONFLICT", "status": "BLOCKED",
                            "category": "project-state", "field": "serviceDeployments.%s.members.%s.host" % key,
                            "safeMessage": "Legacy member host conflicts with canonical inventory placement",
                        })
            for deployment_id, member_id in sorted(placements):
                if deployment_id not in deployments:
                    placement_findings.append({"apiVersion": "platform.installer/finding/v1alpha1", "kind": "Finding", "code": "PLACEMENT_DEPLOYMENT_NOT_FOUND", "status": "BLOCKED", "category": "project-state", "field": "platform_members.%s" % deployment_id, "safeMessage": "Placement references an unknown deployment"})
                elif member_id not in deployments[deployment_id].get("members", {}):
                    placement_findings.append({"apiVersion": "platform.installer/finding/v1alpha1", "kind": "Finding", "code": "PLACEMENT_MEMBER_NOT_FOUND", "status": "BLOCKED", "category": "project-state", "field": "platform_members.%s.%s" % (deployment_id, member_id), "safeMessage": "Placement references an unknown member"})
    validation = validate_project(
        manifest=effective_manifest,
        topology=desired_state,
        desired_hosts={},
        service_catalog=service_catalog,
        inventory_hosts=inventory_hosts,
        placements=placements,
        host_scoped_deployments=host_scoped_deployments,
    )
    findings = validation["findings"] + [item for item in state_findings if item["status"] == "BLOCKED"] + placement_findings
    if findings:
        return {
            "status": "BLOCKED",
            "findings": findings,
        }

    resolved = canonical_topology(desired_state, placements)
    definition_digests = _used_definition_digests(desired_state, service_catalog)
    fingerprint_input = {
        "resolvedTopology": resolved,
        "hostScopedDeployments": {
            deployment_id: {
                host_id: host_scoped_deployments[deployment_id][host_id]
                for host_id in sorted(host_scoped_deployments[deployment_id])
            }
            for deployment_id in sorted(host_scoped_deployments)
        },
        "serviceDefinitionDigests": definition_digests,
    }
    return {
        "status": "PASS",
        "resolvedTopology": resolved,
        "serviceDefinitionDigests": definition_digests,
        "topologyFingerprint": canonical_digest(fingerprint_input),
        "findings": state_findings,
    }

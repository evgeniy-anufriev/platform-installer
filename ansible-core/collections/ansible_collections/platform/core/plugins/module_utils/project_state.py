from __future__ import absolute_import, division, print_function

__metaclass__ = type

try:
    from .project_validation import canonical_digest
except ImportError:
    from project_validation import canonical_digest


def finding(code, field, message, status="BLOCKED"):
    return {
        "apiVersion": "platform.installer/finding/v1alpha1",
        "kind": "Finding",
        "code": code,
        "status": status,
        "category": "project-state",
        "field": field,
        "safeMessage": message,
    }


def select_desired_state(manifest, legacy_topology):
    """Choose the one logical desired-state authority with bounded legacy support."""
    manifest = manifest if isinstance(manifest, dict) else {}
    legacy = legacy_topology if isinstance(legacy_topology, dict) else {}
    current = manifest.get("desiredState")
    has_current = isinstance(current, dict)
    has_legacy = bool(legacy)
    findings = []
    if has_current and has_legacy:
        if canonical_digest(current) != canonical_digest(legacy):
            findings.append(finding(
                "DESIRED_STATE_LEGACY_CONFLICT", "desiredState",
                "project.yml desiredState and legacy platform_project differ",
            ))
        else:
            findings.append(finding(
                "LEGACY_PLATFORM_PROJECT_DEPRECATED", "platform_project",
                "Legacy platform_project duplicates project.yml desiredState", "DEPRECATED",
            ))
        return current, findings
    if has_current:
        return current, findings
    if has_legacy:
        findings.append(finding(
            "LEGACY_PLATFORM_PROJECT_DEPRECATED", "platform_project",
            "Legacy platform_project is a compatibility input; migrate to project.yml desiredState",
            "DEPRECATED",
        ))
        return legacy, findings
    return {}, findings


def canonical_placements(placement_by_host, inventory_hosts):
    """Canonicalize inventory host-level platform_members without Ansible precedence."""
    inventory_set = set(inventory_hosts or [])
    source = placement_by_host if isinstance(placement_by_host, dict) else {}
    result, findings = {}, []
    for host_id in sorted(source):
        deployments = source[host_id]
        if host_id not in inventory_set:
            findings.append(finding("PLACEMENT_HOST_NOT_TARGET", "platform_members.%s" % host_id,
                                    "Placement host is not a platform target"))
            continue
        if not isinstance(deployments, dict):
            findings.append(finding("PLACEMENT_ENTRY_INVALID", "platform_members.%s" % host_id,
                                    "Host platform_members must be a deployment map"))
            continue
        for deployment_id in sorted(deployments):
            members = deployments[deployment_id]
            if not isinstance(members, list):
                findings.append(finding("PLACEMENT_ENTRY_INVALID", "platform_members.%s.%s" % (host_id, deployment_id),
                                        "Deployment placement must be a member list"))
                continue
            for member_id in members:
                key = (deployment_id, member_id)
                if key in result:
                    findings.append(finding("PLACEMENT_ENTRY_DUPLICATE", "platform_members.%s.%s" % (host_id, deployment_id),
                                            "A member may be placed only once"))
                result[key] = host_id
    return result, findings


def canonical_inventory_members(deployments_by_host, inventory_hosts):
    """Normalize reserved host.platform_deployments into canonical members."""
    inventory_set = set(inventory_hosts or [])
    source = deployments_by_host if isinstance(deployments_by_host, dict) else {}
    result, findings = {}, []
    for host_id in sorted(source):
        deployments = source[host_id]
        field_prefix = "platform_deployments.%s" % host_id
        if host_id not in inventory_set:
            findings.append(finding("MEMBER_HOST_NOT_TARGET", field_prefix,
                                    "Host with platform_deployments is not a platform target"))
            continue
        if not isinstance(deployments, dict):
            findings.append(finding("INVENTORY_DEPLOYMENTS_INVALID", field_prefix,
                                    "platform_deployments must be a deployment map"))
            continue
        for deployment_id in sorted(deployments):
            deployment = deployments[deployment_id]
            members = deployment.get("members") if isinstance(deployment, dict) else None
            member_prefix = "%s.%s.members" % (field_prefix, deployment_id)
            if not isinstance(members, dict):
                findings.append(finding("INVENTORY_MEMBERS_INVALID", member_prefix,
                                        "Deployment members must be an object keyed by member id"))
                continue
            for member_id in sorted(members):
                member = members[member_id]
                key = (deployment_id, member_id)
                if key in result:
                    findings.append(finding("INVENTORY_MEMBER_DUPLICATE", member_prefix,
                                            "A member may be owned by only one inventory host"))
                    continue
                if not isinstance(member, dict):
                    findings.append(finding("INVENTORY_MEMBER_INVALID", "%s.%s" % (member_prefix, member_id),
                                            "Inventory member must be an object"))
                    continue
                result[key] = {
                    "host": host_id,
                    "roles": member.get("roles", []),
                    "configuration": member.get("configuration", {}),
                    "identity": member.get("identity", {}),
                }
    return result, findings


def topology_with_inventory_members(desired_state, inventory_members):
    """Compose the ephemeral resolver view; persistent project state stays member-free."""
    desired_state = desired_state if isinstance(desired_state, dict) else {}
    deployments = desired_state.get("serviceDeployments", {})
    result = dict(desired_state)
    result_deployments = {}
    for deployment_id, deployment in (deployments.items() if isinstance(deployments, dict) else []):
        copied = dict(deployment) if isinstance(deployment, dict) else deployment
        if isinstance(copied, dict):
            copied["members"] = {
                member_id: dict(member)
                for (candidate_deployment, member_id), member in sorted(inventory_members.items())
                if candidate_deployment == deployment_id
            }
        result_deployments[deployment_id] = copied
    result["serviceDeployments"] = result_deployments
    return result

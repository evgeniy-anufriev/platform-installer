from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import os
import yaml

try:
    from .kafka_identity import materialize_kafka_identities, validate_kafka_discovery
    from .identity_persistence import persist_generated_state, persist_identity_documents
except ImportError:
    from kafka_identity import materialize_kafka_identities, validate_kafka_discovery
    from identity_persistence import persist_generated_state, persist_identity_documents


def _inventory_hosts_with_managed_deployments(inventory_path, inventory):
    """Return inventory hosts with their canonical per-host deployment input.

    The normal Ansible-native layout keeps ``platform_deployments`` in the
    fixed ``inventory/host_vars/<host>.yml`` document, rather than duplicating
    it into ``hosts.yml``.  Identity materialization reads only that owned
    field; it neither scans arbitrary files nor writes host variables.
    """
    hosts = (inventory.get("all", {}).get("hosts", {}) or {}) if isinstance(inventory, dict) else {}
    host_vars_root = os.path.join(os.path.dirname(os.fspath(inventory_path)), "host_vars")
    for host, host_data in sorted(hosts.items()):
        effective = copy.deepcopy(host_data) if isinstance(host_data, dict) else {}
        if not isinstance(host, str) or not host:
            yield host, effective
            continue
        host_vars_path = os.path.join(host_vars_root, host + ".yml")
        if os.path.isfile(host_vars_path):
            with open(host_vars_path, "r", encoding="utf-8") as source:
                host_vars = yaml.safe_load(source) or {}
            if isinstance(host_vars, dict) and "platform_deployments" in host_vars:
                effective["platform_deployments"] = copy.deepcopy(host_vars["platform_deployments"])
        yield host, effective


def materialize_ansible_kafka(desired_state, inventory_path, state_path, discovery, project_id="ansible-project", random_bytes=None):
    """Materialize Kafka identities into machine-owned Ansible state only."""
    with open(inventory_path, "r", encoding="utf-8") as source:
        inventory = yaml.safe_load(source) or {}
    if state_path and os.path.exists(state_path):
        with open(state_path, "r", encoding="utf-8") as source:
            loaded_document = yaml.safe_load(source) or {}
    else:
        loaded_document = {}
    loaded = loaded_document.get("platform_generated_state", {}) if isinstance(loaded_document, dict) else {}
    state = copy.deepcopy(loaded) if isinstance(loaded, dict) else {}
    state.setdefault("apiVersion", "platform.installer/generated-state/v1alpha1")
    state.setdefault("kind", "PlatformGeneratedState")
    state.setdefault("metadata", {"projectId": project_id})
    state.setdefault("serviceDeployments", {})
    deployments = desired_state.get("serviceDeployments", {}) if isinstance(desired_state, dict) else {}
    result = {"status": "PASS", "changed": False, "decisions": {}}
    for deployment_id, declared in sorted(deployments.items()):
        if not isinstance(declared, dict) or declared.get("serviceType") != "kafka":
            continue
        deployment_state = state["serviceDeployments"].setdefault(deployment_id, {})
        effective = copy.deepcopy(declared)
        effective.setdefault("identity", {}).update(deployment_state.get("identity", {}))
        members = {}
        for host, host_data in _inventory_hosts_with_managed_deployments(inventory_path, inventory):
            owned = (host_data.get("platform_deployments", {}) if isinstance(host_data, dict) else {}).get(deployment_id, {})
            for member_id, member in sorted((owned.get("members", {}) if isinstance(owned, dict) else {}).items()):
                normalized = copy.deepcopy(member)
                normalized.setdefault("identity", {}).update(
                    deployment_state.get("members", {}).get(member_id, {}).get("identity", {})
                )
                members[member_id] = normalized
        metadata, records = {}, []
        for host_discovery in discovery.values() if isinstance(discovery, dict) else []:
            values = host_discovery if isinstance(host_discovery, list) else []
            for record in values:
                if isinstance(record, dict) and record.get("deploymentId") in (None, deployment_id) and record.get("memberId"):
                    records.append(record)
                    metadata[record["memberId"]] = record
        findings = validate_kafka_discovery(members.keys(), records)
        if findings:
            return dict(result, status="BLOCKED", findings=findings)
        kwargs = {"random_bytes": random_bytes} if random_bytes is not None else {}
        decision = materialize_kafka_identities(deployment_id, effective, members, metadata, **kwargs)
        result["decisions"][deployment_id] = decision
        if decision["status"] != "PASS":
            return dict(result, status="BLOCKED", findings=decision.get("findings", []))
        patch = decision.get("patch", {})
        if patch.get("deploymentIdentity"):
            deployment_state.setdefault("identity", {}).update(patch["deploymentIdentity"])
        for member_id, identity in patch.get("memberIdentities", {}).items():
            deployment_state.setdefault("members", {}).setdefault(member_id, {}).setdefault("identity", {}).update(identity)
        result["changed"] = result["changed"] or bool(decision.get("changed"))
    if result["changed"] or not loaded:
        persisted = persist_generated_state(state_path, {"platform_generated_state": state})
        result["changed"] = persisted["changed"]
    with open(state_path, "r", encoding="utf-8") as source:
        result["stateDocument"] = yaml.safe_load(source) or {}
    return result


def materialize_managed_kafka(project_path, inventory_path, discovery, random_bytes=None):
    """Materialize all Kafka identities, then reload canonical documents.

    Discovery is read-only input collected by the Ansible target phase. The
    returned documents are always loaded from disk after persistence.
    """
    with open(project_path, "r", encoding="utf-8") as source:
        project = yaml.safe_load(source) or {}
    with open(inventory_path, "r", encoding="utf-8") as source:
        inventory = yaml.safe_load(source) or {}
    desired = project.get("desiredState", {})
    deployments = desired.get("serviceDeployments", {}) if isinstance(desired, dict) else {}
    result = {"status": "PASS", "changed": False, "decisions": {}}
    candidate_project = copy.deepcopy(project)
    candidate_inventory = copy.deepcopy(inventory)
    for deployment_id, deployment in sorted(deployments.items()):
        if not isinstance(deployment, dict) or deployment.get("serviceType") != "kafka":
            continue
        members = {}
        for host, host_data in _inventory_hosts_with_managed_deployments(inventory_path, inventory):
            owned = (host_data.get("platform_deployments", {}) if isinstance(host_data, dict) else {}).get(deployment_id, {})
            for member_id, member in sorted((owned.get("members", {}) if isinstance(owned, dict) else {}).items()):
                members[member_id] = member
        metadata = {}
        discovery_records = []
        if isinstance(discovery, dict):
            for host_discovery in discovery.values():
                if isinstance(host_discovery, list):
                    for record in host_discovery:
                        if isinstance(record, dict) and record.get("memberId"):
                            if record.get("deploymentId") not in (None, deployment_id):
                                continue
                            discovery_records.append(record)
                            metadata[record["memberId"]] = record
                    continue
                if isinstance(host_discovery, dict):
                    nested = host_discovery.get(deployment_id, {}) or {}
                    if isinstance(nested, dict):
                        for member_id, record in nested.items():
                            if isinstance(record, dict):
                                normalized = dict(record)
                                normalized.setdefault("memberId", member_id)
                                normalized.setdefault("deploymentId", deployment_id)
                                discovery_records.append(normalized)
                                metadata[member_id] = normalized
        discovery_findings = validate_kafka_discovery(members.keys(), discovery_records)
        if discovery_findings:
            return dict(result, status="BLOCKED", findings=discovery_findings)
        kwargs = {"random_bytes": random_bytes} if random_bytes is not None else {}
        decision = materialize_kafka_identities(deployment_id, deployment, members, metadata, **kwargs)
        result["decisions"][deployment_id] = decision
        if decision["status"] != "PASS":
            return dict(result, status="BLOCKED", findings=decision.get("findings", []))
        patch = decision.get("patch", {})
        if patch.get("deploymentIdentity"):
            candidate_project["desiredState"]["serviceDeployments"][deployment_id].setdefault("identity", {}).update(patch["deploymentIdentity"])
        for host, host_data in sorted((candidate_inventory.get("all", {}).get("hosts", {}) or {}).items()):
            owned = (host_data.get("platform_deployments", {}) if isinstance(host_data, dict) else {}).get(deployment_id, {})
            for member_id, identity in patch.get("memberIdentities", {}).items():
                if member_id in (owned.get("members", {}) if isinstance(owned, dict) else {}):
                    owned["members"][member_id].setdefault("identity", {}).update(identity)
        result["changed"] = result["changed"] or bool(decision.get("changed"))
    if result["changed"]:
        persist_identity_documents(project_path, inventory_path, candidate_project, candidate_inventory)
    with open(project_path, "r", encoding="utf-8") as source:
        result["project"] = yaml.safe_load(source) or {}
    with open(inventory_path, "r", encoding="utf-8") as source:
        result["inventory"] = yaml.safe_load(source) or {}
    return result

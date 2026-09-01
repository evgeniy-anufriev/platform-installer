from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import yaml

try:
    from .kafka_identity import materialize_kafka_identities, validate_kafka_discovery
    from .identity_persistence import persist_identity_documents
except ImportError:
    from kafka_identity import materialize_kafka_identities, validate_kafka_discovery
    from identity_persistence import persist_identity_documents


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
        for host, host_data in sorted((inventory.get("all", {}).get("hosts", {}) or {}).items()):
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

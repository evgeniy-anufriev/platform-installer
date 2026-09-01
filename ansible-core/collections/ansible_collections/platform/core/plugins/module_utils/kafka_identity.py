from __future__ import absolute_import, division, print_function

__metaclass__ = type

import base64
import os


def _finding(code, field, message):
    return {"code": code, "status": "BLOCKED", "field": field, "safeMessage": message}


def _new_id(random_bytes):
    return base64.urlsafe_b64encode(random_bytes(16)).decode("ascii").rstrip("=")


def validate_kafka_discovery(member_ids, records):
    """Validate the complete read-only discovery projection for a deployment."""
    expected = set(member_ids)
    seen = {}
    findings = []
    for record in records if isinstance(records, list) else []:
        if not isinstance(record, dict) or not record.get("memberId"):
            continue
        member_id = record["memberId"]
        if member_id in seen:
            findings.append(_finding("KAFKA_IDENTITY_DISCOVERY_DUPLICATE", "discovery", "Kafka identity discovery returned duplicate member records"))
        seen[member_id] = record
    missing = sorted(expected - set(seen))
    unknown = sorted(set(seen) - expected)
    if missing:
        findings.append(_finding("KAFKA_IDENTITY_DISCOVERY_INCOMPLETE", "discovery", "Kafka identity discovery is missing expected deployment members"))
    if unknown:
        findings.append(_finding("KAFKA_IDENTITY_DISCOVERY_UNKNOWN_MEMBER", "discovery", "Kafka identity discovery returned a member outside the deployment"))
    if any(record.get("state") == "UNKNOWN" for record in seen.values()):
        findings.append(_finding("KAFKA_IDENTITY_DISCOVERY_UNKNOWN", "discovery", "Kafka identity discovery could not establish storage state"))
    return findings


def materialize_kafka_identities(deployment_id, deployment, members, metadata, random_bytes=os.urandom):
    """Pure Kafka-specific identity decision before persistence or mutation.

    metadata is an inventory-member keyed read-only projection of meta.properties.
    The caller persists the returned complete patch atomically before projecting
    the role runtime input; this function never formats or changes storage.
    """
    deployment = deployment if isinstance(deployment, dict) else {}
    members = members if isinstance(members, dict) else {}
    metadata = metadata if isinstance(metadata, dict) else {}
    identity = deployment.get("identity", {}) if isinstance(deployment.get("identity"), dict) else {}
    discovered_clusters = sorted(set(
        value.get("clusterId") for value in metadata.values()
        if isinstance(value, dict) and (value.get("initialized") or value.get("state") == "INITIALIZED") and value.get("clusterId")
    ))
    findings = []
    if len(discovered_clusters) > 1:
        findings.append(_finding("KAFKA_CLUSTER_ID_DISCOVERY_CONFLICT", "identity.clusterId", "Initialized Kafka members disagree on cluster identity"))
    cluster_id = identity.get("clusterId")
    if cluster_id and discovered_clusters and cluster_id != discovered_clusters[0]:
        findings.append(_finding("KAFKA_CLUSTER_ID_METADATA_MISMATCH", "identity.clusterId", "Persisted cluster identity does not match initialized Kafka storage"))
    if findings:
        return {"status": "BLOCKED", "findings": findings}
    patch = {"deploymentIdentity": {}, "memberIdentities": {}}
    if not cluster_id:
        patch["deploymentIdentity"]["clusterId"] = discovered_clusters[0] if discovered_clusters else _new_id(random_bytes)
    required = [member_id for member_id, member in sorted(members.items()) if "controller" in member.get("roles", [])]
    if not metadata:
        return {"status": "BLOCKED", "findings": [_finding("KAFKA_IDENTITY_DISCOVERY_REQUIRED", "discovery", "Kafka identity generation requires a successful read-only storage discovery") ]}
    missing = [member_id for member_id in required if member_id not in metadata]
    if missing:
        return {"status": "BLOCKED", "findings": [_finding("KAFKA_IDENTITY_DISCOVERY_INCOMPLETE", "discovery", "Kafka identity discovery is incomplete for required controller members") ]}
    for member_id in required:
        member = members[member_id]
        persisted = member.get("identity", {}).get("directoryId") if isinstance(member.get("identity"), dict) else None
        observed = metadata.get(member_id, {}) if isinstance(metadata.get(member_id), dict) else {}
        recovered = observed.get("directoryId") if (observed.get("initialized") or observed.get("state") == "INITIALIZED") else None
        if persisted and recovered and persisted != recovered:
            findings.append(_finding("KAFKA_DIRECTORY_ID_METADATA_MISMATCH", "members.%s.identity.directoryId" % member_id, "Persisted controller identity does not match initialized Kafka storage"))
        elif not persisted:
            patch["memberIdentities"][member_id] = {"directoryId": recovered or _new_id(random_bytes)}
    if findings:
        return {"status": "BLOCKED", "findings": findings}
    changed = bool(patch["deploymentIdentity"] or patch["memberIdentities"])
    return {"status": "PASS", "changed": changed, "patch": patch, "findings": []}

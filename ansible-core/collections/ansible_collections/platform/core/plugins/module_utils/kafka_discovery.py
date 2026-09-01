from __future__ import absolute_import, division, print_function

__metaclass__ = type


def parse_meta_properties(deployment_id, member_id, host_id, metadata_path, content, exists=True, read_error=None):
    """Parse only Kafka identity metadata; never creates or mutates storage."""
    record = {"deploymentId": deployment_id, "memberId": member_id, "hostId": host_id, "metadataPath": metadata_path}
    if read_error:
        record.update(state="UNKNOWN", diagnostics={"reason": str(read_error)})
        return record
    if not exists:
        record["state"] = "UNINITIALIZED"
        return record
    values = {}
    for line in (content or "").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    required = ("cluster.id", "node.id")
    if any(not values.get(key) for key in required):
        record.update(state="UNKNOWN", diagnostics={"reason": "malformed meta.properties"})
        return record
    record.update(state="INITIALIZED", clusterId=values["cluster.id"], nodeId=values["node.id"])
    if values.get("directory.id"):
        record["directoryId"] = values["directory.id"]
    return record

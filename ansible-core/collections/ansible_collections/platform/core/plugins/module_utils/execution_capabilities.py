"""Machine-readable capability response for an activated Execution runtime."""

import os


def build_capabilities(manifest, core_version):
    if not isinstance(manifest, dict):
        raise ValueError("runtime manifest is invalid")
    required = ("bundleVersion", "bootstrapProtocol", "catalogDigest", "schemaDigest")
    if any(not isinstance(manifest.get(key), str) or not manifest[key] for key in required):
        raise ValueError("runtime manifest identity is incomplete")
    return {
        "apiVersion": "platform.installer/execution-capabilities/v1alpha6",
        "kind": "ExecutionCapabilities",
        "bootstrapProtocol": manifest["bootstrapProtocol"],
        "coreVersion": core_version,
        "catalogDigest": manifest["catalogDigest"],
        "schemaDigest": manifest["schemaDigest"],
        "runtime": {
            "bundleVersion": manifest["bundleVersion"],
            "bundleDigest": manifest.get("bundleDigest", ""),
        },
        "supportedOperations": ["GetCapabilities", "ValidateProject", "BuildProjectSnapshot", "BuildRuntimeSecretDescriptors", "BuildDeploymentPlan", "StartExecution", "GetExecution", "GetEvents", "CancelExecution", "PutRuntimeSecretLease"],
        "projectSnapshotRequestVersions": ["platform.installer/project-snapshot-request/v1alpha1"],
        "deploymentPlanRequestVersions": ["platform.installer/execution-runtime/v1alpha2"],
        "executionStart": {"protocol": "StartExecution/v1alpha2"},
        "targetCredentialLease": {
            "protocol": "PutRuntimeSecretLease/v1alpha2",
            "payloadVersions": ["TargetCredentialLeasePayload/v1alpha4"],
            "maxPayloadBytes": 1088 * 1024,
            "requiredStartProtocol": "StartExecution/v1alpha2",
        },
        "runtimeSecretDescriptors": {"protocol": "BuildRuntimeSecretDescriptors/v1alpha2", "maxDescriptors": 16, "maxHostsPerDescriptor": 256, "maxResponseBytes": 65536},
    }


def core_version(collection_root):
    galaxy = os.path.join(collection_root, "galaxy.yml")
    with open(galaxy, "r", encoding="utf-8") as source:
        for line in source:
            if line.startswith("version:"):
                return line.split(":", 1)[1].strip()
    raise ValueError("Core version is unavailable")

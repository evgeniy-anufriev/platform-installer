import sys
from pathlib import Path
import unittest


MODULES = Path(__file__).resolve().parents[1] / "collections" / "ansible_collections" / "platform" / "core" / "plugins" / "module_utils"
sys.path.insert(0, str(MODULES))
from execution_capabilities import build_capabilities


class ExecutionCapabilitiesTests(unittest.TestCase):
    def test_response_is_machine_readable_and_limited_to_safe_identity(self):
        result = build_capabilities({
            "bundleVersion": "2026.09.03",
            "bootstrapProtocol": "v1alpha1",
            "catalogDigest": "sha256:" + "a" * 64,
            "schemaDigest": "sha256:" + "b" * 64,
            "bundleDigest": "sha256:" + "c" * 64,
        }, "0.1.0")
        self.assertEqual("ExecutionCapabilities", result["kind"])
        self.assertEqual("platform.installer/execution-capabilities/v1alpha2", result["apiVersion"])
        self.assertEqual(["GetCapabilities", "ValidateProject", "BuildProjectSnapshot", "BuildDeploymentPlan", "StartExecution", "GetExecution", "GetEvents", "CancelExecution", "PutRuntimeSecretLease"], result["supportedOperations"])
        self.assertEqual(["platform.installer/project-snapshot-request/v1alpha1"], result["projectSnapshotRequestVersions"])
        self.assertEqual("StartExecution/v1alpha2", result["executionStart"]["protocol"])
        self.assertEqual("PutRuntimeSecretLease/v1alpha1", result["targetCredentialLease"]["protocol"])
        self.assertNotIn("secrets", str(result).lower())

    def test_incomplete_runtime_identity_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "identity is incomplete"):
            build_capabilities({"bundleVersion": "1"}, "0.1.0")


if __name__ == "__main__":
    unittest.main()

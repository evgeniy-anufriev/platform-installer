import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "collections" / "ansible_collections" / "platform" / "core" / "plugins" / "filter"
spec = importlib.util.spec_from_file_location("artifact_source", ROOT / "artifact_source.py")
SOURCE = importlib.util.module_from_spec(spec); spec.loader.exec_module(SOURCE)
DIGEST = "sha256:" + "a" * 64


def authority(offline=True):
    return {"apiVersion": "platform.installer/artifact-source-authority/v1alpha1", "kind": "ArtifactSourceAuthority", "sourcePolicy": "REPOSITORY_THEN_OFFLINE", "repository": {"kind": "REPOSITORY"}, "requirement": {"id": "kafka:kafka-binary", "requirementId": "kafka-binary", "name": "kafka", "version": "4.3.1", "os": "redos", "architecture": "x86_64"}, "offlineBundle": {"kind": "OFFLINE_BUNDLE", "bundleDigest": DIGEST, "ref": "runtime/artifacts/kafka/kafka_2.13-4.3.1.tgz", "sha256": DIGEST, "size": 12, "type": "archive"} if offline else None}


class ArtifactSourceAuthorityTests(unittest.TestCase):
    def test_repository_then_offline_exact_current_policy(self):
        repository = SOURCE.resolve_artifact_source(authority(), {"id": "kafka-binary", "name": "kafka"}, "node1", "redos", "kafka\t4.3.1\tx86_64\n", 0)
        self.assertEqual("REPOSITORY", repository["source"])
        offline = SOURCE.resolve_artifact_source(authority(), {"id": "kafka-binary", "name": "kafka"}, "node1", "redos", "kafka\t4.2.0\tx86_64\n", 0)
        self.assertEqual("OFFLINE_BUNDLE", offline["source"])
        self.assertEqual("runtime/artifacts/kafka/kafka_2.13-4.3.1.tgz", offline["artifacts"][0]["ref"])

    def test_no_authorized_offline_remains_blocked(self):
        result = SOURCE.resolve_artifact_source(authority(False), {"id": "kafka-binary", "name": "kafka"}, "node1", "redos", "", 1)
        self.assertEqual("BLOCKED", result["source"])

    def test_requirement_rebinding_is_rejected(self):
        with self.assertRaises(ValueError):
            SOURCE.resolve_artifact_source(authority(), {"id": "other", "name": "kafka"}, "node1", "redos", "", 1)

    def test_repository_requires_exact_target_os_proof(self):
        arguments = (authority(), {"id": "kafka-binary", "name": "kafka"}, "node1")
        self.assertEqual("OFFLINE_BUNDLE", SOURCE.resolve_artifact_source(*arguments, "alt", "kafka\t4.3.1\tx86_64\n", 0)["source"])
        self.assertEqual("OFFLINE_BUNDLE", SOURCE.resolve_artifact_source(*arguments, "", "kafka\t4.3.1\tx86_64\n", 0)["source"])
        self.assertEqual("REPOSITORY", SOURCE.resolve_artifact_source(*arguments, "redos", "kafka\t4.3.1\tx86_64\n", 0)["source"])


if __name__ == "__main__":
    unittest.main()

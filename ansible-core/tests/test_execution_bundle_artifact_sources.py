import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


TOOL = Path(__file__).resolve().parents[1] / "tools" / "build_execution_runtime_bundle.py"
spec = importlib.util.spec_from_file_location("bundle_builder", TOOL)
BUILDER = importlib.util.module_from_spec(spec); sys.modules["bundle_builder"] = BUILDER; spec.loader.exec_module(BUILDER)


class ExecutionBundleArtifactSourceTests(unittest.TestCase):
    def test_kafka_requirement_maps_to_the_existing_bundle_relative_ref(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = b"kafka-fixture"
            digest = "sha256:" + hashlib.sha256(payload).hexdigest()
            artifact = root / "runtime" / "artifacts" / "kafka" / "kafka_2.13-4.3.1.tgz"
            artifact.parent.mkdir(parents=True); artifact.write_bytes(payload)
            (root / "catalog").mkdir()
            (root / "catalog" / "service-catalog.yml").write_text("definitions:\n  kafka:\n    artifacts:\n      - id: kafka-binary\n        name: kafka\n        version: '4.3.1'\n        os: redos\n        architecture: x86_64\n        digest: %s\n" % digest, encoding="utf-8")
            metadata = root / "services" / "kafka"; metadata.mkdir(parents=True)
            (metadata / "artifacts.yml").write_text("artifacts:\n  - id: kafka-binary\n    version: '4.3.1'\n    filename: kafka_2.13-4.3.1.tgz\n    mediaType: application/gzip\n    sha256: %s\n" % digest[7:], encoding="utf-8")
            sources = BUILDER.artifact_sources(root)
            self.assertEqual(1, len(sources))
            self.assertEqual("runtime/artifacts/kafka/kafka_2.13-4.3.1.tgz", sources[0]["ref"])
            self.assertEqual(digest, sources[0]["sha256"])
            self.assertEqual("archive", sources[0]["type"])

    def test_digest_mismatch_does_not_create_a_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root / "catalog").mkdir(); (root / "services" / "kafka").mkdir(parents=True)
            (root / "catalog" / "service-catalog.yml").write_text("definitions: {kafka: {artifacts: []}}\n", encoding="utf-8")
            (root / "services" / "kafka" / "artifacts.yml").write_text("artifacts: []\n", encoding="utf-8")
            self.assertEqual([], BUILDER.artifact_sources(root))


if __name__ == "__main__":
    unittest.main()

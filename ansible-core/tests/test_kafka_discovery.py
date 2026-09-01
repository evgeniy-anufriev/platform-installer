import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "collections" / "ansible_collections" / "platform" / "core" / "plugins" / "module_utils"
spec = importlib.util.spec_from_file_location("kafka_discovery", ROOT / "kafka_discovery.py")
discovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(discovery)


class KafkaDiscoveryTests(unittest.TestCase):
    def test_missing_metadata_is_proven_uninitialized(self):
        result = discovery.parse_meta_properties("k", "m", "n", "/data/meta.properties", "", False)
        self.assertEqual("UNINITIALIZED", result["state"])

    def test_valid_metadata_is_initialized(self):
        result = discovery.parse_meta_properties("k", "m", "n", "/data/meta.properties", "cluster.id=c\nnode.id=1\ndirectory.id=d\n")
        self.assertEqual("INITIALIZED", result["state"])
        self.assertEqual("d", result["directoryId"])

    def test_read_failure_is_unknown(self):
        result = discovery.parse_meta_properties("k", "m", "n", "/data/meta.properties", "", True, "permission denied")
        self.assertEqual("UNKNOWN", result["state"])


if __name__ == "__main__":
    unittest.main()

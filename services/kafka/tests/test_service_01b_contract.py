import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
SERVICE = ROOT / "services" / "kafka"
ROLE = SERVICE / "ansible_collections" / "platform" / "kafka" / "roles" / "kafka_kraft"


class Service01BContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (SERVICE / "service.yml").open(encoding="utf-8") as stream:
            cls.manifest = yaml.safe_load(stream)
        with (SERVICE / "configuration.schema.json").open(encoding="utf-8") as stream:
            cls.schema = json.load(stream)

    def test_distributed_mode_allows_members_on_one_physical_host(self):
        placement = self.manifest["modes"]["kraft-distributed"]["placement"]
        self.assertEqual(3, placement["minMembers"])
        self.assertFalse(placement["distinctHosts"])
        self.assertEqual(3, placement["roleCardinality"]["controller"]["minimum"])

    def test_member_node_id_is_a_member_scoped_managed_setting(self):
        setting = self.manifest["configuration"]["settings"]["nodeId"]
        self.assertEqual(["member"], setting["scopes"])
        self.assertEqual("platform_kafka_node_id", setting["roleVariable"])
        self.assertEqual("integer", self.schema["properties"]["nodeId"]["type"])

    def test_role_has_one_multi_member_execution_path_and_legacy_normalization(self):
        source = (ROLE / "tasks" / "main.yml").read_text(encoding="utf-8")
        self.assertIn("Normalize SERVICE-01A input into one member", source)
        self.assertIn("include_tasks: member.yml", source)
        self.assertIn("sort(attribute='node_id')", source)

    def test_role_blocks_identity_port_and_storage_collisions(self):
        source = (ROLE / "tasks" / "main.yml").read_text(encoding="utf-8")
        self.assertIn("Reject duplicate Kafka node IDs", source)
        self.assertIn("Reject duplicate Kafka ports", source)
        self.assertIn("Reject duplicate member directories", source)

    def test_member_role_uses_explicit_dynamic_format_and_preserves_legacy_shortcut(self):
        source = (ROLE / "tasks" / "member.yml").read_text(encoding="utf-8")
        self.assertIn("controller.quorum.voters", source)
        self.assertIn("--initial-controllers", source)
        self.assertIn("--standalone", source)
        self.assertIn("_platform_kafka_instances | length > 1", source)

    def test_member_identity_is_not_an_inventory_host(self):
        source = (ROLE / "tasks" / "main.yml").read_text(encoding="utf-8")
        self.assertIn("platform_kafka_instances", source)
        self.assertIn("include_tasks: member.yml", source)
        self.assertNotIn("add_host", source)


if __name__ == "__main__":
    unittest.main()

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

    def test_role_has_one_generic_member_execution_path_and_legacy_adapter(self):
        source = (ROLE / "tasks" / "main.yml").read_text(encoding="utf-8")
        self.assertIn("Adapt legacy single-member variables", source)
        self.assertIn("Normalize Kafka members into the generic internal model", source)
        self.assertIn("include_tasks: member.yml", source)
        self.assertIn("Order normalized Kafka members deterministically", source)
        self.assertNotIn("SERVICE-01", source)
        self.assertNotIn("_platform_kafka_legacy_single", source)
        self.assertNotIn("exactly one local Kafka member", source)

    def test_role_blocks_identity_port_and_storage_collisions(self):
        source = (ROLE / "tasks" / "main.yml").read_text(encoding="utf-8")
        self.assertIn("Reject duplicate Kafka node IDs", source)
        self.assertIn("validate_host_resources.yml", source)
        resources = (ROLE / "tasks" / "validate_host_resources.yml").read_text(encoding="utf-8")
        self.assertIn("listener_ports", resources)
        self.assertIn("managed_paths", resources)

    def test_member_role_uses_controller_count_and_member_role_for_format_strategy(self):
        source = (ROLE / "tasks" / "member.yml").read_text(encoding="utf-8")
        self.assertIn("controller.quorum.voters", source)
        self.assertIn("--initial-controllers", source)
        self.assertIn("--no-initial-controllers", source)
        self.assertIn("--standalone", source)
        self.assertIn("_platform_kafka_controller_instances | length > 1", source)
        self.assertIn("'controller' not in kafka_member.roles", source)

    def test_quorum_and_effective_config_are_role_aware(self):
        main = (ROLE / "tasks" / "main.yml").read_text(encoding="utf-8")
        member = (ROLE / "tasks" / "member.yml").read_text(encoding="utf-8")
        verify = (ROLE / "tasks" / "verify.yml").read_text(encoding="utf-8")
        self.assertIn("_platform_kafka_controller_instances", main)
        self.assertIn("_platform_kafka_broker_instances", main)
        self.assertIn("_platform_kafka_local_controller_instances", main)
        self.assertIn("_platform_kafka_local_broker_instances", main)
        self.assertIn("for member in _platform_kafka_controller_instances", main)
        self.assertIn("'process.roles': kafka_member.roles | join(',')", member)
        self.assertNotIn("'process.roles': 'broker,controller'", member)
        self.assertIn("Add dynamic quorum projection when explicitly selected", member)
        self.assertIn("Add static quorum projection when explicitly selected", member)
        self.assertIn("--bootstrap-controller", verify)

    def test_dynamic_and_static_config_projections_are_mutually_exclusive(self):
        with (ROLE / "tasks" / "member.yml").open(encoding="utf-8") as stream:
            tasks = {task["name"]: task for task in yaml.safe_load(stream)}
        common = tasks["Build common member effective configuration"]["ansible.builtin.set_fact"]["kafka_effective_config"]
        dynamic = tasks["Add dynamic quorum projection when explicitly selected"]["ansible.builtin.set_fact"]["kafka_effective_config"]
        static = tasks["Add static quorum projection when explicitly selected"]["ansible.builtin.set_fact"]["kafka_effective_config"]
        self.assertNotIn("controller.quorum.bootstrap.servers", common)
        self.assertNotIn("controller.quorum.voters", common)
        self.assertIn("controller.quorum.bootstrap.servers", dynamic)
        self.assertNotIn("controller.quorum.voters", dynamic)
        self.assertIn("controller.quorum.voters", static)
        self.assertNotIn("combine({'controller.quorum.bootstrap.servers'", static)

    def test_split_role_static_fixture_uses_only_role_specific_ports(self):
        fixture_path = SERVICE / "tests" / "fixtures" / "split-role-static.yml"
        with fixture_path.open(encoding="utf-8") as stream:
            fixture = yaml.safe_load(stream)
        members = fixture["platform_kafka_instances"]
        controllers = [member for member in members if "controller" in member["roles"]]
        brokers = [member for member in members if "broker" in member["roles"]]
        self.assertEqual("static", fixture["platform_kafka_quorum_mode"])
        self.assertEqual(3, len(controllers))
        self.assertEqual(1, len(brokers))
        self.assertTrue(all("client_port" not in member for member in controllers))
        self.assertTrue(all("controller_port" not in member for member in brokers))

    def test_member_identity_is_not_an_inventory_host(self):
        source = (ROLE / "tasks" / "main.yml").read_text(encoding="utf-8")
        self.assertIn("platform_kafka_instances", source)
        self.assertIn("include_tasks: member.yml", source)
        self.assertNotIn("add_host", source)


if __name__ == "__main__":
    unittest.main()

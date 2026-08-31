import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
SERVICE = ROOT / "services" / "kafka"
ROLE = SERVICE / "ansible_collections" / "platform" / "kafka" / "roles" / "kafka_kraft"
FIXTURE = ROOT / "examples" / "valid" / "kafka-split-multihost"


class Service01DContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (FIXTURE / "inventory" / "group_vars" / "all" / "platform.yml").open(encoding="utf-8") as stream:
            cls.variables = yaml.safe_load(stream)

    def test_fixture_has_three_split_members_on_three_hosts(self):
        members = self.variables["platform_kafka_instances"]
        controllers = [member for member in members if member["roles"] == ["controller"]]
        brokers = [member for member in members if member["roles"] == ["broker"]]
        self.assertEqual(6, len(members))
        self.assertEqual(3, len(controllers))
        self.assertEqual(3, len(brokers))
        self.assertEqual({"node1", "node2", "node3"}, {member["host"] for member in members})
        self.assertEqual({1, 2, 3, 4, 5, 6}, {member["node_id"] for member in members})
        self.assertTrue(all("client_port" not in member for member in controllers))
        self.assertTrue(all("controller_port" not in member for member in brokers))
        self.assertTrue(all("directory_id" in member for member in controllers))

    def test_fixture_places_one_controller_and_broker_on_each_host(self):
        members = self.variables["platform_kafka_instances"]
        for host in ("node1", "node2", "node3"):
            local = [member for member in members if member["host"] == host]
            self.assertEqual([["broker"], ["controller"]], sorted(member["roles"] for member in local))
            self.assertEqual(2, len({member["data_directory"] for member in local}))
            self.assertEqual(2, len({member["log_directory"] for member in local}))

    def test_role_projects_quorum_from_only_controllers_and_formats_brokers_outside_it(self):
        main = (ROLE / "tasks" / "main.yml").read_text(encoding="utf-8")
        member = (ROLE / "tasks" / "member.yml").read_text(encoding="utf-8")
        self.assertIn("for member in _platform_kafka_controller_instances", main)
        self.assertIn("_platform_kafka_broker_bootstrap_servers", main)
        self.assertIn("Format uninitialized dynamic non-controller storage exactly once", member)
        self.assertIn("--no-initial-controllers", member)
        self.assertIn("Validate role-specific effective Kafka configuration", member)

    def test_verify_requires_controller_membership_and_broker_registration(self):
        verify = (ROLE / "tasks" / "verify.yml").read_text(encoding="utf-8")
        self.assertIn("Assert Kafka controller quorum leader and membership", verify)
        self.assertIn("LeaderId", verify)
        self.assertIn("kafka-broker-api-versions.sh", verify)
        self.assertIn("Assert Kafka brokers are registered and unfenced", verify)


if __name__ == "__main__":
    unittest.main()

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
        with (FIXTURE / "project.yml").open(encoding="utf-8") as stream:
            cls.variables = yaml.safe_load(stream)

    def test_fixture_has_three_split_members_on_three_hosts(self):
        placement = yaml.safe_load((FIXTURE / "inventory" / "hosts.yml").read_text(encoding="utf-8"))["all"]["hosts"]
        members = [
            dict(member, id=member_id, host=host)
            for host, host_vars in placement.items()
            for member_id, member in host_vars.get("platform_deployments", {}).get("kafka-main", {}).get("members", {}).items()
        ]
        controllers = [member for member in members if member["roles"] == ["controller"]]
        brokers = [member for member in members if member["roles"] == ["broker"]]
        self.assertEqual(6, len(members))
        self.assertEqual(3, len(controllers))
        self.assertEqual(3, len(brokers))
        self.assertEqual({"node1", "node2", "node3"}, {
            host for host in placement
            if placement[host].get("platform_deployments", {}).get("kafka-main", {}).get("members")
        })
        self.assertEqual({1, 2, 3, 4, 5, 6}, {member["configuration"]["nodeId"] for member in members})
        self.assertTrue(all("clientPort" not in member.get("configuration", {}) for member in controllers))
        self.assertTrue(all("controllerPort" not in member.get("configuration", {}) for member in brokers))
        self.assertTrue(all("directoryId" in member.get("identity", {}) for member in controllers))

    def test_fixture_places_one_controller_and_broker_on_each_host(self):
        placement = yaml.safe_load((FIXTURE / "inventory" / "hosts.yml").read_text(encoding="utf-8"))["all"]["hosts"]
        for host in ("node1", "node2", "node3"):
            local = list(placement[host]["platform_deployments"]["kafka-main"]["members"].values())
            self.assertEqual([["broker"], ["controller"]], sorted(member["roles"] for member in local))
            self.assertEqual(2, len(local))

    def test_role_projects_quorum_from_only_controllers_and_formats_brokers_outside_it(self):
        main = (ROLE / "tasks" / "main.yml").read_text(encoding="utf-8")
        member = (ROLE / "tasks" / "member.yml").read_text(encoding="utf-8")
        self.assertIn("for member in _platform_kafka_controller_instances", main)
        self.assertIn("_platform_kafka_broker_bootstrap_servers", main)
        self.assertIn("Format uninitialized Kafka storage exactly once", member)
        self.assertIn("NO_INITIAL_CONTROLLERS", member)
        self.assertIn("--no-initial-controllers", member)
        self.assertIn("Validate role-specific effective Kafka configuration", member)

    def test_verify_requires_controller_membership_and_broker_registration(self):
        verify = (ROLE / "tasks" / "verify.yml").read_text(encoding="utf-8")
        self.assertIn("Assert Kafka controller quorum leader and membership", verify)
        self.assertIn("LeaderId", verify)
        self.assertIn("kafka-broker-api-versions.sh", verify)
        self.assertIn("Assert Kafka brokers are registered and unfenced", verify)

    def test_acceptance_runner_persists_recoverable_lifecycle_state(self):
        runner = (SERVICE / "tests" / "run_service_01d_acceptance.sh").read_text(encoding="utf-8")
        for token in ("status.json", "pid", "STALE", "write_status PASS", "write_status FAILED"):
            self.assertIn(token, runner)
        self.assertIn("runner process is no longer alive", runner)

    def test_acceptance_runner_rejects_a_live_duplicate(self):
        runner = (SERVICE / "tests" / "run_service_01d_acceptance.sh").read_text(encoding="utf-8")
        self.assertIn("runner is already active", runner)
        self.assertIn("os.kill(pid, 0)", runner)


if __name__ == "__main__":
    unittest.main()

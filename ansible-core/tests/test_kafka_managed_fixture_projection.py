import importlib.util
import os
import sys
import unittest
from pathlib import Path

import yaml


ROOT = os.path.join(os.path.dirname(__file__), "..")
MODULE_ROOT = os.path.join(ROOT, "collections", "ansible_collections", "platform", "core", "plugins", "module_utils")
spec = importlib.util.spec_from_file_location(
    "kafka_runtime_projection",
    os.path.join(MODULE_ROOT, "kafka_runtime_projection.py"),
)
projection = importlib.util.module_from_spec(spec)
sys.modules["kafka_runtime_projection"] = projection
spec.loader.exec_module(projection)


class ManagedKafkaFixtureProjectionTests(unittest.TestCase):
    FIXTURES = {
        "kafka-single": {"mode": "kraft-standalone", "namespace": None},
        "kafka-distributed": {"mode": "kraft-distributed", "namespace": "kafka-same-host"},
        "kafka-real-multihost": {"mode": "kraft-distributed", "namespace": "kafka-main"},
        "kafka-split-multihost": {"mode": "kraft-distributed", "namespace": "kafka-split"},
    }

    def test_managed_fixtures_project_to_the_established_role_shape(self):
        for name, expected in self.FIXTURES.items():
            with self.subTest(fixture=name):
                fixture = os.path.join(ROOT, "..", "examples", "valid", name)
                variables = yaml.safe_load(Path(fixture, "inventory", "group_vars", "all", "platform.yml").read_text(encoding="utf-8"))
                state_variables = yaml.safe_load(Path(fixture, "inventory", "group_vars", "all", "platform-state.yml").read_text(encoding="utf-8"))
                inventory = yaml.safe_load(Path(fixture, "inventory", "hosts.yml").read_text(encoding="utf-8"))
                desired = variables["platform_desired_state"]["serviceDeployments"]["kafka-main"]
                generated = state_variables["platform_generated_state"]["serviceDeployments"]["kafka-main"]
                self.assertNotIn("platform_generated_state", variables)
                placement = inventory["all"]["hosts"]
                members = {}
                addresses = {}
                for host, host_vars in placement.items():
                    if host == "localhost":
                        continue
                    addresses[host] = host_vars.get("ansible_host", host)
                    for member_id, member in host_vars.get("platform_deployments", {}).get("kafka-main", {}).get("members", {}).items():
                        members[member_id] = dict(member, host=host)
                topology = {"resolvedTopology": {"serviceDeployments": {
                    "kafka-main": {
                        "serviceType": "kafka",
                        "mode": expected["mode"],
                        "identity": generated.get("identity", {}),
                        "members": members,
                    }
                }}}
                configuration = {"configuration": desired.get("configuration", {}), "members": {
                    member_id: {"configuration": member.get("configuration", {})}
                    for member_id, member in members.items()
                }}
                result = projection.project_kafka_runtime(
                    topology, {"services": {"kafka-main": configuration}}, addresses
                )["kafka-main"]
                self.assertEqual(generated["identity"].get("clusterId"), result["clusterId"])
                self.assertEqual("dynamic", result["quorumMode"])
                self.assertTrue(result["runtimeProjectionFingerprint"].startswith("sha256:"))
                self.assertEqual(len(members), len(result["instances"]))
                for instance in result["instances"]:
                    member_id = instance["id"]
                    self.assertEqual(members[member_id]["host"], instance["host"])
                    self.assertEqual(members[member_id]["roles"], instance["roles"])
                    self.assertEqual(
                        members[member_id]["configuration"]["nodeId"],
                        instance["node_id"],
                    )
                    if expected["namespace"]:
                        self.assertEqual(
                            f"/var/lib/kafka/{expected['namespace']}/{member_id}",
                            instance["data_directory"],
                        )
                        self.assertEqual(
                            f"/var/log/kafka/{expected['namespace']}/{member_id}",
                            instance["log_directory"],
                        )
                        self.assertEqual(
                            f"/etc/kafka/kafka/{member_id}", instance["config_directory"]
                        )
                    else:
                        self.assertEqual("/var/lib/kafka/kafka-standalone", instance["data_directory"])
                        self.assertEqual("/var/log/kafka/kafka-standalone", instance["log_directory"])
                        self.assertEqual("/etc/kafka", instance["config_directory"])


if __name__ == "__main__":
    unittest.main()

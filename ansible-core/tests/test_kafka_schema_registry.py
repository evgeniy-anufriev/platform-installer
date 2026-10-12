import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "collections"))
from ansible_collections.platform.core.plugins.module_utils.kafka_schema_registry import registry_projection, configuration_registry_findings
from ansible_collections.platform.core.plugins.module_utils.deployment_plan import _artifact_requirements


def member(number=1, roles=None, host=None):
    return {"id": "kafka-%s" % number, "deployment_id": "qa-kafka", "host": host or "node%s" % number,
            "roles": roles or ["broker", "controller"], "advertised_host": "node%s.example.test" % number,
            "listeners": {"SSL": {"purpose": "interBroker", "securityProtocol": "SSL", "port": 9094},
                          "CONTROLLER": {"purpose": "controller", "securityProtocol": "SSL", "port": 9093}}}


class RegistryProjectionTests(unittest.TestCase):
    def test_default_ssl_interbroker_and_both_rest_ports(self):
        result = registry_projection([member()])
        self.assertEqual([], result["findings"])
        value = result["instances"][0]
        self.assertEqual((8081, 8082, 1, 1), (value["http_port"], value["https_port"], value["replication_factor"], value["min_insync_replicas"]))
        self.assertEqual("SSL://node1.example.test:9094", value["bootstrap_servers"])

    def test_each_independent_root_requires_ownership(self):
        value = registry_projection([member()])["instances"][0]
        self.assertEqual([value["config_directory"], value["log_directory"]], value["ownership_paths"])
        self.assertTrue(set(value["ownership_paths"]).issubset(value["managed_paths"]))

    def test_split_controllers_never_host_registry_or_bootstrap(self):
        result = registry_projection([member(1, ["controller"]), member(2, ["broker"])])
        self.assertEqual(["kafka-2"], [entry["id"] for entry in result["instances"]])
        self.assertNotIn("node1", result["instances"][0]["bootstrap_servers"])

    def test_colocated_ports_require_explicit_overrides(self):
        values = [member(1, ["broker"], "node1"), member(2, ["broker"], "node1")]
        values[1]["listeners"]["SSL"]["port"] = 9194
        self.assertIn("SCHEMA_REGISTRY_PORT_COLLISION", [f["code"] for f in registry_projection(values)["findings"]])
        values[1]["schema_registry"] = {"http_port": 8181, "https_port": 8182}
        self.assertEqual([], registry_projection(values)["findings"])

    def test_controller_listener_is_forbidden(self):
        self.assertIn("SCHEMA_REGISTRY_LISTENER_INVALID", [f["code"] for f in registry_projection([member()], listener="CONTROLLER")["findings"]])

    def test_boolean_and_equal_ports_are_rejected(self):
        self.assertTrue(registry_projection([member()], http_port=True)["findings"])
        self.assertTrue(registry_projection([member()], http_port=8082)["findings"])

    def test_disabled_retains_resources_without_listener_requirement(self):
        value = member()
        value["listeners"] = {}
        result = registry_projection([value], enabled=False)
        self.assertEqual([], result["findings"])
        self.assertEqual(1, len(result["instances"]))

    def test_rf_never_depends_on_live_brokers(self):
        result = registry_projection([member(1, ["broker"]), member(2, ["broker"])])
        self.assertEqual((2, 2), (result["instances"][0]["replication_factor"], result["instances"][0]["min_insync_replicas"]))

    def test_mixed_security_protocols_block(self):
        value = member(2)
        value["listeners"]["SSL"]["securityProtocol"] = "PLAINTEXT"
        self.assertIn("SCHEMA_REGISTRY_PROTOCOL_MISMATCH", [f["code"] for f in registry_projection([member(), value])["findings"]])

    def test_traversal_path_is_rejected(self):
        value = member()
        self.assertTrue(registry_projection([value], config_root="/etc/../../root")["findings"])

    def test_member_order_does_not_change_runtime(self):
        self.assertEqual(registry_projection([member(1), member(2)]), registry_projection([member(2), member(1)]))

    def test_resolved_config_validation_blocks_collision(self):
        resolved = lambda value: {"state": "RESOLVED", "value": value}
        config = {"schemaRegistryEnabled": resolved(True), "schemaRegistryHttpPort": resolved(8082),
                  "schemaRegistryHttpsPort": resolved(8082), "listeners": resolved(member()["listeners"])}
        services = {"qa-kafka": {"serviceType": "kafka", "configuration": config,
                                "members": {"kafka-1": {"configuration": config}}}}
        topology = {"resolvedTopology": {"serviceDeployments": {"qa-kafka": {"members": {"kafka-1": member()}}}}}
        self.assertTrue(configuration_registry_findings(services, topology))


class ConditionalArtifactTests(unittest.TestCase):
    def setUp(self):
        self.definitions = {"kafka": {"configuration": {"settings": {"schemaRegistryEnabled": {"type": "boolean", "scopes": ["deployment"]}}},
                                     "artifacts": [{"id": "schema-registry-binary", "name": "confluent-schema-registry", "version": "8.3.2",
                                                    "digest": "sha256:" + "a" * 64, "x-enabledBy": "schemaRegistryEnabled", "x-memberRole": "broker"}]}}
        self.deployments = {"qa-kafka": {"serviceType": "kafka"}}

    def configuration(self, value):
        return {"services": {"qa-kafka": {"configuration": {"schemaRegistryEnabled": {"state": "RESOLVED", "value": value}}}}}

    def test_disabled_does_not_require_registry_artifact(self):
        self.assertEqual([], _artifact_requirements(self.deployments, self.definitions, self.configuration(False)))

    def test_enabled_requires_pinned_artifact(self):
        self.assertEqual("schema-registry-binary", _artifact_requirements(self.deployments, self.definitions, self.configuration(True))[0]["requirementId"])

    def test_unresolved_activation_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "ARTIFACT_ACTIVATION_UNRESOLVED"):
            _artifact_requirements(self.deployments, self.definitions, {})

    def test_invalid_activation_contract_fails_closed(self):
        self.definitions["kafka"]["configuration"]["settings"]["schemaRegistryEnabled"]["type"] = "string"
        with self.assertRaisesRegex(ValueError, "ARTIFACT_ACTIVATION_CONTRACT_INVALID"):
            _artifact_requirements(self.deployments, self.definitions, self.configuration(True))


if __name__ == "__main__":
    unittest.main()

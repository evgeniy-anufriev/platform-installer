import importlib.util
import os
import sys
import unittest
from pathlib import Path

import yaml


ROOT = os.path.join(os.path.dirname(__file__), "..", "collections", "ansible_collections", "platform", "core", "plugins", "module_utils")
sys.path.insert(0, ROOT)
spec = importlib.util.spec_from_file_location("kafka_listener_resolution", os.path.join(ROOT, "kafka_listener_resolution.py"))
resolution = importlib.util.module_from_spec(spec)
sys.modules["kafka_listener_resolution"] = resolution
spec.loader.exec_module(resolution)


class KafkaListenerResolutionTests(unittest.TestCase):
    def setUp(self):
        self.member = {"id": "combined", "roles": ["broker", "controller"], "advertised_host": "kafka.example"}

    def test_named_plaintext_and_ssl_are_deterministic(self):
        config = {"listeners": {
            "CLIENT_SSL": {"purpose": "client", "securityProtocol": "SSL", "port": 9092, "tlsProfile": "infra"},
            "CONTROLLER": {"purpose": "controller", "securityProtocol": "PLAINTEXT", "port": 9093},
            "INTERNAL": {"purpose": "interBroker", "securityProtocol": "SSL", "port": 9094, "tlsProfile": "infra"},
        }}
        first = resolution.listener_runtime_properties(config, self.member)
        second = resolution.listener_runtime_properties(config, self.member)
        self.assertEqual(first, second)
        self.assertEqual("CLIENT_SSL://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093,INTERNAL://0.0.0.0:9094", first["properties"]["listeners"])
        self.assertEqual("INTERNAL", first["properties"]["inter.broker.listener.name"])

    def test_controller_only_does_not_receive_broker_listeners(self):
        config = {"listeners": {
            "CLIENT": {"purpose": "client", "securityProtocol": "PLAINTEXT", "port": 9092},
            "CONTROLLER": {"purpose": "controller", "securityProtocol": "PLAINTEXT", "port": 9093},
        }}
        result = resolution.project_member_listeners(config, {"roles": ["controller"], "advertised_host": "node1"})
        self.assertEqual(["CONTROLLER"], [item["name"] for item in result["listeners"]])

    def test_ssl_listener_uses_service_profile_and_legacy_ports_are_supported(self):
        named = resolution.normalize_listeners({"listeners": {"CLIENT": {"purpose": "client", "securityProtocol": "SSL", "port": 9092}}}, self.member)
        self.assertEqual("PASS", named["status"])
        legacy = resolution.normalize_listeners({}, dict(self.member, client_port=9092, controller_port=9093))
        self.assertEqual("PASS", legacy["status"])
        self.assertEqual("PLAINTEXT", legacy["listeners"]["CLIENT"]["securityProtocol"])

    def test_named_and_legacy_conflict_is_blocked(self):
        result = resolution.normalize_listeners({"clientPort": 9092, "listeners": {"CLIENT": {"purpose": "client", "securityProtocol": "PLAINTEXT", "port": 9192}}}, dict(self.member, client_port=9092))
        self.assertEqual("BLOCKED", result["status"])

    def test_role_defaults_provide_plaintext_and_ssl_listeners(self):
        defaults_path = Path(__file__).parents[2] / "services" / "kafka" / "ansible_collections" / "platform" / "kafka" / "roles" / "kafka_kraft" / "defaults" / "main.yml"
        defaults = yaml.safe_load(defaults_path.read_text(encoding="utf-8"))
        listeners = defaults["platform_kafka_listeners"]
        self.assertEqual("PLAINTEXT", listeners["PLAINTEXT"]["securityProtocol"])
        self.assertEqual("SSL", listeners["SSL"]["securityProtocol"])
        self.assertNotIn("tlsProfile", listeners["SSL"])


if __name__ == "__main__":
    unittest.main()

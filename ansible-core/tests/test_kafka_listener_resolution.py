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

    def test_broker_only_receives_controller_listener_for_kraft_quorum(self):
        config = {"listeners": {
            "PLAINTEXT": {"purpose": "client", "securityProtocol": "PLAINTEXT", "port": 9092},
            "SSL": {"purpose": "interBroker", "securityProtocol": "SSL", "port": 9094},
            "CONTROLLER": {"purpose": "controller", "securityProtocol": "SSL", "port": 9095},
        }}
        result = resolution.project_member_listeners(config, {"roles": ["broker"], "advertised_host": "node1"})
        self.assertEqual(["CONTROLLER", "PLAINTEXT", "SSL"], [item["name"] for item in result["listeners"]])

    def test_ssl_listener_requires_named_configuration(self):
        named = resolution.normalize_listeners({"listeners": {"CLIENT": {"purpose": "client", "securityProtocol": "SSL", "port": 9092}}}, self.member)
        self.assertEqual("PASS", named["status"])
        result = resolution.normalize_listeners({}, self.member)
        self.assertEqual("BLOCKED", result["status"])

    def test_scram_is_a_separate_client_listener_and_never_an_internal_protocol(self):
        listeners = {
            'CLIENT': {'purpose': 'client', 'securityProtocol': 'SASL_SSL', 'port': 9096},
            'SSL': {'purpose': 'interBroker', 'securityProtocol': 'SSL', 'port': 9094},
            'CONTROLLER': {'purpose': 'controller', 'securityProtocol': 'SSL', 'port': 9093},
        }
        result = resolution.listener_runtime_properties({'listeners': listeners}, self.member)
        self.assertEqual('PASS', result['status'])
        self.assertIn('CLIENT:SASL_SSL', result['properties']['listener.security.protocol.map'])
        self.assertEqual('SSL', result['properties']['inter.broker.listener.name'])
        listeners['CLIENT']['purpose'] = 'interBroker'
        self.assertEqual('BLOCKED', resolution.normalize_listeners({'listeners': listeners}, self.member)['status'])

    def test_role_defaults_provide_plaintext_and_ssl_listeners(self):
        defaults_path = Path(__file__).parents[2] / "services" / "kafka" / "ansible_collections" / "platform" / "kafka" / "roles" / "kafka_kraft" / "defaults" / "main.yml"
        defaults = yaml.safe_load(defaults_path.read_text(encoding="utf-8"))
        listeners = defaults["platform_kafka_listeners"]
        self.assertEqual("PLAINTEXT", listeners["PLAINTEXT"]["securityProtocol"])
        self.assertEqual("SSL", listeners["SSL"]["securityProtocol"])
        self.assertNotIn("tlsProfile", listeners["SSL"])

    def test_controller_sasl_ssl_is_projected_for_controller_and_broker_roles(self):
        listeners = {
            'QUORUM': {'purpose': 'controller', 'securityProtocol': 'SASL_SSL', 'port': 19093},
            'CLIENT': {'purpose': 'client', 'securityProtocol': 'SASL_SSL', 'port': 19096},
            'REPLICATION': {'purpose': 'interBroker', 'securityProtocol': 'SSL', 'port': 19094},
        }
        for roles in [['controller'], ['broker'], ['controller','broker']]:
            result = resolution.listener_runtime_properties({'listeners': listeners}, dict(self.member,roles=roles))
            self.assertEqual('PASS',result['status'])
            self.assertIn('QUORUM:SASL_SSL',result['properties']['listener.security.protocol.map'])
            self.assertEqual('QUORUM',result['properties']['controller.listener.names'])


if __name__ == "__main__":
    unittest.main()

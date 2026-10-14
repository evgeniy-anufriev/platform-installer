import importlib.util
import os
import sys
import unittest


ROOT = os.path.join(os.path.dirname(__file__), "..", "collections", "ansible_collections", "platform", "core", "plugins", "module_utils")
sys.path.insert(0, ROOT)
spec = importlib.util.spec_from_file_location("kafka_runtime_projection", os.path.join(ROOT, "kafka_runtime_projection.py"))
projection = importlib.util.module_from_spec(spec)
sys.modules["kafka_runtime_projection"] = projection
spec.loader.exec_module(projection)


class KafkaRuntimeProjectionTests(unittest.TestCase):
    def test_split_projection_is_deterministic_and_preserves_paths(self):
        members = {
            "controller-1": {"host": "node1", "roles": ["controller"]},
            "broker-1": {"host": "node1", "roles": ["broker"]},
        }
        config = {
            "configuration": {"clusterId": "cluster", "quorumMode": "dynamic", "runtimePathNamespace": "kafka-split"},
            "members": {name: {"configuration": {"nodeId": node}} for name, node in (("controller-1", 1), ("broker-1", 4))},
        }
        topology = {"resolvedTopology": {"serviceDeployments": {"kafka-main": {"serviceType": "kafka", "mode": "kraft-distributed", "members": members}}}}
        first = projection.project_kafka_runtime(topology, {"services": {"kafka-main": config}}, {"node1": "192.168.56.101"})
        second = projection.project_kafka_runtime(topology, {"services": {"kafka-main": config}}, {"node1": "192.168.56.101"})
        self.assertEqual(first, second)
        instances = first["kafka-main"]["instances"]
        self.assertEqual("/var/lib/kafka-main/controller-1", instances[1]["data_directory"])
        self.assertEqual("192.168.56.101", instances[0]["advertised_host"])

    def test_explicit_address_wins_over_transport_address(self):
        topology = {"resolvedTopology": {"serviceDeployments": {"k": {"serviceType": "kafka", "mode": "kraft-standalone", "members": {"m": {"host": "node1", "roles": ["broker", "controller"]}}}}}}
        cfg = {"services": {"k": {"configuration": {"clusterId": "c", "dataDirectory": "/var/lib/kafka/one", "logDirectory": "/var/log/kafka/one", "configDirectory": "/etc/kafka/one"}, "members": {"m": {"configuration": {"nodeId": 1, "advertisedHost": "kafka.example"}}}}}}
        out = projection.project_kafka_runtime(topology, cfg, {"node1": "192.0.2.1"})["k"]["instances"][0]
        self.assertEqual("kafka.example", out["advertised_host"])
        self.assertEqual("/var/lib/kafka/one", out["data_directory"])


if __name__ == "__main__":
    unittest.main()

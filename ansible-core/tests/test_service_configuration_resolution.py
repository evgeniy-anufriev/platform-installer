import importlib.util
import os
import sys
import unittest


ROOT = os.path.join(
    os.path.dirname(__file__), "..", "collections", "ansible_collections", "platform",
    "core", "plugins", "module_utils",
)


def load_module(name, filename):
    path = os.path.join(ROOT, filename)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


VALIDATION = load_module("project_validation_for_configuration", "project_validation.py")
RESOLUTION = load_module("topology_resolution_for_configuration", "topology_resolution.py")
CONFIGURATION = load_module("service_configuration_resolution", "service_configuration_resolution.py")


def catalog():
    definition = {
        "metadata": {"id": "kafka", "version": "1"},
        "modes": {"kraft-standalone": {}},
        "configurationSchema": {"$ref": "configuration.schema.json"},
        "configurationMapping": {
            "clientPort": {"roleVariable": "platform_kafka_client_port"},
            "dataDirectory": {"roleVariable": "platform_kafka_data_directory"},
        },
    }
    definition["x-definitionDigest"] = VALIDATION.canonical_digest(definition)
    unsigned = {
        "apiVersion": "platform.installer/catalog/v1alpha1",
        "kind": "ServiceCatalog",
        "definitions": {"kafka": definition},
    }
    return dict(unsigned, digest=VALIDATION.canonical_digest(unsigned))


def topology(configuration=None, member_configuration=None, host="node-a"):
    member = {"host": host, "roles": ["broker", "controller"]}
    if member_configuration is not None:
        member["configuration"] = member_configuration
    deployment = {
        "serviceType": "kafka",
        "definitionVersion": "1",
        "mode": "kraft-standalone",
        "members": {"member-a": member},
    }
    if configuration is not None:
        deployment["configuration"] = configuration
    return {"serviceDeployments": {"kafka-main": deployment}}


def resolved(topology_value):
    return {
        "status": "PASS",
        "resolvedTopology": {
            "serviceDeployments": {
                "kafka-main": {
                    "serviceType": "kafka",
                    "definitionVersion": "1",
                    "mode": "kraft-standalone",
                    "members": {"member-a": {"host": "node-a", "roles": ["broker", "controller"]}},
                }
            }
        },
        "topologyFingerprint": VALIDATION.canonical_digest(topology_value),
    }


class ServiceConfigurationResolutionTests(unittest.TestCase):
    def resolve(self, project_topology, defaults=None, topology_result=None):
        project_topology = project_topology or topology()
        return CONFIGURATION.resolve_service_configuration(
            topology_result or resolved(project_topology),
            project_topology,
            catalog(),
            {"kafka": defaults or {
                "platform_kafka_client_port": 9092,
                "platform_kafka_data_directory": "/var/lib/kafka",
            }},
            {"kafka": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "clientPort": {"type": "integer", "minimum": 1, "maximum": 65535},
                    "dataDirectory": {"type": "string", "minLength": 1},
                },
            }},
        )

    def test_materializes_literal_role_defaults_and_override(self):
        result = self.resolve(topology({"clientPort": 19092}))
        config = result["services"]["kafka-main"]["configuration"]
        self.assertEqual({"state": "RESOLVED", "value": 19092, "source": "OVERRIDE"}, config["clientPort"])
        self.assertEqual({"state": "RESOLVED", "value": "/var/lib/kafka", "source": "DEFAULT"}, config["dataDirectory"])
        self.assertEqual("PASS", result["status"])

    def test_non_literal_default_is_deferred(self):
        result = self.resolve(topology(), {
            "platform_kafka_client_port": "{{ platform_kafka_default_port }}",
            "platform_kafka_data_directory": "/var/lib/kafka",
        })
        value = result["services"]["kafka-main"]["configuration"]["clientPort"]
        self.assertEqual({"state": "DEFERRED", "reason": "NON_LITERAL_ROLE_DEFAULT", "source": "DEFAULT"}, value)
        self.assertEqual("PASS", result["status"])

    def test_member_configuration_is_blocked_with_exact_identity(self):
        result = self.resolve(topology(member_configuration={"clientPort": 1}))
        self.assertEqual("BLOCKED", result["status"])
        finding = result["findings"][0]
        self.assertEqual("MEMBER_CONFIGURATION_UNSUPPORTED", finding["code"])
        self.assertEqual("serviceDeployments.kafka-main.members.member-a.configuration", finding["field"])
        self.assertEqual("kafka-main", finding["safeDetails"]["deploymentId"])
        self.assertEqual("member-a", finding["safeDetails"]["memberId"])

    def test_placement_does_not_affect_configuration_fingerprint(self):
        first_topology = topology({"clientPort": 19092}, host="node-a")
        second_topology = topology({"clientPort": 19092}, host="node-b")
        first = self.resolve(first_topology)
        second_result = resolved(second_topology)
        second = self.resolve(second_topology, topology_result=second_result)
        self.assertNotEqual(first["services"]["kafka-main"]["inputs"]["topologyFingerprint"], second["services"]["kafka-main"]["inputs"]["topologyFingerprint"])
        self.assertEqual(first["configurationFingerprint"], second["configurationFingerprint"])

    def test_unknown_logical_override_requires_mapping(self):
        result = self.resolve(topology({"unknown": 1}))
        self.assertEqual("SERVICE_CONFIGURATION_MAPPING_INVALID", result["findings"][0]["code"])

    def test_schema_type_and_range_findings_are_safe(self):
        result = self.resolve(topology({"clientPort": 0}))
        self.assertEqual("BLOCKED", result["status"])
        self.assertEqual("SERVICE_CONFIGURATION_MINIMUM_INVALID", result["findings"][0]["code"])


if __name__ == "__main__":
    unittest.main()

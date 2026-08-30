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


VALIDATION = load_module("project_validation", "project_validation.py")
RESOLUTION = load_module("topology_resolution", "topology_resolution.py")


def catalog(extra=False):
    definition = {
        "apiVersion": "platform.installer/service-manifest/v1alpha1",
        "kind": "ServiceManifest",
        "metadata": {"id": "kafka", "version": "1"},
        "modes": {
            "kraft-distributed": {
                "displayName": "Distributed",
                "memberRoles": ["broker", "controller"],
                "placement": {
                    "explicit": True,
                    "minMembers": 2,
                    "distinctHosts": True,
                    "roleCardinality": {"controller": {"minimum": 1}},
                },
            }
        },
        "configurationSchema": {"$ref": "configuration.schema.json"},
        "configurationMapping": {
            "clientPort": {"roleVariable": "platform_kafka_client_port"},
            "controllerPort": {"roleVariable": "platform_kafka_controller_port"},
        },
        "roleEntrypoints": {},
    }
    definition["x-definitionDigest"] = VALIDATION.canonical_digest(definition)
    definitions = {"kafka": definition}
    if extra:
        other = dict(definition, metadata={"id": "unused", "version": "1"})
        other["x-definitionDigest"] = VALIDATION.canonical_digest(other)
        definitions["unused"] = other
    unsigned = {
        "apiVersion": "platform.installer/catalog/v1alpha1",
        "kind": "ServiceCatalog",
        "definitions": definitions,
    }
    return dict(unsigned, digest=VALIDATION.canonical_digest(unsigned))


def manifest(project_id="project-a", fixture_catalog=None):
    fixture_catalog = fixture_catalog or catalog()
    return {
        "apiVersion": "platform.installer/v2alpha1",
        "kind": "PlatformProject",
        "metadata": {"id": project_id},
        "desiredStateContract": "platform.installer/project-desired-state/v2alpha1",
        "catalogLock": {
            "apiVersion": "platform.installer/catalog/v1alpha1",
            "digest": fixture_catalog["digest"],
            "services": {
                "kafka": {
                    "definitionVersion": "1",
                    "digest": fixture_catalog["definitions"]["kafka"]["x-definitionDigest"],
                }
            },
        },
        "artifactLock": {
            "apiVersion": "platform.installer/artifacts/v1alpha1",
            "digest": "sha256:" + "1" * 64,
        },
    }


def topology(reverse=False):
    members = {
        "member-b": {"host": "node-b", "roles": ["controller", "broker"]},
        "member-a": {"host": "node-a", "roles": ["broker"]},
    }
    if reverse:
        members = dict(reversed(list(members.items())))
    return {"serviceDeployments": {"kafka-main": {
        "serviceType": "kafka",
        "definitionVersion": "1",
        "mode": "kraft-distributed",
        "members": members,
        "configuration": {"ignoredByTopology": True},
    }}}


class TopologyResolutionTests(unittest.TestCase):
    def test_resolves_only_canonical_explicit_topology(self):
        result = RESOLUTION.resolve_topology(
            manifest(), topology(), ["node-a", "node-b"], catalog()
        )
        self.assertEqual("PASS", result["status"])
        self.assertNotIn("configuration", result["resolvedTopology"]["serviceDeployments"]["kafka-main"])
        self.assertEqual(["broker", "controller"], result["resolvedTopology"]["serviceDeployments"]["kafka-main"]["members"]["member-b"]["roles"])

    def test_unordered_collections_have_same_fingerprint(self):
        first = RESOLUTION.resolve_topology(manifest(), topology(), ["node-a", "node-b"], catalog())
        second = RESOLUTION.resolve_topology(manifest(), topology(True), ["node-b", "node-a"], catalog())
        self.assertEqual(first["resolvedTopology"], second["resolvedTopology"])
        self.assertEqual(first["topologyFingerprint"], second["topologyFingerprint"])

    def test_project_identity_is_not_in_topology_fingerprint(self):
        first = RESOLUTION.resolve_topology(manifest("project-a"), topology(), ["node-a", "node-b"], catalog())
        second = RESOLUTION.resolve_topology(manifest("project-b"), topology(), ["node-a", "node-b"], catalog())
        self.assertEqual(first["topologyFingerprint"], second["topologyFingerprint"])

    def test_only_used_definition_digests_affect_fingerprint(self):
        first_catalog = catalog()
        second_catalog = catalog(extra=True)
        first = RESOLUTION.resolve_topology(manifest(fixture_catalog=first_catalog), topology(), ["node-a", "node-b"], first_catalog)
        second = RESOLUTION.resolve_topology(manifest(fixture_catalog=second_catalog), topology(), ["node-a", "node-b"], second_catalog)
        self.assertEqual(first["serviceDefinitionDigests"], second["serviceDefinitionDigests"])
        self.assertEqual(first["topologyFingerprint"], second["topologyFingerprint"])

    def test_reuses_core_validation_for_placement_conflict(self):
        invalid = topology()
        invalid["serviceDeployments"]["kafka-main"]["members"]["member-a"]["host"] = "node-b"
        result = RESOLUTION.resolve_topology(manifest(), invalid, ["node-a", "node-b"], catalog())
        self.assertEqual("BLOCKED", result["status"])
        self.assertIn("PLACEMENT_DISTINCT_HOSTS_REQUIRED", [item["code"] for item in result["findings"]])

if __name__ == "__main__":
    unittest.main()

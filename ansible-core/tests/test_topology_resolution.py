import importlib.util
import copy
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


def keepalived_catalog():
    fixture_catalog = catalog()
    definition = {
        "apiVersion": "platform.installer/service-manifest/v1alpha1",
        "kind": "ServiceManifest",
        "metadata": {"id": "keepalived", "version": "1"},
        "endpointProvider": {},
        "modes": {"vrrp-unicast": {
            "displayName": "Unicast VRRP", "memberRoles": [],
            "placement": {"explicit": True, "hostScoped": True, "minMembers": 2, "distinctHosts": True},
        }},
        "configuration": {"additionalProperties": False, "settings": {}},
        "configurationSchema": {"$ref": "configuration.schema.json"},
        "roleEntrypoints": {},
    }
    definition["x-definitionDigest"] = VALIDATION.canonical_digest(definition)
    fixture_catalog["definitions"] = {"keepalived": definition}
    unsigned = {"apiVersion": fixture_catalog["apiVersion"], "kind": fixture_catalog["kind"], "definitions": fixture_catalog["definitions"]}
    fixture_catalog["digest"] = VALIDATION.canonical_digest(unsigned)
    return fixture_catalog


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

    def test_definition_version_is_catalog_metadata_not_topology_identity(self):
        first_topology = topology()
        second_topology = topology()
        first_topology["serviceDeployments"]["kafka-main"].pop("definitionVersion")
        second_topology["serviceDeployments"]["kafka-main"]["definitionVersion"] = "1"
        first = RESOLUTION.resolve_topology(manifest(), first_topology, ["node-a", "node-b"], catalog())
        second = RESOLUTION.resolve_topology(manifest(), second_topology, ["node-a", "node-b"], catalog())
        self.assertEqual("PASS", first["status"])
        self.assertEqual("PASS", second["status"])
        self.assertEqual(first["topologyFingerprint"], second["topologyFingerprint"])

    def test_inventory_placement_changes_topology_fingerprint(self):
        desired = topology()
        desired["serviceDeployments"]["kafka-main"].pop("members")
        first_inventory = {
            "node-a": {"kafka-main": {"members": {"member-a": {"roles": ["broker"], "configuration": {}}}}},
            "node-b": {"kafka-main": {"members": {"member-b": {"roles": ["broker", "controller"], "configuration": {}}}}},
        }
        second_inventory = copy.deepcopy(first_inventory)
        second_inventory["node-a"], second_inventory["node-b"] = (
            second_inventory["node-b"], second_inventory["node-a"],
        )
        first = RESOLUTION.resolve_topology(
            {}, {}, ["node-a", "node-b"], catalog(),
            inventory_deployments_by_host=first_inventory,
            ansible_desired_state=desired,
        )
        second = RESOLUTION.resolve_topology(
            {}, {}, ["node-a", "node-b"], catalog(),
            inventory_deployments_by_host=second_inventory,
            ansible_desired_state=desired,
        )
        self.assertEqual("PASS", first["status"])
        self.assertEqual("PASS", second["status"])
        self.assertNotEqual(first["topologyFingerprint"], second["topologyFingerprint"])

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

    def test_joins_current_desired_state_with_inventory_placement(self):
        desired = topology()
        for member in desired["serviceDeployments"]["kafka-main"]["members"].values():
            member.pop("host")
        current_manifest = manifest()
        current_manifest["desiredState"] = desired
        result = RESOLUTION.resolve_topology(
            current_manifest, {}, ["node-a", "node-b"], catalog(),
            {"node-a": {"kafka-main": ["member-a"]}, "node-b": {"kafka-main": ["member-b"]}},
        )
        self.assertEqual("PASS", result["status"])
        self.assertEqual("node-a", result["resolvedTopology"]["serviceDeployments"]["kafka-main"]["members"]["member-a"]["host"])

    def test_composes_inventory_owned_members_for_canonical_desired_state(self):
        desired = topology()
        for member in desired["serviceDeployments"]["kafka-main"]["members"].values():
            member.pop("host")
        desired["serviceDeployments"]["kafka-main"].pop("members")
        current_manifest = manifest()
        current_manifest["desiredState"] = desired
        inventory = {
            "node-a": {"kafka-main": {"members": {"member-a": {"roles": ["broker"], "configuration": {}}}}},
            "node-b": {"kafka-main": {"members": {"member-b": {"roles": ["broker", "controller"], "configuration": {}}}}},
        }
        result = RESOLUTION.resolve_topology(
            current_manifest, {}, ["node-a", "node-b"], catalog(),
            inventory_deployments_by_host=inventory,
        )
        self.assertEqual("PASS", result["status"])
        self.assertEqual("node-b", result["resolvedTopology"]["serviceDeployments"]["kafka-main"]["members"]["member-b"]["host"])

    def test_resolves_ansible_native_state_without_project_desired_state(self):
        desired = topology()
        desired["serviceDeployments"]["kafka-main"].pop("members")
        inventory = {
            "node-a": {"kafka-main": {"members": {"member-a": {"roles": ["broker"], "configuration": {}}}}},
            "node-b": {"kafka-main": {"members": {"member-b": {"roles": ["broker", "controller"], "configuration": {}}}}},
        }
        result = RESOLUTION.resolve_topology(
            {}, {}, ["node-a", "node-b"], catalog(),
            inventory_deployments_by_host=inventory,
            ansible_desired_state=desired,
        )
        self.assertEqual("PASS", result["status"])
        self.assertEqual("node-a", result["resolvedTopology"]["serviceDeployments"]["kafka-main"]["members"]["member-a"]["host"])

    def test_ansible_native_state_cannot_duplicate_inventory_members(self):
        result = RESOLUTION.resolve_topology(
            {}, {}, ["node-a", "node-b"], catalog(),
            inventory_deployments_by_host={},
            ansible_desired_state=topology(),
        )
        self.assertEqual("BLOCKED", result["status"])
        self.assertIn("PERSISTED_MEMBERS_NOT_ALLOWED", [item["code"] for item in result["findings"]])

    def test_host_scoped_placement_has_no_logical_members_and_affects_fingerprint(self):
        fixture_catalog = keepalived_catalog()
        fixture_manifest = manifest()
        fixture_manifest["catalogLock"]["digest"] = fixture_catalog["digest"]
        fixture_manifest["catalogLock"]["services"] = {"keepalived": {"definitionVersion": "1", "digest": fixture_catalog["definitions"]["keepalived"]["x-definitionDigest"]}}
        desired = {"endpointGroups": {"asutp": {"address": {"domain": "asutp.scada.local", "wildcard": True}}}, "serviceDeployments": {"keepalived-asutp": {
            "serviceType": "keepalived", "definitionVersion": "1", "mode": "vrrp-unicast",
            "endpointGroupRef": "asutp", "virtualRouterId": 51,
            "virtualAddresses": [{"address": "192.168.56.111", "interface": "enp0s8"}],
        }}}
        first_inventory = {"node-a": {"keepalived-asutp": {"priority": 150}}, "node-b": {"keepalived-asutp": {"priority": 100}}}
        second_inventory = copy.deepcopy(first_inventory)
        second_inventory["node-a"]["keepalived-asutp"]["priority"] = 100
        first = RESOLUTION.resolve_topology(fixture_manifest, {}, ["node-a", "node-b"], fixture_catalog, inventory_deployments_by_host=first_inventory, ansible_desired_state=desired)
        second = RESOLUTION.resolve_topology(fixture_manifest, {}, ["node-a", "node-b"], fixture_catalog, inventory_deployments_by_host=second_inventory, ansible_desired_state=desired)
        self.assertEqual("PASS", first["status"], first["findings"])
        self.assertNotIn("members", first["resolvedTopology"]["serviceDeployments"]["keepalived-asutp"])
        self.assertNotEqual(first["topologyFingerprint"], second["topologyFingerprint"])

if __name__ == "__main__":
    unittest.main()

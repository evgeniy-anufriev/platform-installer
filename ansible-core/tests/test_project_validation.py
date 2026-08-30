import importlib.util
import json
import os
import tempfile
import unittest


MODULE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "collections", "ansible_collections", "platform",
    "core", "plugins", "module_utils", "project_validation.py",
)
SPEC = importlib.util.spec_from_file_location("project_validation", MODULE_PATH)
VALIDATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATION)


def catalog():
    definition = {
        "metadata": {"id": "kafka", "version": "1"},
        "modes": {
            "kraft-standalone": {
                "memberRoles": ["broker", "controller"],
                "placement": {
                    "minMembers": 1,
                    "maxMembers": 1,
                    "distinctHosts": False,
                    "roleCardinality": {
                        "broker": {"minimum": 1, "maximum": 1},
                        "controller": {"minimum": 1, "maximum": 1},
                    },
                },
            },
            "kraft-distributed": {
                "memberRoles": ["broker", "controller"],
                "placement": {
                    "minMembers": 2,
                    "distinctHosts": True,
                    "roleCardinality": {"controller": {"minimum": 1}},
                },
            },
        },
    }
    definition["x-definitionDigest"] = VALIDATION.canonical_digest(definition)
    definition["x-sourceManifest"] = "services/kafka/service.yml"
    unsigned = {
        "apiVersion": "platform.installer/catalog/v1alpha1",
        "kind": "ServiceCatalog",
        "definitions": {"kafka": definition},
    }
    return dict(unsigned, digest=VALIDATION.canonical_digest(unsigned))


def manifest(project_id="valid-project"):
    fixture_catalog = catalog()
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
            "digest": "sha256:" + "2" * 64,
        },
    }


class ProjectValidationTests(unittest.TestCase):
    def test_valid_explicit_placement_passes(self):
        topology = {"serviceDeployments": {"kafka-main": {
            "serviceType": "kafka", "definitionVersion": "1", "mode": "kraft-standalone",
            "members": {"broker-1": {"host": "node-1", "roles": ["broker", "controller"]}},
        }}}
        result = VALIDATION.validate_project(manifest(), topology, {}, catalog(), ["node-1"])
        self.assertEqual("PASS", result["status"])
        self.assertEqual([], result["findings"])

    def test_unknown_mode_and_host_are_structured_findings(self):
        topology = {"serviceDeployments": {"kafka-main": {
            "serviceType": "kafka", "definitionVersion": "1", "mode": "legacy",
            "members": {"broker-1": {"host": "missing-node", "roles": ["broker"]}},
        }}}
        result = VALIDATION.validate_project(manifest("invalid"), topology, {}, catalog(), ["node-1"])
        self.assertEqual("BLOCKED", result["status"])
        self.assertEqual(
            {"SERVICE_MODE_UNSUPPORTED", "MEMBER_HOST_NOT_FOUND"},
            {finding["code"] for finding in result["findings"]},
        )
        self.assertTrue(all("safeMessage" in finding for finding in result["findings"]))

    def test_unknown_service_is_not_hard_coded(self):
        topology = {"serviceDeployments": {"database": {
            "serviceType": "postgresql", "definitionVersion": "1", "mode": "standalone",
            "members": {"database-1": {"host": "node-1", "roles": ["database"]}},
        }}}
        result = VALIDATION.validate_project(manifest("unknown"), topology, {}, catalog(), ["node-1"])
        self.assertIn("SERVICE_DEFINITION_NOT_FOUND", [item["code"] for item in result["findings"]])

    def test_result_is_deterministic_and_does_not_copy_inventory_secrets(self):
        invalid_manifest = manifest("invalid")
        invalid_manifest["apiVersion"] = "wrong/version"
        topology = {"serviceDeployments": {}}
        first = VALIDATION.validate_project(invalid_manifest, topology, {}, catalog(), ["node-1"])
        second = VALIDATION.validate_project(invalid_manifest, topology, {}, catalog(), ["node-1"])
        self.assertEqual(first, second)
        serialized = json.dumps(first)
        self.assertNotIn("ansible_password", serialized)
        self.assertNotIn("admin", serialized)

    def test_artifact_write_replaces_complete_json(self):
        result = VALIDATION.validate_project(
            manifest("empty"), {"serviceDeployments": {}}, {}, catalog(), []
        )
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "validation.json")
            VALIDATION.write_validation_artifact(path, result)
            with open(path, "r", encoding="utf-8") as artifact:
                loaded = json.load(artifact)
        self.assertEqual(result, loaded)

    def test_unsupported_member_role_is_rejected_from_catalog_metadata(self):
        topology = {"serviceDeployments": {"kafka-main": {
            "serviceType": "kafka", "definitionVersion": "1", "mode": "kraft-standalone",
            "members": {"broker-1": {"host": "node-1", "roles": ["database"]}},
        }}}
        result = VALIDATION.validate_project(manifest(), topology, {}, catalog(), ["node-1"])
        self.assertIn("MEMBER_ROLE_UNSUPPORTED", [item["code"] for item in result["findings"]])

    def test_distinct_host_constraint_is_rejected_from_catalog_metadata(self):
        topology = {"serviceDeployments": {"kafka-main": {
            "serviceType": "kafka", "definitionVersion": "1", "mode": "kraft-distributed",
            "members": {
                "broker-1": {"host": "node-1", "roles": ["broker"]},
                "broker-2": {"host": "node-1", "roles": ["controller"]},
            },
        }}}
        result = VALIDATION.validate_project(manifest(), topology, {}, catalog(), ["node-1"])
        self.assertIn(
            "PLACEMENT_DISTINCT_HOSTS_REQUIRED", [item["code"] for item in result["findings"]]
        )

    def test_fingerprint_covers_manifest_and_topology(self):
        topology = {"serviceDeployments": {}}
        first = VALIDATION.validate_project(manifest("one"), topology, {}, catalog(), [])
        second = VALIDATION.validate_project(manifest("two"), topology, {}, catalog(), [])
        self.assertNotEqual(first["projectFingerprint"], second["projectFingerprint"])

        changed_topology = {"serviceDeployments": {}, "x-test": {"enabled": True}}
        third = VALIDATION.validate_project(manifest("one"), changed_topology, {}, catalog(), [])
        self.assertNotEqual(first["projectFingerprint"], third["projectFingerprint"])

        fourth = VALIDATION.validate_project(
            manifest("one"), topology, {"node-1": {"desiredHostname": "node-1"}}, catalog(), ["node-1"]
        )
        self.assertNotEqual(first["projectFingerprint"], fourth["projectFingerprint"])

    def test_manifest_identity_and_catalog_are_required(self):
        result = VALIDATION.validate_project({}, {"serviceDeployments": {}}, {}, catalog(), [])
        codes = {item["code"] for item in result["findings"]}
        self.assertTrue(
            {
                "PROJECT_API_VERSION_UNSUPPORTED",
                "PROJECT_KIND_INVALID",
                "PROJECT_ID_REQUIRED",
                "PROJECT_CATALOG_API_VERSION_UNSUPPORTED",
            }.issubset(codes)
        )

    def test_plaintext_secret_like_fields_are_blocked_without_value_leakage(self):
        secret_value = "must-not-appear-in-findings"
        topology = {
            "serviceDeployments": {},
            "x-runtime": {
                "adminPassword": secret_value,
                "nested": [
                    {"private_key": secret_value},
                    {"tokenValue": secret_value},
                    {"db_password_hash": secret_value},
                ],
            },
        }

        result = VALIDATION.validate_project(manifest(), topology, {}, catalog(), [])

        secret_findings = [
            item for item in result["findings"]
            if item["code"] == "PLAINTEXT_SECRET_FIELD_FORBIDDEN"
        ]
        self.assertEqual(4, len(secret_findings))
        self.assertNotIn(secret_value, json.dumps(secret_findings))

    def test_secret_reference_keys_and_requirement_ids_are_allowed(self):
        topology = {
            "serviceDeployments": {},
            "secretRequirements": {
                "database-password": {
                    "purpose": "database-password",
                    "providerRef": "runtime:database-password",
                    "credentialRef": "credential:database",
                    "secretRef": "secret:database",
                }
            },
        }

        result = VALIDATION.validate_project(manifest(), topology, {}, catalog(), [])

        self.assertNotIn(
            "PLAINTEXT_SECRET_FIELD_FORBIDDEN",
            [item["code"] for item in result["findings"]],
        )

    def test_platform_host_omission_is_safe_but_private_key_is_blocked(self):
        topology = {"serviceDeployments": {}}
        omitted = VALIDATION.validate_project(
            manifest(), topology, {"node-1": {}}, catalog(), ["node-1"]
        )
        self.assertEqual("PASS", omitted["status"])

        secret_value = "private-material-must-not-leak"
        unsafe = VALIDATION.validate_project(
            manifest(), topology, {"node-1": {"privateKey": secret_value}}, catalog(), ["node-1"]
        )
        self.assertIn(
            "PLAINTEXT_SECRET_FIELD_FORBIDDEN",
            [item["code"] for item in unsafe["findings"]],
        )
        self.assertNotIn(secret_value, json.dumps(unsafe["findings"]))

    def test_member_count_constraints_come_from_mode_manifest(self):
        below = {"serviceDeployments": {"kafka-main": {
            "serviceType": "kafka", "definitionVersion": "1", "mode": "kraft-distributed",
            "members": {"broker-1": {"host": "node-1", "roles": ["broker", "controller"]}},
        }}}
        above = {"serviceDeployments": {"kafka-main": {
            "serviceType": "kafka", "definitionVersion": "1", "mode": "kraft-standalone",
            "members": {
                "broker-1": {"host": "node-1", "roles": ["broker", "controller"]},
                "broker-2": {"host": "node-2", "roles": ["broker", "controller"]},
            },
        }}}

        below_result = VALIDATION.validate_project(
            manifest(), below, {}, catalog(), ["node-1"]
        )
        above_result = VALIDATION.validate_project(
            manifest(), above, {}, catalog(), ["node-1", "node-2"]
        )

        self.assertIn("SERVICE_MEMBER_COUNT_BELOW_MINIMUM", [item["code"] for item in below_result["findings"]])
        self.assertIn("SERVICE_MEMBER_COUNT_ABOVE_MAXIMUM", [item["code"] for item in above_result["findings"]])

    def test_role_cardinality_constraints_come_from_mode_manifest(self):
        missing_controller = {"serviceDeployments": {"kafka-main": {
            "serviceType": "kafka", "definitionVersion": "1", "mode": "kraft-distributed",
            "members": {
                "broker-1": {"host": "node-1", "roles": ["broker"]},
                "broker-2": {"host": "node-2", "roles": ["broker"]},
            },
        }}}
        too_many_controllers = {"serviceDeployments": {"kafka-main": {
            "serviceType": "kafka", "definitionVersion": "1", "mode": "kraft-standalone",
            "members": {
                "broker-1": {"host": "node-1", "roles": ["broker", "controller"]},
                "broker-2": {"host": "node-2", "roles": ["broker", "controller"]},
            },
        }}}

        missing_result = VALIDATION.validate_project(
            manifest(), missing_controller, {}, catalog(), ["node-1", "node-2"]
        )
        excessive_result = VALIDATION.validate_project(
            manifest(), too_many_controllers, {}, catalog(), ["node-1", "node-2"]
        )

        self.assertIn("SERVICE_ROLE_COUNT_BELOW_MINIMUM", [item["code"] for item in missing_result["findings"]])
        self.assertIn("SERVICE_ROLE_COUNT_ABOVE_MAXIMUM", [item["code"] for item in excessive_result["findings"]])

    def test_catalog_digest_is_recomputed_from_canonical_content(self):
        stale_catalog = catalog()
        stale_catalog["digest"] = "sha256:" + "f" * 64

        result = VALIDATION.validate_project(
            manifest(), {"serviceDeployments": {}}, {}, stale_catalog, []
        )

        self.assertIn("SERVICE_CATALOG_DIGEST_MISMATCH", [item["code"] for item in result["findings"]])
        self.assertNotIn("PROJECT_CATALOG_DIGEST_MISMATCH", [item["code"] for item in result["findings"]])

    def test_definition_digest_is_recomputed_without_generated_metadata(self):
        stale_catalog = catalog()
        stale_catalog["definitions"]["kafka"]["modes"]["kraft-standalone"]["displayName"] = "Changed"
        unsigned_catalog = {
            key: value for key, value in stale_catalog.items() if key != "digest"
        }
        stale_catalog["digest"] = VALIDATION.canonical_digest(unsigned_catalog)

        topology = {"serviceDeployments": {"kafka-main": {
            "serviceType": "kafka", "definitionVersion": "1", "mode": "kraft-standalone",
            "members": {"broker-1": {"host": "node-1", "roles": ["broker", "controller"]}},
        }}}
        project_manifest = manifest()
        project_manifest["catalogLock"]["digest"] = stale_catalog["digest"]
        result = VALIDATION.validate_project(
            project_manifest, topology, {}, stale_catalog, ["node-1"]
        )

        self.assertIn("SERVICE_DEFINITION_DIGEST_MISMATCH", [item["code"] for item in result["findings"]])
        self.assertIn(
            "PROJECT_SERVICE_DEFINITION_DIGEST_MISMATCH",
            [item["code"] for item in result["findings"]],
        )


if __name__ == "__main__":
    unittest.main()

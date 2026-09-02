import importlib.util
import os
import unittest
from copy import deepcopy
from pathlib import Path


MODULE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "tools", "build_fixture_catalog.py"
)
SPEC = importlib.util.spec_from_file_location("build_fixture_catalog", MODULE_PATH)
CATALOG = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CATALOG)

SCHEMA_MODULE_PATH = Path(__file__).resolve().parents[1] / "collections" / "ansible_collections" / "platform" / "core" / "plugins" / "module_utils" / "schema_validation.py"
SCHEMA_SPEC = importlib.util.spec_from_file_location("schema_validation", SCHEMA_MODULE_PATH)
SCHEMA = importlib.util.module_from_spec(SCHEMA_SPEC)
SCHEMA_SPEC.loader.exec_module(SCHEMA)
CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
CATALOG_SCHEMA = CONTRACTS / "service-catalog" / "v1alpha1" / "schema.json"


class FixtureCatalogTests(unittest.TestCase):
    def test_committed_catalog_is_reproducible(self):
        self.assertEqual(CATALOG.build_catalog(), CATALOG.load_yaml(CATALOG.OUTPUT))

    def test_digest_rule_is_order_independent(self):
        self.assertEqual(
            CATALOG.digest({"a": 1, "b": 2}),
            CATALOG.digest({"b": 2, "a": 1}),
        )

    def test_definition_digests_are_recomputable_from_catalog(self):
        catalog = CATALOG.build_catalog()
        for definition in catalog["definitions"].values():
            expected = definition["x-definitionDigest"]
            digest_input = dict(definition)
            digest_input.pop("x-definitionDigest")
            digest_input.pop("x-sourceManifest")
            self.assertEqual(expected, CATALOG.digest(digest_input))

    def test_project_catalog_locks_match_generated_catalog(self):
        self.assertEqual([], CATALOG.verify_project_locks(CATALOG.build_catalog()))

    def test_catalog_accepts_supported_configuration_ui_metadata(self):
        findings = SCHEMA.SchemaValidator(CONTRACTS).validate(
            CATALOG.build_catalog(), CATALOG_SCHEMA
        )
        self.assertEqual([], findings)

    def test_catalog_rejects_unknown_configuration_ui_metadata(self):
        catalog = deepcopy(CATALOG.build_catalog())
        catalog["definitions"]["postgresql"]["configuration"]["settings"]["port"]["ui"]["unsupported"] = True
        findings = SCHEMA.SchemaValidator(CONTRACTS).validate(catalog, CATALOG_SCHEMA)
        self.assertTrue(findings)
        self.assertTrue(all(item["code"] == "SCHEMA_VALIDATION_FAILED" for item in findings))


if __name__ == "__main__":
    unittest.main()

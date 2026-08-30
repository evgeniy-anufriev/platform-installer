import importlib.util
import os
import unittest


MODULE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "tools", "build_fixture_catalog.py"
)
SPEC = importlib.util.spec_from_file_location("build_fixture_catalog", MODULE_PATH)
CATALOG = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CATALOG)


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


if __name__ == "__main__":
    unittest.main()

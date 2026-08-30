import json
import os
import unittest
from pathlib import Path


CONTRACTS_ROOT = Path(__file__).resolve().parents[1]


def schema_paths():
    return sorted(
        path
        for path in CONTRACTS_ROOT.rglob("*.json")
        if path.name == "schema.json" or path.name.endswith(".schema.json")
    )


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


class ContractSchemaDocumentTests(unittest.TestCase):
    def test_all_schema_documents_are_valid_json(self):
        paths = schema_paths()
        self.assertGreater(len(paths), 0)
        for path in paths:
            with self.subTest(path=path.relative_to(CONTRACTS_ROOT)):
                with path.open("r", encoding="utf-8") as source:
                    json.load(source)

    def test_schema_ids_are_unique_and_use_draft_2020_12(self):
        seen = {}
        for path in schema_paths():
            with path.open("r", encoding="utf-8") as source:
                document = json.load(source)
            self.assertEqual(
                "https://json-schema.org/draft/2020-12/schema",
                document.get("$schema"),
                path,
            )
            schema_id = document.get("$id")
            self.assertIsInstance(schema_id, str, path)
            self.assertNotIn(schema_id, seen, "%s duplicates %s" % (path, seen.get(schema_id)))
            seen[schema_id] = path

    def test_relative_file_refs_resolve(self):
        for path in schema_paths():
            with path.open("r", encoding="utf-8") as source:
                document = json.load(source)
            for item in walk(document):
                reference = item.get("$ref")
                if not isinstance(reference, str) or reference.startswith(("#", "http://", "https://")):
                    continue
                file_part = reference.split("#", 1)[0]
                target = (path.parent / file_part).resolve()
                with self.subTest(schema=path.relative_to(CONTRACTS_ROOT), ref=reference):
                    self.assertTrue(target.is_file(), "missing schema reference %s" % target)

    def test_no_schema_contains_plaintext_secret_examples(self):
        forbidden = ("admin:admin", '"password": "', '"privateKey": "-----BEGIN')
        for path in schema_paths():
            content = path.read_text(encoding="utf-8")
            for marker in forbidden:
                with self.subTest(path=path.relative_to(CONTRACTS_ROOT), marker=marker):
                    self.assertNotIn(marker, content)


if __name__ == "__main__":
    unittest.main()

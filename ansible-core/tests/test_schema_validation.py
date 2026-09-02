import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "collections" / "ansible_collections" / "platform" / "core" / "plugins" / "module_utils" / "schema_validation.py"
SPEC = importlib.util.spec_from_file_location("schema_validation", MODULE_PATH)
ENGINE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENGINE)


FEATURE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://platform-installer.local/tests/feature.schema.json",
    "type": "object",
    "required": ["kind", "name"],
    "properties": {
        "kind": {"const": "Example"},
        "name": {"type": "string", "minLength": 1},
        "id": {"$ref": "#/$defs/identifier"},
        "mode": {"enum": ["standalone", "cluster"]},
        "member": {"type": "string"},
    },
    "allOf": [
        {
            "if": {"properties": {"mode": {"const": "cluster"}}},
            "then": {"required": ["member"]},
        }
    ],
    "unevaluatedProperties": False,
    "$defs": {
        "identifier": {
            "type": "string",
            "pattern": "^[a-z][a-z0-9-]*$",
        }
    },
}


class Draft202012EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.schema_path = self.root / "feature.schema.json"
        self.schema_path.write_text(json.dumps(FEATURE_SCHEMA), encoding="utf-8")
        self.engine = ENGINE.SchemaValidator(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_positive_2020_12_features_pass(self):
        findings = self.engine.validate(
            {
                "kind": "Example",
                "name": "kafka",
                "id": "service-1",
                "mode": "cluster",
                "member": "broker-1",
            },
            self.schema_path,
        )
        self.assertEqual([], findings)

    def test_negative_2020_12_features_are_findings(self):
        findings = self.engine.validate(
            {"kind": "Example", "name": "kafka", "mode": "cluster", "extra": "bad"},
            self.schema_path,
        )
        self.assertGreaterEqual(len(findings), 2)
        self.assertTrue(all(item["code"] == "SCHEMA_VALIDATION_FAILED" for item in findings))
        self.assertTrue(all("bad" not in json.dumps(item) for item in findings))

    def test_unknown_external_reference_is_rejected_without_network(self):
        external = dict(FEATURE_SCHEMA)
        external["$id"] = "https://platform-installer.local/tests/external.schema.json"
        external["properties"] = {"value": {"$ref": "https://example.invalid/schema.json"}}
        external_path = self.root / "external.schema.json"
        external_path.write_text(json.dumps(external), encoding="utf-8")
        # Rebuild the local registry after adding the schema so the test
        # reaches the network-denying handler rather than a missing-file path.
        engine = ENGINE.SchemaValidator(self.root)
        with self.assertRaises(ENGINE.SchemaValidationError) as context:
            engine.validate({"value": "x"}, external_path)
        self.assertIn("SCHEMA_EXTERNAL_REF_FORBIDDEN", str(context.exception))

    def test_generated_state_rejects_user_configuration(self):
        contracts = Path(__file__).resolve().parents[2] / "contracts"
        schema = contracts / "project" / "v2alpha1" / "generated-state.schema.json"
        document = {
            "apiVersion": "platform.installer/generated-state/v1alpha1",
            "kind": "PlatformGeneratedState",
            "metadata": {"projectId": "example"},
            "serviceDeployments": {
                "kafka-main": {"configuration": {"clientPort": 9092}},
            },
        }
        findings = ENGINE.SchemaValidator(contracts).validate(document, schema)
        self.assertTrue(findings)
        self.assertTrue(all(item["code"] == "SCHEMA_VALIDATION_FAILED" for item in findings))

    def test_desired_state_accepts_group_assignment_and_rejects_endpoint_bindings(self):
        contracts = Path(__file__).resolve().parents[2] / "contracts"
        schema = contracts / "project" / "v2alpha1" / "desired-state.schema.json"
        document = {
            "serviceDeployments": {
                "postgres-main": {
                    "serviceType": "postgresql", "definitionVersion": "1", "mode": "standalone", "endpointGroup": "asutp",
                },
            },
            "endpointGroups": {
                "asutp": {"address": {"domain": "asutp.scada.local", "wildcard": True}},
            },
        }
        validator = ENGINE.SchemaValidator(contracts)
        self.assertEqual([], validator.validate(document, schema))
        document["endpointBindings"] = {}
        self.assertTrue(validator.validate(document, schema))


if __name__ == "__main__":
    unittest.main()

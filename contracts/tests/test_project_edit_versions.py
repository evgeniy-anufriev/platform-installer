import sys
import unittest
from pathlib import Path

CONTRACTS = Path(__file__).resolve().parents[1]
MODULE_UTILS = CONTRACTS.parent / "ansible-core" / "collections" / "ansible_collections" / "platform" / "core" / "plugins" / "module_utils"
sys.path.insert(0, str(MODULE_UTILS))

from schema_validation import SchemaValidator


REVISION = "sha256:" + "a" * 64


class ProjectEditVersionTests(unittest.TestCase):
    def validate(self, payload, version):
        path = CONTRACTS / "project-edit" / version / "schema.json"
        return SchemaValidator(str(CONTRACTS)).validate(payload, str(path))

    def test_v1alpha2_historical_create_server_remains_valid(self):
        payload = {
            "apiVersion": "platform.installer/edit-command/v1alpha2",
            "kind": "EditCommand",
            "baseProjectRevision": REVISION,
            "operation": "CreateServer",
            "hostId": "node1",
            "address": "192.0.2.10",
        }
        self.assertEqual([], self.validate(payload, "v1alpha2"))

    def test_v1alpha3_requires_grammar_valid_type(self):
        payload = {
            "apiVersion": "platform.installer/edit-command/v1alpha3",
            "kind": "EditCommand",
            "baseProjectRevision": REVISION,
            "operation": "CreateServer",
            "hostId": "node1",
            "address": "192.0.2.10",
        }
        self.assertTrue(self.validate(payload, "v1alpha3"))
        payload["type"] = "infra"
        self.assertEqual([], self.validate(payload, "v1alpha3"))
        payload["type"] = "Инфраструктура"
        self.assertTrue(self.validate(payload, "v1alpha3"))

    def test_v1alpha3_preserves_unchanged_v1alpha2_operations(self):
        payload = {
            "apiVersion": "platform.installer/edit-command/v1alpha3",
            "kind": "EditCommand",
            "baseProjectRevision": REVISION,
            "operation": "DeleteServiceDeployment",
            "deploymentId": "kafka-main",
        }
        self.assertEqual([], self.validate(payload, "v1alpha3"))


if __name__ == "__main__":
    unittest.main()

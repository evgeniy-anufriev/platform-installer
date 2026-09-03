import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_ROOT = Path(__file__).resolve().parents[1] / "collections" / "ansible_collections" / "platform" / "core" / "plugins" / "module_utils"
sys.path.insert(0, str(MODULE_ROOT))
SPEC = importlib.util.spec_from_file_location("schema_validation", MODULE_ROOT / "schema_validation.py")
SCHEMA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCHEMA)

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
EDIT_SCHEMA = CONTRACTS / "project-edit" / "v1alpha1" / "schema.json"
REVISION = "sha256:" + "a" * 64
DIGEST = "sha256:" + "b" * 64


class ProjectEditContractTests(unittest.TestCase):
    def setUp(self):
        self.validator = SCHEMA.SchemaValidator(CONTRACTS)

    def test_command_plan_and_result_contracts_pass(self):
        command = {
            "apiVersion": "platform.installer/edit-command/v1alpha1",
            "kind": "EditCommand", "baseProjectRevision": REVISION,
            "operation": "SetServiceConfigurationValue", "deploymentId": "postgres-ha",
            "setting": "port", "value": 55432,
        }
        plan = {
            "apiVersion": "platform.installer/edit-plan/v1alpha1", "kind": "EditPlan",
            "status": "READY", "planId": "1" * 32, "baseProjectRevision": REVISION,
            "commandSummary": {"operation": "SetServiceConfigurationValue"},
            "semanticChanges": [], "affectedEntities": ["postgres-ha"],
            "affectedDocuments": [{"logicalPath": "inventory/group_vars/all/platform-installer.yml",
                                     "beforeDigest": DIGEST, "afterDigest": DIGEST}],
            "impacts": ["CONFIGURATION_CHANGED"],
            "validation": {"status": "PASS", "findings": []},
            "reviewDiff": "", "commitAllowed": True, "applyRequired": True,
            "timing": {},
        }
        result = {
            "apiVersion": "platform.installer/edit-commit-result/v1alpha1",
            "kind": "EditCommitResult", "status": "COMMITTED", "changed": True,
            "oldProjectRevision": REVISION, "newProjectRevision": REVISION,
            "affectedDocuments": plan["affectedDocuments"], "snapshot": {},
            "applyRequired": True, "timing": {},
        }
        for document in (command, plan, result):
            self.assertEqual([], self.validator.validate(document, EDIT_SCHEMA))

    def test_arbitrary_path_and_raw_yaml_are_not_contract_fields(self):
        command = {
            "apiVersion": "platform.installer/edit-command/v1alpha1",
            "kind": "EditCommand", "baseProjectRevision": REVISION,
            "operation": "SetServiceConfigurationValue", "deploymentId": "postgres-ha",
            "setting": "port", "value": 55432, "destinationPath": "../outside.yml",
            "rawYaml": "password: plain",
        }
        findings = self.validator.validate(command, EDIT_SCHEMA)
        self.assertTrue(findings)
        self.assertTrue(all(item["code"] == "SCHEMA_VALIDATION_FAILED" for item in findings))


if __name__ == "__main__":
    unittest.main()

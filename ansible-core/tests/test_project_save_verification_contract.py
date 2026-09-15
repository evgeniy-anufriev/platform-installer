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
SAVE_SCHEMA = CONTRACTS / "project-save" / "v1alpha1" / "schema.json"
VERIFY_SCHEMA = CONTRACTS / "project-verification" / "v1alpha1" / "schema.json"
REVISION = "sha256:" + "a" * 64


class ProjectSaveVerificationContractTests(unittest.TestCase):
    def setUp(self):
        self.validator = SCHEMA.SchemaValidator(CONTRACTS)

    def test_structural_plan_and_save_result_are_closed(self):
        change = {
            "logicalPath": "inventory/hosts.yml",
            "before": {"state": "PRESENT", "digest": REVISION},
            "after": {"state": "PRESENT", "digest": "sha256:" + "b" * 64},
        }
        plan = {
            "apiVersion": "platform.installer/structural-edit-plan/v1alpha1",
            "kind": "StructuralEditPlan", "status": "READY", "planId": "1" * 32,
            "baseProjectRevision": REVISION,
            "semanticChanges": [{"operation": "UpdateServer", "entityId": "node1", "safeSummary": "UpdateServer node1"}],
            "affectedEntities": ["node1"], "affectedDocuments": [change], "reviewDiff": "", "saveAllowed": True,
        }
        result = {
            "apiVersion": "platform.installer/structural-save-result/v1alpha1",
            "kind": "StructuralSaveResult", "status": "COMMITTED", "changed": True,
            "oldProjectRevision": REVISION, "newProjectRevision": "sha256:" + "c" * 64,
            "affectedDocuments": [change], "managed": {"projectRevision": "sha256:" + "c" * 64, "servers": {}}, "timing": {"transaction": 1, "snapshot": 0},
        }
        self.assertEqual([], self.validator.validate(plan, SAVE_SCHEMA))
        self.assertEqual([], self.validator.validate(result, SAVE_SCHEMA))
        plan["coreStatus"] = "PASS"
        self.assertTrue(self.validator.validate(plan, SAVE_SCHEMA))

    def test_verification_is_revision_bound_and_closed(self):
        evidence = {
            "apiVersion": "platform.installer/project-verification/v1alpha1",
            "kind": "ProjectVerification", "status": "VERIFIED", "projectIdentity": "project-1",
            "projectRevision": REVISION, "executionNodeId": "node-1",
            "runtime": {"bundleDigest": "sha256:" + "d" * 64, "coreVersion": "1.0.0", "catalogDigest": "sha256:" + "e" * 64, "protocol": "platform.installer/execution-runtime/v1alpha1"},
            "checkedAt": "2026-09-15T00:00:00Z", "findings": [],
        }
        self.assertEqual([], self.validator.validate(evidence, VERIFY_SCHEMA))
        evidence["preparesExecutionNode"] = True
        self.assertTrue(self.validator.validate(evidence, VERIFY_SCHEMA))
        evidence.pop("preparesExecutionNode")
        evidence["status"] = "UNVERIFIED"
        self.assertTrue(self.validator.validate(evidence, VERIFY_SCHEMA))


if __name__ == "__main__":
    unittest.main()

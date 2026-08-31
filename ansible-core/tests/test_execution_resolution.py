import unittest

from pathlib import Path
import sys


MODULES = Path(__file__).resolve().parents[1] / "collections" / "ansible_collections" / "platform" / "core" / "plugins" / "module_utils"
sys.path.insert(0, str(MODULES))

from execution_resolution import evaluate_candidate, resolve_execution_selection


class ExecutionResolutionTests(unittest.TestCase):
    def test_eligibility_does_not_require_post_preparation_readiness(self):
        result = evaluate_candidate(
            {"id": "node1", "kind": "EXPLICIT_TARGET"},
            {"linux": True, "bootstrapReachable": True, "resourcesAvailable": True},
        )
        self.assertEqual("CANDIDATE_ELIGIBLE", result["eligibility"])
        self.assertEqual("NOT_READY", result["readiness"])
        self.assertIn("python", result["missingReadiness"])

    def test_auto_prefers_eligible_local_candidate(self):
        result = resolve_execution_selection(
            {"mode": "AUTO"},
            {"id": "local", "kind": "LOCAL_INSTALLER", "capabilities": {"linux": True, "bootstrapReachable": True, "resourcesAvailable": True}},
            [{"id": "node1", "capabilities": {"linux": True, "bootstrapReachable": True, "resourcesAvailable": True}}],
        )
        self.assertEqual("local", result["selected"]["candidateId"])

    def test_explicit_target_does_not_fallback(self):
        result = resolve_execution_selection(
            {"mode": "EXPLICIT_TARGET", "targetHostId": "node2"},
            {"id": "local", "capabilities": {"linux": True, "bootstrapReachable": True, "resourcesAvailable": True}},
            [{"id": "node1", "capabilities": {"linux": True, "bootstrapReachable": True, "resourcesAvailable": True}}],
        )
        self.assertEqual("BLOCKED", result["status"])

    def test_ready_requires_all_preparation_outputs(self):
        result = evaluate_candidate({}, {"linux": True, "bootstrapReachable": True, "resourcesAvailable": True, "python": True, "ansible": True, "workspace": True, "offlinePayload": True, "executionIdentity": True})
        self.assertEqual("EXECUTION_READY", result["readiness"])


if __name__ == "__main__":
    unittest.main()

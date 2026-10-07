"""The plan action reads PKI marker state only for a valid managed snapshot."""

import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock


CORE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE / "collections"))
from ansible_collections.platform.core.plugins.action import build_deployment_plan as action_module


class BuildDeploymentPlanActionTests(unittest.TestCase):
    def test_managed_valid_snapshot_supplies_exact_reissue_observation(self):
        snapshot = {"project": {"id": "project-a", "identitySource": "PROJECT_MANIFEST"},
                    "validation": {"status": "PASS"}}
        pki = {"status": "PASS", "requests": [{"id": "tls--node1"}]}
        selected = [{"requestId": "tls--node1"}]
        action = object.__new__(action_module.ActionModule)
        action._task = SimpleNamespace(args={"snapshot": snapshot, "pki_materialization": pki,
                                             "pki_state_root": "/state", "deployment_order": []})
        result = {"executionManifest": None, "deploymentPlan": {"status": "PLAN_REVIEW"},
                  "executionManifestDigest": None}
        with mock.patch.dict(os.environ, {}, clear=False), \
             mock.patch.object(action_module, "inspect_reissue", return_value=selected) as inspect, \
             mock.patch.object(action_module, "build_deployment_plan", return_value=result) as build:
            self.assertEqual("PLAN_REVIEW", action.run()["deployment_plan"]["status"])
        inspect.assert_called_once_with("/state", "project-a", pki["requests"])
        self.assertEqual(selected, build.call_args.args[-2])
        self.assertEqual([], build.call_args.args[-1])

    def test_invalid_snapshot_remains_a_blocked_plan_without_pki_state_read(self):
        snapshot = {"project": {"id": "project-a", "identitySource": "PATH_FALLBACK"},
                    "validation": {"status": "BLOCKED"}}
        action = object.__new__(action_module.ActionModule)
        action._task = SimpleNamespace(args={"snapshot": snapshot,
                                             "pki_materialization": {"status": "PASS", "requests": []},
                                             "pki_state_root": "/state", "deployment_order": []})
        result = {"executionManifest": None, "deploymentPlan": {"status": "PLAN_BLOCKED"},
                  "executionManifestDigest": None}
        with mock.patch.object(action_module, "inspect_reissue") as inspect, \
             mock.patch.object(action_module, "build_deployment_plan", return_value=result) as build:
            self.assertEqual("PLAN_BLOCKED", action.run()["deployment_plan"]["status"])
        inspect.assert_not_called()
        self.assertEqual([], build.call_args.args[-2])
        self.assertEqual([], build.call_args.args[-1])


if __name__ == "__main__":
    unittest.main()

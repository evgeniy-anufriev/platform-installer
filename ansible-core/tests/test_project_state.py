import importlib.util
import os
import sys
import unittest


ROOT = os.path.join(os.path.dirname(__file__), "..", "collections", "ansible_collections", "platform", "core", "plugins", "module_utils")


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


VALIDATION = load("project_validation")
STATE = load("project_state")


class ProjectStateTests(unittest.TestCase):
    def test_new_desired_state_is_selected(self):
        state, findings = STATE.select_desired_state({"desiredState": {"serviceDeployments": {}}}, {})
        self.assertEqual({"serviceDeployments": {}}, state)
        self.assertEqual([], findings)

    def test_legacy_state_is_deprecated_but_selected(self):
        state, findings = STATE.select_desired_state({}, {"serviceDeployments": {}})
        self.assertEqual({"serviceDeployments": {}}, state)
        self.assertEqual("LEGACY_PLATFORM_PROJECT_DEPRECATED", findings[0]["code"])

    def test_conflicting_dual_state_is_blocked(self):
        _, findings = STATE.select_desired_state(
            {"desiredState": {"serviceDeployments": {"one": {}}}},
            {"serviceDeployments": {"two": {}}},
        )
        self.assertEqual("DESIRED_STATE_LEGACY_CONFLICT", findings[0]["code"])

    def test_ansible_native_state_is_canonical(self):
        native = {"serviceDeployments": {"native": {}}}
        state, findings = STATE.select_desired_state({}, {}, native)
        self.assertEqual(native, state)
        self.assertEqual([], findings)

    def test_ansible_native_and_project_state_conflict(self):
        _, findings = STATE.select_desired_state(
            {"desiredState": {"serviceDeployments": {}}}, {},
            {"serviceDeployments": {"native": {}}},
        )
        self.assertEqual("ANSIBLE_DESIRED_STATE_CONFLICT", findings[0]["code"])

    def test_identical_ansible_native_and_project_state_is_deprecated(self):
        native = {"serviceDeployments": {"native": {}}}
        state, findings = STATE.select_desired_state(
            {"desiredState": native}, native, native,
        )
        self.assertEqual(native, state)
        self.assertEqual("ANSIBLE_DESIRED_STATE_COMPATIBILITY_DEPRECATED", findings[0]["code"])
        self.assertEqual("DEPRECATED", findings[0]["status"])

    def test_placement_is_host_scoped_and_duplicate_is_reported(self):
        placements, findings = STATE.canonical_placements(
            {"node1": {"kafka-main": ["broker-1"]}, "node2": {"kafka-main": ["broker-1"]}},
            ["node1", "node2"],
        )
        self.assertEqual("node2", placements[("kafka-main", "broker-1")])
        self.assertEqual("PLACEMENT_ENTRY_DUPLICATE", findings[0]["code"])

    def test_inventory_members_are_owned_by_one_target_host(self):
        members, findings = STATE.canonical_inventory_members(
            {"node1": {"kafka-main": {"members": {"broker-1": {"roles": ["broker"], "configuration": {"nodeId": 1}}}}}},
            ["node1"],
        )
        self.assertEqual([], findings)
        self.assertEqual("node1", members[("kafka-main", "broker-1")]["host"])

    def test_inventory_duplicate_member_is_blocked(self):
        _, findings = STATE.canonical_inventory_members(
            {"node1": {"kafka-main": {"members": {"member-1": {}}}},
             "node2": {"kafka-main": {"members": {"member-1": {}}}}},
            ["node1", "node2"],
        )
        self.assertEqual("INVENTORY_MEMBER_DUPLICATE", findings[0]["code"])


if __name__ == "__main__":
    unittest.main()

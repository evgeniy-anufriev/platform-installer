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

    def test_v1alpha4_requires_desired_hostname_and_keeps_v2_v3_unchanged(self):
        payload = {
            "apiVersion": "platform.installer/edit-command/v1alpha4",
            "kind": "EditCommand",
            "baseProjectRevision": REVISION,
            "operation": "CreateServer",
            "hostId": "node1",
            "address": "192.0.2.10",
            "type": "infra",
        }
        self.assertTrue(self.validate(payload, "v1alpha4"))
        payload["desiredHostname"] = "node1.example.internal"
        self.assertEqual([], self.validate(payload, "v1alpha4"))
        payload["desiredHostname"] = None
        self.assertTrue(self.validate(payload, "v1alpha4"))

    def test_v1alpha4_update_is_closed_semantic_patch(self):
        payload = {
            "apiVersion": "platform.installer/edit-command/v1alpha4",
            "kind": "EditCommand",
            "baseProjectRevision": REVISION,
            "operation": "UpdateServer",
            "hostId": "node1",
            "desiredHostname": "node1.example.internal",
        }
        self.assertEqual([], self.validate(payload, "v1alpha4"))
        payload["patch"] = {"unsafe": True}
        self.assertTrue(self.validate(payload, "v1alpha4"))

    def test_v1alpha5_supports_both_closed_placement_forms(self):
        base = {
            "apiVersion": "platform.installer/edit-command/v1alpha5",
            "kind": "EditCommand",
            "baseProjectRevision": REVISION,
            "deploymentId": "service-main",
        }
        member = dict(base, operation="ReconcileDeploymentPlacement", members=[{
            "memberId": "member-1", "hostId": "node1", "roles": ["server"],
        }])
        host = dict(base, operation="ReconcileHostScopedDeploymentPlacement", hosts=[{
            "hostId": "node1", "roles": [],
        }])
        self.assertEqual([], self.validate(member, "v1alpha5"))
        self.assertEqual([], self.validate(host, "v1alpha5"))
        member["members"][0]["configuration"] = {"unsafe": True}
        self.assertTrue(self.validate(member, "v1alpha5"))

    def test_v1alpha5_topology_commands_are_closed(self):
        commands = [
            {"operation": "CreateServiceDeployment", "deploymentId": "kafka-main", "serviceType": "kafka", "mode": "kraft-standalone"},
            {"operation": "DeleteServiceDeployment", "deploymentId": "kafka-main"},
            {"operation": "CreateEndpointGroup", "endpointGroupId": "edge", "endpointGroup": {"address": {"domain": "edge.example.test", "wildcard": False}}},
            {"operation": "UpdateEndpointGroup", "endpointGroupId": "edge", "endpointGroup": {"address": {"domain": "new.example.test", "wildcard": True}}},
            {"operation": "DeleteEndpointGroup", "endpointGroupId": "edge"},
            {"operation": "SetServiceEndpointGroup", "deploymentId": "kafka-main", "endpointGroupId": "edge"},
            {"operation": "ClearServiceEndpointGroup", "deploymentId": "kafka-main"},
        ]
        for fields in commands:
            payload = {"apiVersion": "platform.installer/edit-command/v1alpha5", "kind": "EditCommand", "baseProjectRevision": REVISION, **fields}
            self.assertEqual([], self.validate(payload, "v1alpha5"), fields["operation"])
            payload["rawYaml"] = "unsafe"
            self.assertTrue(self.validate(payload, "v1alpha5"), fields["operation"])


if __name__ == "__main__":
    unittest.main()

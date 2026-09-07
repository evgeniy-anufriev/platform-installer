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
EDIT_SCHEMA_V2 = CONTRACTS / "project-edit" / "v1alpha2" / "schema.json"
DESIRED_STATE_SCHEMA = CONTRACTS / "project" / "v2alpha1" / "desired-state.schema.json"
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

    def test_v2_first_save_session_plan_and_result_pass(self):
        command = {"apiVersion": "platform.installer/edit-command/v1alpha2", "kind": "EditCommand", "baseProjectRevision": REVISION, "operation": "CreateServer", "hostId": "node1", "address": "192.0.2.10", "sshPort": 22}
        session = {"apiVersion": "platform.installer/edit-session/v1alpha1", "kind": "EditSession", "sessionId": "1" * 32, "projectContextId": "project-1", "baseProjectRevision": REVISION, "status": "REVIEWED", "commandCount": 1, "encodedBytes": 256, "expiresAt": "2026-09-07T00:30:00Z", "reviewedPlanId": "2" * 32}
        change = {"logicalPath": "inventory/hosts.yml", "before": {"state": "ABSENT"}, "after": {"state": "PRESENT", "digest": DIGEST}}
        plan = {"apiVersion": "platform.installer/edit-plan/v1alpha2", "kind": "EditPlan", "status": "READY", "planId": "2" * 32, "baseProjectRevision": REVISION, "commandSummary": {}, "semanticChanges": [], "affectedEntities": ["node1"], "affectedDocuments": [change], "impacts": ["TOPOLOGY_CHANGED"], "validation": {"status": "PASS", "findings": []}, "reviewDiff": "", "commitAllowed": True, "applyRequired": True, "timing": {}}
        result = {"apiVersion": "platform.installer/edit-commit-result/v1alpha2", "kind": "EditCommitResult", "status": "COMMITTED", "changed": True, "oldProjectRevision": REVISION, "newProjectRevision": DIGEST, "affectedDocuments": [change], "applyRequired": True, "timing": {}}
        for document in (command, session, plan, result):
            self.assertEqual([], self.validator.validate(document, EDIT_SCHEMA_V2), document)

    def test_v2_rejects_cross_operation_and_raw_fields(self):
        command = {"apiVersion": "platform.installer/edit-command/v1alpha2", "kind": "EditCommand", "baseProjectRevision": REVISION, "operation": "CreateServer", "hostId": "node1", "address": "192.0.2.10", "deploymentId": "not-allowed", "rawYaml": "secret: value"}
        self.assertTrue(self.validator.validate(command, EDIT_SCHEMA_V2))
        absent_absent = {"apiVersion": "platform.installer/edit-plan/v1alpha2", "kind": "EditPlan", "status": "READY", "baseProjectRevision": REVISION, "semanticChanges": [], "affectedDocuments": [{"logicalPath": "ansible.cfg", "before": {"state": "ABSENT"}, "after": {"state": "ABSENT"}}], "validation": {"status": "PASS", "findings": []}, "reviewDiff": "", "commitAllowed": True, "applyRequired": True}
        self.assertTrue(self.validator.validate(absent_absent, EDIT_SCHEMA_V2))

    def test_v2_command_variants_and_value_shapes_match_closed_schema(self):
        base = {"apiVersion": "platform.installer/edit-command/v1alpha2", "kind": "EditCommand", "baseProjectRevision": REVISION}
        endpoint = {"address": {"domain": "kafka.example.test", "wildcard": False}}
        authority = {"mode": "MANAGED", "commonName": "Platform Root CA"}
        certificate_profile = {"authorityRef": "root-ca", "sanPolicy": {"includeHostDns": True}}
        tls_profile = {"certificateProfileRef": "server-cert", "scope": "DEPLOYMENT", "storePasswordSecretRef": "runtime:kafka-store-password"}
        certificate_scope = {"profile": "server-cert", "scope": "DEPLOYMENT", "sources": {"serviceDeployments": ["kafka-main"]}}
        variants = [
            {"operation": "CreateServer", "hostId": "node1", "address": "192.0.2.1", "sshPort": 22},
            {"operation": "UpdateServer", "hostId": "node1", "clearSSHPort": True},
            {"operation": "DeleteServer", "hostId": "node1"},
            {"operation": "CreateServiceDeployment", "deploymentId": "kafka-main", "serviceType": "kafka", "mode": "kraft"},
            {"operation": "DeleteServiceDeployment", "deploymentId": "kafka-main"},
            {"operation": "SetServiceConfigurationValue", "deploymentId": "kafka-main", "setting": "retention", "value": None},
            {"operation": "RemoveServiceConfigurationOverride", "deploymentId": "kafka-main", "setting": "retention"},
            {"operation": "CreateEndpointGroup", "endpointGroupId": "kafka-clients", "endpointGroup": endpoint},
            {"operation": "UpdateEndpointGroup", "endpointGroupId": "kafka-clients", "endpointGroup": endpoint},
            {"operation": "DeleteEndpointGroup", "endpointGroupId": "kafka-clients"},
            {"operation": "SetServiceEndpointGroup", "deploymentId": "kafka-main", "endpointGroupId": "kafka-clients"},
            {"operation": "ClearServiceEndpointGroup", "deploymentId": "kafka-main"},
            {"operation": "SetHAProxyIntegration", "deploymentId": "postgres-main", "haproxyDeploymentId": "haproxy-main"},
            {"operation": "ClearHAProxyIntegration", "deploymentId": "postgres-main"},
            {"operation": "ReconcileDeploymentPlacement", "deploymentId": "kafka-main", "members": [{"memberId": "kafka-1", "hostId": "node1", "roles": ["broker"]}]},
        ]
        for operation, entity in (
            ("CertificateAuthority", authority), ("CertificateProfile", certificate_profile),
            ("TLSProfile", tls_profile), ("CertificateScope", certificate_scope),
        ):
            variants.extend([
                {"operation": "Create" + operation, "entityId": "entity-one", "entity": entity},
                {"operation": "Update" + operation, "entityId": "entity-one", "entity": entity},
                {"operation": "Delete" + operation, "entityId": "entity-one"},
            ])
        for variant in variants:
            command = dict(base)
            command.update(variant)
            self.assertEqual([], self.validator.validate(command, EDIT_SCHEMA_V2), command)

        invalid = [
            {"operation": "UpdateServer", "hostId": "node1", "clearSSHPort": False},
            {"operation": "ReconcileDeploymentPlacement", "deploymentId": "kafka-main", "members": [{"memberId": "kafka-1", "hostId": "node1", "roles": []}]},
            {"operation": "SetServiceConfigurationValue", "deploymentId": "kafka-main", "setting": "missing"},
            {"operation": "SetServiceConfigurationValue", "deploymentId": "kafka-main", "setting": "x" * 129, "value": 1},
            {"operation": "CreateEndpointGroup", "endpointGroupId": "kafka-clients", "endpointGroup": {}},
            {"operation": "CreateTLSProfile", "entityId": "kafka-tls", "entity": {"certificateProfileRef": "server-cert", "storePasswordSecretRef": "file:/tmp/secret"}},
        ]
        for variant in invalid:
            command = dict(base)
            command.update(variant)
            self.assertTrue(self.validator.validate(command, EDIT_SCHEMA_V2), command)

    def test_desired_state_tls_profile_accepts_only_runtime_secret_refs(self):
        base = {"certificateAuthorities": {}, "certificateProfiles": {}, "tlsProfiles": {"tls": {"certificateProfileRef": "profile", "storePasswordSecretRef": "runtime:store-password"}}, "certificateScopes": {}, "serviceDeployments": {}, "endpointGroups": {}}
        self.assertEqual([], self.validator.validate(base, DESIRED_STATE_SCHEMA))
        for invalid in ("file:/tmp/secret", "plaintext", "runtime:", "runtime:bad/name"):
            candidate = dict(base)
            candidate["tlsProfiles"] = {"tls": {"certificateProfileRef": "profile", "storePasswordSecretRef": invalid}}
            self.assertTrue(self.validator.validate(candidate, DESIRED_STATE_SCHEMA), invalid)


if __name__ == "__main__":
    unittest.main()

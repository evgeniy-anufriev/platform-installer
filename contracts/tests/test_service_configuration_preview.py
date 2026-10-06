import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
sys.path.insert(0, str(ROOT / "ansible-core" / "collections" / "ansible_collections" / "platform" / "core" / "plugins" / "module_utils"))
from schema_validation import SchemaValidator


class ServiceConfigurationPreviewContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = SchemaValidator(CONTRACTS)
        cls.schema = CONTRACTS / "service-configuration-preview" / "v1alpha1" / "schema.json"

    def payload(self):
        return {
            "apiVersion": "platform.installer/service-configuration-preview/v1alpha1",
            "kind": "ServiceConfigurationPreview",
            "projectRevision": "sha256:" + "a" * 64,
            "services": {"vault-main": {"configuration": {
                "apiPort": {"state": "RESOLVED", "source": "ROLE_DEFAULT", "value": 8200},
            }, "members": {"vault-1": {"tlsProfile": {
                "state": "RESOLVED", "source": "MEMBER_OVERRIDE", "value": "infrastructure-tls",
            }}}}},
        }

    def test_safe_ordinary_values_are_valid(self):
        self.assertEqual([], self.validator.validate(self.payload(), self.schema))

    def test_raw_object_and_unknown_field_are_rejected(self):
        for value in ({"passwordSecretRef": "runtime:secret"}, ["secret"]):
            payload = self.payload()
            payload["services"]["vault-main"]["configuration"]["apiPort"]["value"] = value
            self.assertTrue(self.validator.validate(payload, self.schema))
        payload = self.payload()
        payload["services"]["vault-main"]["configuration"]["apiPort"]["expression"] = "{{ password }}"
        self.assertTrue(self.validator.validate(payload, self.schema))

    def test_identity_and_setting_bounds_are_closed(self):
        payload = self.payload()
        payload["services"]["vault-main"]["configuration"]["bad/id"] = {
            "state": "RESOLVED", "source": "ROLE_DEFAULT", "value": True,
        }
        self.assertTrue(self.validator.validate(payload, self.schema))
        payload = self.payload()
        payload["services"]["vault-main"]["members"]["bad/member"] = {}
        self.assertTrue(self.validator.validate(payload, self.schema))
        payload = self.payload()
        payload["services"]["vault-main"]["configuration"]["apiPort"]["state"] = "UNKNOWN"
        self.assertTrue(self.validator.validate(payload, self.schema))

    def test_new_capability_requires_exact_preview_advertisement(self):
        schema = CONTRACTS / "execution-capabilities" / "v1alpha5" / "schema.json"
        capability = {
            "apiVersion": "platform.installer/execution-capabilities/v1alpha5",
            "kind": "ExecutionCapabilities",
            "bootstrapProtocol": "v1alpha1", "coreVersion": "test",
            "catalogDigest": "sha256:" + "a" * 64,
            "schemaDigest": "sha256:" + "b" * 64,
            "runtime": {"bundleVersion": "test", "bundleDigest": "sha256:" + "c" * 64},
            "supportedOperations": ["GetCapabilities", "BuildRuntimeSecretDescriptors", "PutRuntimeSecretLease", "BuildServiceConfigurationPreview"],
            "executionStart": {"protocol": "StartExecution/v1alpha2"},
            "targetCredentialLease": {"protocol": "PutRuntimeSecretLease/v1alpha2", "payloadVersions": ["TargetCredentialLeasePayload/v1alpha4"], "maxPayloadBytes": 1114112, "requiredStartProtocol": "StartExecution/v1alpha2"},
            "runtimeSecretDescriptors": {"protocol": "BuildRuntimeSecretDescriptors/v1alpha2", "maxDescriptors": 16, "maxHostsPerDescriptor": 256, "maxResponseBytes": 65536},
            "serviceConfigurationPreview": {"protocol": "BuildServiceConfigurationPreview/v1alpha1", "maxResponseBytes": 1048576},
        }
        self.assertEqual([], self.validator.validate(capability, schema))
        for path, value in (("protocol", "unknown"), ("maxResponseBytes", 0), ("unknown", True)):
            changed = copy.deepcopy(capability)
            changed["serviceConfigurationPreview"][path] = value
            self.assertTrue(self.validator.validate(changed, schema))
        changed = copy.deepcopy(capability)
        changed["supportedOperations"].remove("BuildServiceConfigurationPreview")
        self.assertTrue(self.validator.validate(changed, schema))
        self.assertTrue(self.validator.validate(capability, CONTRACTS / "execution-capabilities" / "v1alpha4" / "schema.json"))


if __name__ == "__main__":
    unittest.main()

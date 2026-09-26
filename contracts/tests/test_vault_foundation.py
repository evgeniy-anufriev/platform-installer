import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
UTILS = ROOT / "ansible-core" / "collections" / "ansible_collections" / "platform" / "core" / "plugins" / "module_utils"
sys.path.insert(0, str(UTILS))
sys.path.insert(0, str(ROOT / "ansible-core" / "tools"))
from schema_validation import SchemaValidator
from service_configuration_contract import generated_schema
from secret_input_wire import decode_payload, InputWireError
import execution_secret_lease
import yaml


class VaultFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = SchemaValidator(CONTRACTS)
        cls.payload_schema = CONTRACTS / "target-credential-payload" / "v1alpha4" / "schema.json"

    def payload(self):
        return {"apiVersion": "TargetCredentialLeasePayload/v1alpha4", "kind": "TargetCredentialLeasePayload",
                "username": "qa", "password": "test-only", "privateKey": None, "sudoPassword": None,
                "pkiStorePassword": None, "runtimeSecretValues": {}, "runtimeSecretInputs": []}

    def item(self, purpose="SERVICE_ADMIN_TOKEN", value="test-token"):
        return {"requirementRef": "input-test", "purpose": purpose, "serviceDeployment": "vault-ha",
                "operations": ["SERVICE_APPLY", "SERVICE_VERIFY"], "value": value}

    def admit(self, payload, expected=None):
        if expected is None:
            expected = [{key: item[key] for key in ("requirementRef", "purpose", "serviceDeployment", "operations")}
                        for item in payload["runtimeSecretInputs"]]
        return decode_payload(json.dumps(payload, ensure_ascii=False).encode(), self.validator, self.payload_schema, expected)

    def test_manifest_and_exact_generated_settings(self):
        manifest = yaml.safe_load((ROOT / "services" / "vault" / "service.yml").read_text())
        self.assertEqual(self.validator.validate(manifest, CONTRACTS / "service-manifest" / "v1alpha1" / "schema.json"), [])
        schema = json.loads((ROOT / "services" / "vault" / "configuration.schema.json").read_text())
        self.assertEqual(schema, generated_schema(manifest))
        for mode, count in (("standalone", 1), ("raft-ha", 3)):
            placement = manifest["modes"][mode]["placement"]
            self.assertEqual((placement["minMembers"], placement["maxMembers"]), (count, count))
            self.assertFalse(placement["distinctHosts"])
        for name in ("unsealShares", "unsealThreshold"):
            self.assertEqual(schema["properties"][name], {"type": "integer", "minimum": 1, "maximum": 255})
        self.assertEqual(self.validator.validate(manifest["x-secretInputs"], CONTRACTS / "service-secret-inputs" / "v1alpha1" / "schema.json"), [])
        self.assertEqual(self.validator.validate(manifest["x-secretOutputs"], CONTRACTS / "secret-output-delivery" / "v1alpha1" / "declaration.schema.json"), [])

    def test_new_payload_does_not_pass_old_runtime_admission(self):
        with self.assertRaises(execution_secret_lease.LifecycleError):
            execution_secret_lease._payload(self.payload())
        self.admit(self.payload())

    def test_token_exact_utf8_byte_bounds_and_no_rewrite(self):
        for token in ("x", "x" * 4096, "é" * 2048, " token\n"):
            payload = self.payload()
            payload["runtimeSecretInputs"] = [self.item(value=token)]
            self.assertEqual(self.admit(payload)["runtimeSecretInputs"][0]["value"], token)
        for token in ("", "x" * 4097, "é" * 2049):
            payload = self.payload()
            payload["runtimeSecretInputs"] = [self.item(value=token)]
            with self.assertRaisesRegex(InputWireError, "^TARGET_CREDENTIAL_LEASE_INPUT_INVALID$"):
                self.admit(payload)

    def test_shares_collection_type_count_and_byte_bounds(self):
        for shares in (["share"], ["é" * 64], ["share-%03d" % n for n in range(255)]):
            payload = self.payload()
            payload["runtimeSecretInputs"] = [self.item("SERVICE_UNSEAL_SHARES", shares)]
            self.admit(payload)
        for shares in ([], None, "not-an-array", [""], ["x", "x"], ["é" * 65], [str(n) for n in range(256)],
                       [("x" * 124) + str(n).zfill(3) for n in range(255)]):
            payload = self.payload()
            payload["runtimeSecretInputs"] = [self.item("SERVICE_UNSEAL_SHARES", shares)]
            with self.assertRaises(InputWireError): self.admit(payload)

    def test_scope_and_duplicates_are_not_ignored(self):
        payload = self.payload()
        payload["runtimeSecretInputs"] = [self.item()]
        expected = [{k: payload["runtimeSecretInputs"][0][k] for k in ("requirementRef", "purpose", "serviceDeployment", "operations")}]
        for field, value in (("serviceDeployment", "other"), ("purpose", "SERVICE_PASSWORD"), ("operations", ["SERVICE_APPLY"])):
            changed = copy.deepcopy(payload)
            changed["runtimeSecretInputs"][0][field] = value
            with self.assertRaises(InputWireError): self.admit(changed, expected)
        payload["runtimeSecretInputs"] *= 2
        with self.assertRaises(InputWireError): self.admit(payload, expected)

    def test_wrong_type_raw_diagnostics_and_output_password_rejected(self):
        payload = self.payload()
        for field in ("outputEncryptionPassword", "path", "rootToken"):
            changed = dict(payload, **{field: "sensitive-test-canary"})
            with self.assertRaisesRegex(InputWireError, "^TARGET_CREDENTIAL_LEASE_INPUT_INVALID$"):
                self.admit(changed)
        for data in (b"\xff", b"{} {}", b'{"apiVersion":NaN}', b'{"kind":"a","kind":"b"}', b" " * 1114113):
            with self.assertRaisesRegex(InputWireError, "^TARGET_CREDENTIAL_LEASE_INPUT_INVALID$"):
                decode_payload(data, self.validator, self.payload_schema, [])

    def test_request_versions_are_separate(self):
        request = {"apiVersion": "platform.installer/runtime-secret-lease/v1alpha2", "kind": "PutRuntimeSecretLeaseRequest",
                   "requestId": "a" * 32, "startAttemptId": "b" * 32, "projectIdentity": "qa",
                   "projectRevision": "sha256:" + "c" * 64, "planFingerprint": "sha256:" + "d" * 64,
                   "executionManifestDigest": "sha256:" + "e" * 64,
                   "runtimeRelease": {"bundleDigest": "sha256:" + "f" * 64, "coreVersion": "test", "catalogDigest": "sha256:" + "c" * 64, "planningProtocol": "test"},
                   "payload": self.payload()}
        self.assertEqual(self.validator.validate(request, CONTRACTS / "runtime-secret-lease" / "v1alpha2" / "request.schema.json"), [])
        old = dict(request, apiVersion="platform.installer/runtime-secret-lease/v1alpha1")
        self.assertTrue(self.validator.validate(old, CONTRACTS / "runtime-secret-lease" / "v1alpha1" / "request.schema.json"))

    def test_capability_is_closed_and_not_a_legacy_fallback(self):
        cap = {"apiVersion": "platform.installer/execution-capabilities/v1alpha4", "kind": "ExecutionCapabilities",
               "bootstrapProtocol": "v1alpha1", "coreVersion": "test", "catalogDigest": "sha256:" + "a" * 64,
               "schemaDigest": "sha256:" + "b" * 64, "runtime": {"bundleVersion": "test", "bundleDigest": "sha256:" + "c" * 64},
               "supportedOperations": ["BuildRuntimeSecretDescriptors", "PutRuntimeSecretLease"],
               "executionStart": {"protocol": "StartExecution/v1alpha2"},
               "targetCredentialLease": {"protocol": "PutRuntimeSecretLease/v1alpha2", "payloadVersions": ["TargetCredentialLeasePayload/v1alpha4"], "maxPayloadBytes": 1114112, "requiredStartProtocol": "StartExecution/v1alpha2"},
               "runtimeSecretDescriptors": {"protocol": "BuildRuntimeSecretDescriptors/v1alpha2", "maxDescriptors": 16, "maxHostsPerDescriptor": 256, "maxResponseBytes": 65536}}
        schema = CONTRACTS / "execution-capabilities" / "v1alpha4" / "schema.json"
        self.assertEqual(self.validator.validate(cap, schema), [])
        for field, value in (("protocol", "PutRuntimeSecretLease/v1alpha1"), ("payloadVersions", ["TargetCredentialLeasePayload/v1alpha3"]), ("maxPayloadBytes", 0), ("maxPayloadBytes", True), ("maxPayloadBytes", 1114113), ("unexpected", "test")):
            changed = copy.deepcopy(cap)
            changed["targetCredentialLease"][field] = value
            self.assertTrue(self.validator.validate(changed, schema))
        self.assertTrue(self.validator.validate(cap, CONTRACTS / "execution-capabilities" / "v1alpha3" / "schema.json"))

    def test_safe_descriptor_rejects_values_paths_and_wrong_conditions(self):
        descriptor = {"requirementRef": "input-test", "purpose": "SERVICE_ADMIN_TOKEN", "serviceDeployment": "vault-ha",
                      "displayLabel": "Token", "hosts": ["node1"], "requiredWhen": "INITIALIZED", "operations": ["SERVICE_APPLY", "SERVICE_VERIFY"]}
        value = {"apiVersion": "BuildRuntimeSecretDescriptors/v1alpha2", "projectIdentity": "qa", "projectRevision": "sha256:" + "a" * 64,
                 "descriptors": [descriptor], "descriptorSetFingerprint": "sha256:" + "b" * 64}
        schema = CONTRACTS / "runtime-secret-descriptors" / "v1alpha2" / "schema.json"
        self.assertEqual(self.validator.validate(value, schema), [])
        for field, setting in (("value", "sensitive-test-canary"), ("path", "/foreign"), ("requiredWhen", "ALWAYS"), ("hosts", ["node1", "node1"])):
            changed = copy.deepcopy(value)
            changed["descriptors"][0][field] = setting
            self.assertTrue(self.validator.validate(changed, schema))

    def test_typed_input_aggregate_bytes_and_shared_password_bytes(self):
        payload = self.payload()
        payload["runtimeSecretInputs"] = [dict(self.item(value="x" * 4096), requirementRef="input-%d" % n) for n in range(16)]
        self.admit(payload)
        payload["runtimeSecretInputs"][0] = dict(self.item("SERVICE_UNSEAL_SHARES", ["x" * 127] + ["share"]), requirementRef="input-0")
        self.admit(payload)
        payload["runtimeSecretInputs"][0]["value"] = [str(n).zfill(3) + "x" * 125 for n in range(40)]
        with self.assertRaises(InputWireError): self.admit(payload)
        payload = self.payload()
        payload["pkiStorePassword"] = "é" * 2048
        self.admit(payload)
        payload["pkiStorePassword"] += "x"
        with self.assertRaises(InputWireError): self.admit(payload)


if __name__ == "__main__":
    unittest.main()

import copy
import json
from pathlib import Path
import sys
import unittest

CONTRACTS = Path(__file__).resolve().parents[1]
MODULE_UTILS = CONTRACTS.parent / "ansible-core" / "collections" / "ansible_collections" / "platform" / "core" / "plugins" / "module_utils"
sys.path.insert(0, str(MODULE_UTILS))
from schema_validation import SchemaValidator  # Initializes the established offline dependencies.
from jsonschema import Draft202012Validator, RefResolver


ROOT = Path(__file__).resolve().parents[1] / "secret-output-delivery" / "v1alpha1"


def validator(name):
    schema = json.loads((ROOT / name).read_text(encoding="utf-8"))
    store = {}
    for path in ROOT.glob("*.schema.json"):
        document = json.loads(path.read_text(encoding="utf-8"))
        store[document["$id"]] = document
    return Draft202012Validator(schema, resolver=RefResolver.from_schema(schema, store=store))


class SecretOutputDeliveryContractTests(unittest.TestCase):
    def setUp(self):
        self.request = validator("request.schema.json")
        self.base = {"protocol": "SecretOutputDelivery/v1alpha1", "projectId": "project-test"}
        self.fetch = dict(self.base, operation="Fetch", packageId="a" * 32, expectedGeneration=1)
        self.ack = dict(self.fetch, operation="Acknowledge", receiptId="b" * 32,
                        ciphertextDigests={"admin-token": "sha256:" + "c" * 64,
                                           "unseal-shares": "sha256:" + "d" * 64})

    def test_all_closed_operations_are_admitted(self):
        for request in (dict(self.base, operation="GetCapabilities"),
                        dict(self.base, operation="ListPending", limit=32), self.fetch, self.ack):
            with self.subTest(operation=request["operation"]):
                self.request.validate(request)

    def test_unknown_fields_paths_and_secret_values_are_rejected(self):
        for key in ("path", "password", "rootToken", "unsealKeys"):
            request = dict(self.fetch, **{key: "unexpected"})
            self.assertFalse(self.request.is_valid(request), key)
        self.assertFalse(self.request.is_valid(dict(self.fetch, packageId="../foreign")))
        self.assertFalse(self.request.is_valid(dict(self.fetch, protocol="SecretOutputDelivery/v2")))

    def test_generation_and_collection_bounds(self):
        for generation in (0, -1, 2147483648, 1.5, True):
            self.assertFalse(self.request.is_valid(dict(self.fetch, expectedGeneration=generation)))
        for limit in (0, 33, 1.5, True):
            self.assertFalse(self.request.is_valid(dict(self.base, operation="ListPending", limit=limit)))

    def test_ack_requires_both_exact_ciphertext_digests(self):
        for digest in ("sha256:1234", "sha256:" + "C" * 64, "sha512:" + "c" * 64):
            request = copy.deepcopy(self.ack)
            request["ciphertextDigests"]["admin-token"] = digest
            self.assertFalse(self.request.is_valid(request))
        for key in ("admin-token", "unseal-shares"):
            request = copy.deepcopy(self.ack)
            del request["ciphertextDigests"][key]
            self.assertFalse(self.request.is_valid(request))

    def test_safe_metadata_never_admits_content_or_arbitrary_entries(self):
        validate = validator("metadata.schema.json")
        metadata = dict(protocol=self.base["protocol"], packageId="a" * 32,
                        projectId="project-test", deploymentId="vault-ha",
                        sourceRunId="installer-" + "e" * 32, runtimeDigest="sha256:" + "f" * 64,
                        generation=1, state="READY", entries=["admin-token", "unseal-shares"])
        validate.validate(metadata)
        self.assertFalse(validate.is_valid(dict(metadata, clusterId="12345678-1234-1234-1234-123456789abc")))
        self.assertFalse(validate.is_valid(dict(metadata, content="unexpected")))
        self.assertFalse(validate.is_valid(dict(metadata, entries=["admin-token", "admin-token"])))
        self.assertFalse(validate.is_valid(dict(metadata, entries=["unseal-shares", "admin-token"])))

    def test_control_responses_remain_secret_free_and_closed(self):
        validate = validator("response.schema.json")
        capabilities = {"protocol": self.base["protocol"], "operation": "GetCapabilities",
                        "maxPayloadBytes": 65536, "operations": ["ListPending", "Fetch", "Acknowledge"]}
        validate.validate(capabilities)
        validate.validate(dict(self.base, operation="ListPending", packages=[], nextCursor=None))
        ack = dict(self.base, operation="Acknowledge", packageId="a" * 32,
                   generation=1, receiptId="b" * 32, state="DELIVERED")
        validate.validate(ack)
        self.assertFalse(validate.is_valid(dict(ack, state="READY")))
        self.assertFalse(validate.is_valid(dict(ack, token="unexpected")))
        self.assertFalse(validate.is_valid(dict(capabilities, maxPayloadBytes=65537)))
        error = {"protocol": self.base["protocol"], "operation": "Fetch", "errorCode": "OUTPUT_TRANSFER_FAILED"}
        validate.validate(error)
        self.assertFalse(validate.is_valid(dict(error, message="remote output")))


if __name__ == "__main__":
    unittest.main()

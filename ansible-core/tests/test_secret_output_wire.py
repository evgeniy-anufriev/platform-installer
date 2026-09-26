import json
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ansible-core" / "tools"))
sys.path.insert(0, str(ROOT / "ansible-core" / "collections" / "ansible_collections" / "platform" / "core" / "plugins" / "module_utils"))
from schema_validation import SchemaValidator
from secret_output_wire import decode_request, encode_fetch, OutputWireError


class SecretOutputWireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schemas = ROOT / "contracts" / "secret-output-delivery" / "v1alpha1"
        cls.validator = SchemaValidator(cls.schemas)

    def decode(self, data):
        return decode_request(data, self.validator, self.schemas / "request.schema.json")

    def test_request_closed_and_bounded(self):
        request = {"protocol": "SecretOutputDelivery/v1alpha1", "operation": "ListPending", "projectId": "qa", "limit": 32}
        self.assertEqual(self.decode(json.dumps(request).encode()), request)
        for value in (0, 33, True, None, 1.5):
            with self.assertRaisesRegex(OutputWireError, "^OUTPUT_REQUEST_INVALID$"):
                self.decode(json.dumps(dict(request, limit=value)).encode())
        for data in (b" " * 8193, b"\xff", b"{} {}", b'{"projectId":"qa","projectId":"other"}',
                     json.dumps(dict(request, password="sensitive-test-canary")).encode(),
                     b'{"limit":NaN}'):
            with self.assertRaisesRegex(OutputWireError, "^OUTPUT_REQUEST_INVALID$"):
                self.decode(data)

    def metadata(self):
        return {"protocol": "SecretOutputDelivery/v1alpha1", "packageId": "a" * 32,
                "projectId": "qa", "deploymentId": "vault-ha", "clusterId": "12345678-1234-1234-1234-123456789abc",
                "sourceRunId": "installer-test", "runtimeDigest": "sha256:" + "b" * 64,
                "generation": 1, "state": "READY", "entries": ["admin-token", "unseal-shares"]}

    def frame(self, metadata, token=b"test-token", shares=b'{"keys":["test-share"]}'):
        return encode_fetch(metadata, token, shares, self.validator, self.schemas / "metadata.schema.json")

    def test_frame_exact_bytes_and_lengths(self):
        data = self.frame(self.metadata())
        magic, m, t, s = struct.unpack(">4sIII", data[:16])
        self.assertEqual(magic, b"SOD1")
        self.assertEqual(len(data), 16 + m + t + s)
        self.assertEqual(json.loads(data[16:16+m]), self.metadata())
        self.assertEqual(data[16+m:16+m+t], b"test-token")
        self.assertEqual(data[16+m+t:], b'{"keys":["test-share"]}')

    def test_frame_rejects_invalid_package_and_content_safely(self):
        for metadata, token, shares in (
            (dict(self.metadata(), state="DELIVERED"), b"token", b"{}"),
            (dict(self.metadata(), path="foreign"), b"token", b"{}"),
            (self.metadata(), b"", b"{}"), (self.metadata(), b"x" * 4097, b"{}"),
            (self.metadata(), b"\xff", b"{}"), (self.metadata(), b"token", b"x" * 32769),
            (self.metadata(), b"token", b'{"keys":NaN}'),
            (self.metadata(), b"token", b'{"keys":[],"keys":[]}'),
        ):
            with self.assertRaisesRegex(OutputWireError, "^OUTPUT_TRANSFER_FAILED$"):
                self.frame(metadata, token, shares)


if __name__ == "__main__":
    unittest.main()

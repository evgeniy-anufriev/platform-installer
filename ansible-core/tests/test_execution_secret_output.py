import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ansible-core" / "tools"))
sys.path.insert(0, str(ROOT / "ansible-core" / "collections" / "ansible_collections" / "platform" / "core" / "plugins" / "module_utils"))
from schema_validation import SchemaValidator
import execution_secret_output as storage
from secret_output_wire import OutputWireError


class SecretOutputStorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.schemas = ROOT / "contracts" / "secret-output-delivery" / "v1alpha1"
        self.validator = SchemaValidator(self.schemas)
        self.schema = self.schemas / "metadata.schema.json"
        self.meta = {"protocol": "SecretOutputDelivery/v1alpha1", "packageId": "a" * 32,
                     "projectId": "qa", "deploymentId": "vault-ha", "clusterId": "12345678-1234-1234-1234-123456789abc",
                     "sourceRunId": "installer-test", "runtimeDigest": "sha256:" + "b" * 64,
                     "generation": 1, "state": "READY", "entries": ["admin-token", "unseal-shares"]}
        self.package = self.root / "secret-outputs" / self.meta["packageId"]

    def publish(self, meta=None, token=b"test-token"):
        return storage.publish(str(self.root), self.meta if meta is None else meta, token,
                               b'{"keys":["test-share"]}', self.validator, self.schema)

    def fetch(self, project="qa", generation=1):
        return storage.fetch(str(self.root), self.meta["packageId"], project, generation, self.validator, self.schema)

    def test_durable_publish_fetch_and_idempotent_retry(self):
        self.assertEqual(self.publish(), self.meta)
        original = self.fetch()
        self.publish()
        self.assertEqual(self.fetch(), original)
        self.assertEqual(original[:4], b"SOD1")
        self.assertEqual(stat.S_IMODE(self.package.stat().st_mode), 0o700)
        for name in ("admin-token", "unseal-shares", "metadata.json", ".binding.json", ".lock"):
            self.assertEqual(stat.S_IMODE((self.package / name).stat().st_mode), 0o600)
        self.assertFalse((self.root / "runs").exists())

    def test_identity_and_content_cannot_be_overwritten(self):
        self.publish()
        before = self.fetch()
        for meta in (dict(self.meta, projectId="other"), dict(self.meta, generation=2), dict(self.meta, clusterId="22345678-1234-1234-1234-123456789abc")):
            with self.assertRaisesRegex(OutputWireError, "OUTPUT_IDENTITY_MISMATCH"):
                self.publish(meta)
        with self.assertRaisesRegex(OutputWireError, "OUTPUT_IDENTITY_MISMATCH"):
            self.publish(token=b"replacement")
        for project, generation in (("other", 1), ("qa", 2)):
            with self.assertRaisesRegex(OutputWireError, "OUTPUT_IDENTITY_MISMATCH"):
                self.fetch(project, generation)
        self.assertEqual(self.fetch(), before)

    def test_canonical_deployment_ids_schema_publish_fetch(self):
        accepted = ("vault-ha", "vault.ha", "vault_ha", "a" * 128)
        rejected = ("1vault", "vault--ha", "vault/ha", "vault-", "a" * 129)
        for index, deployment in enumerate(accepted + rejected):
            with self.subTest(deployment=deployment):
                meta = dict(self.meta, deploymentId=deployment, packageId=format(index + 1, "032x"))
                if deployment in accepted:
                    self.assertEqual(self.publish(meta), meta)
                    frame = storage.fetch(str(self.root), meta["packageId"], "qa", 1, self.validator, self.schema)
                    self.assertEqual(frame[:4], b"SOD1")
                    self.assertIn(deployment.encode("ascii"), frame)
                else:
                    with self.assertRaises(OutputWireError):
                        self.publish(meta)
                    self.assertFalse((self.root / "secret-outputs" / meta["packageId"]).exists())

    def test_partial_failure_preserves_material_and_same_identity_can_retry(self):
        write = storage._exclusive
        def fault(package, name, data):
            if name == "unseal-shares":
                raise OSError("sensitive-test-canary")
            return write(package, name, data)
        with patch.object(storage, "_exclusive", side_effect=fault):
            with self.assertRaisesRegex(OutputWireError, "^OUTPUT_RECOVERY_REQUIRED$"):
                self.publish()
        self.assertTrue((self.package / "admin-token").exists())
        self.assertFalse((self.package / "metadata.json").exists())
        with self.assertRaises(OutputWireError):
            self.fetch()
        with self.assertRaisesRegex(OutputWireError, "OUTPUT_IDENTITY_MISMATCH"):
            self.publish(dict(self.meta, projectId="other"))
        self.publish()
        self.assertEqual(self.fetch()[:4], b"SOD1")

    def test_symlink_hardlink_and_opened_permissions_fail_closed(self):
        self.publish()
        token = self.package / "admin-token"
        foreign = self.root / "foreign"
        foreign.write_bytes(b"foreign-token")
        foreign.chmod(0o600)
        token.unlink()
        token.symlink_to(foreign)
        with self.assertRaises(OutputWireError): self.fetch()
        self.assertEqual(foreign.read_bytes(), b"foreign-token")
        token.unlink()
        os.link(foreign, token)
        with self.assertRaises(OutputWireError): self.fetch()
        token.unlink()
        token.write_bytes(b"test-token")
        token.chmod(0o644)
        with self.assertRaisesRegex(OutputWireError, "OUTPUT_ACCESS_DENIED"): self.fetch()

    def test_substituted_package_directory_never_followed(self):
        self.publish()
        moved = self.root / "original"
        self.package.rename(moved)
        self.package.symlink_to(moved, target_is_directory=True)
        with self.assertRaises(OutputWireError): self.fetch()
        self.assertTrue((moved / "admin-token").exists())

    def test_read_uses_held_directory_not_later_path_replacement(self):
        self.publish()
        before = self.fetch()
        read = storage._read
        moved = self.root / "held-original"
        swapped = []
        def replace_path(package, name, bound):
            if not swapped:
                self.package.rename(moved)
                self.package.mkdir(mode=0o700)
                (self.package / "admin-token").write_bytes(b"foreign-token")
                swapped.append(True)
            return read(package, name, bound)
        with patch.object(storage, "_read", side_effect=replace_path):
            self.assertEqual(self.fetch(), before)
        self.assertEqual((self.package / "admin-token").read_bytes(), b"foreign-token")
        self.assertTrue((moved / "unseal-shares").exists())

    def test_ready_metadata_not_published_when_atomic_replace_fails(self):
        with patch.object(storage.os, "replace", side_effect=OSError("sensitive-test-canary")):
            with self.assertRaisesRegex(OutputWireError, "^OUTPUT_RECOVERY_REQUIRED$"):
                self.publish()
        self.assertFalse((self.package / "metadata.json").exists())
        self.assertTrue((self.package / "admin-token").exists())
        self.assertTrue((self.package / "unseal-shares").exists())
        self.publish()
        self.assertEqual(self.fetch()[:4], b"SOD1")

    def test_fifo_and_oversized_entry_rejected_before_unbounded_read(self):
        self.publish()
        token = self.package / "admin-token"
        token.unlink()
        os.mkfifo(token, mode=0o600)
        with self.assertRaisesRegex(OutputWireError, "OUTPUT_ACCESS_DENIED"):
            self.fetch()
        token.unlink()
        token.write_bytes(b"x" * 4097)
        token.chmod(0o600)
        with self.assertRaisesRegex(OutputWireError, "OUTPUT_TRANSFER_FAILED"):
            self.fetch()

    def test_boolean_generation_is_not_integer_identity(self):
        self.publish()
        with self.assertRaisesRegex(OutputWireError, "OUTPUT_REQUEST_INVALID"):
            self.fetch(generation=True)

    def test_invalid_metadata_never_materializes_storage(self):
        with self.assertRaises(OutputWireError): self.publish(dict(self.meta, packageId="../foreign"))
        self.assertFalse((self.root / "secret-outputs").exists())


if __name__ == "__main__":
    unittest.main()

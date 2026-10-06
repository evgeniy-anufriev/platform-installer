import sys
import tempfile
import unittest
from pathlib import Path


MODULE_UTILS = Path(__file__).resolve().parents[1] / "collections" / "ansible_collections" / "platform" / "core" / "plugins" / "module_utils"
sys.path.insert(0, str(MODULE_UTILS))
from pki_reissue_state import assert_reissue_unchanged, inspect_reissue


OLD = "sha256:" + "a" * 64
NEW = "sha256:" + "b" * 64
AUTHORITY = "sha256:" + "c" * 64
REQUEST = {"id": "platform-tls--node1", "certificateRequestFingerprint": NEW,
           "authorityId": "platform-ca", "authorityFingerprint": AUTHORITY}


class PKIReissueStateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.request_dir = self.root / "pki" / "project-1" / "requests" / REQUEST["id"]
        self.recovery_dir = self.root / "pki" / "project-1" / "reissues"

    def marker(self, value=OLD):
        authority_dir = self.root / "pki" / "project-1" / "authorities" / REQUEST["authorityId"]
        authority_dir.mkdir(parents=True, exist_ok=True)
        (authority_dir / "authority-fingerprint").write_text(AUTHORITY + "\n", encoding="ascii")
        for name in ("ca.key", "ca.crt"):
            (authority_dir / name).write_bytes(b"test")
        self.request_dir.mkdir(parents=True, exist_ok=True)
        (self.request_dir / "request-fingerprint").write_text(value + "\n", encoding="ascii")
        for name in ("leaf.key", "leaf.crt", "keystore.p12", "truststore.p12"):
            (self.request_dir / name).write_bytes(b"test")

    def recovery(self, value=NEW):
        self.recovery_dir.mkdir(parents=True, exist_ok=True)
        (self.recovery_dir / (REQUEST["id"] + ".fingerprint")).write_text(value + "\n", encoding="ascii")

    def inspect(self):
        return inspect_reissue(str(self.root), "project-1", [REQUEST])

    def test_initial_unchanged_and_changed(self):
        self.assertEqual([], self.inspect())
        self.marker(NEW)
        self.assertEqual([], self.inspect())
        self.marker(OLD)
        self.assertEqual([{"requestId": REQUEST["id"], "expectedOldFingerprint": OLD,
                           "desiredFingerprint": NEW, "recoveryFingerprint": None,
                           "authorityId": REQUEST["authorityId"], "authorityFingerprint": AUTHORITY}], self.inspect())

    def test_interrupted_reissue_is_resumed_without_old_marker(self):
        self.marker()
        self.recovery()
        (self.request_dir / "request-fingerprint").unlink()
        for name in ("leaf.key", "leaf.crt"):
            (self.request_dir / name).unlink()
        expected = [{"requestId": REQUEST["id"], "expectedOldFingerprint": None,
                     "desiredFingerprint": NEW, "recoveryFingerprint": NEW,
                     "authorityId": REQUEST["authorityId"], "authorityFingerprint": AUTHORITY}]
        self.assertEqual(expected, self.inspect())
        assert_reissue_unchanged(str(self.root), "project-1", expected)
        self.marker(NEW)
        with self.assertRaisesRegex(ValueError, "PKI_REISSUE_PLAN_STALE"):
            assert_reissue_unchanged(str(self.root), "project-1", expected)

    def test_completed_leaf_with_stale_recovery_marker_is_resumable(self):
        self.marker(NEW)
        self.recovery()
        self.assertEqual(NEW, self.inspect()[0]["recoveryFingerprint"])

    def test_changed_request_can_repair_missing_derived_store(self):
        self.marker()
        self.assertEqual(OLD, self.inspect()[0]["expectedOldFingerprint"])
        (self.request_dir / "truststore.p12").unlink()
        self.assertEqual(OLD, self.inspect()[0]["expectedOldFingerprint"])
        self.recovery()
        self.assertEqual(NEW, self.inspect()[0]["recoveryFingerprint"])

    def test_changed_authority_blocks_and_stales_committed_observation(self):
        self.marker()
        expected = self.inspect()
        authority_marker = self.root / "pki" / "project-1" / "authorities" / REQUEST["authorityId"] / "authority-fingerprint"
        authority_marker.write_text(OLD + "\n", encoding="ascii")
        with self.assertRaisesRegex(ValueError, "PKI_REISSUE_AUTHORITY_CHANGED"):
            self.inspect()
        with self.assertRaisesRegex(ValueError, "PKI_REISSUE_AUTHORITY_CHANGED"):
            assert_reissue_unchanged(str(self.root), "project-1", expected)

    def test_wrong_recovery_marker_and_partial_material_block(self):
        self.recovery(OLD)
        with self.assertRaisesRegex(ValueError, "PKI_REISSUE_RECOVERY_MISMATCH"):
            self.inspect()
        (self.recovery_dir / (REQUEST["id"] + ".fingerprint")).unlink()
        self.request_dir.mkdir(parents=True)
        (self.request_dir / "leaf.key").write_bytes(b"partial")
        with self.assertRaisesRegex(ValueError, "PKI_REISSUE_STATE_INCOMPLETE"):
            self.inspect()

    def test_symlinked_marker_or_parent_blocks(self):
        self.marker()
        marker = self.request_dir / "request-fingerprint"
        marker.unlink()
        marker.symlink_to(self.root / "foreign")
        with self.assertRaisesRegex(ValueError, "PKI_REISSUE_STATE_UNAVAILABLE"):
            self.inspect()


if __name__ == "__main__":
    unittest.main()

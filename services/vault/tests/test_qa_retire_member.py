"""Narrow safety checks for the SI08-F exact-member retirement tool."""

from contextlib import ExitStack
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parent / "qa_retire_member.py"
spec = importlib.util.spec_from_file_location("qa_retire_member", SCRIPT)
retire = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retire)


@unittest.skipUnless(os.name == "posix" and os.geteuid() == 0, "root-owned Linux temp dirs required")
class QARetireMemberSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="platform-vault-retire-test-", dir="/var/lib")
        self.root = Path(self.temporary.name)
        os.chmod(self.root, 0o700)

    def tearDown(self):
        self.temporary.cleanup()

    @unittest.skipUnless(Path("/var/lib/platform-installer/runtime/releases/fd43413180b166e3bd439eb5916d5d98094cf2e98d6e15c2b6320ba8fc66c3e4").is_dir(),
                         "pinned QA releases required")
    def test_each_old_qa_variant_binds_to_its_pinned_package(self):
        if retire.socket.gethostname() != "redos-node1":
            self.skipTest("pinned releases are held by the QA Execution Node")
        release_root = Path("/var/lib/platform-installer/runtime/releases")
        for member in ("vault-1", "vault-ha-1", "vault-hb-1"):
            with self.subTest(member=member):
                digest = retire.MEMBERS["redos-node1"][member]
                compat = str(release_root / retire.COMPAT_RELEASE) if member == "vault-1" else None
                deployment, user, module, sources = retire.load_pinned_identity(
                    member, str(release_root / digest), compat)
                self.assertEqual(("vault", "platform-vault"), (deployment, user))
                self.assertEqual("/var/lib/platform-vault/vault", sources[3][1])
                self.assertEqual("/etc/platform-vault/vault", sources[2][1])
                self.assertEqual("/etc/systemd/system", module.UNIT_ROOT)

    def test_wrong_pinned_release_is_rejected_before_member_inspection(self):
        if retire.socket.gethostname() != "redos-node1":
            self.skipTest("pinned releases are held by the QA Execution Node")
        wrong = "/var/lib/platform-installer/runtime/releases/d84df0dc93eee8673276981fa94a2d7a20bd6373fa7cffea3a4271fd3216e89d"
        with self.assertRaises((retire.RetirementBlocked, FileNotFoundError)):
            retire.load_pinned_identity("vault-hb-1", wrong)

    def test_compat_clear_is_for_standalone_only(self):
        if retire.socket.gethostname() != "redos-node1":
            self.skipTest("pinned releases are held by the QA Execution Node")
        release_root = Path("/var/lib/platform-installer/runtime/releases")
        with self.assertRaisesRegex(retire.RetirementBlocked, "COMPAT_CLEAR_FORBIDDEN"):
            retire.load_pinned_identity(
                "vault-hb-1", str(release_root / retire.COMPAT_RELEASE),
                str(release_root / retire.COMPAT_RELEASE))

    def test_fixed_unit_header_and_mode_are_required(self):
        name = "platform-vault-example.service"
        unit = self.root / name
        unit.write_bytes(b"# platform-vault-managed: vault/vault-1\n[Unit]\n")
        os.chmod(unit, 0o644)
        with ExitStack() as stack:
            parent = retire.open_root_directory(stack, str(self.root))
            self.assertEqual(unit.stat().st_ino,
                retire.fixed_file(parent, name, b"# platform-vault-managed: vault/vault-1", 0o644).st_ino)
            with self.assertRaisesRegex(retire.RetirementBlocked, "OWNERSHIP_UNKNOWN"):
                retire.fixed_file(parent, name, b"# platform-vault-managed: vault/other", 0o644)

    def test_source_symlink_is_not_followed(self):
        unit = self.root / "unit.service"
        unit.write_bytes(b"# platform-vault-managed: vault/vault-1\n")
        os.chmod(unit, 0o644)
        (self.root / "linked.service").symlink_to(unit)
        with ExitStack() as stack:
            parent = retire.open_root_directory(stack, str(self.root))
            with self.assertRaises(OSError):
                retire.fixed_file(parent, "linked.service",
                    b"# platform-vault-managed: vault/vault-1", 0o644)

    def test_archive_child_must_be_root_private(self):
        (self.root / "unsafe").mkdir(mode=0o755)
        with ExitStack() as stack:
            parent = retire.open_root_directory(stack, str(self.root))
            with self.assertRaisesRegex(retire.RetirementBlocked, "ARCHIVE_UNSAFE"):
                retire.child_dir(stack, parent, "unsafe")
            safe = retire.child_dir(stack, parent, "safe", create=True)
            self.assertEqual(0o700, os.fstat(safe).st_mode & 0o777)


if __name__ == "__main__":
    unittest.main()

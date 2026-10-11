"""Focused Linux safety tests for the narrow HAProxy fragment archiver."""

import importlib.util
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch


MODULE = (Path(__file__).resolve().parents[1] / "ansible_collections" / "platform" /
          "haproxy" / "plugins" / "modules" / "archive_managed_backends.py")
spec = importlib.util.spec_from_file_location("archive_managed_backends", MODULE)
archive_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive_module)


@unittest.skipUnless(os.name == "posix" and os.geteuid() == 0, "root-owned Linux temp dirs required")
class BackendArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="platform-haproxy-archive-test-", dir="/var/tmp")
        self.root = Path(self.temporary.name)
        os.chmod(self.root, 0o700)
        (self.root / "conf.d").mkdir(mode=0o750)

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, name, contents, mode=0o640):
        path = self.root / "conf.d" / name
        path.write_bytes(contents)
        os.chmod(path, mode)
        return path

    @staticmethod
    def owned(name):
        return ("# platform-installer-managed-backend/v1 " + name + "\nbackend test\n").encode()

    def prior_proof(self):
        prior = self.root / ".candidate"
        (prior / "conf.d").mkdir(parents=True)
        shutil.copy2(self.root / "haproxy.cfg", prior / "haproxy.cfg")
        for source in (self.root / "conf.d").iterdir():
            shutil.copy2(source, prior / "conf.d" / source.name)
        return archive_module.capture_prior_candidate(str(self.root))

    def test_explicit_prefix_uses_matching_candidate_and_archive(self):
        (self.root / "haproxy.cfg").write_bytes(b"global\n")
        old = "30-backend-old-main.cfg"
        self.write(old, self.owned(old))
        prior = self.root / ".platform-candidate"
        (prior / "conf.d").mkdir(parents=True)
        shutil.copy2(self.root / "haproxy.cfg", prior / "haproxy.cfg")
        shutil.copy2(self.root / "conf.d" / old, prior / "conf.d" / old)
        proof = archive_module.capture_prior_candidate(str(self.root), "platform")
        result = archive_module.archive(str(self.root), [], True, proof, "platform")
        self.assertEqual([old], result["archived"])
        self.assertEqual(".platform-backend-archive", Path(result["archivePath"]).parent.name)

    def test_fresh_install_creates_no_archive(self):
        result = archive_module.archive(str(self.root), ["30-backend-vault-main.cfg"], True)
        self.assertFalse(result["changed"])
        self.assertFalse((self.root / ".backend-archive").exists())

    def test_owned_stale_is_moved_with_bytes_and_snapshot(self):
        (self.root / "haproxy.cfg").write_bytes(b"global\n")
        old = "30-backend-old-main.cfg"
        new = "30-backend-new-main.cfg"
        self.write(old, self.owned(old))
        self.write("10-public.cfg", b"frontend public\n")
        result = archive_module.archive(str(self.root), [new], True, self.prior_proof())
        self.assertTrue(result["changed"])
        self.assertEqual([old], result["archived"])
        self.assertFalse((self.root / "conf.d" / old).exists())
        archive = Path(result["archivePath"])
        self.assertEqual(self.owned(old), (archive / "stale" / old).read_bytes())
        self.assertEqual(self.owned(old), (archive / "previous" / "conf.d" / old).read_bytes())
        self.assertEqual(b"global\n", (archive / "previous" / "haproxy.cfg").read_bytes())
        self.assertEqual(0o640, (archive / "stale" / old).stat().st_mode & 0o777)

    def test_unowned_same_pattern_blocks_before_mutation(self):
        (self.root / "haproxy.cfg").write_bytes(b"global\n")
        unowned = self.write("30-backend-foreign-main.cfg", b"backend foreign\n")
        with self.assertRaisesRegex(archive_module.ArchiveError, "OWNERSHIP_UNPROVEN"):
            archive_module.archive(str(self.root), [], True)
        self.assertEqual(b"backend foreign\n", unowned.read_bytes())
        self.assertFalse((self.root / ".backend-archive").exists())

    def test_legacy_headerless_owned_fragment_is_archived_with_prior_graph_proof(self):
        (self.root / "haproxy.cfg").write_bytes(b"global\n")
        name = "30-backend-old-main.cfg"
        old_bytes = b"backend old\n    server old 127.0.0.1:8200\n"
        self.write(name, old_bytes)
        proof = self.prior_proof()
        result = archive_module.archive(str(self.root), [], True, proof)
        self.assertEqual([name], result["archived"])
        self.assertEqual(old_bytes, (Path(result["archivePath"]) / "stale" / name).read_bytes())

    def test_spoofed_header_without_prior_graph_proof_blocks(self):
        (self.root / "haproxy.cfg").write_bytes(b"global\n")
        name = "30-backend-foreign-main.cfg"
        foreign = self.write(name, self.owned(name))
        with self.assertRaisesRegex(archive_module.ArchiveError, "OWNERSHIP_UNPROVEN"):
            archive_module.archive(str(self.root), [], True, [])
        self.assertTrue(foreign.exists())
        self.assertFalse((self.root / ".backend-archive").exists())

    def test_prior_candidate_mismatch_cannot_admit_old_fragment(self):
        (self.root / "haproxy.cfg").write_bytes(b"global\n")
        name = "30-backend-old-main.cfg"
        self.write(name, b"backend old\n")
        self.prior_proof()
        self.write(name, b"backend unproven\n")
        with self.assertRaisesRegex(archive_module.ArchiveError, "PRIOR_GRAPH_MISMATCH"):
            archive_module.capture_prior_candidate(str(self.root))

    def test_symlink_same_pattern_blocks_without_following(self):
        (self.root / "haproxy.cfg").write_bytes(b"global\n")
        target = self.write("unrelated.cfg", b"do-not-touch")
        (self.root / "conf.d" / "30-backend-foreign-main.cfg").symlink_to(target)
        with self.assertRaises((OSError, archive_module.ArchiveError)):
            archive_module.archive(str(self.root), [], True)
        self.assertEqual(b"do-not-touch", target.read_bytes())

    def test_unchanged_owned_graph_does_not_create_archive(self):
        name = "30-backend-vault-main.cfg"
        (self.root / "haproxy.cfg").write_bytes(b"global\n")
        self.write(name, self.owned(name))
        result = archive_module.archive(str(self.root), [name], False, self.prior_proof())
        self.assertFalse(result["changed"])
        self.assertFalse((self.root / ".backend-archive").exists())

    def test_partial_move_failure_restores_already_moved_files(self):
        (self.root / "haproxy.cfg").write_bytes(b"global\n")
        first, second = "30-backend-a-main.cfg", "30-backend-b-main.cfg"
        self.write(first, self.owned(first))
        self.write(second, self.owned(second))
        proof = self.prior_proof()
        real_rename = archive_module.os.rename
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected move failure")
            return real_rename(*args, **kwargs)

        with patch.object(archive_module.os, "rename", side_effect=fail_second):
            with self.assertRaises(OSError):
                archive_module.archive(str(self.root), [], True, proof)
        self.assertEqual(self.owned(first), (self.root / "conf.d" / first).read_bytes())
        self.assertEqual(self.owned(second), (self.root / "conf.d" / second).read_bytes())


if __name__ == "__main__":
    unittest.main()

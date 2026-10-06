import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import run_with_runtime_credentials as runner
from execution_lifecycle import Journal, LifecycleError


class RuntimeCredentialRunnerTests(unittest.TestCase):
    def write_credentials(self, directory, payload):
        path = Path(directory) / "credentials.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_passes_only_ephemeral_descriptor_path_and_cleans_it(self):
        with tempfile.TemporaryDirectory() as directory:
            credentials = self.write_credentials(directory, {"ansible_password": "secret", "ansible_become_password": "secret"})
            runtime = Path(directory) / "runtime"
            captured = {}

            def fake_run(command, check, env):
                captured["command"] = command
                descriptor = Path(command[-1][1:])
                captured["mode"] = stat.S_IMODE(descriptor.stat().st_mode)
                captured["payload"] = json.loads(descriptor.read_text(encoding="utf-8"))
                return type("Completed", (), {"returncode": 0})()

            with patch.object(runner.subprocess, "run", fake_run):
                result = runner.main(["--credentials-file", str(credentials), "--runtime-dir", str(runtime), "--", "ansible-playbook", "site.yml"])

            self.assertEqual(0, result)
            self.assertEqual(["ansible-playbook", "site.yml", "--extra-vars"], captured["command"][:-1])
            self.assertEqual(0o600, captured["mode"])
            self.assertEqual({"ansible_password": "secret", "ansible_become_password": "secret"}, captured["payload"])
            self.assertEqual([], list(runtime.glob("bootstrap-*.json")))

    def test_private_key_is_runtime_only_and_removed_after_process(self):
        with tempfile.TemporaryDirectory() as directory:
            credentials = self.write_credentials(directory, {"privateKey": "synthetic-private-key", "ansible_become_password": "sudo-secret"})
            runtime = Path(directory) / "runtime"
            captured = {}
            def fake_run(command, check, env):
                key = Path(env["ANSIBLE_PRIVATE_KEY_FILE"])
                captured["key_mode"] = stat.S_IMODE(key.stat().st_mode)
                captured["key_contents"] = key.read_text(encoding="utf-8")
                captured["key_path"] = key
                descriptor = Path(command[-1][1:])
                captured["extra_vars"] = json.loads(descriptor.read_text(encoding="utf-8"))
                captured["command"] = command
                return type("Completed", (), {"returncode": 0})()
            with patch.object(runner.subprocess, "run", fake_run):
                result = runner.main(["--credentials-file", str(credentials), "--runtime-dir", str(runtime), "--", "ansible-playbook", "site.yml"])
            self.assertEqual(0, result)
            self.assertEqual(0o600, captured["key_mode"])
            self.assertEqual("synthetic-private-key", captured["key_contents"])
            self.assertEqual({"ansible_become_password": "sudo-secret"}, captured["extra_vars"])
            self.assertNotIn("synthetic-private-key", " ".join(captured["command"]))
            self.assertFalse(captured["key_path"].exists())
            self.assertEqual([], list(runtime.iterdir()))

    def test_private_key_without_sudo_needs_no_extra_vars(self):
        with tempfile.TemporaryDirectory() as directory:
            credentials = self.write_credentials(directory, {"privateKey": "synthetic-private-key"})
            runtime = Path(directory) / "runtime"
            captured = {}
            def fake_run(command, check, env):
                captured["command"] = command
                captured["key_path"] = Path(env["ANSIBLE_PRIVATE_KEY_FILE"])
                self.assertTrue(captured["key_path"].is_file())
                return type("Completed", (), {"returncode": 0})()
            with patch.object(runner.subprocess, "run", fake_run):
                self.assertEqual(0, runner.main(["--credentials-file", str(credentials), "--runtime-dir", str(runtime), "--", "ansible-playbook", "site.yml"]))
            self.assertEqual(["ansible-playbook", "site.yml"], captured["command"])
            self.assertFalse(captured["key_path"].exists())

    def test_private_key_is_removed_on_child_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            credentials = self.write_credentials(directory, {"privateKey": "synthetic-private-key"})
            runtime = Path(directory) / "runtime"
            with patch.object(runner.subprocess, "run", side_effect=OSError("synthetic spawn failure")):
                with self.assertRaises(OSError):
                    runner.main(["--credentials-file", str(credentials), "--runtime-dir", str(runtime), "--", "ansible-playbook", "site.yml"])
            self.assertEqual([], list(runtime.iterdir()))

    def test_rejects_two_ssh_credentials_and_unsafe_runtime_dir(self):
        with tempfile.TemporaryDirectory() as directory:
            credentials = self.write_credentials(directory, {"ansible_password": "secret", "privateKey": "synthetic-private-key"})
            with self.assertRaisesRegex(ValueError, "exactly one"):
                runner.main(["--credentials-file", str(credentials), "--runtime-dir", str(Path(directory) / "runtime"), "--", "ansible-playbook", "site.yml"])
            credentials = self.write_credentials(directory, {"privateKey": "synthetic-private-key"})
            outside = Path(directory) / "outside"; outside.mkdir()
            linked = Path(directory) / "linked"; linked.symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "unsafe"):
                runner.main(["--credentials-file", str(credentials), "--runtime-dir", str(linked), "--", "ansible-playbook", "site.yml"])
            self.assertEqual([], list(outside.iterdir()))

    def test_rejects_unknown_credential_key(self):
        with tempfile.TemporaryDirectory() as directory:
            credentials = self.write_credentials(directory, {"not_allowed": "secret"})
            with self.assertRaisesRegex(ValueError, "unsupported"):
                runner.main(["--credentials-file", str(credentials), "--runtime-dir", str(Path(directory) / "runtime"), "--", "ansible-playbook", "site.yml"])

    def test_terminal_cleanup_only_removes_owned_temporary_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = Journal(directory, "installer-1")
            lock = journal.lock(); os.close(lock)
            runtime = Path(journal.directory) / ".ansible-runtime"
            runtime.mkdir(mode=0o700)
            key = runtime / "target-key-12345678.pem"; key.write_text("synthetic-private-key")
            bootstrap = runtime / "bootstrap-12345678.json"; bootstrap.write_text("{}")
            unrelated = runtime / "unrelated.txt"; unrelated.write_text("keep")
            input_file = Path(journal.directory) / ".ansible-runtime-credentials.json"; input_file.write_text("synthetic")
            journal.cleanup_runtime_connection_credentials()
            self.assertFalse(key.exists())
            self.assertFalse(bootstrap.exists())
            self.assertFalse(input_file.exists())
            self.assertTrue(unrelated.exists())

    def test_cleanup_rejects_runtime_symlink_without_deleting_outside_file(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = Journal(directory, "installer-1")
            lock = journal.lock(); os.close(lock)
            outside = Path(directory) / "outside"; outside.mkdir(mode=0o700)
            key = outside / "target-key-12345678.pem"; key.write_text("synthetic-private-key")
            (Path(journal.directory) / ".ansible-runtime").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(LifecycleError):
                journal.cleanup_runtime_connection_credentials()
            self.assertTrue(key.exists())

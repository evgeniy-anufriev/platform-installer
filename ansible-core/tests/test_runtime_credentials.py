import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import run_with_runtime_credentials as runner


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

            def fake_run(command, check):
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

    def test_rejects_unknown_credential_key(self):
        with tempfile.TemporaryDirectory() as directory:
            credentials = self.write_credentials(directory, {"not_allowed": "secret"})
            with self.assertRaisesRegex(ValueError, "unsupported"):
                runner.main(["--credentials-file", str(credentials), "--runtime-dir", str(Path(directory) / "runtime"), "--", "ansible-playbook", "site.yml"])

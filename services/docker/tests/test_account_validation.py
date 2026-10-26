"""Run the production account admission tasks through Ansible on RED OS."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[3]


@unittest.skipUnless(shutil.which("ansible-playbook"), "RED OS Ansible required")
class DockerAccountValidationTests(unittest.TestCase):
    def test_root_is_denied_and_other_valid_names_are_accepted(self):
        env = dict(os.environ, ANSIBLE_COLLECTIONS_PATH=os.pathsep.join([
            str(ROOT / "services/docker/ansible_collections"),
            str(ROOT / "ansible-core/collections"),
        ]))
        cases = [
            ("auto", "platform-automation", True),
            ("auto", "root", False),
            ("existing-user", "platform-automation", True),
            ("create-user", "platform-automation", True),
            ("existing-user", "root", False),
            ("create-user", "root", False),
            ("existing-user", "admin", True),
            ("create-user", "admin", True),
            ("existing-user", "qa-docker", True),
        ]
        with tempfile.TemporaryDirectory(prefix="docker-account-admission-") as directory:
            playbook = Path(directory) / "validate.yml"
            password_file = Path(directory) / "synthetic-password"
            password_file.write_text("synthetic-test-input", encoding="utf-8")
            password_file.chmod(0o600)
            playbook.write_text(yaml.safe_dump([{
                "hosts": "localhost", "connection": "local", "gather_facts": False,
                "tasks": [{"ansible.builtin.include_role": {
                    "name": "platform.docker.docker_rootless", "tasks_from": "validate.yml",
                }}],
            }]), encoding="utf-8")
            for mode, account, accepted in cases:
                with self.subTest(mode=mode, account=account):
                    result = subprocess.run([
                        "ansible-playbook", "-i", "localhost,", str(playbook),
                        "-e", f"platform_docker_mode={mode}",
                        "-e", f"platform_docker_account_name={account}",
                        "-e", "platform_docker_data_root=/data/docker",
                        "-e", "platform_docker_tls_directory=/etc/ssl",
                        "-e", json.dumps({
                            "platform_docker_account_credential": {"passwordSecretRef": "runtime:qa-password"},
                            "platform_docker_secret_files": {"runtime:qa-password": str(password_file)},
                        }),
                    ], cwd=ROOT, env=env, capture_output=True, text=True, timeout=90)
                    output = result.stdout + result.stderr
                    if accepted:
                        self.assertEqual(result.returncode, 0, output[-3000:])
                        self.assertRegex(output, r"changed=0\s+unreachable=0\s+failed=0")
                    else:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn("DOCKER_ROOTLESS_INPUT_INVALID", output)


if __name__ == "__main__":
    unittest.main()

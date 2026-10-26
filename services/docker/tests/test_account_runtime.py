"""Native account branch, password rejection and repeat tests; RED OS only."""

import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import tempfile
import unittest
import uuid

import yaml


ROOT = Path(__file__).resolve().parents[3]


@unittest.skipUnless(shutil.which("ansible-playbook") and os.geteuid() == 0, "RED OS Ansible/root required")
class DockerAccountRuntimeTests(unittest.TestCase):
    def test_concurrent_creation_keeps_the_other_creators_password(self):
        account = "qa-dkr-" + uuid.uuid4().hex[:10]
        original_password = "synthetic-original-" + uuid.uuid4().hex
        supplied_password = "synthetic-supplied-" + uuid.uuid4().hex
        original_hash = subprocess.run(["openssl", "passwd", "-6", "-stdin"],
                                       input=original_password, capture_output=True,
                                       text=True, check=True).stdout.strip()
        role = ROOT / "services/docker/ansible_collections/platform/docker/roles/docker_rootless"
        tasks = yaml.safe_load((role / "tasks/account.yml").read_text())
        creation = next(index for index, task in enumerate(tasks)
                        if task.get("ansible.builtin.command", {}).get("argv", [None])[0] == "useradd")
        tasks.insert(creation, {
            "name": "Fixture creates the competing account after production getent",
            "ansible.builtin.user": {"name": account, "create_home": True,
                                    "shell": "/bin/bash", "password": original_hash},
            "no_log": True,
        })
        with tempfile.TemporaryDirectory(prefix="docker-account-race-") as directory:
            secret = Path(directory) / "password"
            secret.write_text(supplied_password, encoding="utf-8")
            secret.chmod(0o600)
            variables = yaml.safe_load((role / "defaults/main.yml").read_text())
            variables.update({
                "platform_docker_mode": "auto", "platform_docker_account_name": account,
                "platform_docker_account_credential": {"passwordSecretRef": "runtime:test-password"},
                "platform_docker_secret_files": {"runtime:test-password": str(secret)},
            })
            playbook = Path(directory) / "race.yml"
            playbook.write_text(yaml.safe_dump([{
                "hosts": "localhost", "connection": "local", "gather_facts": False,
                "vars": variables, "tasks": tasks,
            }]), encoding="utf-8")
            try:
                result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(playbook)],
                                        cwd=ROOT, capture_output=True, text=True, timeout=120)
                output = result.stdout + result.stderr
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("useradd", output)
                for protected in (original_password, supplied_password, original_hash):
                    self.assertNotIn(protected, output)
                final_hash = subprocess.run(["getent", "shadow", account],
                                            capture_output=True, text=True, check=True).stdout.split(":")[1]
                self.assertEqual(original_hash, final_hash)
            finally:
                subprocess.run(["userdel", "-r", account], capture_output=True)

    def test_create_existing_wrong_password_locked_and_repeat(self):
        account = "qa-dkr-" + uuid.uuid4().hex[:10]
        with tempfile.TemporaryDirectory(prefix="docker-account-runtime-") as directory:
            work = Path(directory)
            secret = work / "password"
            password = "synthetic-" + uuid.uuid4().hex
            secret.write_text(password, encoding="utf-8")
            secret.chmod(0o600)
            variables = {
                "platform_docker_mode": "auto",
                "platform_docker_account_name": account,
                "platform_docker_account_credential": {"passwordSecretRef": "runtime:test-password"},
                "platform_docker_secret_files": {"runtime:test-password": str(secret)},
            }
            play = work / "account.yml"
            play.write_text(yaml.safe_dump([{
                "hosts": "localhost", "connection": "local", "gather_facts": False,
                "vars": variables,
                "tasks": [{"ansible.builtin.include_role": {
                    "name": "platform.docker.docker_rootless", "tasks_from": "account.yml",
                }}],
            }]), encoding="utf-8")
            env = dict(os.environ, ANSIBLE_COLLECTIONS_PATH=os.pathsep.join([
                str(ROOT / "services/docker/ansible_collections"),
                str(ROOT / "ansible-core/collections"),
            ]))

            def invoke(mode="auto"):
                result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(play),
                                         "-e", f"platform_docker_mode={mode}"],
                                        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
                output = result.stdout + result.stderr
                self.assertNotIn(password, output)
                self.assertNotIn("synthetic-wrong-password", output)
                return result.returncode, output

            def shadow():
                result = subprocess.run(["getent", "shadow", account], capture_output=True, text=True, check=True)
                return result.stdout.split(":")[1]

            try:
                code, output = invoke("existing-user")
                self.assertNotEqual(code, 0)
                self.assertIn("DOCKER_ACCOUNT_REQUIRED", output)
                with self.assertRaises(KeyError):
                    pwd.getpwnam(account)
                code, output = invoke()
                self.assertEqual(code, 0, output[-2000:])
                self.assertGreaterEqual(pwd.getpwnam(account).pw_uid, 1000)
                original = shadow()
                for mode in ("auto", "existing-user", "create-user"):
                    code, output = invoke(mode)
                    self.assertEqual(code, 0, output[-2000:])
                    self.assertRegex(output, r"changed=0\s+unreachable=0\s+failed=0")
                    self.assertEqual(shadow(), original)
                secret.write_text("synthetic-wrong-password", encoding="utf-8")
                code, output = invoke()
                self.assertNotEqual(code, 0)
                self.assertIn("DOCKER_ACCOUNT_PASSWORD_MISMATCH", output)
                self.assertEqual(shadow(), original)
                secret.write_text(password, encoding="utf-8")
                subprocess.run(["usermod", "-L", account], check=True, capture_output=True)
                locked = shadow()
                code, output = invoke()
                self.assertNotEqual(code, 0)
                self.assertIn("DOCKER_ACCOUNT_PASSWORD_MISMATCH", output)
                self.assertEqual(shadow(), locked)
            finally:
                subprocess.run(["userdel", "-r", account], capture_output=True)


if __name__ == "__main__":
    unittest.main()

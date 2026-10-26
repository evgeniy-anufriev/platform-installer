"""Exercise data-root tasks in private temporary directories, without Docker."""

import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import tempfile
import unittest

import yaml


ROLE = Path(__file__).resolve().parents[1] / "ansible_collections/platform/docker/roles/docker_rootless"


@unittest.skipUnless(shutil.which("ansible-playbook"), "RED OS Ansible required")
class DockerDataRootTests(unittest.TestCase):
    def setUp(self):
        self.account = pwd.getpwuid(os.getuid())
        self.temporary = tempfile.TemporaryDirectory(prefix="docker-data-root-", dir=Path.home())
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        (self.home / ".config/docker").mkdir(parents=True, mode=0o700)
        self.config = self.home / ".config/docker/daemon.json"
        self.data = self.home / "data"

    def run_tasks(self, data=None, verify=False, accepted=True):
        play = [{"hosts": "localhost", "connection": "local", "gather_facts": False,
                 "vars": {"_platform_docker_home": str(self.home),
                          "platform_docker_account_name": self.account.pw_name,
                          "_platform_docker_gid": os.getgid(),
                          "platform_docker_data_root": str(self.data) if data is None else data,
                          "platform_docker_verify_only": verify},
                 "tasks": [{"ansible.builtin.include_tasks": str(ROLE / "tasks/data_root.yml")}],
                 "handlers": [{"name": "Перезапуск системной службы пользовательского Docker",
                               "ansible.builtin.debug": {"msg": "fixture restart notification"}}]}]
        playbook = self.home / "test.yml"
        playbook.write_text(yaml.safe_dump(play))
        result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(playbook)],
                                text=True, capture_output=True, timeout=90)
        self.assertEqual(accepted, result.returncode == 0, result.stdout[-2500:] + result.stderr[-1000:])
        return result.stdout

    def test_preserve_repeat_verify_and_switch_without_migration(self):
        self.config.write_text(json.dumps({"log-driver": "local", "features": {"buildkit": True}}))
        self.run_tasks()
        expected = {"log-driver": "local", "features": {"buildkit": True}, "data-root": str(self.data)}
        self.assertEqual(expected, json.loads(self.config.read_text()))
        self.assertEqual(0o600, self.config.stat().st_mode & 0o777)
        self.assertEqual(0o700, self.data.stat().st_mode & 0o777)
        self.assertIn("changed=0", self.run_tasks())
        before = self.config.stat().st_mtime_ns
        self.assertIn("changed=0", self.run_tasks(verify=True))
        self.assertEqual(before, self.config.stat().st_mtime_ns)
        witness = self.data / "retained-volume"
        witness.write_text("retained")
        other = self.home / "other-data"
        self.run_tasks(str(other))
        self.assertEqual("retained", witness.read_text())
        self.assertFalse((other / witness.name).exists())
        self.assertEqual(str(other), json.loads(self.config.read_text())["data-root"])
        self.assertIn("DOCKER_DATA_ROOT_CONFIG_MISMATCH", self.run_tasks(verify=True, accepted=False))

    def test_missing_config_created_and_verify_does_not_create(self):
        self.run_tasks(verify=True, accepted=False)
        self.assertFalse(self.data.exists())
        self.assertFalse(self.config.exists())
        self.run_tasks()
        self.assertEqual({"data-root": str(self.data)}, json.loads(self.config.read_text()))

    def test_unsafe_paths_rejected_before_config_write(self):
        for path in ("relative/path", "/", "/etc/docker", str(self.home / "../escape"),
                     str(self.home / ".config/docker/data"), "/home/another-account/docker"):
            with self.subTest(path=path):
                self.run_tasks(path, accepted=False)
                self.assertFalse(self.config.exists())

    def test_symlink_or_writable_data_ancestor_rejected(self):
        real = self.home / "real"
        real.mkdir()
        linked = self.home / "linked"
        linked.symlink_to(real, target_is_directory=True)
        self.run_tasks(str(linked / "data"), accepted=False)
        real.chmod(0o777)
        self.run_tasks(str(real / "data"), accepted=False)
        self.assertFalse(self.config.exists())

    def test_foreign_json_shape_and_symlink_config_retained(self):
        self.config.write_text("[]")
        self.run_tasks(accepted=False)
        self.assertEqual("[]", self.config.read_text())
        self.config.unlink()
        foreign = self.home / "foreign.json"
        foreign.write_text("{}")
        self.config.symlink_to(foreign)
        self.run_tasks(accepted=False)
        self.assertEqual("{}", foreign.read_text())


if __name__ == "__main__":
    unittest.main()

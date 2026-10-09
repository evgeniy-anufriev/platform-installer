import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


TASKS = Path(__file__).resolve().parents[1] / "ansible_collections/platform/docker/roles/docker_rootless/tasks/shell_environment.yml"


class DockerShellEnvironmentTests(unittest.TestCase):
    def test_profiles_preserve_content_and_repeat_without_changes(self):
        ansible = shutil.which("ansible-playbook")
        if not ansible:
            self.skipTest("Ansible runtime required")
        import pwd
        account = pwd.getpwuid(os.getuid())
        with tempfile.TemporaryDirectory(prefix="platform-docker-profile-") as directory:
            home = Path(directory)
            profile = home / ".bash_profile"
            profile.write_text("# operator setting\nexport OPERATOR_SETTING=retained\n")
            play = [{"hosts": "localhost", "connection": "local", "gather_facts": False,
                     "vars": {"_platform_docker_home": directory,
                              "platform_docker_account_name": account.pw_name,
                              "_platform_docker_gid": os.getgid()},
                     "tasks": [{"ansible.builtin.include_tasks": str(TASKS)}]}]
            playbook = home / "test.yml"
            playbook.write_text(yaml.safe_dump(play))
            for iteration in range(2):
                result = subprocess.run([ansible, "-i", "localhost,", str(playbook)],
                                        text=True, capture_output=True, timeout=60)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                if iteration:
                    self.assertIn("changed=0", result.stdout)
            self.assertIn("export OPERATOR_SETTING=retained", profile.read_text())
            for name in [".bash_profile", ".bashrc"]:
                self.assertEqual(1, (home / name).read_text().count("export DOCKER_HOST="))
                env = dict(os.environ)
                for key in ["XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS", "DOCKER_HOST"]:
                    env.pop(key, None)
                command = '. "$1"; printf "%s\\n" "$XDG_RUNTIME_DIR" "$DBUS_SESSION_BUS_ADDRESS" "$DOCKER_HOST"'
                shell = subprocess.run(["bash", "-c", command, "test", str(home / name)],
                                       env=env, text=True, capture_output=True, check=True)
                runtime = "/run/user/" + str(os.getuid())
                self.assertEqual([runtime, "unix:path=" + runtime + "/bus", "unix://" + runtime + "/docker.sock"],
                                 shell.stdout.splitlines())


if __name__ == "__main__":
    unittest.main()

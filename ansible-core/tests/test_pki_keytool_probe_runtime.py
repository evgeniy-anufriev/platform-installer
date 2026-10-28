import copy
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROLE = Path(__file__).resolve().parents[1] / "collections/ansible_collections/platform/core/roles/pki_materialize"


class PkiKeytoolProbeRuntimeTests(unittest.TestCase):
    def test_existing_keytool_skips_second_probe_and_install_still_requires_readiness(self):
        if not shutil.which("ansible-playbook"):
            self.skipTest("Ansible runtime required")
        original = yaml.safe_load((ROLE / "tasks/main.yml").read_text())
        selected = [t for t in original if t.get("register") in {
            "_platform_pki_keytool_probe", "_platform_pki_keytool_install", "_platform_pki_keytool_ready"}
            or t.get("ansible.builtin.assert", {}).get("fail_msg") == "PKI_KEYTOOL_UNAVAILABLE"]
        self.assertEqual(4, len(selected))
        with tempfile.TemporaryDirectory(prefix="platform-pki-probe-") as directory:
            root = Path(directory)
            executable = root / "keytool"
            for existing, pkcs12, install_ok in ((True, True, True), (False, True, True),
                                                (False, False, True), (False, True, False)):
                with self.subTest(existing=existing, pkcs12=pkcs12, install_ok=install_ok):
                    executable.unlink(missing_ok=True)
                    if existing:
                        executable.write_text("#!/bin/sh\nexit 0\n")
                        executable.chmod(0o700)
                    tasks = copy.deepcopy(selected)
                    for task in tasks:
                        if "ansible.builtin.shell" in task:
                            task["ansible.builtin.shell"] = "command -v " + shlex.quote(str(executable))
                        if "ansible.builtin.package" in task:
                            task.pop("ansible.builtin.package")
                            task["ansible.builtin.copy"] = {"content": "#!/bin/sh\nexit 0\n", "mode": "0755",
                                "dest": str(executable if install_ok else root / "other-tool")}
                    tasks.append({"ansible.builtin.assert": {"that": [
                        "(_platform_pki_keytool_ready.skipped | default(false)) == " + str(existing or not pkcs12).lower()]}})
                    play = root / "play.yml"
                    play.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False,
                        "vars": {"platform_pki_materialization_plans": [{"formats": ["PKCS12_KEYSTORE"] if pkcs12 else ["PEM"]}]},
                        "tasks": tasks}]))
                    result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(play)],
                                            capture_output=True, text=True, timeout=60)
                    self.assertEqual(install_ok or not pkcs12, result.returncode == 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

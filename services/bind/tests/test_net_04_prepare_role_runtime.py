import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parents[1]


class RootOwnedTemporaryDirectory(tempfile.TemporaryDirectory):
    def cleanup(self):
        if self.name and Path(self.name).exists():
            path = Path(self.name).resolve()
            if path.parent != Path("/tmp") or not path.name.startswith("platform-bind-prepare-role-"):
                raise RuntimeError("refusing to clean an unexpected BIND role test path")
            subprocess.run(["sudo", "-n", "rm", "-rf", "--", str(path)], check=True)
        super().cleanup()


def read_root_owned_file(path):
    result = subprocess.run(
        ["sudo", "-n", "cat", "--", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def root_owned_path_exists(path):
    result = subprocess.run(
        ["sudo", "-n", "test", "-e", str(path)],
        check=False,
    )
    return result.returncode == 0


class BindPrepareRoleRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not sys.platform.startswith("linux"):
            raise unittest.SkipTest("the isolated role runtime test requires Linux")
        cls.ansible_playbook = shutil.which("ansible-playbook")
        cls.checkconf = shutil.which("named-checkconf")
        cls.checkzone = shutil.which("named-checkzone")
        cls.sudo = shutil.which("sudo")
        getent = shutil.which("getent")
        if not all((cls.ansible_playbook, cls.checkconf, cls.checkzone, cls.sudo, getent)):
            raise unittest.SkipTest("Ansible, BIND validation tools, sudo and getent are required")
        if subprocess.run([getent, "passwd", "named"], capture_output=True, text=True).returncode:
            raise unittest.SkipTest("the isolated QA host must provide the named account")
        if subprocess.run([getent, "group", "named"], capture_output=True, text=True).returncode:
            raise unittest.SkipTest("the isolated QA host must provide the named group")
        if subprocess.run([cls.sudo, "-n", "true"], capture_output=True, text=True).returncode:
            raise unittest.SkipTest("the isolated QA host must provide non-interactive sudo")

    def test_existing_zone_is_preserved_unless_full_reconcile_renders_candidate(self):
        with RootOwnedTemporaryDirectory(prefix="platform-bind-prepare-role-") as temporary:
            root = Path(temporary)
            primary = root / "primary"
            secondary = root / "secondary"
            recovery = root / "recovery"
            primary.mkdir()
            secondary.mkdir()

            zone = "qa.example.test"
            active_zone = primary / f"{zone}.zone"
            active_zone.write_text(
                "$TTL 300\n"
                f"@ IN SOA ns.{zone}. hostmaster.{zone}. (\n"
                "  10 300 60 1209600 300\n)\n"
                f"@ IN NS ns.{zone}.\n"
                f"ns IN A 192.0.2.53\n"
                "manually-owned IN A 192.0.2.77\n",
                encoding="utf-8",
            )
            original_zone = active_zone.read_text(encoding="utf-8")

            distribution_config = root / "named.conf"
            distribution_config.write_text(
                'options {\n  directory "/var/named";\n  recursion no;\n};\n',
                encoding="utf-8",
            )

            bind_deployment = {
                "serviceType": "bind",
                "configuration": {},
            }
            projection = {
                "zone": zone,
                "defaultTtl": 300,
                "mname": f"ns.{zone}",
                "rname": f"hostmaster.{zone}",
                "nameservers": [f"ns.{zone}"],
                "records": [
                    {"owner": "ns", "type": "A", "values": ["192.0.2.53"]},
                    {"owner": "managed", "type": "A", "values": ["192.0.2.10"]},
                ],
                "secondaries": [],
                "primary": {"address": "127.0.0.1", "fqdn": f"ns.{zone}"},
            }
            variables = {
                "platform_resolved_artifact_sources": {
                    "bind": {"source": "TEST"},
                    "bind-utils": {"source": "TEST"},
                },
                "platform_desired_state": {"serviceDeployments": {"bind-qa": bind_deployment}},
                "platform_deployments": {"bind-qa": {"roles": ["primary"]}},
                "platform_bind_resolved_zones": {"bind-qa": projection},
                "platform_bind_runtime_projection": {
                    "generatedState": {
                        "metadata": {"projectId": "bind-prepare-runtime-test"},
                        "serviceDeployments": {"bind-qa": {"dns": {"currentSerial": 20}}},
                    }
                },
                "platform_bind_distribution_config": str(distribution_config),
                "platform_bind_candidate_main_config": str(root / "named.conf.candidate"),
                "platform_bind_include_file": str(root / "platform-installer.conf"),
                "platform_bind_options_include_file": str(root / "platform-installer-options.conf"),
                "platform_bind_primary_zone_directory": str(primary),
                "platform_bind_secondary_zone_directory": str(secondary),
                "platform_bind_recovery_directory": str(recovery),
                "platform_bind_checkconf_binary": self.checkconf,
                "platform_bind_checkzone_binary": self.checkzone,
                "platform_bind_rndc_binary": "/usr/sbin/rndc",
            }
            playbook = [
                {
                    "hosts": "localhost",
                    "connection": "local",
                    "gather_facts": False,
                    "become": True,
                    "vars": variables,
                    "tasks": [
                        {
                            "name": "Run the real BIND prepare role tasks",
                            "ansible.builtin.include_role": {
                                "name": "platform.bind.bind",
                                "tasks_from": "prepare",
                            },
                        }
                    ],
                }
            ]
            harness = root / "prepare-role.yml"
            harness.write_text(json.dumps(playbook), encoding="utf-8")
            inventory = root / "inventory.ini"
            inventory.write_text("localhost ansible_connection=local\n", encoding="utf-8")

            environment = os.environ.copy()
            collections_path = os.pathsep.join(
                (
                    str(REPOSITORY_ROOT / "ansible-core" / "collections"),
                    str(ROOT),
                    str(REPOSITORY_ROOT / "services" / "haproxy"),
                    str(REPOSITORY_ROOT / "services" / "integrations"),
                )
            )
            environment["ANSIBLE_COLLECTIONS_PATH"] = collections_path
            environment["ANSIBLE_COLLECTIONS_PATHS"] = collections_path

            def run_prepare(full_reconcile):
                command = [self.ansible_playbook, "-i", str(inventory), str(harness)]
                if full_reconcile:
                    command.extend(["-e", "platform_bind_full_reconcile=true"])
                result = subprocess.run(
                    command,
                    cwd=REPOSITORY_ROOT,
                    env=environment,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(
                    0,
                    result.returncode,
                    (result.stdout + "\n" + result.stderr)[-6000:],
                )
                return result.stdout

            run_prepare(full_reconcile=False)
            self.assertEqual(original_zone, read_root_owned_file(active_zone))
            self.assertFalse(root_owned_path_exists(primary / f"{zone}.zone.candidate"))

            run_prepare(full_reconcile=True)
            candidate = primary / f"{zone}.zone.candidate"
            self.assertTrue(root_owned_path_exists(candidate))
            rendered = read_root_owned_file(candidate)
            self.assertIn("  20  ; serial", rendered)
            self.assertIn("managed 300 IN A 192.0.2.10", rendered)
            self.assertNotIn("manually-owned", rendered)
            self.assertEqual(original_zone, read_root_owned_file(active_zone))


if __name__ == "__main__":
    unittest.main()

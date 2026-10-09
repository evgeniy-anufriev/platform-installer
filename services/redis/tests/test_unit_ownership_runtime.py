import copy
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


TASKS = Path(__file__).resolve().parents[1] / "ansible_collections/platform/redis/roles/redis_tls/tasks/preflight.yml"


class RedisUnitOwnershipRuntimeTests(unittest.TestCase):
    def test_missing_owned_and_foreign_redis_and_sentinel_units(self):
        executable = shutil.which("ansible-playbook")
        if not executable:
            self.skipTest("Ansible runtime required")
        source = yaml.safe_load(TASKS.read_text(encoding="utf-8"))
        names = {
            "redis": ["Inspect exact Redis member unit paths before rendering",
                      "Reject unsafe existing Redis member unit paths",
                      "Read ownership headers from existing Redis member units",
                      "Refuse replacement of foreign Redis member units"],
            "sentinel": ["Inspect exact Sentinel unit paths before rendering",
                         "Reject unsafe existing Sentinel unit paths",
                         "Read ownership headers from existing Sentinel units",
                         "Refuse replacement of foreign Sentinel units"],
        }
        with tempfile.TemporaryDirectory(prefix="platform-redis-ownership-") as directory:
            root = Path(directory)
            for kind, task_names in names.items():
                checks = copy.deepcopy([next(task for task in source if task.get("name") == name)
                                        for name in task_names])
                marker = "# platform-redis-managed: qa/member-1/" + kind
                for scenario, header, expected in [("missing", None, 0), ("owned", marker, 0),
                                                  ("foreign", "# foreign", 2)]:
                    with self.subTest(kind=kind, scenario=scenario):
                        unit = root / (kind + "-" + scenario + ".service")
                        if header is not None:
                            unit.write_text(header + "\n[Unit]\n", encoding="utf-8")
                        tasks = copy.deepcopy(checks)
                        tasks[0]["ansible.builtin.stat"]["path"] = str(unit)
                        tasks[2]["ansible.builtin.slurp"]["src"] = str(unit)
                        play = [{"hosts": "localhost", "connection": "local", "gather_facts": False,
                                 "vars": {"platform_redis_deployment_id": "qa",
                                          "_platform_redis_local_instances": [{"id": "member-1",
                                              "instance_name": "qa-1", "roles": ["redis", "sentinel"]}]},
                                 "tasks": tasks}]
                        path = root / "test.yml"
                        path.write_text(yaml.safe_dump(play), encoding="utf-8")
                        result = subprocess.run([executable, "-i", "localhost,", str(path)],
                                                capture_output=True, text=True, timeout=60)
                        self.assertEqual(expected, result.returncode, result.stdout + result.stderr)
                        if header is None:
                            self.assertFalse(unit.exists())
                        else:
                            self.assertEqual(header + "\n[Unit]\n", unit.read_text(encoding="utf-8"))
                        if expected:
                            self.assertIn("REDIS_UNIT_OWNERSHIP_UNKNOWN", result.stdout)


if __name__ == "__main__":
    unittest.main()

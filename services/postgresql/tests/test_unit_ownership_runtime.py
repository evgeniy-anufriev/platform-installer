import copy
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


ROLE = Path(__file__).resolve().parents[1] / "ansible_collections/platform/postgresql/roles/postgresql"


class PostgreSQLUnitOwnershipRuntimeTests(unittest.TestCase):
    def test_existing_unit_ownership_and_first_install(self):
        executable = shutil.which("ansible-playbook")
        if not executable:
            self.skipTest("Ansible runtime required")
        source = yaml.safe_load((ROLE / "tasks/main.yml").read_text(encoding="utf-8"))
        names = ["Проверить точный путь к службе systemd PostgreSQL перед изменением",
                 "Отклонить замененный путь к службе systemd PostgreSQL",
                 "Прочитать заголовок владения из существующей службы systemd PostgreSQL",
                 "Отказаться от замены неуправляемой службы systemd PostgreSQL"]
        checks = [next(task for task in source if task.get("name") == name) for name in names]
        template = (ROLE / "templates/postgresql.service.j2").read_text(encoding="utf-8")
        owned = template.replace("{{ platform_postgresql_name }}", "platform-postgresql").replace("{{ platform_postgresql_deployment_id }}", "qa-postgresql").replace(
            "{{ (_platform_postgresql_local_members | first).id }}", "postgresql-1")
        marker = "# platform-postgresql-managed: qa-postgresql/postgresql-1"
        scenarios = [("missing", None, 0), ("current-template", owned, 0),
                     ("marker-first", marker + "\n[Unit]\n", 0),
                     ("foreign", "[Unit]\n# foreign\n", 2),
                     ("other-member", owned.replace("/postgresql-1", "/postgresql-2"), 2),
                     ("other-deployment", owned.replace("qa-postgresql/", "other/"), 2),
                     ("marker-prefix", owned.replace(marker, marker + "-foreign"), 2)]
        with tempfile.TemporaryDirectory(prefix="platform-postgresql-ownership-") as directory:
            root = Path(directory)
            for scenario, content, expected in scenarios:
                with self.subTest(scenario=scenario):
                    unit = root / (scenario + ".service")
                    if content is not None:
                        unit.write_text(content, encoding="utf-8")
                    tasks = copy.deepcopy(checks)
                    tasks[0]["ansible.builtin.stat"]["path"] = str(unit)
                    tasks[2]["ansible.builtin.slurp"]["src"] = str(unit)
                    play = [{"hosts": "localhost", "connection": "local", "gather_facts": False,
                             "vars": {"platform_postgresql_verify_only": False,
                                      "platform_postgresql_name": "platform-postgresql",
                                      "platform_postgresql_deployment_id": "qa-postgresql",
                                      "_platform_postgresql_local_members": [{"id": "postgresql-1"}]},
                             "tasks": tasks}]
                    path = root / "test.yml"
                    path.write_text(yaml.safe_dump(play), encoding="utf-8")
                    result = subprocess.run([executable, "-i", "localhost,", str(path)],
                                            capture_output=True, text=True, timeout=60)
                    self.assertEqual(expected, result.returncode, result.stdout + result.stderr)
                    if content is None:
                        self.assertFalse(unit.exists())
                    else:
                        self.assertEqual(content, unit.read_text(encoding="utf-8"))
                    if expected:
                        self.assertIn("POSTGRES_UNIT_OWNERSHIP_UNKNOWN", result.stdout)


if __name__ == "__main__":
    unittest.main()

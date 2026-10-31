import copy
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


TASKS = Path(__file__).resolve().parents[1] / "ansible_collections/platform/redis/roles/redis_tls/tasks/preflight.yml"


class RedisUnitOwnershipRuntimeTests(unittest.TestCase):
    def test_owned_units_repeat_when_current_and_former_names_coincide(self):
        executable = shutil.which("ansible-playbook")
        if not executable:
            self.skipTest("Ansible runtime required")
        source = yaml.safe_load(TASKS.read_text(encoding="utf-8"))
        end = next(index for index, task in enumerate(source) if task.get("name") ==
                   "Проверка существующего маркера состояния экземпляра службы Redis")
        with tempfile.TemporaryDirectory(prefix="platform-redis-repeat-") as directory:
            root = Path(directory)
            headers = {"redis@redis-3.service": "# redis-managed: redis/redis-3/redis\n",
                       "redis-sentinel@redis-3.service": "# redis-managed: redis/redis-3/sentinel\n"}
            for name, header in headers.items():
                (root / name).write_text(header + "[Unit]\n", encoding="utf-8")
            checks = yaml.safe_load(yaml.safe_dump(source[:end]).replace("/etc/systemd/system", str(root)))
            normalize = {"ansible.builtin.include_tasks": str(TASKS.parent / "normalize.yml")}
            tasks = [normalize, {"ansible.builtin.set_fact": {
                "_platform_redis_local_instances": "{{ _platform_redis_instances }}"}}] + checks + checks
            variables = dict(platform_redis_name="redis", platform_redis_deployment_id="redis",
                             platform_redis_port=6379, platform_redis_sentinel_port=26379,
                             platform_redis_data_root=str(root / "data"),
                             platform_redis_config_root=str(root / "config"),
                             platform_redis_log_root=str(root / "logs"),
                             platform_redis_instances=[dict(id="redis-3", host="localhost", roles=["redis", "sentinel"])])
            play = root / "repeat.yml"
            play.write_text(yaml.safe_dump([dict(hosts="localhost", connection="local", gather_facts=False,
                                                vars=variables, tasks=tasks)]), encoding="utf-8")
            result = subprocess.run([executable, "-i", "localhost,", str(play)],
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("changed=0", result.stdout)
            for name, header in headers.items():
                self.assertEqual(header + "[Unit]\n", (root / name).read_text(encoding="utf-8"))

    def test_services_have_no_legacy_installation_blockers(self):
        repository = TASKS.parents[7]
        roles = {"redis": "redis_tls/tasks/preflight.yml", "vault": "vault_tls/tasks/preflight.yml",
                 "clickhouse": "clickhouse_tls/tasks/preflight.yml", "kafka": "kafka_kraft/tasks/apply.yml",
                 "postgresql": "postgresql/tasks/main.yml"}
        for service, role in roles.items():
            path = repository / service / "ansible_collections/platform" / service / "roles" / role
            text = path.read_text(encoding="utf-8")
            with self.subTest(service=service):
                self.assertNotIn("LEGACY_UNIT_REQUIRES_S11_CLEANUP", text)
                self.assertNotIn("_legacy_unit", text)

    def test_acl_overwrite_gate_requires_all_markers_and_exact_deployment_units(self):
        executable = shutil.which("ansible-playbook")
        if not executable:
            self.skipTest("Ansible runtime required")
        source = yaml.safe_load(TASKS.read_text(encoding="utf-8"))
        authorize = next(task for task in source if task.get("name") ==
                         "Разрешение перезаписи ACL только для развёртывания с маркерами владения и управляемыми службами")
        show = {"ansible.builtin.debug": {"var": "_platform_redis_acl_overwrite_allowed"}}
        owned_redis = {"content": "# platform-redis-managed: qa/member-1/redis"}
        owned_sentinel = {"content": "# platform-redis-managed: qa/member-1/sentinel"}
        scenarios = [
            ("same deployment", True, {"results": [owned_redis]},
             {"results": [owned_sentinel]}, True),
            ("no state marker", False, {"results": [owned_redis]},
             {"results": [owned_sentinel]}, False),
            ("missing redis unit", True, {"results": [{"skipped": True}]},
             {"results": [owned_sentinel]}, False),
            ("missing sentinel unit", True, {"results": [owned_redis]},
             {"results": [{"skipped": True}]}, False),
        ]
        with tempfile.TemporaryDirectory(prefix="platform-redis-acl-gate-") as directory:
            root = Path(directory)
            for label, marked, redis_units, sentinel_units, expected in scenarios:
                with self.subTest(scenario=label):
                    variables = {
                        "_platform_redis_all_have_persistent_state": marked,
                        "_platform_redis_local_instances": [{"roles": ["redis", "sentinel"]}],
                        "_platform_redis_existing_unit_headers": redis_units,
                        "_platform_sentinel_existing_unit_headers": sentinel_units,
                    }
                    play = [{"hosts": "localhost", "connection": "local", "gather_facts": False,
                             "vars": variables, "tasks": [copy.deepcopy(authorize), show]}]
                    path = root / "gate.yml"
                    path.write_text(yaml.safe_dump(play), encoding="utf-8")
                    result = subprocess.run([executable, "-i", "localhost,", str(path)],
                                            capture_output=True, text=True, timeout=60)
                    self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                    self.assertIn("_platform_redis_acl_overwrite_allowed\": " + str(expected).lower(), result.stdout)

    def test_missing_owned_and_foreign_redis_and_sentinel_units(self):
        executable = shutil.which("ansible-playbook")
        if not executable:
            self.skipTest("Ansible runtime required")
        source = yaml.safe_load(TASKS.read_text(encoding="utf-8"))
        names = {
            "redis": ["Проверка путей служб экземпляра Redis перед формированием файлов",
                      "Отклонение небезопасных существующих путей службы systemd экземпляра службы Redis",
                      "Чтение заголовков владения из существующих системных служб экземпляра службы Redis",
                      "Запрет замены неуправляемых служб экземпляра Redis"],
            "sentinel": ["Проверка путей службы Sentinel перед формированием файлов",
                         "Отклонение небезопасных существующих путей службы systemd Sentinel",
                         "Чтение заголовков владения из существующих системных служб Sentinel",
                         "Запрет замены неуправляемых служб Sentinel"],
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
                                          "platform_redis_name": "platform-redis",
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

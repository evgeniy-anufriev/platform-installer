import shutil
import subprocess
import tempfile
from pathlib import Path
import unittest

import yaml

ROLE = Path(__file__).resolve().parents[1] / "ansible_collections/platform/kafka/roles/kafka_kraft"


class RegistryPhaseRuntimeTests(unittest.TestCase):
    def test_principals_are_calculated_once_and_shared_with_reverse_host_order(self):
        if not shutil.which("ansible-playbook"):
            self.skipTest("Ansible runtime required")
        main = yaml.safe_load((ROLE / "tasks/apply.yml").read_text())
        names = {"Выбор узла расчёта principals для текущего запуска Kafka",
                 "Определение удостоверений сертификата экземпляра доверенной службы перед активацией авторизатора",
                 "Передача рассчитанных principals всем участникам текущего запуска Kafka"}
        tasks = [task for task in main if task["name"] in names]
        self.assertEqual(3, len(tasks))
        with tempfile.TemporaryDirectory(prefix="platform-principal-phase-") as directory:
            root = Path(directory)
            child = root / "identity.yml"
            child.write_text(yaml.safe_dump([{"ansible.builtin.set_fact": {
                "identity_source": True,
                "_platform_kafka_internal_principals": "{{ _platform_kafka_internal_principals + ['User:' ~ kafka_authorization_member.id] }}"}}]))
            tasks[1]["ansible.builtin.include_tasks"] = str(child)
            tasks.append({"ansible.builtin.assert": {"that": [
                "_platform_kafka_internal_principals == ['User:m1', 'User:m2']",
                "identity_source is not defined or inventory_hostname == _platform_kafka_principal_source_host"]}})
            inventory = root / "inventory.yml"
            inventory.write_text(yaml.safe_dump({"all": {"hosts": {"h1": {"ansible_connection": "local"},
                                                                   "h2": {"ansible_connection": "local"}}}}))
            play = root / "play.yml"
            play.write_text(yaml.safe_dump([{"hosts": "all", "order": "reverse_inventory", "gather_facts": False,
                "vars": {"_platform_kafka_scram_enabled": True, "platform_kafka_verify_only": False,
                         "_platform_kafka_internal_principals": [], "_platform_kafka_instances": [{"id": "m1"}, {"id": "m2"}]},
                "tasks": tasks}]))
            result = subprocess.run(["ansible-playbook", "-i", str(inventory), str(play)],
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertRegex(result.stdout, r"changed=0\s")

    def test_next_play_reuses_prepared_facts_and_loads_role_defaults(self):
        if not shutil.which("ansible-playbook"):
            self.skipTest("Ansible runtime required")
        with tempfile.TemporaryDirectory(prefix="platform-registry-phase-") as directory:
            root = Path(directory)
            role = root / "roles/registry"
            (role / "tasks").mkdir(parents=True)
            shutil.copytree(ROLE / "defaults", role / "defaults")
            shutil.copyfile(ROLE / "tasks/schema_registry_apply.yml", role / "tasks/schema_registry_apply.yml")
            (role / "tasks/main.yml").write_text("- ansible.builtin.fail: {msg: MAIN_MUST_NOT_RUN}\n")
            (role / "tasks/schema_registry.yml").write_text(yaml.safe_dump([
                {"ansible.builtin.assert": {"that": ["prepared_cluster == 'prepared'", "_platform_kafka_registry_local | length == 1"]}},
                {"ansible.builtin.set_fact": {"registry_ran": True}},
            ]))
            plays = [
                {"hosts": "localhost", "gather_facts": False, "tasks": [
                    {"ansible.builtin.set_fact": {"prepared_cluster": "prepared", "_platform_kafka_registry_local": [{"id": "member-1"}]}}]},
                {"hosts": "localhost", "gather_facts": False, "tasks": [
                    {"ansible.builtin.include_role": {"name": "registry", "tasks_from": "schema_registry_apply.yml"},
                     "vars": {"platform_kafka_schema_registry_enabled": False}},
                    {"ansible.builtin.assert": {"that": ["registry_ran is not defined"]}},
                    {"ansible.builtin.include_role": {"name": "registry", "tasks_from": "schema_registry_apply.yml"}},
                    {"ansible.builtin.assert": {"that": ["registry_ran | bool"]}},
                ]},
            ]
            file = root / "play.yml"
            file.write_text(yaml.safe_dump(plays))
            result = subprocess.run(["ansible-playbook", "-i", "localhost,", "-c", "local", str(file)],
                                    cwd=root, capture_output=True, text=True, timeout=60)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertRegex(result.stdout, r"changed=0\s")


if __name__ == "__main__":
    unittest.main()

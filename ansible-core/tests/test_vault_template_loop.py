import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
ROLE = ROOT / "services/vault/ansible_collections/platform/vault/roles/vault_tls"


@unittest.skipUnless(shutil.which("ansible-playbook"), "Ansible runtime required")
class VaultTemplateLoopTests(unittest.TestCase):
    def test_real_templates_track_changed_members_using_standard_item(self):
        source = yaml.safe_load((ROLE / "tasks/provision.yml").read_text())
        names = ["Отрисовка изолированной конфигурации Vault",
                 "Запись экземпляров службы, конфигурация Vault которых изменилась",
                 "Установка изолированных системных служб Vault systemd",
                 "Установить ограниченную политику ротации журналов аудита Vault для каждого экземпляра",
                 "Запись экземпляров службы, чья системная служба systemd изменилась"]
        selected = [copy.deepcopy(next(task for task in source if task["name"] == name))
                    for name in names]
        with tempfile.TemporaryDirectory(prefix="vault-loop-test-") as directory:
            root = Path(directory)
            members = []
            for index in range(3):
                config = root / f"config-{index}"
                config.mkdir()
                members.append(dict(id=f"vault-{index}", slot=index,
                                    instance_name=f"vault-test-{index}", address="127.0.0.1",
                                    api_port=8200 + index * 2, cluster_port=8201 + index * 2,
                                    config_directory=str(config),
                                    data_directory=str(root / f"data-{index}"),
                                    log_directory=str(root / f"logs-{index}")))
            for task in selected:
                if "ansible.builtin.template" in task:
                    template = task["ansible.builtin.template"]
                    template["src"] = str(ROLE / "templates" / template["src"])
                    template.pop("owner")
                    template.pop("group")
                    if template["dest"].startswith("/etc/"):
                        template["dest"] = str(root) + "/{{ vault_member.instance_name }}." + (
                            "service" if template["src"].endswith("vault.service.j2") else "logrotate")
                    self.assertNotIn("loop_var", task["loop_control"])
            tasks = []
            for phase, expected in enumerate((["vault-0", "vault-1", "vault-2"], [], ["vault-1"])):
                current = copy.deepcopy(members)
                if phase == 2:
                    current[1]["data_directory"] += "-changed"
                tasks.append({"ansible.builtin.set_fact": {
                    "_platform_vault_restart_member_ids": [],
                    "_platform_vault_local_instances": current}})
                tasks.extend(copy.deepcopy(selected))
                tasks.append({"ansible.builtin.assert": {"that": [
                    "_platform_vault_restart_member_ids == " + repr(expected),
                    "_platform_vault_config_rendered.results | map(attribute='ansible_loop_var') | unique | list == ['item']",
                    "_platform_vault_units_rendered.results | map(attribute='ansible_loop_var') | unique | list == ['item']",
                    "_platform_vault_config_rendered.results | map(attribute='item.id') | list == ['vault-0', 'vault-1', 'vault-2']",
                    "_platform_vault_units_rendered.results | map(attribute='item.id') | list == ['vault-0', 'vault-1', 'vault-2']"]}})
            play = [{"hosts": "localhost", "connection": "local", "gather_facts": False,
                     "vars_files": [str(ROLE / "defaults/main.yml")],
                     "vars": {"platform_vault_user": "qa", "platform_vault_group": "qa",
                              "platform_vault_deployment_id": "qa", "platform_vault_mode": "standalone"},
                     "tasks": tasks}]
            path = root / "probe.json"
            path.write_text(json.dumps(play), encoding="utf-8")
            result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(path)],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90,
                                    env=dict(os.environ, ANSIBLE_NOCOLOR="1"))
            self.assertEqual(0, result.returncode, "Synthetic Vault template/tracking probe failed")

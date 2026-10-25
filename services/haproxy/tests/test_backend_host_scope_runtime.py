"""Execute the production file-model tasks; no services or target files change."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml


ROLE = Path(__file__).resolve().parents[1] / "ansible_collections/platform/haproxy/roles/haproxy"


class BackendHostScopeRuntimeTests(unittest.TestCase):
    def test_plural_partial_scope_keeps_each_provider_host_and_unrelated_files(self):
        if not shutil.which('ansible-playbook'):
            self.skipTest('Ansible runtime required')
        prepare = yaml.safe_load((ROLE / 'tasks/prepare.yml').read_text())
        names = {'Выбрать точные имена файлов, принадлежащие частичному источнику конечной точки',
                 'Сохранение точных проверенных внутренних ресурсов в базовом режиме',
                 'Выбрать backend развёртывания источника для частичной интеграции HAProxy'}
        tasks = yaml.safe_load((ROLE / 'tasks/partial_scope.yml').read_text())
        tasks += [task for task in prepare if task.get('name') in names]
        backends = [dict(targetDeploymentId='app-one', configFileName='30-backend-app-one.cfg', providerHostIds=['node1']),
                    dict(targetDeploymentId='app-two', configFileName='30-backend-app-two.cfg', providerHostIds=['node2'])]
        plays = []
        for host, source in [('node1', 'app-one'), ('node2', 'app-two')]:
            variables = dict(inventory_hostname=host, platform_deployments={'proxy': {}},
                             platform_haproxy_full_reconcile=False,
                             platform_haproxy_partial_deployment_ids=['app-one', 'app-two'],
                             platform_haproxy_runtime_projection={'backends': {'backends': {'proxy': backends}}},
                             _platform_haproxy_prior_backend_capture={'previousInventory': [
                                 {'name': '30-backend-' + source + '.cfg'}, {'name': '30-backend-unselected.cfg'}]},
                             expected_source=source)
            checks = [{'ansible.builtin.assert': {'that': [
                "platform_haproxy_application_backends | map(attribute='targetDeploymentId') | list == [expected_source]",
                "platform_haproxy_managed_application_backend_files | length == 2",
                "'30-backend-unselected.cfg' in platform_haproxy_managed_application_backend_files"]}}]
            plays.append(dict(hosts='localhost', connection='local', gather_facts=False, vars=variables, tasks=tasks + checks))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.yml'
            path.write_text(yaml.safe_dump(plays))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(path)], capture_output=True, text=True, timeout=40)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_partial_backend_does_not_reinstall_provider_under_source_authority(self):
        executable = shutil.which("ansible-playbook")
        if not executable:
            self.skipTest("ansible-playbook is required")
        main = yaml.safe_load((ROLE / "tasks/lifecycle.yml").read_text())
        prepare = yaml.safe_load((ROLE / "tasks/prepare.yml").read_text())
        selected = [task for task in main if task.get("name") in {
            "Проверка разрешенных источников артефактов HAProxy перед изменением",
            "Доставка выбранных автономных артефактов HAProxy"}]
        selected += [task for task in prepare if task.get("name") ==
                     "Установить HAProxy из настроенных системных репозиториев"]
        repository = Path(__file__).resolve().parents[3]
        env = dict(os.environ)
        env["ANSIBLE_COLLECTIONS_PATH"] = str(repository / "ansible-core/collections")
        with tempfile.TemporaryDirectory(prefix="platform-haproxy-artifact-") as temporary:
            path = Path(temporary, "test.yml")
            variables = {"platform_haproxy_partial_deployment_id": "qa-vault-consumer",
                         "platform_execution_service_deployment": "qa-vault-consumer",
                         "platform_artifact_source_authority_active": True,
                         "platform_artifact_source_authorities_by_deployment": {
                             "qa-vault-consumer": {"vault-runtime": {}}},
                         "platform_resolved_artifact_sources": {},
                         "platform_haproxy_phase": "prepare"}
            play = [{"hosts": "localhost", "connection": "local", "gather_facts": False,
                     "vars": variables, "tasks": selected}]
            path.write_text(yaml.safe_dump(play), encoding="utf-8")
            result = subprocess.run([executable, "-i", "localhost,", str(path)],
                                    env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("changed=0", result.stdout)
            # The identical invalid authority still fails for a full provider apply.
            variables.pop("platform_haproxy_partial_deployment_id")
            play[0]["tasks"] = selected[:1]
            path.write_text(yaml.safe_dump(play), encoding="utf-8")
            result = subprocess.run([executable, "-i", "localhost,", str(path)],
                                    env=env, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("Проверить наличие утверждённых источников артефактов Core для развёртывания сервиса", result.stdout)

    def test_full_and_partial_models_filter_hosts_and_preserve_other_sources(self):
        executable = shutil.which("ansible-playbook")
        if not executable:
            self.skipTest("ansible-playbook is required")
        tasks = yaml.safe_load((ROLE / "tasks/prepare.yml").read_text(encoding="utf-8"))
        names = {"Выбрать точные имена файлов, принадлежащие частичному источнику конечной точки",
                 "Выбор полной модели файла серверной части управляемого приложения",
                 "Сохранение точных проверенных внутренних ресурсов в базовом режиме",
                 "Выбрать backend развёртывания источника для частичной интеграции HAProxy"}
        selected = [task for task in tasks if task.get("name") in names]
        backend = {"targetDeploymentId": "app", "providerHostIds": ["node1", "node2"],
                   "configFileName": "30-backend-app-public.cfg"}
        plays = []
        for partial in (False, True):
            for host in ("node1", "node2", "node3"):
                expected = [backend["configFileName"]] if host != "node3" else []
                if partial:
                    expected.append("30-backend-other-public.cfg")
                    # An old group absent from the exact current mapping needs full reconcile.
                    expected.append("30-backend-app-old.cfg")
                variables = {
                    "inventory_hostname": host, "platform_deployments": {"proxy": {}},
                    "platform_haproxy_full_reconcile": not partial,
                    "platform_haproxy_runtime_projection": {"backends": {"backends": {"proxy": [backend]}}},
                    "_platform_haproxy_prior_backend_capture": {"previousInventory": [
                        {"name": "30-backend-app-old.cfg"}, {"name": "30-backend-other-public.cfg"}]},
                    "expected_files": sorted(expected),
                    "expected_source_count": 0 if host == "node3" else 1,
                }
                if partial:
                    variables["platform_haproxy_partial_deployment_id"] = "app"
                plays.append({"hosts": "localhost", "connection": "local", "gather_facts": False,
                              "vars": variables, "tasks": yaml.safe_load((ROLE / "tasks/partial_scope.yml").read_text()) + selected + [{"ansible.builtin.assert": {"fail_msg": "{{ platform_haproxy_managed_application_backend_files }} != {{ expected_files }}", "that": [
                                  "platform_haproxy_managed_application_backend_files == expected_files",
                                  "platform_haproxy_application_backends | length == expected_source_count",
                              ]}}]})
        with tempfile.TemporaryDirectory(prefix="platform-haproxy-hosts-") as temporary:
            path = Path(temporary, "test.yml")
            path.write_text(yaml.safe_dump(plays, sort_keys=False), encoding="utf-8")
            result = subprocess.run([executable, "-i", "localhost,", str(path)],
                                    capture_output=True, text=True, timeout=60)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_all_partial_phases_target_only_resolved_hosts(self):
        executable = shutil.which("ansible-playbook")
        if not executable:
            self.skipTest("ansible-playbook is required")
        source = yaml.safe_load((ROLE.parents[4] / "playbooks/integrate.yml").read_text(encoding="utf-8"))
        plays = [{"hosts": "localhost", "gather_facts": False, "tasks": [{"ansible.builtin.set_fact": {
            "platform_service_integration_projection": {"haproxyHosts": ["node2"]}}}]}]
        for original in source:
            plays.append({"hosts": original["hosts"], "gather_facts": False, "tasks": [
                {"ansible.builtin.assert": {"that": ["inventory_hostname == 'node2'"]}}]})
        with tempfile.TemporaryDirectory(prefix="platform-haproxy-phases-") as temporary:
            path = Path(temporary, "test.yml")
            path.write_text(yaml.safe_dump(plays, sort_keys=False), encoding="utf-8")
            result = subprocess.run([executable, "-i", "localhost,node1,node2,node3,", str(path)],
                                    capture_output=True, text=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertNotIn("ok: [node1]", result.stdout)
        self.assertNotIn("ok: [node3]", result.stdout)


if __name__ == "__main__":
    unittest.main()

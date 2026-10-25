import os
import shutil
import subprocess
import tempfile
import unittest

import yaml


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
PLAYBOOK = os.path.join(ROOT, "services", "integrations", "tasks", "resolve-source.yml")
HAPROXY_PLAYBOOK = os.path.join(ROOT, "services", "haproxy", "playbooks", "integrate.yml")
APPLY_SOURCE = os.path.join(ROOT, "services", "integrations", "tasks", "apply-source.yml")


class SourceDnsProjectionTests(unittest.TestCase):
    def test_resolved_provider_projection_is_shared_with_every_target_host(self):
        executable = shutil.which("ansible-playbook")
        if not executable:
            self.skipTest("ansible-playbook is required")
        with open(APPLY_SOURCE, encoding="utf-8") as source:
            tasks = yaml.safe_load(source)
        publish = next(task for task in tasks if task.get("name") ==
                       "Опубликовать решенную исходную проекцию один раз для каждого хоста провайдера")
        playbook = [{
            "name": "Exercise the production cross-host projection handoff",
            "hosts": "node1,node2",
            "connection": "local",
            "gather_facts": False,
            "vars": {
                "platform_service_integration_projection": {
                    "haproxyHosts": ["node1", "node2"],
                    "haproxyDeployments": ["qa-haproxy"],
                    "dnsDeployments": ["qa-bind"],
                },
                "platform_bind_source_dns_records": [{"owner": "app.example.test."}],
                "_platform_integration_selected_sources": [{"sourceId": "app"}],
            },
            "tasks": [publish, {
                "name": "Require controller-scoped source data on every target",
                "ansible.builtin.assert": {"that": [
                    "hostvars['localhost'].platform_service_integration_projection.haproxyHosts == ['node1', 'node2']",
                    "hostvars['localhost'].platform_bind_source_dns_records[0].owner == 'app.example.test.'",
                ]},
            }],
        }]
        with tempfile.TemporaryDirectory(prefix="platform-source-context-") as temporary:
            path = os.path.join(temporary, "test.yml")
            with open(path, "w", encoding="utf-8") as output:
                yaml.safe_dump(playbook, output, sort_keys=False)
            result = subprocess.run([executable, "-i", "localhost,node1,node2,", path],
                                    capture_output=True, text=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_empty_source_initializes_an_empty_haproxy_host_scope(self):
        executable = shutil.which("ansible-playbook")
        if not executable:
            self.skipTest("ansible-playbook is required")
        with open(PLAYBOOK, encoding="utf-8") as source:
            source_plays = yaml.safe_load(source)
        initialize = source_plays[0]
        with open(HAPROXY_PLAYBOOK, encoding="utf-8") as source:
            proxy_plays = yaml.safe_load(source)
        plays = [{"hosts": "localhost", "connection": "local", "gather_facts": False,
                  "tasks": [initialize, {"ansible.builtin.assert": {"that": [
                      "platform_service_integration_projection.haproxyHosts == []"]}}]}]
        for play in proxy_plays:
            plays.append({"hosts": play["hosts"], "gather_facts": False,
                          "tasks": [{"ansible.builtin.fail": {"msg": "No source must not target any proxy"}}]})
        with tempfile.TemporaryDirectory(prefix="platform-source-empty-") as temporary:
            path = os.path.join(temporary, "test.yml")
            with open(path, "w", encoding="utf-8") as output:
                yaml.safe_dump(plays, output, sort_keys=False)
            result = subprocess.run([executable, "-i", "localhost,node1,node2,", path],
                                    capture_output=True, text=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_production_task_preserves_list_and_record_addresses(self):
        ansible_playbook = shutil.which("ansible-playbook")
        if not ansible_playbook:
            self.skipTest("ansible-playbook is required")

        with open(PLAYBOOK, encoding="utf-8") as source:
            plays = yaml.safe_load(source)
        tasks = plays
        build_task = next(task for task in tasks if task.get("name") == "Сборка точных исходных обновлений DNS для решенных развертываний BIND")
        playbook = [
            {
                "name": "Exercise the production source DNS projection",
                "hosts": "localhost",
                "connection": "local",
                "gather_facts": False,
                "vars": {
                    "platform_bind_source_dns_records": [],
                    "platform_service_integration_projection": {"dnsDeployments": ["qa-bind"]},
                    "_platform_integration_source_fqdns": ["qa-vault.example.internal"],
                    "_platform_integration_dns_resolution": {
                        "resolved_dns_zones": {
                            "zones": {
                                "qa-bind": {
                                    "zone": "example.internal",
                                    "defaultTtl": 300,
                                    "records": [{
                                        "owner": "qa-vault.example.internal.",
                                        "values": ["192.0.2.10"],
                                    }],
                                },
                            },
                        },
                    },
                },
                "tasks": [
                    build_task,
                    {
                        "name": "Validate the exact record projection",
                        "ansible.builtin.assert": {
                            "that": [
                                "platform_bind_source_dns_records is sequence",
                                "platform_bind_source_dns_records is not string",
                                "platform_bind_source_dns_records | length == 1",
                                "platform_bind_source_dns_records[0]['addresses'] == ['192.0.2.10']",
                            ],
                        },
                    },
                ],
            },
        ]
        with tempfile.TemporaryDirectory(prefix="platform-source-dns-") as temporary:
            path = os.path.join(temporary, "test.yml")
            with open(path, "w", encoding="utf-8") as output:
                yaml.safe_dump(playbook, output, sort_keys=False)
            result = subprocess.run(
                [ansible_playbook, "-i", "localhost,", path],
                capture_output=True, text=True, timeout=30,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_probe_address_projection_uses_one_contract_for_application_and_service_sources(self):
        ansible_playbook = shutil.which("ansible-playbook")
        if not ansible_playbook:
            self.skipTest("ansible-playbook is required")

        with open(PLAYBOOK, encoding="utf-8") as source:
            tasks = yaml.safe_load(source)
        normalize = next(task for task in tasks if task.get("name") ==
                         "Нормализовать ожидаемые адреса DNS для выбранного источника конечной точки")
        playbook = [{
            "name": "Exercise common endpoint probe address projection",
            "hosts": "localhost",
            "connection": "local",
            "gather_facts": False,
            "vars": {
                "_platform_integration_source_id": "qa-vault",
                "_platform_integration_source_fqdns": ["qa-vault.example.internal"],
                "platform_bind_source_dns_records": [{
                    "owner": "qa-vault.example.internal.",
                    "addresses": ["192.0.2.10"],
                }],
            },
            "tasks": [normalize, {
                "name": "Require the service DNS address in the shared probe contract",
                "ansible.builtin.assert": {"that": [
                    "platform_endpoint_probe_expected_addresses == ['192.0.2.10']",
                ]},
            }],
        }]
        with tempfile.TemporaryDirectory(prefix="platform-probe-addresses-") as temporary:
            path = os.path.join(temporary, "test.yml")
            with open(path, "w", encoding="utf-8") as output:
                yaml.safe_dump(playbook, output, sort_keys=False)
            result = subprocess.run([ansible_playbook, "-i", "localhost,", path],
                                    capture_output=True, text=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_haproxy_hook_receives_explicit_standalone_source_id(self):
        ansible_playbook = shutil.which("ansible-playbook")
        if not ansible_playbook:
            self.skipTest("ansible-playbook is required")

        with open(PLAYBOOK, encoding="utf-8") as source:
            source_plays = yaml.safe_load(source)
        initialize = next(task for task in source_plays
                          if task.get("name") == "Инициализация пустой проекции интеграции конечной точки")
        with open(HAPROXY_PLAYBOOK, encoding="utf-8") as source:
            haproxy_plays = yaml.safe_load(source)
        source_ids = [play["roles"][0]["platform_haproxy_partial_deployment_id"]
                      for play in haproxy_plays]

        playbook = [
            {
                "hosts": "localhost", "connection": "local", "gather_facts": False,
                "vars": {"platform_integration_source_deployment_id": "qa-vault-consumer"},
                "tasks": [initialize],
            },
            {
                "hosts": "localhost", "connection": "local", "gather_facts": False,
                "vars": {"selected_source_ids": source_ids},
                "tasks": [{
                    "ansible.builtin.assert": {"that": [
                        "selected_source_ids | length == 3",
                        "selected_source_ids | unique | list == ['qa-vault-consumer']",
                    ]},
                }],
            },
        ]
        with tempfile.TemporaryDirectory(prefix="platform-haproxy-source-") as temporary:
            path = os.path.join(temporary, "test.yml")
            with open(path, "w", encoding="utf-8") as output:
                yaml.safe_dump(playbook, output, sort_keys=False)
            result = subprocess.run(
                [ansible_playbook, "-i", "localhost,", path],
                capture_output=True, text=True, timeout=30,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

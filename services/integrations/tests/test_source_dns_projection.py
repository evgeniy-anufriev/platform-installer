import os
import shutil
import subprocess
import tempfile
import unittest

import yaml


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
PLAYBOOK = os.path.join(ROOT, "services", "integrations", "playbooks", "apply-endpoint.yml")
HAPROXY_PLAYBOOK = os.path.join(ROOT, "services", "haproxy", "playbooks", "integrate.yml")


class SourceDnsProjectionTests(unittest.TestCase):
    def test_production_task_preserves_list_and_record_addresses(self):
        ansible_playbook = shutil.which("ansible-playbook")
        if not ansible_playbook:
            self.skipTest("ansible-playbook is required")

        with open(PLAYBOOK, encoding="utf-8") as source:
            plays = yaml.safe_load(source)
        tasks = plays[0]["tasks"]
        build_task = next(task for task in tasks if task.get("name") == "Build exact source DNS updates for resolved BIND deployments")
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

    def test_haproxy_hook_receives_explicit_standalone_source_id(self):
        ansible_playbook = shutil.which("ansible-playbook")
        if not ansible_playbook:
            self.skipTest("ansible-playbook is required")

        with open(PLAYBOOK, encoding="utf-8") as source:
            source_plays = yaml.safe_load(source)
        initialize = next(task for task in source_plays[0]["tasks"]
                          if task.get("name") == "Initialize an empty endpoint integration projection")
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

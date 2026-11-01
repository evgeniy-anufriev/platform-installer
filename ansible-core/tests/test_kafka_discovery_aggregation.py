import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest


ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
AGGREGATE = os.path.join(ROOT, "services", "kafka", "playbooks", "aggregate_discovery.yml")


@unittest.skipUnless(shutil.which("ansible-playbook"), "ansible-playbook is required")
class KafkaDiscoveryAggregationTests(unittest.TestCase):
    def test_three_host_discovery_is_one_complete_controller_snapshot(self):
        """Regression for delegated-fact loop loss: all hosts must survive."""
        self.run_aggregation()

    def test_limited_three_of_five_hosts_excludes_non_kafka_hosts(self):
        """Inventory groups retain excluded hosts even when --limit is used."""
        self.run_aggregation(limited=True)

    def test_missing_discovery_on_selected_host_is_not_silently_ignored(self):
        self.run_aggregation(limited=True, missing_discovery=True)

    def run_aggregation(self, limited=False, missing_discovery=False):
        with tempfile.TemporaryDirectory() as root:
            inventory = os.path.join(root, "hosts.yml")
            playbook = os.path.join(root, "aggregation.yml")
            with open(inventory, "w", encoding="utf-8") as handle:
                handle.write("""all:\n  children:\n    platform_targets:\n      hosts:\n        node1: {ansible_connection: local}\n        node2: {ansible_connection: local}\n        node3: {ansible_connection: local}\n""")
                if limited:
                    handle.write("        app1: {ansible_connection: local}\n        app2: {ansible_connection: local}\n")
            with open(playbook, "w", encoding="utf-8") as handle:
                handle.write(textwrap.dedent("""\
                    - hosts: platform_targets
                      gather_facts: false
                      tasks:
                        - ansible.builtin.set_fact:
                            platform_kafka_identity_discovery:
                              - memberId: "{{ inventory_hostname | regex_replace('node', 'kafka-') }}"
                          when: not (missing_discovery | default(false) | bool) or inventory_hostname != 'node3'
                    - hosts: platform_targets
                      gather_facts: false
                      tasks:
                        - ansible.builtin.include_tasks: %s
                    - hosts: localhost
                      gather_facts: false
                      tasks:
                        - ansible.builtin.assert:
                            that:
                              - platform_kafka_discovery_by_host.keys() | list | sort == ['node1', 'node2', 'node3']
                              - platform_kafka_discovery_by_host.values() | map('first') | map(attribute='memberId') | list | sort == ['kafka-1', 'kafka-2', 'kafka-3']
                """) % AGGREGATE.replace("\\", "/"))
            command = ["ansible-playbook", "-i", inventory, playbook]
            if limited:
                command.extend(["--limit", "localhost:node3:node1:node2"])
            if missing_discovery:
                command.extend(["-e", '{"missing_discovery": true}'])
            result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if missing_discovery:
                self.assertNotEqual(0, result.returncode, result.stdout)
                self.assertIn("platform_kafka_identity_discovery", result.stdout)
            else:
                self.assertEqual(0, result.returncode, result.stdout)


if __name__ == "__main__":
    unittest.main()

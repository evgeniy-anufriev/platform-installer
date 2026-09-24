import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest


ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
RUN_CLI = os.path.join(
    ROOT,
    "services",
    "kafka",
    "ansible_collections",
    "platform",
    "kafka",
    "roles",
    "kafka_kraft",
    "tasks",
    "run_cli_command.yml",
)


@unittest.skipUnless(shutil.which("ansible-playbook"), "ansible-playbook is required")
class KafkaCLIReadinessRetryTests(unittest.TestCase):
    def test_quorum_command_retries_until_all_expected_voters_are_visible(self):
        with tempfile.TemporaryDirectory() as root:
            inventory = os.path.join(root, "hosts.yml")
            command = os.path.join(root, "quorum.py")
            counter = os.path.join(root, "counter")
            playbook = os.path.join(root, "retry.yml")
            with open(inventory, "w", encoding="utf-8") as handle:
                handle.write("all:\n  hosts:\n    localhost: {ansible_connection: local}\n")
            with open(command, "w", encoding="utf-8") as handle:
                handle.write(textwrap.dedent("""\
                    #!/usr/bin/env python3
                    import os
                    path = os.environ["KAFKA_RETRY_COUNTER"]
                    attempt = int(open(path).read()) + 1 if os.path.exists(path) else 1
                    open(path, "w").write(str(attempt))
                    if attempt == 1:
                        print('LeaderId: -1')
                    else:
                        print('LeaderId: 2')
                        print('CurrentVoters: [{"id": 1,}, {"id": 2,}, {"id": 3,}]')
                """))
            os.chmod(command, 0o755)
            with open(playbook, "w", encoding="utf-8") as handle:
                handle.write(textwrap.dedent("""\
                    - hosts: localhost
                      gather_facts: false
                      vars:
                        kafka_cli_connection: {securityProtocol: PLAINTEXT}
                        kafka_cli_command_prefix: [%s]
                        kafka_cli_command_suffix: []
                        kafka_cli_expected_controller_ids: [1, 2, 3]
                        platform_kafka_startup_readiness_retries: 3
                        platform_kafka_startup_readiness_delay: 0
                      environment:
                        KAFKA_RETRY_COUNTER: %s
                      tasks:
                        - ansible.builtin.include_tasks: %s
                        - ansible.builtin.assert:
                            that:
                              - platform_kafka_cli_command_result.attempts == 2
                              - platform_kafka_cli_command_result.stdout is search('LeaderId: 2')
                """) % (command.replace("\\", "/"), counter.replace("\\", "/"), RUN_CLI.replace("\\", "/")))
            result = subprocess.run(
                ["ansible-playbook", "-i", inventory, playbook],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            self.assertEqual(0, result.returncode, result.stdout)


if __name__ == "__main__":
    unittest.main()

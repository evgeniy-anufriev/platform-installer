import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


TASKS = Path(__file__).resolve().parents[1] / "ansible_collections/platform/kafka/roles/kafka_kraft/tasks/normalize_member.yml"


class KafkaMemberNormalizationRuntimeTests(unittest.TestCase):
    def test_fresh_process_and_sequential_members(self):
        executable = shutil.which("ansible-playbook")
        if not executable:
            self.skipTest("Ansible runtime required")
        tasks = []
        scenarios = [("broker-1", ["broker"], {}),
                     ("controller-2", ["controller"], {"name": "old-controller", "runtime_directory": "/tmp/custom-runtime"}),
                     ("combined-3", ["broker", "controller"], {}),
                     ("broker-4", ["broker"], {"environment_pattern": "/tmp/custom.env"})]
        for member_id, roles, compatibility in scenarios:
            member = {"id": member_id, "node_id": int(member_id[-1]), "roles": roles,
                      "advertised_host": "node.test", "data_directory": "/tmp/data/" + member_id,
                      "log_directory": "/tmp/log/" + member_id, "_compatibility_unit": compatibility,
                      "listeners": {"CLIENT": {"purpose": "client", "securityProtocol": "SSL", "port": 9093},
                                    "CONTROLLER": {"purpose": "controller", "securityProtocol": "SSL", "port": 9094}}}
            runtime = compatibility.get("runtime_directory", "/tmp/config/kafka-" + member_id)
            service = "platform-kafka" if len(roles) == 2 else "platform-kafka-" + roles[0]
            tasks.extend([
                {"ansible.builtin.set_fact": {"kafka_input_member": member}},
                {"ansible.builtin.include_tasks": str(TASKS)},
                {"ansible.builtin.assert": {"that": [
                    "_platform_kafka_normalized_member.runtime_directory == expected_runtime",
                    "_platform_kafka_normalized_member.systemd_environment_pattern == expected_env",
                    "_platform_kafka_normalized_member.systemd_unit_name == expected_unit",
                    "_platform_kafka_normalized_member.legacy_systemd_unit_name == expected_legacy",
                ]}, "vars": {"expected_runtime": runtime,
                    "expected_env": compatibility.get("environment_pattern", runtime + "/systemd.env"),
                    "expected_unit": service + "@qa-kafka-" + member_id[-1] + ".service",
                    "expected_legacy": compatibility.get("name", "kafka@kafka-" + member_id) + ".service"}},
            ])
        variables = yaml.safe_load((TASKS.parent.parent / "defaults/main.yml").read_text(encoding="utf-8"))
        variables.update({"platform_name_prefix": "platform",
                          "platform_kafka_config_directory": "/tmp/config", "platform_kafka_service_name": "kafka",
                          "platform_kafka_deployment_id": "qa-kafka", "platform_kafka_tls_profile": "tls",
                          "_platform_kafka_instances": []})
        play = [{"hosts": "localhost", "connection": "local", "gather_facts": False,
                 "vars": variables, "tasks": tasks}]
        with tempfile.TemporaryDirectory(prefix="platform-kafka-normalize-") as directory:
            path = Path(directory) / "test.yml"
            path.write_text(yaml.safe_dump(play), encoding="utf-8")
            result = subprocess.run([executable, "-i", "localhost,", str(path)],
                                    capture_output=True, text=True, timeout=60)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

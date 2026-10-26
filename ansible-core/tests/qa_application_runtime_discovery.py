"""Read-only native rootless discovery QA; run on the RED OS Execution Node."""
import copy
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


REPO = Path(__file__).resolve().parents[2]
TASKS = REPO / "ansible-core/collections/ansible_collections/platform/core/roles/application_runtime/tasks"
ACCOUNT = "platform-docker"
HOSTS = ("discovery_target_a", "discovery_target_b")
ROUTING_NAMES = (
    "Привязка учётной записи операции приложения и ключа обнаружения конфигурации Docker",
    "Однократная проверка выбранных учётных записей и Docker без прав root",
)
DISCOVERY_NAME = "Обнаружение выбранной учетной записи Docker"


class ApplicationRuntimeDiscoveryQA(unittest.TestCase):
    def protected_failure(self, output, message):
        # Preserve failure evidence privately without exposing native task output.
        with tempfile.NamedTemporaryFile(prefix="a2-discovery-failure-", suffix=".log", delete=False) as stream:
            os.chmod(stream.name, 0o600)
            stream.write(output)
            path = stream.name
        self.fail("%s; private evidence: %s" % (message, path))

    def test_configuration_keys_are_cached_per_target_and_per_invocation(self):
        routing = yaml.safe_load((TASKS / "preflight.yml").read_text())[:2]
        self.assertEqual(list(ROUTING_NAMES), [task.get("name") for task in routing])
        self.assertEqual("discover_runtime.yml", routing[1].get("ansible.builtin.include_tasks"))
        with tempfile.TemporaryDirectory(prefix="a2-discovery-qa-") as directory:
            root = Path(directory)
            # Resolve the unchanged production relative include to the actual role file.
            (root / "discover_runtime.yml").symlink_to(TASKS / "discover_runtime.yml")
            # Sibling nonexistent paths remain traversable by the Docker account;
            # the generated play and captured controller data stay private.
            config_a, config_b = str(root) + "-absent-config-a", str(root) + "-absent-config-b"
            expected_key_a = "([application_runtime_job.account, discovery_config_a] | to_json)"
            expected_key_b = "([application_runtime_job.account, discovery_config_b] | to_json)"
            routed = copy.deepcopy(routing) + [{
                "name": "Require exactly the successful discovery keys so far",
                "ansible.builtin.assert": {"that": [
                    "application_runtime_discoveries | length == discovery_step.count",
                    expected_key_a + " in application_runtime_discoveries",
                    "discovery_step.count == 1 or " + expected_key_b + " in application_runtime_discoveries",
                ]},
                "no_log": True,
            }]
            (root / "routing.yml").write_text(yaml.safe_dump(routed, sort_keys=False))
            inventory = {"all": {"hosts": {host: {"ansible_connection": "local"} for host in HOSTS}}}
            (root / "inventory.yml").write_text(yaml.safe_dump(inventory, sort_keys=False))
            play = [{
                "name": "Read-only production runtime discovery cache QA",
                "hosts": "all", "gather_facts": False, "become": True,
                "become_method": "sudo", "become_flags": "-n",
                "vars": {
                    "application_runtime_job": {"account": ACCOUNT},
                    "application_runtime_discoveries": {},
                    "discovery_config_a": config_a, "discovery_config_b": config_b,
                },
                "tasks": [
                    {"name": "Require a fresh discovery cache", "ansible.builtin.assert": {
                        "that": "application_runtime_discoveries | length == 0"}, "no_log": True},
                    {"name": "Exercise A B A through production routing tasks",
                     "ansible.builtin.include_tasks": "routing.yml",
                     "loop": [{"config": config_a, "count": 1},
                              {"config": config_b, "count": 2},
                              {"config": config_a, "count": 2}],
                     "loop_control": {"loop_var": "discovery_step", "label": "{{ discovery_step.count }}"},
                     "vars": {"platform_application_registry_config_directory": "{{ discovery_step.config }}"}},
                    {"name": "Require independent complete target caches",
                     "ansible.builtin.assert": {"that": [
                         "application_runtime_discoveries | length == 2",
                         expected_key_a + " in application_runtime_discoveries",
                         expected_key_b + " in application_runtime_discoveries",
                     ]}, "no_log": True},
                ],
            }]
            (root / "play.yml").write_text(yaml.safe_dump(play, sort_keys=False))
            env = dict(os.environ, ANSIBLE_CONFIG=str(REPO / "ansible-core/ansible.cfg"),
                       ANSIBLE_STDOUT_CALLBACK="default", ANSIBLE_NOCOLOR="1",
                       ANSIBLE_CALLBACKS_ENABLED="", ANSIBLE_LOG_PATH="",
                       ANSIBLE_CACHE_PLUGIN="memory")
            for invocation in range(2):
                try:
                    result = subprocess.run(
                        ["ansible-playbook", "-i", str(root / "inventory.yml"), str(root / "play.yml")],
                        cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
                except subprocess.TimeoutExpired as error:
                    self.protected_failure(error.stdout or b"", "Discovery QA timed out")
                if result.returncode:
                    self.protected_failure(result.stdout, "Discovery QA invocation %s failed" % (invocation + 1))
                output = result.stdout.decode("utf-8", errors="replace")
                blocks = re.split(r"(?m)^TASK \[", output)
                discoveries = [block for block in blocks if block.startswith(DISCOVERY_NAME + "]")]
                counts = {host: sum(len(re.findall(r"(?m)^ok: \[" + re.escape(host) + r"\]", block))
                                    for block in discoveries) for host in HOSTS}
                if counts != dict.fromkeys(HOSTS, 2):
                    self.protected_failure(result.stdout, "Expected exactly two discoveries per logical target")
                if any(not re.search(re.escape(host) + r"\s+:.*\bchanged=0\b.*\bfailed=0\b", output) for host in HOSTS):
                    self.protected_failure(result.stdout, "Read-only discovery recap did not pass")
                self.assertFalse(Path(config_a).exists())
                self.assertFalse(Path(config_b).exists())


if __name__ == "__main__":
    unittest.main()

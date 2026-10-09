"""Production task regressions in disposable local Ansible fixtures."""
import copy
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
ROLES = {"bind": "bind", "keepalived": "keepalived", "vault": "vault_tls",
         "kafka": "kafka_kraft", "clickhouse": "clickhouse_tls", "docker": "docker_rootless",
         "postgresql": "postgresql", "redis": "redis_tls"}


@unittest.skipUnless(shutil.which("ansible-playbook"), "Ansible runtime required")
class ServiceRuntimeOptimizationTests(unittest.TestCase):
    def run_play(self, tasks, variables, expected=0):
        with tempfile.TemporaryDirectory(prefix="service-optimization-") as directory:
            path = Path(directory) / "play.yml"
            path.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local",
                "gather_facts": False, "vars": variables, "tasks": tasks}]), encoding="utf-8")
            environment = dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(ROOT / "ansible-core/collections"))
            result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(path)],
                capture_output=True, text=True, timeout=90, env=environment)
            self.assertEqual(expected, result.returncode, result.stdout + result.stderr)
            return result.stdout

    def source(self, service, file):
        path = ROOT / f"services/{service}/ansible_collections/platform/{service}/roles/{ROLES[service]}/tasks/{file}"
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def test_verify_skips_source_resolution_but_apply_rejects_missing_authority(self):
        for service in ROLES:
            source = self.source(service, "main.yml")
            if service == "vault":
                source = next(task["block"] for task in source if "block" in task)
            gates = [task for task in source if task.get("ansible.builtin.include_role", {}).get("name")
                     == "platform.core.artifact_source_gate"]
            variables = {f"platform_{service}_verify_only": True,
                "platform_bind_phase": "verify", "platform_keepalived_lifecycle_phase": "prepare",
                "platform_postgresql_mode": "pg_auto_failover", "platform_artifact_source_authority_active": True,
                "platform_resolved_artifact_sources": {}}
            with self.subTest(service=service, phase="verify"):
                output = self.run_play(gates, variables)
                self.assertNotIn("Require a resolved source for every service artifact requirement", output)
            variables.update({f"platform_{service}_verify_only": False, "platform_bind_phase": "prepare"})
            with self.subTest(service=service, phase="apply"):
                self.run_play(gates, variables, expected=2)
            if service in ("bind", "keepalived"):
                variables.update({"platform_bind_phase": "activate", "platform_keepalived_lifecycle_phase": "activate"})
                with self.subTest(service=service, phase="activate"):
                    self.run_play(gates, variables)

    def test_kafka_combined_state_keeps_active_and_pid_guards(self):
        source = self.source("kafka", "verify_member.yml")
        checks = [task for task in source if task.get("name") in
                  ("Assert Kafka member service is active", "Verify Kafka member process")]
        for state, pid, expected in [("active", 123, 0), ("inactive", 123, 2), ("active", 0, 2)]:
            with self.subTest(state=state, pid=pid):
                lines = ["MainPID=" + str(pid), "ActiveState=" + state]
                self.run_play(checks, {"platform_kafka_member_service_state":
                    {"stdout": "\n".join(lines), "stdout_lines": lines}}, expected)

    def test_combined_commands_use_real_systemd_and_rpm_read_only(self):
        query = copy.deepcopy(self.source("clickhouse", "preflight.yml")[1])
        query["ansible.builtin.command"]["argv"][-4:] = ["bash"]
        state = copy.deepcopy(self.source("kafka", "verify_member.yml")[0])
        self.run_play([query, state, {"ansible.builtin.assert": {"that": [
            "_platform_clickhouse_installed_packages.stdout is search('(?m)^bash\\t')",
            "platform_kafka_member_service_state.stdout is search('(?m)^ActiveState=')",
            "platform_kafka_member_service_state.stdout is search('(?m)^MainPID=[0-9]+$')",
        ]}}], {"kafka_member": {"systemd_unit_name": "dbus.service"}})

    def test_clickhouse_batched_rpm_keeps_each_package_and_keeper_guards(self):
        source = self.source("clickhouse", "preflight.yml")
        guard = next(task for task in source if task.get("name") == "Refuse an incompatible foreign ClickHouse package generation")
        version = "25.8.1"
        packages = ["clickhouse-common-static", "clickhouse-server", "clickhouse-client"]
        valid = [name + "\t" + version + "-1.x86_64" for name in packages]
        for lines, expected in [([], 0), (valid, 0), (valid + ["clickhouse-keeper\t1-1.x86_64"], 2),
                                (["clickhouse-server\tforeign-1.x86_64"], 2), (valid + [valid[0]], 2)]:
            with self.subTest(lines=lines):
                self.run_play([guard], {"platform_clickhouse_package_version": version,
                    "_platform_clickhouse_installed_packages": {"stdout_lines": lines}}, expected)

    def test_bind_mixed_repository_and_bundle_selection(self):
        task = self.source("bind", "prepare.yml")[0]
        for first, second, expected in [("REPOSITORY", "REPOSITORY", ["bind", "bind-utils"]),
                                       ("REPOSITORY", "OFFLINE_BUNDLE", ["bind"]),
                                       ("OFFLINE_BUNDLE", "REPOSITORY", ["bind-utils"]),
                                       ("OFFLINE_BUNDLE", "OFFLINE_BUNDLE", [])]:
            variables = {"platform_bind_package": "bind", "platform_bind_utils_package": "bind-utils",
                "platform_resolved_artifact_sources": {"bind": {"source": first}, "bind-utils": {"source": second}}}
            assertion = {"ansible.builtin.assert": {"that": "_platform_bind_repository_packages == expected"},
                         "vars": dict(task["vars"], expected=expected)}
            self.run_play([assertion], variables)


if __name__ == "__main__":
    unittest.main()

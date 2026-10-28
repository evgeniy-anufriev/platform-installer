import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
SERVICE = ROOT / "services" / "kafka"
ROLE = SERVICE / "ansible_collections" / "platform" / "kafka" / "roles" / "kafka_kraft"
FIXTURE = ROOT / "examples" / "valid" / "kafka-split-multihost"


class Service01DContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (FIXTURE / "inventory" / "group_vars" / "all" / "platform.yml").open(encoding="utf-8") as stream:
            cls.variables = yaml.safe_load(stream)
        with (FIXTURE / "inventory" / "group_vars" / "all" / "platform-state.yml").open(encoding="utf-8") as stream:
            cls.generated_variables = yaml.safe_load(stream)

    def test_fixture_has_three_split_members_on_three_hosts(self):
        placement = yaml.safe_load((FIXTURE / "inventory" / "hosts.yml").read_text(encoding="utf-8"))["all"]["hosts"]
        members = [
            dict(member, id=member_id, host=host)
            for host, host_vars in placement.items()
            for member_id, member in host_vars.get("platform_deployments", {}).get("kafka-main", {}).get("members", {}).items()
        ]
        controllers = [member for member in members if member["roles"] == ["controller"]]
        brokers = [member for member in members if member["roles"] == ["broker"]]
        self.assertEqual(6, len(members))
        self.assertEqual(3, len(controllers))
        self.assertEqual(3, len(brokers))
        self.assertEqual({"node1", "node2", "node3"}, {
            host for host in placement
            if placement[host].get("platform_deployments", {}).get("kafka-main", {}).get("members")
        })
        self.assertEqual({1, 2, 3, 4, 5, 6}, {member["configuration"]["nodeId"] for member in members})
        self.assertTrue(all(not {"clientPort", "controllerPort"}.intersection(member.get("configuration", {})) for member in members))
        generated = self.generated_variables["platform_generated_state"]["serviceDeployments"]["kafka-main"]["members"]
        self.assertNotIn("platform_generated_state", self.variables)
        self.assertTrue(all("directoryId" in generated[member["id"]]["identity"] for member in controllers))
        self.assertTrue(all("identity" not in member for member in members))

    def test_fixture_places_one_controller_and_broker_on_each_host(self):
        placement = yaml.safe_load((FIXTURE / "inventory" / "hosts.yml").read_text(encoding="utf-8"))["all"]["hosts"]
        for host in ("node1", "node2", "node3"):
            local = list(placement[host]["platform_deployments"]["kafka-main"]["members"].values())
            self.assertEqual([["broker"], ["controller"]], sorted(member["roles"] for member in local))
            self.assertEqual(2, len(local))

    def test_role_projects_quorum_from_only_controllers_and_formats_brokers_outside_it(self):
        main = (ROLE / "tasks" / "apply.yml").read_text(encoding="utf-8")
        member = (ROLE / "tasks" / "member.yml").read_text(encoding="utf-8")
        self.assertIn("for member in _platform_kafka_controller_instances", main)
        self.assertIn("controller_endpoint.bootstrap_host", main)
        self.assertIn("controller_endpoint.bootstrap_port", main)
        self.assertIn("Форматирование неинициализированного хранилища Kafka ровно один раз", member)
        self.assertIn("NO_INITIAL_CONTROLLERS", member)
        self.assertIn("--no-initial-controllers", member)
        self.assertIn("Проверка действующей конфигурации Kafka для выбранной роли", member)

    def test_verify_requires_controller_membership_and_broker_registration(self):
        verify = (ROLE / "tasks" / "verify.yml").read_text(encoding="utf-8")
        self.assertIn("verify_quorum.yml", verify)
        quorum = (ROLE / "tasks" / "verify_quorum.yml").read_text(encoding="utf-8")
        ssl_verify = (ROLE / "tasks" / "verify_ssl_listener.yml").read_text(encoding="utf-8")
        self.assertIn("Подтверждение лидера кворума и членства контроллера Kafka", quorum)
        self.assertIn("LeaderId", quorum)
        self.assertIn("kafka-broker-api-versions{{ platform_kafka_script_extension }}", verify)
        self.assertIn("Выбор диагностических заголовков брокера без внесения изменений", verify)
        self.assertIn("Подтверждение регистрации брокеров Kafka и состояния unfenced", verify)
        self.assertIn("*[!0-9.]*)", ssl_verify)
        self.assertIn('"$verification_option" "$verification_host"', ssl_verify)
        self.assertIn("-cert {{ _platform_kafka_tls_runtime.targetDirectory }}/certificate.pem", ssl_verify)
        self.assertIn("-key {{ _platform_kafka_tls_runtime.targetDirectory }}/private-key.pem", ssl_verify)
        self.assertIn("until: platform_kafka_ssl_handshake.rc == 0", ssl_verify)

    def test_verify_reconstructs_the_derived_pki_plan(self):
        playbook = (SERVICE / "playbooks" / "verify.yml").read_text(encoding="utf-8")
        self.assertIn("../../../ansible-core/playbooks/pki-resolve.yml", playbook)

    def test_apply_restarts_members_when_target_pki_material_changes(self):
        member = (ROLE / "tasks" / "member.yml").read_text(encoding="utf-8")
        self.assertIn("platform_pki_material_changed | default(false) | bool", member)
        self.assertIn("platform_kafka_member_pki_changed | default(false) | bool", member)
        listener = (ROLE / "tasks" / "prepare_member_tls.yml").read_text(encoding="utf-8")
        self.assertIn("_platform_kafka_copied_pki_material.changed", listener)

    def test_kafka_tls_requires_server_and_client_auth_certificate_usage(self):
        runtime = (ROLE / "tasks" / "resolve_tls_runtime.yml").read_text(encoding="utf-8")
        self.assertIn("'serverAuth' in _platform_kafka_tls_runtime_requests[0].usages", runtime)
        self.assertIn("'clientAuth' in _platform_kafka_tls_runtime_requests[0].usages", runtime)
        real_fixture = yaml.safe_load(
            (ROOT / "examples" / "valid" / "kafka-real-multihost" / "inventory" / "group_vars" / "all" / "platform.yml").read_text(encoding="utf-8")
        )
        self.assertEqual(
            ["serverAuth", "clientAuth"],
            real_fixture["platform_desired_state"]["certificateProfiles"]["infrastructure"]["usages"],
        )
        self.assertEqual(
            "DEPLOYMENT",
            real_fixture["platform_desired_state"]["tlsProfiles"]["infrastructure-tls"]["scope"],
        )

    def test_acceptance_runner_persists_recoverable_lifecycle_state(self):
        runner = (SERVICE / "tests" / "run_service_01d_acceptance.sh").read_text(encoding="utf-8")
        for token in ("status.json", "pid", "STALE", "write_status PASS", "write_status FAILED"):
            self.assertIn(token, runner)
        self.assertIn("runner process is no longer alive", runner)

    def test_acceptance_runner_rejects_a_live_duplicate(self):
        runner = (SERVICE / "tests" / "run_service_01d_acceptance.sh").read_text(encoding="utf-8")
        self.assertIn("runner is already active", runner)
        self.assertIn("os.kill(pid, 0)", runner)


if __name__ == "__main__":
    unittest.main()

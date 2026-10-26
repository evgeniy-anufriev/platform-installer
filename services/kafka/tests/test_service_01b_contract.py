import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
SERVICE = ROOT / "services" / "kafka"
ROLE = SERVICE / "ansible_collections" / "platform" / "kafka" / "roles" / "kafka_kraft"


class Service01BContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (SERVICE / "service.yml").open(encoding="utf-8") as stream:
            cls.manifest = yaml.safe_load(stream)
        with (SERVICE / "configuration.schema.json").open(encoding="utf-8") as stream:
            cls.schema = json.load(stream)

    def test_distributed_mode_allows_members_on_one_physical_host(self):
        placement = self.manifest["modes"]["kraft-distributed"]["placement"]
        self.assertEqual(3, placement["minMembers"])
        self.assertFalse(placement["distinctHosts"])
        self.assertEqual(3, placement["roleCardinality"]["controller"]["minimum"])

    def test_member_node_id_is_a_member_scoped_managed_setting(self):
        setting = self.manifest["configuration"]["settings"]["nodeId"]
        self.assertEqual(["member"], setting["scopes"])
        self.assertEqual("platform_kafka_node_id", setting["roleVariable"])
        self.assertEqual("integer", self.schema["properties"]["nodeId"]["type"])

    def test_role_has_one_generic_member_execution_path_and_legacy_adapter(self):
        source = (ROLE / "tasks" / "main.yml").read_text(encoding="utf-8")
        self.assertIn("Преобразование устаревших переменных одного экземпляра сервиса", source)
        self.assertIn("Нормализация экземпляров службы Kafka в общую внутреннюю модель", source)
        self.assertIn("include_tasks: member.yml", source)
        self.assertIn("Упорядочивание нормализованных экземпляров Kafka", source)
        self.assertNotIn("SERVICE-01", source)
        self.assertNotIn("_platform_kafka_legacy_single", source)
        self.assertNotIn("exactly one local Kafka member", source)

    def test_manual_member_input_does_not_require_project_state(self):
        with (ROLE / "tasks" / "main.yml").open(encoding="utf-8") as stream:
            tasks = yaml.safe_load(stream)
        projection = next(task for task in tasks if task["name"] == "Получение экземпляров Kafka из проекта, если список не задан явно")
        self.assertIn("platform_kafka_instances | length == 0", projection["when"])
        explicit = next(task for task in tasks if task["name"] == "Выбор явного ввода экземпляра службы Kafka")
        self.assertEqual("platform_kafka_instances | length > 0", explicit["when"])
        self.assertNotIn("platform_project", explicit["when"])

    def test_managed_projection_leaves_absent_settings_to_ansible_defaults(self):
        with (ROLE / "tasks" / "project_runtime.yml").open(encoding="utf-8") as stream:
            tasks = yaml.safe_load(stream)
        by_name = {task["name"]: task for task in tasks}
        self.assertNotIn("platform_kafka_quorum_mode", by_name["Определение идентификатора Kafka для выбранного развёртывания"]["ansible.builtin.set_fact"])
        task = by_name["Определение явных параметров Kafka для выбранного развёртывания"]
        self.assertIn("'quorumMode' in", task["when"])
        self.assertIn("platform_kafka_quorum_mode", task["ansible.builtin.set_fact"])

    def test_role_blocks_identity_port_and_storage_collisions(self):
        source = (ROLE / "tasks" / "main.yml").read_text(encoding="utf-8")
        self.assertIn("Отклонение повторяющихся идентификаторов узла Kafka", source)
        self.assertIn("validate_host_resources.yml", source)
        resources = (ROLE / "tasks" / "validate_host_resources.yml").read_text(encoding="utf-8")
        self.assertIn("listener_ports", resources)
        self.assertIn("managed_paths", resources)

    def test_systemd_unit_uses_deployment_and_numeric_member_identity(self):
        source = (ROLE / "tasks" / "normalize_member.yml").read_text(encoding="utf-8")
        self.assertIn("_platform_kafka_normalized_unit_service }}@{{ _platform_kafka_normalized_deployment_id }}-{{ _platform_kafka_normalized_member_number }}.service", source)
        self.assertIn("_platform_kafka_normalized_runtime_directory ~ '/systemd.env'", source)
        self.assertIn("legacy_systemd_unit_name", source)
        main = (ROLE / "tasks" / "main.yml").read_text(encoding="utf-8")
        self.assertIn("KAFKA_LEGACY_UNIT_REQUIRES_S11_CLEANUP", main)
        self.assertIn("KAFKA_UNIT_NAME_COLLISION", main)
        self.assertIn("KAFKA_UNIT_OWNERSHIP_UNKNOWN", main)
        self.assertLess(main.index("Проверка общих входных данных экземпляра службы Kafka"), main.index("Доставка выбранных автономных артефактов Kafka"))
        self.assertLess(main.index("Отклонение конфликтов имен служб systemd Kafka на одном и том же хосте"), main.index("Доставка выбранных автономных артефактов Kafka"))
        self.assertIn("# {{ platform_kafka_name }}-managed: {{ kafka_member.systemd_unit_name }}",
                      (ROLE / "templates/kafka.service.j2").read_text(encoding="utf-8"))
        self.assertIn("'systemd_unit_ownership_marker': '# ' ~ platform_kafka_name ~ '-managed: '", source)

    def test_member_role_uses_controller_count_and_member_role_for_format_strategy(self):
        source = (ROLE / "tasks" / "member.yml").read_text(encoding="utf-8")
        self.assertIn("controller.quorum.voters", source)
        self.assertIn("Определение стратегии формата хранения Kafka", source)
        self.assertIn("Форматирование неинициализированного хранилища Kafka ровно один раз", source)
        self.assertIn("INITIAL_CONTROLLERS", source)
        self.assertIn("NO_INITIAL_CONTROLLERS", source)
        self.assertIn("STANDALONE_COMPATIBILITY", source)
        self.assertIn("--initial-controllers", source)
        self.assertIn("--no-initial-controllers", source)
        self.assertIn("--standalone", source)
        self.assertIn("kafka_member.directory_id is defined", source)
        self.assertEqual(1, source.count("kafka-storage.sh"))

    def test_quorum_and_effective_config_are_role_aware(self):
        main = (ROLE / "tasks" / "main.yml").read_text(encoding="utf-8")
        member = (ROLE / "tasks" / "member.yml").read_text(encoding="utf-8")
        verify = (ROLE / "tasks" / "verify.yml").read_text(encoding="utf-8")
        self.assertIn("_platform_kafka_controller_instances", main)
        self.assertIn("_platform_kafka_broker_instances", main)
        self.assertIn("_platform_kafka_local_controller_instances", main)
        self.assertIn("_platform_kafka_local_broker_instances", main)
        self.assertIn("for member in _platform_kafka_controller_instances", main)
        self.assertIn("'process.roles': kafka_member.roles | join(',')", member)
        self.assertNotIn("'process.roles': 'broker,controller'", member)
        self.assertIn("Добавление динамической проекции кворума при явном выборе", member)
        self.assertIn("Добавление статической проекции кворума при явном выборе", member)
        self.assertIn("verify_quorum.yml", verify)
        quorum = (ROLE / "tasks" / "verify_quorum.yml").read_text(encoding="utf-8")
        self.assertIn("--bootstrap-controller", quorum)

    def test_kafka_cli_diagnostics_consume_runtime_projection(self):
        verify = (ROLE / "tasks" / "verify.yml").read_text(encoding="utf-8")
        resolve = (ROLE / "tasks" / "resolve_cli_connection.yml").read_text(encoding="utf-8")
        runtime = (ROLE / "tasks" / "resolve_tls_runtime.yml").read_text(encoding="utf-8")
        runner = (ROLE / "tasks" / "run_cli_command.yml").read_text(encoding="utf-8")
        self.assertIn("resolve_cli_connection.yml", verify)
        self.assertIn("run_cli_command.yml", verify)
        self.assertNotIn("server.properties", verify)
        self.assertNotIn("sed -n", verify)
        self.assertNotIn("security.protocol=SSL", verify)
        self.assertNotIn("ssl.endpoint.identification.algorithm=", verify)
        self.assertIn("kafka_cli_purpose", resolve)
        self.assertNotIn("CONTROLLER", resolve)
        self.assertIn("bootstrapHost", resolve)
        self.assertIn("bootstrapPort", resolve)
        self.assertIn("storePasswordSecretRef", runtime)
        self.assertNotIn("ssl.truststore.password", resolve + runtime)
        self.assertIn("security.protocol={{ kafka_cli_connection.securityProtocol }}", runner)
        self.assertIn("truststorePath", runner)
        self.assertIn("truststoreType", runner)
        self.assertIn("Удаление временной конфигурации Kafka CLI", runner)

    def test_listener_endpoint_projection_is_name_independent(self):
        normalize = (ROLE / "tasks" / "normalize_member.yml").read_text(encoding="utf-8")
        self.assertIn("listener_endpoints", normalize)
        self.assertIn("listener.purpose == 'controller'", normalize)
        self.assertIn("listener.advertisedAddress", normalize)
        self.assertNotIn("CONTROLLER", normalize)
        self.assertNotIn("9093", normalize)

    def test_schema_registry_findings_are_serialized_for_ansible_assert_message(self):
        with (ROLE / "tasks" / "schema_registry_validate.yml").open(encoding="utf-8") as stream:
            tasks = yaml.safe_load(stream)
        validation = next(task for task in tasks if task["name"] == "Отклонение неверной топологии и портов Schema Registry до изменений")
        self.assertEqual(
            "{{ _platform_kafka_registry_projection.findings | to_nice_yaml }}",
            validation["ansible.builtin.assert"]["fail_msg"],
        )

    def test_tls_handshake_keeps_hostname_verification_enabled(self):
        handshake = (ROLE / "tasks" / "verify_ssl_listener.yml").read_text(encoding="utf-8")
        self.assertIn("-verify_hostname", handshake)
        self.assertIn("-verify_ip", handshake)
        self.assertNotIn("endpoint.identification.algorithm=", handshake)

    def test_registry_source_preflight_is_apply_only(self):
        with (ROLE / "tasks" / "schema_registry_validate.yml").open(encoding="utf-8") as stream:
            tasks = yaml.safe_load(stream)
        preflight = next(task for task in tasks if task["name"] == "Предварительная проверка источника Schema Registry перед изменением Kafka")
        self.assertIn("not (platform_kafka_verify_only | bool)", preflight["when"])
        self.assertIn("platform_kafka_schema_registry_enabled", preflight["when"])
        self.assertEqual("platform.core.artifact_source_gate", preflight["ansible.builtin.include_role"]["name"])

    def test_dynamic_and_static_config_projections_are_mutually_exclusive(self):
        with (ROLE / "tasks" / "member.yml").open(encoding="utf-8") as stream:
            tasks = {task["name"]: task for task in yaml.safe_load(stream)}
        common = tasks["Создание действующей конфигурации экземпляра службы"]["ansible.builtin.set_fact"]["kafka_effective_config"]
        dynamic = tasks["Добавление запрошенной проекции динамического кворума"]["ansible.builtin.set_fact"]["kafka_effective_config"]
        static = tasks["Добавление статической проекции кворума при явном выборе"]["ansible.builtin.set_fact"]["kafka_effective_config"]
        self.assertNotIn("controller.quorum.bootstrap.servers", common)
        self.assertNotIn("controller.quorum.voters", common)
        self.assertIn("controller.quorum.bootstrap.servers", dynamic)
        self.assertNotIn("controller.quorum.voters", dynamic)
        self.assertIn("controller.quorum.voters", static)
        self.assertNotIn("combine({'controller.quorum.bootstrap.servers'", static)

    def test_split_role_static_fixture_uses_named_role_specific_listeners(self):
        fixture_path = SERVICE / "tests" / "fixtures" / "split-role-static.yml"
        with fixture_path.open(encoding="utf-8") as stream:
            fixture = yaml.safe_load(stream)
        members = fixture["platform_kafka_instances"]
        controllers = [member for member in members if "controller" in member["roles"]]
        brokers = [member for member in members if "broker" in member["roles"]]
        self.assertEqual("static", fixture["platform_kafka_quorum_mode"])
        self.assertEqual(3, len(controllers))
        self.assertEqual(1, len(brokers))
        self.assertTrue(all(set(member["listeners"]) == {"CONTROLLER"} for member in controllers))
        self.assertTrue(all(set(member["listeners"]) == {"PLAINTEXT", "SSL"} for member in brokers))

    def test_member_identity_is_not_an_inventory_host(self):
        source = (ROLE / "tasks" / "main.yml").read_text(encoding="utf-8")
        self.assertIn("platform_kafka_instances", source)
        self.assertIn("include_tasks: member.yml", source)
        self.assertNotIn("add_host", source)

    def test_optional_clean_install_is_guarded_and_reuses_common_lifecycle(self):
        defaults = (ROLE / "defaults" / "main.yml").read_text(encoding="utf-8")
        main = (ROLE / "tasks" / "main.yml").read_text(encoding="utf-8")
        clear = (ROLE / "tasks" / "clear.yml").read_text(encoding="utf-8")
        member = (ROLE / "tasks" / "member.yml").read_text(encoding="utf-8")
        self.assertIn("platform_kafka_clean_install: false", defaults)
        self.assertIn("platform_kafka_confirm_destructive_reset: ''", defaults)
        self.assertIn("include_tasks: clear.yml", main)
        self.assertIn("platform_kafka_clean_install | bool", main)
        self.assertNotIn("platform_kafka_confirm_destructive_reset", main)
        self.assertIn("Проверка точного подтверждения очистки Kafka перед новой установкой", clear)
        self.assertIn("platform_kafka_confirm_destructive_reset", clear)
        self.assertLess(
            main.index("Очистка выбранного развёртывания Kafka явно по запросу"),
            main.index("Однократная подготовка узла Kafka"),
        )
        self.assertIn("Удаление только выбранного состояния экземпляра службы развертывания Kafka", clear)
        self.assertIn("systemctl, is-active", clear)
        self.assertIn("'/var/lib/kafka'", clear)
        self.assertIn("state: stopped", clear)
        self.assertIn("Обнаружение JVM Kafka, владеющих выбранными портами listeners", clear)
        self.assertIn("Остановка конфликтующих служб systemd Kafka перед очисткой", clear)
        self.assertIn("Завершение работы только JVM Kafka, оставшихся после ограниченной остановки", clear)
        self.assertEqual(clear.count("item.split('|')[2] in _platform_kafka_clear_owned_config_files"), 2)
        self.assertIn("Отклонение занятых портов Kafka listeners после ограниченной очистки", clear)
        self.assertIn("Удаление только unit-файлов Kafka выбранного развёртывания", clear)
        self.assertIn("daemon_reload: true", clear)
        self.assertIn("Очистка устаревшего состояния для выбранных системных служб Kafka", clear)
        self.assertIn("reject('equalto', '/etc/systemd/system/kafka@.service')", clear)
        self.assertNotIn("state: absent\n  loop: \"{{ [platform_kafka_install_directory]", clear)
        self.assertIn("Форматирование неинициализированного хранилища Kafka ровно один раз", member)
        self.assertNotIn("platform_kafka_operation", main + defaults + clear)

    def test_member_tasks_avoid_path_and_handler_duplication(self):
        member = (ROLE / "tasks" / "member.yml").read_text(encoding="utf-8")
        verify_member = (ROLE / "tasks" / "verify_member.yml").read_text(encoding="utf-8")
        handlers = ROLE / "handlers" / "main.yml"
        self.assertNotIn("Set member-derived Kafka paths", member)
        self.assertNotIn("_platform_kafka_member_config_file", member)
        self.assertNotIn("_platform_kafka_member_runtime_dir", member)
        self.assertNotIn("Set member verification paths", verify_member)
        self.assertNotIn("_platform_kafka_verify_service", verify_member)
        self.assertNotIn("notify: Reload systemd", member)
        self.assertFalse(handlers.exists())

    def test_host_reset_is_separate_guarded_qa_operation(self):
        reset = (SERVICE / "playbooks" / "reset_kafka_host.yml").read_text(encoding="utf-8")
        self.assertIn("RESET_ALL_KAFKA_RUNTIME_ON_TARGET_HOSTS", reset)
        self.assertIn("Проверка точного подтверждения удаления данных Kafka на узле", reset)
        self.assertIn("Поиск всех служб Kafka в systemd", reset)
        self.assertIn("Ожидание завершения JVM Kafka в пределах таймаута", reset)
        self.assertIn("Проверка того, что JVM Kafka отсутствуют перед удалением файлов среды выполнения", reset)
        self.assertIn("/opt/kafka_2.13-4.3.1", reset)
        self.assertIn("patterns:\n          - 'kafka*.service'", reset)
        self.assertIn("daemon_reload: true", reset)
        self.assertIn("Очистка устаревшего состояния обнаруженных системных служб Kafka", reset)
        self.assertNotIn("platform_kafka_host_reset_confirmation", (ROLE / "defaults" / "main.yml").read_text(encoding="utf-8"))

    def test_fresh_distribution_has_writable_runtime_log_directory(self):
        prepare = (ROLE / "tasks" / "prepare_host.yml").read_text(encoding="utf-8")
        self.assertIn("Подготовка каталога журналов дистрибутива Kafka с доступом для записи", prepare)
        self.assertIn('path: "/opt/{{ platform_kafka_archive_directory }}/logs"', prepare)
        self.assertIn('owner: "{{ platform_kafka_user }}"', prepare)
        self.assertIn("mode: '0750'", prepare)

    def test_apply_waits_for_all_role_aware_member_listeners(self):
        main = (ROLE / "tasks" / "main.yml").read_text(encoding="utf-8")
        member = (ROLE / "tasks" / "member.yml").read_text(encoding="utf-8")
        self.assertIn("Ожидание всех локальных портов Kafka listeners после запуска экземпляра", main)
        self.assertIn("subelements('listener_ports'", main)
        self.assertIn("state: started", main)
        self.assertNotIn("listener startup readiness", member)

    def test_single_controller_explicit_identity_uses_initial_controllers(self):
        member = (ROLE / "tasks" / "member.yml").read_text(encoding="utf-8")
        self.assertIn("kafka_member.directory_id is defined", member)
        self.assertIn("kafka_member.directory_id is not defined", member)
        self.assertIn("--initial-controllers", member)
        self.assertIn("--standalone", member)


if __name__ == "__main__":
    unittest.main()

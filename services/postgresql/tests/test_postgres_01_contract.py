from pathlib import Path
import unittest

import yaml


ROLE = (
    Path(__file__).resolve().parents[1]
    / "ansible_collections/platform/postgresql/roles/postgresql"
)


class PostgreSQLHaLifecycleContractTests(unittest.TestCase):
    def setUp(self):
        self.main = (ROLE / "tasks/main.yml").read_text(encoding="utf-8")
        self.resolve_packages = (ROLE / "tasks/resolve_packages.yml").read_text(encoding="utf-8")
        self.failover = (ROLE / "tasks/pg_auto_failover.yml").read_text(
            encoding="utf-8"
        )
        self.hba = (ROLE / "templates/pg_hba.conf.j2").read_text(encoding="utf-8")
        self.tls = (ROLE / "tasks/resolve_tls.yml").read_text(encoding="utf-8")
        self.handlers = (ROLE / "handlers/main.yml").read_text(encoding="utf-8")

    def test_default_data_directory_is_nested_under_deployment_postgres(self):
        defaults = (ROLE / "defaults/main.yml").read_text(encoding="utf-8")
        self.assertIn(
            "platform_postgresql_data_directory: \"{{ platform_data_root_directory | default('/var/lib') }}/{{ platform_postgresql_deployment_id }}/postgres\"",
            defaults,
        )

    def test_standalone_retains_platform_initdb(self):
        self.assertIn("Инициализировать PostgreSQL ровно один раз", self.main)
        self.assertIn("platform_postgresql_mode == 'standalone'", self.main)

    def test_postgresql_unit_is_member_scoped_and_legacy_unit_is_not_adopted(self):
        self.assertIn("platform_postgresql_name ~ '@' ~ platform_postgresql_deployment_id", self.main)
        self.assertIn("dest: \"/etc/systemd/system/{{ _platform_postgresql_unit_name }}\"", self.main)
        self.assertIn("argv: [systemctl, is-active, \"{{ _platform_postgresql_unit_name }}\"]", self.main)
        self.assertIn("POSTGRES_LEGACY_UNIT_REQUIRES_S11_CLEANUP", self.main)
        self.assertIn("POSTGRES_UNIT_NAME_COLLISION", (ROLE / "tasks/validate.yml").read_text(encoding="utf-8"))
        self.assertIn("{{ platform_postgresql_name }}-managed:", (ROLE / "templates/postgresql.service.j2").read_text(encoding="utf-8"))

    def test_pg_auto_failover_is_not_required_by_standalone(self):
        gate = self.main[: self.main.index("Проверка входных данных службы PostgreSQL")]
        self.assertIn("platform_postgresql_mode == 'pg_auto_failover'", gate)
        package = self.main[
            self.main.index("Установить одобренные пакеты PostgreSQL из настроенного системного репозитория") :
            self.main.index("Убедиться, что учетная запись службы PostgreSQL существует")
        ]
        self.assertIn("platform_postgresql_mode == 'pg_auto_failover'", package)
        tasks = yaml.safe_load(self.main)
        failover_package_tasks = [task for task in tasks
                                  if "pg_auto_failover" in task.get("name", "")]
        self.assertTrue(failover_package_tasks)
        for task in failover_package_tasks:
            self.assertIn("platform_postgresql_mode == 'pg_auto_failover'", str(task["when"]))

    def test_repository_package_selection_probes_exact_version_masks(self):
        tasks = yaml.safe_load(self.resolve_packages)
        legacy_probe = next(task for task in tasks
                            if task.get("name") == "Проверка имен устаревших пакетов PostgreSQL по маскам точной версии")
        major_probe = next(task for task in tasks
                           if task.get("name") == "Проверка имен пакетов PostgreSQL с основной областью действия по маскам точной версии")
        legacy_argv = legacy_probe["ansible.builtin.command"]["argv"]
        major_argv = major_probe["ansible.builtin.command"]["argv"]
        self.assertIn("--latest-limit=1", legacy_argv)
        self.assertIn("postgresql-{{ platform_postgresql_version }}-*.x86_64", legacy_argv)
        self.assertIn("postgresql-server-{{ platform_postgresql_version }}-*.x86_64", legacy_argv)
        self.assertIn("postgresql-contrib-{{ platform_postgresql_version }}-*.x86_64", legacy_argv)
        self.assertTrue(any("postgresql{{ platform_postgresql_version.split('.')[0] }}-" in item
                            for item in major_argv))
        install = next(task for task in yaml.safe_load(self.main)
                       if task.get("name") == "Установить одобренные пакеты PostgreSQL из настроенного системного репозитория")
        self.assertIn("_platform_postgresql_repository_packages", str(install["ansible.builtin.package"]["name"]))
        self.assertIn("POSTGRES_PACKAGE_FAMILY_UNAVAILABLE", str(tasks))

    def test_pg_auto_failover_package_selection_supports_major_scoped_names(self):
        tasks = yaml.safe_load(self.resolve_packages)
        major_probe = next(task for task in tasks
                           if task.get("name") == "Проверка имени пакета pg_auto_failover с основной областью действия по маске версии")
        legacy_probe = next(task for task in tasks
                            if task.get("name") == "Проверка имени устаревшего пакета pg_auto_failover по маске версии")
        self.assertIn("pg_auto_failover-{{ platform_postgresql_version.split('.')[0] }}-",
                      str(major_probe["ansible.builtin.command"]["argv"]))
        self.assertIn("pg_auto_failover-{{ platform_postgresql_pg_auto_failover_version }}-*.x86_64",
                      legacy_probe["ansible.builtin.command"]["argv"])
        install = next(task for task in yaml.safe_load(self.main)
                       if task.get("name") == "Установить одобренный пакет pg_auto_failover из настроенного системного репозитория")
        self.assertIn("_platform_postgresql_failover_repository_package",
                      str(install["ansible.builtin.package"]["name"]))
        self.assertIn("POSTGRES_FAILOVER_PACKAGE_UNAVAILABLE", str(tasks))

    def test_ha_data_members_do_not_run_platform_initdb(self):
        initdb = next(task for task in yaml.safe_load(self.main)
                      if task.get("name") == "Инициализировать PostgreSQL ровно один раз")
        self.assertIn("platform_postgresql_mode == 'standalone'", initdb["when"])

    def test_pg_autoctl_owns_empty_data_member_bootstrap(self):
        self.assertIn("pg_autoctl\n      - create\n      - postgres", self.failover)
        self.assertNotIn("Start temporary PostgreSQL bootstrap instance", self.failover)
        self.assertNotIn("initdb", self.failover)
        self.assertNotIn("pg_basebackup", self.failover)

    def test_existing_monitor_uri_is_reconciled_only_for_initialized_data(self):
        self.assertIn("Прочитать существующий URI монитора pg_autoctl", self.failover)
        self.assertIn("platform_postgresql_pg_autoctl_pg_version.stat.exists", self.failover)
        self.assertIn(
            "platform_postgresql_pg_autoctl_monitor_uri.stdout | trim != _platform_postgresql_monitor_uri",
            self.failover,
        )

    def test_monitor_uri_is_secret_free_and_uses_the_resolved_endpoint(self):
        self.assertIn("_platform_postgresql_monitor_uri", self.failover)
        self.assertIn("postgres://{{ platform_postgresql_monitor_credential.username }}@", self.failover)
        self.assertNotIn("password@", self.failover)
        self.assertIn("PGPASSFILE", self.failover)

    def test_data_node_uses_local_postgres_user_not_monitor_identity(self):
        self.assertIn('- "{{ platform_postgresql_user }}"', self.failover)

    def test_pg_autoctl_owns_slot_convergence_retry(self):
        self.assertIn("until: platform_postgresql_pg_autoctl_create_postgres.rc == 0", self.failover)
        self.assertIn("retries: 20", self.failover)

    def test_pgpass_covers_pg_autoctl_replication_database(self):
        self.assertIn(":*:{{ platform_postgresql_replication_credential.username }}:", self.failover)

    def test_monitor_healthcheck_uses_upstream_probe_identity_and_monitor_scoped_tls_trust(self):
        self.assertIn("hostssl postgres pgautofailover_monitor", self.hba)
        self.assertIn("{{ monitor.address }}/32 trust", self.hba)
        self.assertNotIn("host postgres pgautofailover_monitor", self.hba)
        self.assertNotIn("pgautofailover_monitor", self.failover)

    def test_monitor_healthcheck_role_is_least_privilege_and_has_no_password(self):
        self.assertIn("Согласование роли зонда проверки работоспособности pg_auto_failover без пароля", self.main)
        self.assertIn("NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION", self.main)
        self.assertIn("SELECT FROM pg_authid WHERE rolname = 'pgautofailover_monitor'", self.main)
        self.assertNotIn("SELECT FROM pg_roles WHERE rolname = 'pgautofailover_monitor' AND rolcanlogin", self.main)
        self.assertIn("rolpassword IS NULL", self.main)
        self.assertIn("PASSWORD NULL", self.main)
        self.assertNotIn("healthcheckCredential", self.main + self.failover)

    def test_postgres_login_shell_has_pg_autoctl_environment(self):
        self.assertIn("Сохранение среды pg_autoctl для оболочки входа PostgreSQL", self.failover)
        self.assertIn('export PGDATA="{{ platform_postgresql_data_directory }}"', self.failover)
        self.assertIn('export PGPASSFILE="{{ platform_postgresql_pgpass_file }}"', self.failover)

    def test_monitor_credential_is_set_after_monitor_start(self):
        self.assertIn("Согласование учетных данных монитора после инициализации монитора pg_autoctl", self.main)
        self.assertLess(
            self.main.index("Включение и запуск службы PostgreSQL на уровне экземпляра"),
            self.main.index("Согласование учетных данных монитора после инициализации монитора pg_autoctl"),
        )

    def test_primary_secondary_are_not_desired_inputs(self):
        self.assertNotIn("primary", self.failover.lower())
        self.assertNotIn("secondary", self.failover.lower())

    def test_credential_reconciliation_targets_only_the_runtime_writable_member(self):
        self.assertIn("Определить, доступен ли для записи экземпляр службы данных pg_auto_failover", self.main)
        self.assertIn("platform_postgresql_data_write_state.stdout | trim == 'primary'", self.main)

    def test_replication_credential_reconcile_is_gated_by_a_read_only_probe(self):
        self.assertIn("Проверка учетных данных репликации через TLS на экземпляре службы данных с возможностью записи", self.main)
        self.assertIn("platform_postgresql_replication_login.rc | default(1) != 0", self.main)

    def test_tls_credential_probes_run_as_the_owner_of_the_private_pgpass_file(self):
        task_names = (
            "Проверка учетных данных для мониторинга данных через TLS",
            "Проверка учетных данных репликации через TLS на экземпляре службы данных с возможностью записи",
        )
        for task_name in task_names:
            start = self.main.index(task_name)
            end = self.main.find("\n- name:", start + len(task_name))
            task = self.main[start:] if end == -1 else self.main[start:end]
            self.assertIn('become_user: "{{ platform_postgresql_user }}"', task)

    def test_monitor_tls_probe_uses_the_resolved_defaultable_monitor_port(self):
        start = self.main.index("Проверка учетных данных для мониторинга данных через TLS")
        end = self.main.find("\n- name:", start + len("Проверка учетных данных для мониторинга данных через TLS"))
        task = self.main[start:] if end == -1 else self.main[start:end]
        self.assertIn("{{ _platform_postgresql_monitor_port }}", task)
        self.assertNotIn("{{ _platform_postgresql_monitor.port }}", task)

    def test_tls_material_is_reloaded_by_the_pg_autoctl_owned_postgres_process(self):
        install_tls = (ROLE / "tasks/install_tls.yml").read_text(encoding="utf-8")
        self.assertIn("notify: Перезагрузить материал PostgreSQL TLS", install_tls)
        self.assertIn("pg_ctl, reload, -D", self.handlers)
        self.assertLess(
            self.main.index("Применить измененный материал PostgreSQL TLS перед проверками учетных данных TLS"),
            self.main.index("Проверка учетных данных для мониторинга данных через TLS"),
        )

    def test_service_account_and_base_directories_precede_owned_tls_materialization(self):
        names = [task.get("name") for task in yaml.safe_load(self.main)]
        self.assertLess(
            names.index("Решить точный потребительский план PostgreSQL PKI перед внесением изменений"),
            names.index("Установить одобренные пакеты PostgreSQL из настроенного системного репозитория"),
        )
        self.assertLess(
            names.index("Установить одобренные пакеты PostgreSQL из настроенного системного репозитория"),
            names.index("Убедиться, что учетная запись службы PostgreSQL существует"),
        )
        self.assertLess(
            names.index("Убедиться, что учетная запись службы PostgreSQL существует"),
            names.index("Создать каталоги развертывания и экземпляра службы PostgreSQL"),
        )
        self.assertLess(
            names.index("Создать каталоги развертывания и экземпляра службы PostgreSQL"),
            names.index("Установить принадлежащий PostgreSQL материал TLS после существования каталогов учетной записи и базы"),
        )
        install_tls = yaml.safe_load((ROLE / "tasks/install_tls.yml").read_text(encoding="utf-8"))
        tls_directory = next(task for task in install_tls
                             if task.get("name") == "Создать каталог TLS, принадлежащий PostgreSQL, после настройки учетной записи")
        self.assertEqual("{{ platform_postgresql_user }}", tls_directory["ansible.builtin.file"]["owner"])
        self.assertEqual("{{ platform_postgresql_group }}", tls_directory["ansible.builtin.file"]["group"])

    def test_tls_verification_failure_blocks_credential_ddl(self):
        self.assertIn("Блокировать сверку учетных данных монитора при сбое проверки TLS", self.main)
        self.assertIn("Блокировать согласование учетных данных репликации при сбое проверки TLS", self.main)
        self.assertNotIn("healthcheck_login", self.main)
        self.assertIn("certificate verify failed", self.main)

    def test_healthcheck_password_is_not_a_catalog_or_runtime_secret(self):
        service_root = Path(__file__).resolve().parents[1]
        manifest = (service_root / "service.yml").read_text(encoding="utf-8")
        schema = (service_root / "configuration.schema.json").read_text(encoding="utf-8")
        self.assertNotIn("healthcheckCredential", manifest)
        self.assertNotIn("healthcheck-password", manifest)
        self.assertNotIn("healthcheckCredential", schema)
        self.assertNotIn("healthcheck-password", schema)

    def test_serving_certificate_guard_reloads_only_on_a_network_fingerprint_mismatch(self):
        self.assertIn("Получение отпечатка листа сетевого прослушивателя PostgreSQL", self.main)
        self.assertIn("Перезагрузить управляемый дочерний элемент PostgreSQL только в том случае, если обслуживающий лист TLS устарел", self.main)
        self.assertIn("pg_ctl, reload, -D", self.main)
        self.assertIn("POSTGRES_TLS_SERVING_CERTIFICATE_MISMATCH", self.main)
        self.assertLess(
            self.main.index("Потребовать, чтобы сетевой прослушиватель PostgreSQL обслуживал материализованный лист TLS"),
            self.main.index("Проверка учетных данных для мониторинга данных через TLS"),
        )

    def test_pg_autoctl_basebackup_has_tls_only_hba_access(self):
        self.assertIn("hostssl replication {{ platform_postgresql_replication_credential.username }}", self.hba)
        self.assertIn("hostssl postgres {{ platform_postgresql_replication_credential.username }}", self.hba)


if __name__ == "__main__":
    unittest.main()

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
        self.failover = (ROLE / "tasks/pg_auto_failover.yml").read_text(
            encoding="utf-8"
        )
        self.hba = (ROLE / "templates/pg_hba.conf.j2").read_text(encoding="utf-8")
        self.tls = (ROLE / "tasks/resolve_tls.yml").read_text(encoding="utf-8")
        self.handlers = (ROLE / "handlers/main.yml").read_text(encoding="utf-8")

    def test_standalone_retains_platform_initdb(self):
        self.assertIn("Initialize PostgreSQL exactly once", self.main)
        self.assertIn("platform_postgresql_mode == 'standalone'", self.main)

    def test_pg_auto_failover_is_not_required_by_standalone(self):
        gate = self.main[: self.main.index("Validate PostgreSQL service inputs")]
        self.assertIn("platform_postgresql_mode == 'pg_auto_failover'", gate)
        package = self.main[
            self.main.index("Install approved PostgreSQL packages") :
            self.main.index("Ensure PostgreSQL service account exists")
        ]
        self.assertNotIn("pg_auto_failover-", package.split("Install approved pg_auto_failover package")[0])
        self.assertIn("platform_postgresql_mode == 'pg_auto_failover'", package)

    def test_ha_data_members_do_not_run_platform_initdb(self):
        initdb = next(task for task in yaml.safe_load(self.main)
                      if task.get("name") == "Initialize PostgreSQL exactly once")
        self.assertIn("platform_postgresql_mode == 'standalone'", initdb["when"])

    def test_pg_autoctl_owns_empty_data_member_bootstrap(self):
        self.assertIn("pg_autoctl\n      - create\n      - postgres", self.failover)
        self.assertNotIn("Start temporary PostgreSQL bootstrap instance", self.failover)
        self.assertNotIn("initdb", self.failover)
        self.assertNotIn("pg_basebackup", self.failover)

    def test_existing_monitor_uri_is_reconciled_only_for_initialized_data(self):
        self.assertIn("Read existing pg_autoctl monitor URI", self.failover)
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

    def test_monitor_healthcheck_has_a_dedicated_runtime_credential(self):
        self.assertIn("platform_postgresql_healthcheck_credential", self.failover)
        self.assertIn(":postgres:{{ platform_postgresql_healthcheck_credential.username }}:", self.failover)

    def test_monitor_healthcheck_hba_is_tls_only_and_monitor_scoped(self):
        self.assertIn("hostssl postgres {{ platform_postgresql_healthcheck_credential.username }}", self.hba)
        self.assertIn("{{ monitor.address }}/32", self.hba)
        self.assertNotIn("host postgres {{ platform_postgresql_healthcheck_credential.username }}", self.hba)

    def test_monitor_healthcheck_role_is_least_privilege_and_password_is_reconciled_only_after_failure(self):
        self.assertIn("Probe monitor healthcheck credential over TLS", self.main)
        self.assertIn("NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION", self.main)
        self.assertIn("platform_postgresql_healthcheck_login.rc | default(1) != 0", self.main)

    def test_postgres_login_shell_has_pg_autoctl_environment(self):
        self.assertIn("Persist pg_autoctl environment for the PostgreSQL login shell", self.failover)
        self.assertIn('export PGDATA="{{ platform_postgresql_data_directory }}"', self.failover)
        self.assertIn('export PGPASSFILE="{{ platform_postgresql_pgpass_file }}"', self.failover)

    def test_monitor_credential_is_set_after_monitor_start(self):
        self.assertIn("Reconcile monitor credential after pg_autoctl monitor initialization", self.main)
        self.assertLess(
            self.main.index("Enable and start member-scoped PostgreSQL"),
            self.main.index("Reconcile monitor credential after pg_autoctl monitor initialization"),
        )

    def test_primary_secondary_are_not_desired_inputs(self):
        self.assertNotIn("primary", self.failover.lower())
        self.assertNotIn("secondary", self.failover.lower())

    def test_credential_reconciliation_targets_only_the_runtime_writable_member(self):
        self.assertIn("Discover whether a pg_auto_failover data member is writable", self.main)
        self.assertIn("platform_postgresql_data_write_state.stdout | trim == 'primary'", self.main)

    def test_replication_credential_reconcile_is_gated_by_a_read_only_probe(self):
        self.assertIn("Probe replication credential over TLS on the writable data member", self.main)
        self.assertIn("platform_postgresql_replication_login.rc | default(1) != 0", self.main)

    def test_tls_credential_probes_run_as_the_owner_of_the_private_pgpass_file(self):
        task_names = (
            "Probe data-to-monitor credential over TLS",
            "Probe replication credential over TLS on the writable data member",
            "Probe monitor healthcheck credential over TLS",
        )
        for task_name in task_names:
            start = self.main.index(task_name)
            end = self.main.find("\n- name:", start + len(task_name))
            task = self.main[start:] if end == -1 else self.main[start:end]
            self.assertIn('become_user: "{{ platform_postgresql_user }}"', task)

    def test_monitor_tls_probe_uses_the_resolved_defaultable_monitor_port(self):
        start = self.main.index("Probe data-to-monitor credential over TLS")
        end = self.main.find("\n- name:", start + len("Probe data-to-monitor credential over TLS"))
        task = self.main[start:] if end == -1 else self.main[start:end]
        self.assertIn("{{ _platform_postgresql_monitor_port }}", task)
        self.assertNotIn("{{ _platform_postgresql_monitor.port }}", task)

    def test_tls_material_is_reloaded_by_the_pg_autoctl_owned_postgres_process(self):
        self.assertIn("notify: Reload PostgreSQL TLS material", self.tls)
        self.assertIn("pg_ctl, reload, -D", self.handlers)
        self.assertLess(
            self.main.index("Apply changed PostgreSQL TLS material before TLS credential probes"),
            self.main.index("Probe data-to-monitor credential over TLS"),
        )

    def test_tls_verification_failure_blocks_credential_ddl(self):
        self.assertIn("Block monitor credential reconciliation when TLS verification fails", self.main)
        self.assertIn("Block replication credential reconciliation when TLS verification fails", self.main)
        self.assertIn("Block monitor healthcheck credential reconciliation when TLS verification fails", self.main)
        self.assertIn("certificate verify failed", self.main)

    def test_serving_certificate_guard_reloads_only_on_a_network_fingerprint_mismatch(self):
        self.assertIn("Derive PostgreSQL network listener leaf fingerprint", self.main)
        self.assertIn("Reload managed PostgreSQL child only when the serving TLS leaf is stale", self.main)
        self.assertIn("pg_ctl, reload, -D", self.main)
        self.assertIn("POSTGRES_TLS_SERVING_CERTIFICATE_MISMATCH", self.main)
        self.assertLess(
            self.main.index("Require PostgreSQL network listener to serve materialized TLS leaf"),
            self.main.index("Probe data-to-monitor credential over TLS"),
        )

    def test_pg_autoctl_basebackup_has_tls_only_hba_access(self):
        self.assertIn("hostssl replication {{ platform_postgresql_replication_credential.username }}", self.hba)
        self.assertIn("hostssl postgres {{ platform_postgresql_replication_credential.username }}", self.hba)


if __name__ == "__main__":
    unittest.main()

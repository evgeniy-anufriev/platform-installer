import os
import unittest


ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


class ServiceApplyPkiContractTests(unittest.TestCase):
    def test_pki_ensures_keytool_before_materializing_pkcs12_stores(self):
        role_root = os.path.join(
            ROOT,
            "ansible-core/collections/ansible_collections/platform/core/roles/pki_materialize",
        )
        with open(os.path.join(role_root, "tasks/main.yml"), encoding="utf-8") as handle:
            tasks = handle.read()
        with open(os.path.join(role_root, "tasks/stores.yml"), encoding="utf-8") as handle:
            stores = handle.read()
        with open(os.path.join(role_root, "defaults/main.yml"), encoding="utf-8") as handle:
            defaults = handle.read()

        self.assertIn("Проверка наличия keytool перед материализацией хранилища PKCS12", tasks)
        self.assertIn("Установить среду выполнения Java, предоставляя ключевой инструмент, когда он отсутствует", tasks)
        self.assertIn("Перепроверить keytool после проверки среды выполнения Java", tasks)
        self.assertIn("PKI_KEYTOOL_UNAVAILABLE", tasks)
        self.assertIn("platform_pki_keytool_package: java-21-openjdk-headless", defaults)
        self.assertLess(tasks.index("Требовать keytool перед материализацией хранилища PKCS12"),
                        tasks.index("Материализация разрешенных запросов сертификатов PKI"))
        self.assertIn("keytool", stores)

    def test_pki_resolution_reloads_portable_manifest_for_stable_project_identity(self):
        resolve_tasks = os.path.join(
            ROOT,
            "ansible-core/collections/ansible_collections/platform/core/roles/pki_materialize/tasks/resolve.yml",
        )
        with open(resolve_tasks, encoding="utf-8") as handle:
            tasks = handle.read()
        self.assertIn("platform_project_manifest_path", tasks)
        self.assertIn("_platform_pki_project_manifest_document.metadata.id", tasks)
        self.assertNotIn("platform_project_manifest_document.metadata.id", tasks)
        self.assertIn("_platform_pki_project_id", tasks)

    def test_transient_request_workspace_is_project_scoped(self):
        request_tasks = os.path.join(
            ROOT,
            "ansible-core/collections/ansible_collections/platform/core/roles/pki_materialize/tasks/request.yml",
        )
        with open(request_tasks, encoding="utf-8") as handle:
            tasks = handle.read()
        self.assertIn(
            "platform_pki_runtime_root }}/{{ platform_pki_project_id }}/{{ platform_pki_request.id }}",
            tasks,
        )

    def test_explicit_pki_reissue_selection_rotates_same_identity_without_reconcile_bypass(self):
        request_tasks = os.path.join(
            ROOT,
            "ansible-core/collections/ansible_collections/platform/core/roles/pki_materialize/tasks/request.yml",
        )
        with open(request_tasks, encoding="utf-8") as handle:
            tasks = handle.read()
        self.assertIn("_platform_pki_reissue_requested: \"{{ platform_pki_request.id in platform_pki_reissue_request_ids }}\"", tasks)
        self.assertIn("or\n          _platform_pki_reissue_requested", tasks)
        self.assertIn("not _platform_pki_reissue_required or _platform_pki_reissue_requested", tasks)
        self.assertIn("_platform_pki_reissue_active", tasks)
        self.assertIn("Сохранить материал предыдущего запроса PKI перед явным повторным выпуском", tasks)
        self.assertIn("Удалить замененный материал запроса PKI во время явного повторного выпуска", tasks)
        self.assertIn("not _platform_pki_reissue_resumable and platform_pki_request_marker.stat.exists", tasks)
        self.assertLess(tasks.index("Сохранить материал предыдущего запроса PKI перед явным повторным выпуском"),
                        tasks.index("Запустить явно авторизованный повторный выпуск PKI после полного резервного копирования"))
        self.assertLess(tasks.index("Запустить явно авторизованный повторный выпуск PKI после полного резервного копирования"),
                        tasks.index("Удалить замененный материал запроса PKI во время явного повторного выпуска"))
        self.assertLess(tasks.index("Отклонить изменение политики управляемого центра сертификации перед повторной очисткой"),
                        tasks.index("Сохранить материал предыдущего запроса PKI перед явным повторным выпуском"))
        self.assertLess(tasks.index("Отклонить изменение политики управляемого центра сертификации перед повторной очисткой"),
                        tasks.index("Удалить замененный материал запроса PKI во время явного повторного выпуска"))
        self.assertIn("Сохранить существующие производные хранилища PKCS12 перед явным повторным выпуском", tasks)
        self.assertIn("platform_pki_request_files.results[item.index].stat.isreg | default(false)", tasks)
        self.assertIn("CERTIFICATE_REISSUE_REQUIRED", tasks)

    def test_pki_deploy_publishes_a_non_secret_change_signal(self):
        deploy_tasks = os.path.join(
            ROOT,
            "ansible-core/collections/ansible_collections/platform/core/roles/pki_deploy/tasks/plan.yml",
        )
        with open(deploy_tasks, encoding="utf-8") as handle:
            tasks = handle.read()
        self.assertIn("platform_pki_material_changed:", tasks)

    def test_kafka_secret_bearing_config_render_suppresses_logs_and_diffs(self):
        path = os.path.join(
            ROOT,
            "services/kafka/ansible_collections/platform/kafka/roles/kafka_kraft/tasks/member.yml",
        )
        with open(path, encoding="utf-8") as handle:
            tasks = handle.read()
        render = tasks[tasks.index("- name: Отрисовка детерминированного экземпляра службы server.properties"):]
        render = render[:render.index("\n- name:")]
        self.assertIn("diff: false", render)
        self.assertIn("no_log: true", render)

    def test_controller_side_validate_manifest_fallback_does_not_require_inventory_dir(self):
        validate = os.path.join(ROOT, "ansible-core/playbooks/validate.yml")
        with open(validate, encoding="utf-8") as handle:
            tasks = handle.read()
        self.assertIn("inventory_dir | default('/project/inventory', true)", tasks)
        self.assertNotIn("default(inventory_dir ~ '/../project.yml', true)", tasks)
        self.assertNotIn("default((inventory_dir | dirname | basename), true)", tasks)

    def test_kafka_controller_side_identity_materialization_does_not_require_inventory_dir(self):
        paths = (
            "services/kafka/playbooks/apply.yml",
            "services/kafka/playbooks/discover.yml",
        )
        for relative_path in paths:
            with open(os.path.join(ROOT, relative_path), encoding="utf-8") as handle:
                tasks = handle.read()
            self.assertIn("inventory_dir | default('/project/inventory', true)", tasks)
            self.assertNotIn("default(inventory_dir ~ '/../project.yml', true)", tasks)
        with open(os.path.join(ROOT, paths[0]), encoding="utf-8") as handle:
            apply_tasks = handle.read()
        self.assertNotIn("default((inventory_dir | dirname | basename), true)", apply_tasks)
        self.assertIn("platform_project_manifest_path", apply_tasks)
        self.assertIn("platform_project_root", apply_tasks)
        self.assertIn("Выбрать эффективное желаемое состояние Kafka для материализации на стороне контроллера", apply_tasks)
        self.assertIn("Передать служебное состояние идентификаторов Kafka на целевые узлы", apply_tasks)
        self.assertNotIn("Refresh inventory after canonical identity persistence", apply_tasks)
        aggregate = os.path.join(ROOT, "services/kafka/playbooks/aggregate_discovery.yml")
        with open(aggregate, encoding="utf-8") as handle:
            aggregate_tasks = handle.read()
        self.assertIn("dict((groups['platform_targets'] | default([]) | sort) | zip", aggregate_tasks)
        self.assertIn("map('extract', hostvars, 'platform_kafka_identity_discovery')", aggregate_tasks)
        self.assertNotIn("platform_kafka_discovery_by_host | default({}) | combine", apply_tasks)
        materializer = apply_tasks[apply_tasks.index("Материализация управляемых удостоверений Kafka перед изменением"):apply_tasks.index("Kafka создал проекцию идентичности")]
        self.assertIn("changed_when: false", materializer)

    def test_tls_service_apply_playbooks_use_project_wide_pki_before_role_reconcile(self):
        cases = {
            "kafka": "services/kafka/playbooks/apply.yml",
            "postgresql": "services/postgresql/playbooks/apply.yml",
            "haproxy": "services/haproxy/playbooks/apply.yml",
        }
        for _service_type, relative_path in cases.items():
            with open(os.path.join(ROOT, relative_path), encoding="utf-8") as handle:
                playbook = handle.read()
            pki_import = "import_playbook: ../../../ansible-core/playbooks/pki-apply.yml"
            self.assertIn(pki_import, playbook)
            self.assertNotIn("platform_pki_service_types:", playbook)
            self.assertLess(playbook.index(pki_import), playbook.index("roles:"))

    def test_pki_consumers_use_exact_request_binding_instead_of_first_profile_match(self):
        selector = os.path.join(
            ROOT,
            "ansible-core/collections/ansible_collections/platform/core/roles/pki_materialize/tasks/select_consumer_plan.yml",
        )
        with open(selector, encoding="utf-8") as handle:
            selector_tasks = handle.read()
        self.assertIn("platform_execution_service_deployment", selector_tasks)
        self.assertIn("selectattr('deploymentId', 'equalto', _platform_pki_consumer_deployment_id)", selector_tasks)
        self.assertIn("selectattr('requestId', 'in', _platform_pki_consumer_request_ids)", selector_tasks)
        self.assertIn("_platform_pki_consumer_plans | length == 1", selector_tasks)

        consumers = {
            "postgresql": "services/postgresql/ansible_collections/platform/postgresql/roles/postgresql/tasks/resolve_tls.yml",
            "redis": "services/redis/ansible_collections/platform/redis/roles/redis_tls/tasks/resolve_tls.yml",
            "haproxy": "services/haproxy/ansible_collections/platform/haproxy/roles/haproxy/tasks/lifecycle.yml",
        }
        for service, relative_path in consumers.items():
            with open(os.path.join(ROOT, relative_path), encoding="utf-8") as handle:
                tasks = handle.read()
            self.assertIn("tasks_from: select_consumer_plan.yml", tasks, service)

        haproxy_prepare = os.path.join(
            ROOT,
            "services/haproxy/ansible_collections/platform/haproxy/roles/haproxy/tasks/prepare.yml",
        )
        with open(haproxy_prepare, encoding="utf-8") as handle:
            haproxy_prepare_tasks = handle.read()
        self.assertNotIn("_platform_haproxy_pki_plan", haproxy_prepare_tasks)

        postgresql_main = os.path.join(
            ROOT,
            "services/postgresql/ansible_collections/platform/postgresql/roles/postgresql/tasks/main.yml",
        )
        with open(postgresql_main, encoding="utf-8") as handle:
            postgresql_tasks = handle.read()
        self.assertLess(
            postgresql_tasks.index("Решить точный потребительский план PostgreSQL PKI перед внесением изменений"),
            postgresql_tasks.index("Доставка выбранных автономных артефактов PostgreSQL"),
        )

        haproxy_lifecycle = os.path.join(
            ROOT,
            "services/haproxy/ansible_collections/platform/haproxy/roles/haproxy/tasks/lifecycle.yml",
        )
        with open(haproxy_lifecycle, encoding="utf-8") as handle:
            haproxy_tasks = handle.read()
        self.assertIn('platform_pki_consumer_tls_profile_id: "{{ platform_haproxy_tls_profile }}"', haproxy_tasks)
        self.assertIn('platform_execution_service_deployment: "{{ _platform_haproxy_local_deployments[0].key }}"', haproxy_tasks)
        self.assertIn("platform_haproxy_phase == 'prepare'", haproxy_tasks)
        self.assertLess(
            haproxy_tasks.index("Выбрать точный потребительский план PKI перед изменением HAProxy"),
            haproxy_tasks.index("Доставка выбранных автономных артефактов HAProxy"),
        )

        redis_main = os.path.join(
            ROOT,
            "services/redis/ansible_collections/platform/redis/roles/redis_tls/tasks/main.yml",
        )
        with open(redis_main, encoding="utf-8") as handle:
            redis_tasks = handle.read()
        self.assertLess(
            redis_tasks.index("Разрешить материал Redis TLS"),
            redis_tasks.index("Установить утвержденный пакет Redis из настроенного репозитория"),
        )

    def test_runtime_role_variable_guard_projects_only_the_private_host_map(self):
        path = os.path.join(
            ROOT,
            "ansible-core/collections/ansible_collections/platform/core/roles/runtime_role_variables/tasks/main.yml",
        )
        with open(path, encoding="utf-8") as handle:
            tasks = handle.read()
        self.assertIn("platform_execution_role_variables_by_host[inventory_hostname] is mapping", tasks)
        self.assertIn("platform.core.apply_runtime_role_variables", tasks)
        self.assertNotIn("| dict2items", tasks)

    def test_kafka_verify_reloads_controller_owned_generated_state(self):
        verify = os.path.join(ROOT, "services/kafka/playbooks/verify.yml")
        loader = os.path.join(ROOT, "services/kafka/playbooks/load_generated_state.yml")
        with open(verify, encoding="utf-8") as handle:
            verify_tasks = handle.read()
        with open(loader, encoding="utf-8") as handle:
            loader_tasks = handle.read()
        self.assertIn("import_playbook: load_generated_state.yml", verify_tasks)
        self.assertIn("Проецировать созданное состояние Kafka, принадлежащее контроллеру, на узлы проверки", verify_tasks)
        self.assertIn("platform_generated_state_path", loader_tasks)
        self.assertIn("KAFKA_GENERATED_STATE_REQUIRED", loader_tasks)
        self.assertIn("_platform_kafka_generated_state_document.platform_generated_state", loader_tasks)

    def test_pg_auto_failover_uses_routable_member_addresses_for_cluster_identity(self):
        lifecycle = os.path.join(
            ROOT,
            "services/postgresql/ansible_collections/platform/postgresql/roles/postgresql/tasks/pg_auto_failover.yml",
        )
        main = os.path.join(
            ROOT,
            "services/postgresql/ansible_collections/platform/postgresql/roles/postgresql/tasks/main.yml",
        )
        reconcile = os.path.join(
            ROOT,
            "services/postgresql/ansible_collections/platform/postgresql/roles/postgresql/tasks/reconcile.yml",
        )
        with open(lifecycle, encoding="utf-8") as handle:
            lifecycle_tasks = handle.read()
        with open(main, encoding="utf-8") as handle:
            main_tasks = handle.read()
        with open(reconcile, encoding="utf-8") as handle:
            reconcile_tasks = handle.read()

        self.assertIn('"postgres://{{ platform_postgresql_monitor_credential.username }}@{{ _platform_postgresql_monitor.address }}:{{ _platform_postgresql_monitor.port | default(platform_postgresql_port) }}/pg_auto_failover"', lifecycle_tasks)
        self.assertIn("_platform_postgresql_monitor.address", lifecycle_tasks)
        self.assertIn("_platform_postgresql_member.address", lifecycle_tasks)
        self.assertIn("- --hostname\n      - \"{{ _platform_postgresql_member.address }}\"", lifecycle_tasks)
        self.assertNotIn("_platform_postgresql_monitor.hostname", lifecycle_tasks)
        self.assertNotIn("_platform_postgresql_member.hostname", lifecycle_tasks)
        self.assertIn("file: reconcile.yml", main_tasks)
        self.assertIn("_platform_postgresql_monitor.address", reconcile_tasks)
        self.assertIn("_platform_postgresql_member.address", reconcile_tasks)


if __name__ == "__main__":
    unittest.main()

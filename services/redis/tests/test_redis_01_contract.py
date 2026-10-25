from pathlib import Path
import base64
import unittest

import yaml
from jinja2 import Environment
from ansible.plugins.filter.core import b64decode, regex_escape
from ansible.plugins.test.core import search


ROOT = Path(__file__).resolve().parents[3]


def manifest():
    return yaml.safe_load((ROOT / "services" / "redis" / "service.yml").read_text(encoding="utf-8"))


class RedisContractTests(unittest.TestCase):
    def test_redis_quoted_paths_preserve_exact_static_guard(self):
        role = ROOT / "services" / "redis" / "ansible_collections" / "platform" / "redis" / "roles" / "redis_tls"
        tasks = yaml.safe_load((role / "tasks" / "preflight.yml").read_text(encoding="utf-8"))
        guard = next(task for task in tasks if task["name"] == "Отклонить небезопасное изменение статической конфигурации Redis")
        self.assertTrue(guard["no_log"])
        env = Environment()
        env.filters.update(b64decode=b64decode, regex_escape=regex_escape)
        env.tests["search"] = search
        directory = "/etc/platform-redis/redis-1"
        data_directory = "/var/lib/platform-redis/redis-1"
        cases = (
            ("tls-cert-file", f"{directory}/pki/certificate.pem", 2),
            ("tls-key-file", f"{directory}/pki/private-key.pem", 3),
            ("tls-ca-cert-file", f"{directory}/pki/ca-chain.pem", 4),
            ("dir", data_directory, 7),
        )
        for directive, path, index in cases:
            template = env.from_string("{{ " + guard["ansible.builtin.assert"]["that"][index] + " }}")
            for value, accepted in (
                (path, True), ('"' + path + '"', True),
                ('"' + path, False), (path + '"', False),
                ('"' + path + '" trailing', False),
                (path + ".other", False),
                (path.replace("redis-1", "foreign"), False),
            ):
                with self.subTest(directive=directive, value=value):
                    content = base64.b64encode(f"{directive} {value}\n".encode()).decode()
                    result = template.render(
                        _platform_redis_config_file={"results": [{"stat": {"exists": True}}]},
                        _platform_redis_existing_config={"results": [{"content": content}]},
                        redis_config_index=0,
                        item={"config_directory": directory, "data_directory": data_directory},
                    )
                    self.assertEqual(result, str(accepted))

    def test_sentinel_rewritten_tls_paths_preserve_exact_static_guard(self):
        role = ROOT / "services" / "redis" / "ansible_collections" / "platform" / "redis" / "roles" / "redis_tls"
        tasks = yaml.safe_load((role / "tasks" / "preflight.yml").read_text(encoding="utf-8"))
        guard = next(task for task in tasks if task["name"] == "Отклонить небезопасное изменение статической конфигурации Sentinel")
        self.assertTrue(guard["no_log"])
        env = Environment()
        env.filters.update(b64decode=b64decode, regex_escape=regex_escape)
        env.tests["search"] = search
        directory = "/etc/platform-redis/redis-ha33-a"
        for expression, directive, filename in zip(guard["ansible.builtin.assert"]["that"][2:5],
                ("tls-cert-file", "tls-key-file", "tls-ca-cert-file"),
                ("certificate.pem", "private-key.pem", "ca-chain.pem")):
            path = f"{directory}/pki/{filename}"
            template = env.from_string("{{ " + expression + " }}")
            for value, accepted in ((path, True), ('"' + path + '"', True),
                    ('"' + path, False), (path + '"', False),
                    (path + ".other", False), (path.replace("redis-ha33-a", "foreign"), False),
                    (path.replace(".pem", "Xpem"), False)):
                with self.subTest(directive=directive, value=value):
                    content = base64.b64encode(f"{directive} {value}\n".encode()).decode()
                    result = template.render(
                        _platform_sentinel_config_stat={"results": [{"stat": {"exists": True}}]},
                        _platform_sentinel_existing_config={"results": [{"content": content}]},
                        sentinel_config_index=0, item={"config_directory": directory})
                    self.assertEqual(result, str(accepted))

    def test_modes_keep_member_scoped_tls_contract(self):
        value = manifest()
        settings = value["configuration"]["settings"]
        self.assertEqual(["deployment"], settings["dataRoot"]["scopes"])
        self.assertEqual(["member"], settings["dataDirectory"]["scopes"])
        self.assertNotIn("configRoot", settings)
        self.assertEqual(value["modes"]["standalone"]["placement"]["minMembers"], 1)
        ha = value["modes"]["sentinel-ha"]
        self.assertEqual(ha["placement"]["minMembers"], 3)
        self.assertFalse(ha["placement"]["distinctHosts"])
        self.assertEqual(ha["placement"]["roleCardinality"], {
            "redis": {"minimum": 3, "maximum": 3},
            "sentinel": {"minimum": 3, "maximum": 3},
        })
        self.assertEqual(value["listeners"]["client"]["scope"], "member")
        self.assertEqual(value["listeners"]["sentinel"]["scope"], "member")

    def test_instance_units_use_numeric_member_suffix_and_preserve_legacy_guard(self):
        role = ROOT / "services" / "redis" / "ansible_collections" / "platform" / "redis" / "roles" / "redis_tls"
        normalize = (role / "tasks" / "normalize.yml").read_text(encoding="utf-8")
        validate = (role / "tasks" / "validate.yml").read_text(encoding="utf-8")
        preflight = (role / "tasks" / "preflight.yml").read_text(encoding="utf-8")
        self.assertIn("platform_redis_instances | sort(attribute='id')", normalize)
        self.assertIn("index_var: redis_slot", normalize)
        self.assertIn("'instance_name': platform_redis_deployment_id ~ '-'", normalize)
        self.assertIn("REDIS_UNIT_NAME_COLLISION", normalize)
        projection = (role.parents[1] / 'plugins/module_utils/member_projection.py').read_text(encoding='utf-8')
        self.assertIn("source['id'].rsplit('-', 1)[-1]", projection)
        self.assertIn("^.+-[1-9][0-9]*$", validate)
        self.assertIn("REDIS_LEGACY_UNIT_REQUIRES_S11_CLEANUP", preflight)
        self.assertIn("REDIS_UNIT_OWNERSHIP_UNKNOWN", preflight)
        self.assertIn("REDIS_UNIT_PATH_UNSAFE", preflight)
        self.assertIn("# {{ platform_redis_name }}-managed:", (role / "templates/redis.service.j2").read_text(encoding="utf-8"))
        self.assertIn("# {{ platform_redis_name }}-managed:", (role / "templates/sentinel.service.j2").read_text(encoding="utf-8"))

    def test_repository_source_version_matches_dnf_repoquery_identity(self):
        value = manifest()
        self.assertEqual(value["runtimeRequirements"][0]["version"], "8.6.4")
        defaults = (ROOT / "services" / "redis" / "ansible_collections" / "platform" / "redis" / "roles" / "redis_tls" / "defaults" / "main.yml").read_text(encoding="utf-8")
        package_source = (ROOT / "services" / "redis" / "artifacts.yml").read_text(encoding="utf-8")
        self.assertIn('platform_redis_version: "8.6.4-1.red80"', defaults)
        self.assertIn("platform_data_root_directory | default('/var/lib')", defaults)
        self.assertIn('platform_redis_config_root: "/etc/{{ platform_redis_name }}"', defaults)
        self.assertIn('platform_redis_log_root: "/var/log/{{ platform_redis_name }}"', defaults)
        validate = (ROOT / "services" / "redis" / "ansible_collections" / "platform" / "redis" / "roles" / "redis_tls" / "tasks" / "validate.yml").read_text(encoding="utf-8")
        self.assertIn("platform_redis_data_root is string", validate)
        self.assertIn("platform_redis_config_root == '/etc/' ~ platform_redis_name", validate)
        self.assertIn("platform_redis_log_root == '/var/log/' ~ platform_redis_name", validate)
        self.assertIn("redis-8.6.4-1.red80", package_source)

    def test_secret_references_are_runtime_only_contract_values(self):
        settings = manifest()["configuration"]["settings"]
        self.assertEqual(settings["redisCredential"]["ui"]["x-runtimeSecretRequirement"]["requirementRef"], "redis-password")
        self.assertEqual(settings["sentinelCredential"]["ui"]["x-runtimeSecretRequirement"]["requirementRef"], "redis-sentinel-password")

    def test_sentinel_replication_seed_is_only_rendered_for_initial_ha_members(self):
        role = ROOT / "services" / "redis" / "ansible_collections" / "platform" / "redis" / "roles" / "redis_tls"
        template = (role / "templates" / "redis.conf.j2").read_text(encoding="utf-8")
        sentinel_template = (role / "templates" / "sentinel.conf.j2").read_text(encoding="utf-8")
        member = (role / "tasks" / "member.yml").read_text(encoding="utf-8")
        finalize = (role / "tasks" / "finalize_bootstrap.yml").read_text(encoding="utf-8")
        main = (role / "tasks" / "main.yml").read_text(encoding="utf-8")
        self.assertIn("platform_redis_mode == 'sentinel-ha' and redis_member.slot | int > 0", template)
        self.assertIn("when: not _platform_redis_has_persistent_state", member)
        self.assertIn("sentinel monitor {{ (_platform_redis_instances | first).id }}", sentinel_template)
        self.assertIn("sentinel sentinel-user default", sentinel_template)
        self.assertIn("sentinel sentinel-pass {{ lookup('ansible.builtin.file', platform_redis_secret_files[platform_redis_sentinel_credential.passwordSecretRef]) | to_json }}", sentinel_template)
        member_tasks = yaml.safe_load(member)
        peer_user = next(task for task in member_tasks if task["name"] == "Настройка одноранговой аутентификации Sentinel для пользователя ACL по умолчанию")
        peer_password = next(task for task in member_tasks if task["name"] == "Настройка пароля узла Sentinel из секрета времени выполнения")
        self.assertTrue(peer_user["no_log"])
        self.assertTrue(peer_password["no_log"])
        self.assertEqual(peer_user["ansible.builtin.lineinfile"]["line"], "sentinel sentinel-user default")
        self.assertIn("platform_redis_sentinel_credential.passwordSecretRef", peer_password["ansible.builtin.lineinfile"]["line"])
        self.assertIn("_platform_sentinel_peer_user.changed or _platform_sentinel_peer_password.changed", member)
        self.assertIn("- not _platform_redis_has_persistent_state", member)
        self.assertIn("Создать начальную конфигурацию нового Sentinel с поддержкой только TLS", member)
        self.assertIn("regexp: '^replicaof '\n    state: absent", finalize)
        self.assertLess(finalize.index("Удаление целевой реплики начальной загрузки из постоянной конфигурации Redis"), finalize.index("Запись постоянного маркера владения Redis после успешной начальной загрузки"))
        self.assertLess(main.index("include_tasks: member.yml"), main.index("include_tasks: finalize_bootstrap.yml"))
        verify = (role / "tasks" / "verify.yml").read_text(encoding="utf-8")
        self.assertNotIn("--tls-host", verify)

    def test_password_values_are_not_trimmed_and_are_quoted_in_redis_configuration(self):
        role = ROOT / "services" / "redis" / "ansible_collections" / "platform" / "redis" / "roles" / "redis_tls"
        redis_template = (role / "templates" / "redis.conf.j2").read_text(encoding="utf-8")
        sentinel_template = (role / "templates" / "sentinel.conf.j2").read_text(encoding="utf-8")
        for template in (redis_template, sentinel_template):
            self.assertNotIn("| trim", template)
            self.assertIn("| to_json", template)

    def test_tls_ping_failure_reports_only_closed_safe_category(self):
        verify = (ROOT / "services" / "redis" / "ansible_collections" / "platform" / "redis" / "roles" / "redis_tls" / "tasks" / "verify.yml").read_text(encoding="utf-8")
        for code in (
            "REDIS_TLS_AUTH_REJECTED",
            "REDIS_TLS_AUTH_REQUIRED",
            "REDIS_TLS_CONNECTION_FAILED",
            "REDIS_TLS_PING_FAILED",
        ):
            self.assertIn(code, verify)
        self.assertIn("no_log: true", verify)
        self.assertIn("ignore_errors: true", verify)
        self.assertIn("_platform_redis_ping.stdout | trim == 'PONG'", verify)

    def test_replication_role_checks_accept_redis_cli_crlf_output(self):
        verify = (ROOT / "services" / "redis" / "ansible_collections" / "platform" / "redis" / "roles" / "redis_tls" / "tasks" / "verify.yml").read_text(encoding="utf-8")
        self.assertIn("role:(master|slave|replica)\\\\r?$", verify)
        self.assertIn("regex_search('(?m)^role:(master|slave|replica)')", verify)
        self.assertIn("regex_search('(?m)^master_link_status:up')", verify)

    def test_master_aggregation_uses_closed_role_text(self):
        verify_member = (ROOT / "services" / "redis" / "ansible_collections" / "platform" / "redis" / "roles" / "redis_tls" / "tasks" / "verify.yml").read_text(encoding="utf-8")
        verify_deployment = (ROOT / "services" / "redis" / "ansible_collections" / "platform" / "redis" / "roles" / "redis_tls" / "tasks" / "verify_deployment.yml").read_text(encoding="utf-8")
        self.assertIn("'role': (", verify_member)
        self.assertIn("default('role:unknown', true)", verify_member)
        self.assertIn("selectattr('role', 'equalto', 'master')", verify_deployment)

    def test_deployment_verify_assertions_are_bounded_and_separately_identifiable(self):
        verify = (ROOT / "services" / "redis" / "ansible_collections" / "platform" / "redis" / "roles" / "redis_tls" / "tasks" / "verify_deployment.yml").read_text(encoding="utf-8")
        self.assertIn("Требовать ожидаемое количество наблюдений экземпляра службы Redis", verify)
        self.assertIn("Требуется ровно один наблюдаемый мастер Redis", verify)
        self.assertIn("Требовать две готовые реплики Redis в Sentinel HA", verify)
        self.assertIn("Проверить, что все Sentinel указывают на одного мастера Redis", verify)
        self.assertIn("Потребовать, чтобы мастер Sentinel соответствовал наблюдению Redis", verify)
        self.assertIn("run_once: true", verify)

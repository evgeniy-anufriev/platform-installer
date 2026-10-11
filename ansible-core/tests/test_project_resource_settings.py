"""Read-only proof of portable service names, data roots, and fixed Installer PKI."""

from pathlib import Path
import unittest

from jinja2 import Environment, StrictUndefined
import yaml


ROOT = Path(__file__).resolve().parents[2]
RENDER = Environment(undefined=StrictUndefined).from_string


def defaults(service, collection, role):
    path = (ROOT / "services" / service / "ansible_collections" / "platform" /
            collection / "roles" / role / "defaults" / "main.yml")
    return yaml.safe_load(path.read_text())


class ProjectResourceSettingsTests(unittest.TestCase):
    ROLES = (
        ("vault", "vault", "vault_tls", "platform_vault_name", "platform_vault_data_root", "platform_vault_deployment_id"),
        ("redis", "redis", "redis_tls", "platform_redis_name", "platform_redis_data_root", "platform_redis_deployment_id"),
        ("kafka", "kafka", "kafka_kraft", "platform_kafka_name", "platform_kafka_data_directory", "platform_kafka_deployment_id"),
        ("clickhouse", "clickhouse", "clickhouse_tls", "platform_clickhouse_name", "platform_clickhouse_data_root", "platform_clickhouse_deployment_id"),
        ("postgresql", "postgresql", "postgresql", "platform_postgresql_name", "platform_postgresql_data_directory", "platform_postgresql_deployment_id"),
    )

    def test_empty_and_named_prefix_with_default_and_custom_root(self):
        for service, collection, role, name_key, data_key, deployment_key in self.ROLES:
            values = defaults(service, collection, role)
            for prefix, expected_name in (("", service), ("platform", "platform-" + service), ("qa", "qa-" + service)):
                for root in ("/var/lib", "/srv/service-data"):
                    with self.subTest(service=service, prefix=prefix, root=root):
                        context = {"platform_name_prefix": prefix,
                                   "platform_data_root_directory": root,
                                   deployment_key: "qa-" + service}
                        self.assertEqual(expected_name, RENDER(values[name_key]).render(context))
                        self.assertEqual(root + "/qa-" + service,
                                         RENDER(values[data_key]).render(context))

    def test_vault_config_and_installer_pki_are_separate(self):
        vault = defaults("vault", "vault", "vault_tls")
        self.assertEqual("/etc/vault", RENDER(vault["platform_vault_config_root"]).render(platform_vault_name="vault"))
        self.assertEqual("/etc/platform-vault", RENDER(vault["platform_vault_config_root"]).render(platform_vault_name="platform-vault"))
        pki = yaml.safe_load((ROOT / "ansible-core/collections/ansible_collections/platform/core/roles/"
                              "pki_materialize/defaults/main.yml").read_text())
        self.assertEqual("/etc/platform-installer/pki", pki["platform_pki_policy_defaults"]["targetRoot"])


if __name__ == "__main__":
    unittest.main()

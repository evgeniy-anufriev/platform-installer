import hashlib
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from jinja2 import Environment


ROLE = Path(__file__).resolve().parents[1] / "ansible_collections/platform/clickhouse/roles/clickhouse_tls"


class ClickHouseSQLUserManagementTests(unittest.TestCase):
    def test_default_user_can_manage_sql_accounts_and_uses_private_member_storage(self):
        environment = Environment(autoescape=False)
        environment.filters["hash"] = lambda value, algorithm: hashlib.new(algorithm, value.encode()).hexdigest()
        user_template = environment.from_string((ROLE / "templates/users.xml.j2").read_text(encoding="utf-8"))
        user_xml = ET.fromstring(user_template.render(_platform_clickhouse_default_password="fixture-password"))
        self.assertEqual("1", user_xml.findtext("./users/default/access_management"))
        self.assertNotIn("fixture-password", ET.tostring(user_xml, encoding="unicode"))

        server_template = environment.from_string((ROLE / "templates/server.xml.j2").read_text(encoding="utf-8"))
        member = {
            "id": "clickhouse-1",
            "address": "192.0.2.10",
            "data_directory": "/var/lib/platform-clickhouse/example/clickhouse-1",
            "config_directory": "/etc/platform-clickhouse/example/clickhouse-1",
            "log_directory": "/var/log/platform-clickhouse/example/clickhouse-1",
            "https_port": 8443,
            "native_port": 9440,
            "interserver_port": 9010,
        }
        server_xml = ET.fromstring(server_template.render(
            clickhouse_member=member,
            platform_clickhouse_mode="standalone",
            _platform_clickhouse_instances=[],
        ))
        self.assertEqual(member["data_directory"] + "/access/", server_xml.findtext("access_control_path"))

    def test_raft_ha_exposes_default_cluster_for_secure_distributed_ddl(self):
        environment = Environment(autoescape=False)
        server_template = environment.from_string((ROLE / "templates/server.xml.j2").read_text(encoding="utf-8"))
        members = [
            {"id": f"clickhouse-{index}", "address": f"192.0.2.{index}", "native_port": 9440 + index}
            for index in range(1, 4)
        ]
        rendered = server_template.render(
            clickhouse_member=members[0],
            platform_clickhouse_mode="raft-ha",
            _platform_clickhouse_instances=members,
        )
        server_xml = ET.fromstring(rendered)
        replicas = server_xml.findall("./remote_servers/default/shard/replica")
        self.assertEqual(3, len(replicas))
        self.assertEqual([member["address"] for member in members], [replica.findtext("host") for replica in replicas])
        self.assertEqual([str(member["native_port"]) for member in members], [replica.findtext("port") for replica in replicas])
        self.assertTrue(all(replica.findtext("secure") == "1" for replica in replicas))

    def test_access_control_directory_is_preflighted_and_created_private(self):
        import yaml

        provision = yaml.safe_load((ROLE / "tasks/provision.yml").read_text(encoding="utf-8"))
        task = next(item for item in provision if item.get("name") ==
                    "Create private persistent SQL access-control directories")
        self.assertEqual("{{ item.data_directory }}/access", task["ansible.builtin.file"]["path"])
        self.assertEqual("0700", task["ansible.builtin.file"]["mode"])

        safety = yaml.safe_load((ROLE / "tasks/path_safety.yml").read_text(encoding="utf-8"))
        inspection = next(item for item in safety if item.get("name") ==
                          "Inspect member, SQL access-control and private PKI paths without following links")
        self.assertIn("access_control_directory", inspection["loop"])


if __name__ == "__main__":
    unittest.main()

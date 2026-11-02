"""Check SZI package projections with representative placements."""

import copy
import json
import pathlib
import unittest

import jinja2
import yaml


ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = ROOT / "application-packages/grant-access/1.0.0/roles/application_grant-access/defaults/main.yml"
LIBRARY = ROOT / "library-packages/szi/1.0.0/roles/library_szi/defaults/main.yml"
BASE_COMPOSE = ROOT / "library-packages/szi/1.0.0/roles/library_szi/templates/.base_compose.yml.j2"


def combine(left, right, recursive=False):
    merged = copy.deepcopy(left)
    for key, value in right.items():
        if recursive and isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = combine(merged[key], value, recursive=True)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


class GrantAccessProjectionTest(unittest.TestCase):
    def test_keycloak_env_uses_own_placements_and_published_ports(self):
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        env.filters['combine'] = combine
        path = ROOT / 'application-packages/keycloak/1.0.0/roles/application_keycloak/defaults/main.yml'
        defaults = yaml.safe_load(path.read_text())['platform_application_definition']['defaults']
        self.assertNotIn('parameters', defaults)
        def placement(library, host, port):
            return dict(libraryId=library, slotId='keycloak', hostId=host,
                        application={'definition': {'defaults': {'ports': defaults['ports']}}},
                        slot={'overrides': {}}, instance={'overrides': {}},
                        hostOverride={'ports': {'port-2': {'published': port}}})
        jobs = [placement('szi', 'app2', 17800), placement('other', 'node1', 27800), placement('szi', 'app1', 7800)]
        context = dict(application_job=jobs[0], library_instance_id='szi', _application_inputs={'jobs': jobs},
                       hostvars={'app1': {'ansible_host': '10.0.0.11'}, 'app2': {'ansible_host': '10.0.0.12'}})
        values = {key: env.from_string(str(defaults['environment'][key])).render(context)
                  for key in ('KC_INITIAL_HOSTS', 'KC_EXTERNAL_ADDR', 'JGROUPS_DISCOVERY_EXTERNAL_IP',
                              'KC_SPI_STICKY_SESSION_ENCODER_INFINISPAN_NODE_NAME', 'KEYCLOAK_MEMORY_LIMIT')}
        self.assertEqual('10.0.0.11[7800],10.0.0.12[17800]', values['KC_INITIAL_HOSTS'])
        self.assertEqual('10.0.0.12', values['KC_EXTERNAL_ADDR'])
        self.assertEqual('10.0.0.12', values['JGROUPS_DISCOVERY_EXTERNAL_IP'])
        self.assertEqual('app2', values['KC_SPI_STICKY_SESSION_ENCODER_INFINISPAN_NODE_NAME'])
        self.assertEqual('2G', values['KEYCLOAK_MEMORY_LIMIT'])

    def test_application_parameters_only_contain_structured_settings(self):
        for family in ('szi', 'sdku'):
            for path in (ROOT.parent / family / 'application-packages').glob('*/*/roles/*/defaults/main.yml'):
                defaults = yaml.safe_load(path.read_text())['platform_application_definition']['defaults']
                self.assertLessEqual(set(defaults.get('parameters') or {}), {'IDENTITY_CLIENT', 'mount_sources'}, str(path))

    def test_endpoints_and_cluster_use_identity_placements_and_effective_ports(self):
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        env.filters["combine"] = combine
        env.filters["to_json"] = json.dumps
        app = yaml.safe_load(APP.read_text(encoding="utf-8"))["platform_application_definition"]
        library = yaml.safe_load(LIBRARY.read_text(encoding="utf-8"))["platform_library_definition"]
        self.assertEqual("application-name", library["instance_id_strategy"])
        ports = app["defaults"]["ports"]

        def placement(host, published):
            return {
                "libraryId": "szi-main",
                "slotId": "grant-access",
                "hostId": host,
                "application": {"name": "grant-access", "definition": {"defaults": {"ports": ports}}},
                "slot": {"overrides": {}},
                "instance": {"overrides": {}},
                "hostOverride": {"ports": {"port-2": {"published": published}}},
            }

        current = placement("node-b", 6701)
        jobs = [placement("node-c", 6702), current, placement("node-a", 6700)]
        context = {
            "application_job": current,
            "application_parameters": {"SZI_REALM": "master", "HZ_CLUSTERNAME": "szi-main"},
            "application_connections": {"sso": {"url": "https://keycloak.internal.example",
                                                   "parameters": {"realm": "master", "proxy_url": "https://nginx.internal.example"}}},
            "library_instance_id": "szi-main",
            "library_runtime": {"connections": {"postgres": {"targets": [{"address": "10.0.0.1", "port": 5432}]}}},
            "groups": {"all": ["node-c", "node-a", "node-b"]},
            "hostvars": {"node-a": {"ansible_host": "10.0.0.1"}, "node-b": {"ansible_host": "10.0.0.2"},
                         "node-c": {"ansible_host": "10.0.0.3"}},
            "_application_inputs": {"jobs": jobs},
            "platform_desired_state": {
                "endpointGroups": {
                    "internal": {"address": {"domain": "internal.example"}},
                },
                "applicationLibraryDeployments": {
                    "szi-main": {
                        "applications": {
                            "keycloak": {"overrides": {"endpoint": {"endpoint_group": "internal"}}},
                            "nginx": {"overrides": {"endpoint": {"endpoint_group": "internal"}}},
                        },
                    },
                },
            },
        }
        rendered = {
            key: env.from_string(str(value)).render(context)
            for key, value in app["defaults"]["environment"].items()
            if key in {
                "APIPROVIDER_CLIENT_ID", "KEYCLOAK_CLIENT_HOST", "KEYCLOAK_CLIENT_REALM", "NGINX_URL",
                "HZ_CLUSTERNAME", "HZ_NETWORK_PUBLICADDRESS", "HZ_NETWORK_PORT",
                "HZ_NETWORK_JOIN_TCPIP_MEMBERS", "SERVER_PORT",
            }
        }
        self.assertEqual("https://keycloak.internal.example", rendered["KEYCLOAK_CLIENT_HOST"])
        self.assertEqual("https://nginx.internal.example", rendered["NGINX_URL"])
        self.assertEqual("master", rendered["KEYCLOAK_CLIENT_REALM"])
        self.assertEqual("grant-access", rendered["APIPROVIDER_CLIENT_ID"])
        self.assertEqual("szi-main", rendered["HZ_CLUSTERNAME"])
        self.assertEqual("10.0.0.2:6701", rendered["HZ_NETWORK_PUBLICADDRESS"])
        self.assertEqual("5701", rendered["HZ_NETWORK_PORT"])
        self.assertEqual("8011", rendered["SERVER_PORT"])
        self.assertEqual(
            "10.0.0.1:6700,10.0.0.2:6701,10.0.0.3:6702",
            rendered["HZ_NETWORK_JOIN_TCPIP_MEMBERS"],
        )
        self.assertNotIn('HZ_CLUSTERNAME', library['defaults']['parameters'])
        self.assertNotIn('SZI_REALM', library['defaults']['parameters'])
        base = env.from_string(BASE_COMPOSE.read_text(encoding="utf-8")).render(context)
        for number in (1, 2, 3):
            self.assertIn(f'"SERVER_{number}_IP": "${{SERVER_{number}_IP}}"', base)


if __name__ == "__main__":
    unittest.main()

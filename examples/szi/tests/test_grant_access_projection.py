"""Check SZI package projections with representative placements."""

import copy
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
    def test_endpoints_and_cluster_use_identity_placements_and_effective_ports(self):
        env = jinja2.Environment(undefined=jinja2.StrictUndefined)
        env.filters["combine"] = combine
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
            "library_instance_id": "szi-main",
            "groups": {"all": ["node-c", "node-a", "node-b"]},
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
        self.assertEqual("$${SERVER_2_IP}:6701", rendered["HZ_NETWORK_PUBLICADDRESS"])
        self.assertEqual("5701", rendered["HZ_NETWORK_PORT"])
        self.assertEqual("8011", rendered["SERVER_PORT"])
        self.assertEqual(
            "$${SERVER_1_IP}:6700,$${SERVER_2_IP}:6701,$${SERVER_3_IP}:6702",
            rendered["HZ_NETWORK_JOIN_TCPIP_MEMBERS"],
        )
        self.assertEqual(
            "szi-main",
            env.from_string(library["defaults"]["parameters"]["HZ_CLUSTERNAME"]).render(context),
        )
        base = env.from_string(BASE_COMPOSE.read_text(encoding="utf-8")).render(context)
        for number in (1, 2, 3):
            self.assertIn(f'"SERVER_{number}_IP": "${{SERVER_{number}_IP}}"', base)


if __name__ == "__main__":
    unittest.main()

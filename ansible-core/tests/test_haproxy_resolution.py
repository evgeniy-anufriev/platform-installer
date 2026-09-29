import importlib.util
import copy
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "collections", "ansible_collections", "platform", "core", "plugins", "module_utils")
sys.path.insert(0, ROOT)

def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

ENDPOINTS = load("service_endpoint_resolution")
HAPROXY = load("haproxy_resolution")

CATALOG = {"definitions": {"haproxy": {"endpoint": {}}, "postgresql": {"endpoint": {}}}}
TOPOLOGY = {"endpointGroups": {"asutp": {"address": {"domain": "asutp.scada.local", "wildcard": True}}}, "serviceDeployments": {
    "haproxy": {"serviceType": "haproxy", "mode": "https-host-routing", "endpointGroup": "asutp", "configuration": {"tlsProfile": "platform-tls"}},
    "postgres-main": {"serviceType": "postgresql", "mode": "standalone", "endpointGroup": "asutp", "configuration": {"port": 5432}, "haproxy": {"deploymentRef": "haproxy", "backend": {"ssl": False, "check": False}}},
}}
PLACEMENT = {"node1": {"haproxy": {"hostEndpoint": True}}, "node2": {"haproxy": {"hostEndpoint": True}}, "node3": {"haproxy": {"hostEndpoint": False}, "postgres-main": {}}}
HOSTS = {"node1": {"ansible_host": "192.0.2.1"}, "node2": {"ansible_host": "192.0.2.2"}, "node3": {"ansible_host": "192.0.2.3"}}
DEFAULTS = {"postgresql": {"balance": "leastconn", "check": True, "fall": 3, "rise": 2, "ssl": True, "sslVerify": "required"}}

class HAProxyResolutionTests(unittest.TestCase):
    def test_host_endpoint_is_opt_in(self):
        result = ENDPOINTS.resolve_service_endpoints(TOPOLOGY, CATALOG, inventory_deployments=PLACEMENT)
        self.assertEqual("PASS", result["status"], result["findings"])
        self.assertEqual("haproxy.asutp.scada.local", result["endpoints"]["haproxy"]["fqdn"])
        self.assertEqual(["haproxy--node1", "haproxy--node2"], sorted(result["hostEndpoints"]))

    def test_partial_override_normalizes_dependencies(self):
        effective, findings = HAPROXY.normalize_backend_settings(DEFAULTS["postgresql"], {"ssl": False, "check": False}, "x")
        self.assertFalse(findings)
        self.assertEqual({"balance": "leastconn", "ssl": False, "check": False}, effective)

    def test_relation_uses_configuration_port_and_deterministic_target(self):
        endpoints = ENDPOINTS.resolve_service_endpoints(TOPOLOGY, CATALOG, inventory_deployments=PLACEMENT)
        result = HAPROXY.resolve_haproxy_backends(TOPOLOGY, CATALOG, HOSTS, PLACEMENT, endpoints, DEFAULTS)
        self.assertEqual("PASS", result["status"], result["findings"])
        backend = result["backends"]["haproxy"][0]
        self.assertEqual(5432, backend["targets"][0]["port"])
        self.assertEqual("30-backend-postgres-main-asutp.cfg", backend["configFileName"])
        self.assertNotIn("sslVerify", backend["settings"])
        self.assertNotIn("fall", backend["settings"])

    def test_missing_port_is_blocked(self):
        topology = {key: value for key, value in TOPOLOGY.items()}
        topology["serviceDeployments"] = {key: dict(value) for key, value in TOPOLOGY["serviceDeployments"].items()}
        topology["serviceDeployments"]["postgres-main"]["configuration"] = {}
        endpoints = ENDPOINTS.resolve_service_endpoints(topology, CATALOG, inventory_deployments=PLACEMENT)
        result = HAPROXY.resolve_haproxy_backends(topology, CATALOG, HOSTS, PLACEMENT, endpoints, DEFAULTS)
        self.assertIn("HAPROXY_BACKEND_PORT_UNRESOLVED", [item["code"] for item in result["findings"]])

    def test_resolved_role_default_port_is_used_when_not_explicit(self):
        topology = {key: value for key, value in TOPOLOGY.items()}
        topology["serviceDeployments"] = {key: dict(value) for key, value in TOPOLOGY["serviceDeployments"].items()}
        topology["serviceDeployments"]["postgres-main"]["configuration"] = {}
        endpoints = ENDPOINTS.resolve_service_endpoints(topology, CATALOG, inventory_deployments=PLACEMENT)
        configuration = {"services": {"postgres-main": {"configuration": {
            "port": {"state": "RESOLVED", "source": "ROLE_DEFAULT", "value": 5432}
        }}}}
        result = HAPROXY.resolve_haproxy_backends(
            topology, CATALOG, HOSTS, PLACEMENT, endpoints, DEFAULTS, configuration
        )
        self.assertEqual("PASS", result["status"], result["findings"])
        self.assertEqual(5432, result["backends"]["haproxy"][0]["targets"][0]["port"])

    def test_unique_deployment_listener_default_port_is_used_before_configuration_resolution(self):
        topology = {key: value for key, value in TOPOLOGY.items()}
        topology["serviceDeployments"] = {key: dict(value) for key, value in TOPOLOGY["serviceDeployments"].items()}
        topology["serviceDeployments"]["postgres-main"]["configuration"] = {}
        catalog = {"definitions": dict(CATALOG["definitions"])}
        catalog["definitions"]["postgresql"] = {
            "endpoint": {}, "listeners": {"client": {"scope": "deployment", "defaultPort": 5432}}
        }
        endpoints = ENDPOINTS.resolve_service_endpoints(topology, catalog, inventory_deployments=PLACEMENT)
        result = HAPROXY.resolve_haproxy_backends(topology, catalog, HOSTS, PLACEMENT, endpoints, DEFAULTS)
        self.assertEqual("PASS", result["status"], result["findings"])
        self.assertEqual(5432, result["backends"]["haproxy"][0]["targets"][0]["port"])

    def test_removed_relation_is_absent_from_the_rebuilt_full_backend_model(self):
        topology = {key: value for key, value in TOPOLOGY.items()}
        topology["serviceDeployments"] = {key: dict(value) for key, value in TOPOLOGY["serviceDeployments"].items()}
        topology["serviceDeployments"]["postgres-main"].pop("haproxy")
        endpoints = ENDPOINTS.resolve_service_endpoints(topology, CATALOG, inventory_deployments=PLACEMENT)
        result = HAPROXY.resolve_haproxy_backends(topology, CATALOG, HOSTS, PLACEMENT, endpoints, DEFAULTS)
        self.assertEqual({}, result["backends"])

    def test_inventory_owned_members_are_used_for_member_scoped_backend(self):
        catalog = copy.deepcopy(CATALOG)
        catalog["definitions"]["vault"] = {
            "endpoint": {}, "listeners": {"client": {"scope": "member", "defaultPort": 8200}},
            "configuration": {"settings": {"port": {"scopes": ["deployment", "member"]}}},
            "x-backendClientListener": {"listener": "client", "allocation": {"kind": "HOST_LOCAL_ORDINAL", "stride": 2}},
        }
        topology = copy.deepcopy(TOPOLOGY)
        topology["serviceDeployments"]["vault-ha"] = {
            "serviceType": "vault", "endpointGroup": "asutp",
            "haproxy": {"deploymentRef": "haproxy", "backend": {"balance": "roundrobin", "ssl": True,
                                                                        "sslVerify": "required", "check": True, "fall": 2, "rise": 2}},
        }
        inventory = copy.deepcopy(PLACEMENT)
        inventory["node1"]["vault-ha"] = {"members": {"vault-1": {"roles": ["vault"]}}}
        inventory["node2"]["vault-ha"] = {"members": {"vault-2": {"roles": ["vault"]}}}
        inventory["node3"]["vault-ha"] = {"members": {"vault-3": {"roles": ["vault"]}}}
        endpoints = ENDPOINTS.resolve_service_endpoints(topology, catalog, inventory_deployments=inventory)
        result = HAPROXY.resolve_haproxy_backends(topology, catalog, HOSTS, inventory, endpoints, DEFAULTS)
        self.assertEqual("PASS", result["status"], result["findings"])
        backend = next(item for item in result["backends"]["haproxy"] if item["targetDeploymentId"] == "vault-ha")
        self.assertEqual(["vault-1", "vault-2", "vault-3"], [item["memberId"] for item in backend["targets"]])
        self.assertEqual([8200, 8200, 8200], [item["port"] for item in backend["targets"]])

    def test_member_client_port_uses_host_local_ordinals_without_host_deduplication(self):
        catalog = copy.deepcopy(CATALOG)
        catalog["definitions"]["vault"] = {
            "endpoint": {}, "listeners": {"client": {"scope": "member", "defaultPort": 8200}},
            "configuration": {"settings": {"port": {"scopes": ["deployment", "member"]}}},
            "x-backendClientListener": {"listener": "client", "allocation": {"kind": "HOST_LOCAL_ORDINAL", "stride": 2}},
        }
        topology = copy.deepcopy(TOPOLOGY)
        topology["serviceDeployments"]["vault-ha"] = {
            "serviceType": "vault", "endpointGroup": "asutp", "members": {
                "vault-1": {"host": "node1"}, "vault-2": {"host": "node1"},
                "vault-3": {"host": "node1", "configuration": {"port": 8210}},
            },
            "haproxy": {"deploymentRef": "haproxy", "backend": {"balance": "roundrobin", "ssl": True,
                                                                "sslVerify": "required", "check": True, "fall": 2, "rise": 2}},
        }
        endpoints = ENDPOINTS.resolve_service_endpoints(topology, catalog, inventory_deployments=PLACEMENT)
        result = HAPROXY.resolve_haproxy_backends(topology, catalog, HOSTS, PLACEMENT, endpoints, DEFAULTS)
        self.assertEqual("PASS", result["status"], result["findings"])
        targets = next(item for item in result["backends"]["haproxy"] if item["targetDeploymentId"] == "vault-ha")["targets"]
        self.assertEqual([8200, 8202, 8210], [item["port"] for item in targets])
        self.assertEqual(["vault-1", "vault-2", "vault-3"], [item["memberId"] for item in targets])
        topology["serviceDeployments"]["vault-ha"]["members"]["vault-2"]["host"] = "node2"
        topology["serviceDeployments"]["vault-ha"]["members"]["vault-3"]["host"] = "node3"
        topology["serviceDeployments"]["vault-ha"]["members"]["vault-3"].pop("configuration")
        result = HAPROXY.resolve_haproxy_backends(topology, catalog, HOSTS, PLACEMENT, endpoints, DEFAULTS)
        self.assertEqual("PASS", result["status"], result["findings"])
        targets = next(item for item in result["backends"]["haproxy"] if item["targetDeploymentId"] == "vault-ha")["targets"]
        self.assertEqual([8200, 8200, 8200], [item["port"] for item in targets])
        fqdn = endpoints["endpoints"]["vault-ha"]["fqdn"]
        requests = [{"dnsNames": [fqdn], "consumers": [
            {"deploymentId": "vault-ha", "memberId": item["memberId"], "hostId": item["hostId"]}
            for item in targets]}]
        result = HAPROXY.resolve_haproxy_backends(topology, catalog, HOSTS, PLACEMENT,
                                                  endpoints, DEFAULTS, pki_requests=requests)
        backend = next(item for item in result["backends"]["haproxy"] if item["targetDeploymentId"] == "vault-ha")
        self.assertEqual(fqdn, backend["expectedServerName"])
        requests[0]["dnsNames"] = ["*.asutp.scada.local"]
        result = HAPROXY.resolve_haproxy_backends(topology, catalog, HOSTS, PLACEMENT,
                                                  endpoints, DEFAULTS, pki_requests=requests)
        self.assertEqual("PASS", result["status"], result["findings"])
        requests[0]["dnsNames"] = ["wrong.example.test"]
        result = HAPROXY.resolve_haproxy_backends(topology, catalog, HOSTS, PLACEMENT,
                                                  endpoints, DEFAULTS, pki_requests=requests)
        self.assertIn("HAPROXY_BACKEND_TLS_IDENTITY_UNRESOLVED", [item["code"] for item in result["findings"]])

    def test_pkix_wildcard_covers_only_one_dns_label(self):
        self.assertTrue(HAPROXY._request_dns_covers_name(["*.asutp.scada.local"], "vault.asutp.scada.local"))
        self.assertFalse(HAPROXY._request_dns_covers_name(["*.asutp.scada.local"], "a.vault.asutp.scada.local"))
        self.assertFalse(HAPROXY._request_dns_covers_name(["*.asutp.scada.local"], "vault.other.scada.local"))

if __name__ == "__main__":
    unittest.main()

import importlib.util
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

    def test_removed_relation_is_absent_from_the_rebuilt_full_backend_model(self):
        topology = {key: value for key, value in TOPOLOGY.items()}
        topology["serviceDeployments"] = {key: dict(value) for key, value in TOPOLOGY["serviceDeployments"].items()}
        topology["serviceDeployments"]["postgres-main"].pop("haproxy")
        endpoints = ENDPOINTS.resolve_service_endpoints(topology, CATALOG, inventory_deployments=PLACEMENT)
        result = HAPROXY.resolve_haproxy_backends(topology, CATALOG, HOSTS, PLACEMENT, endpoints, DEFAULTS)
        self.assertEqual({}, result["backends"])

if __name__ == "__main__":
    unittest.main()

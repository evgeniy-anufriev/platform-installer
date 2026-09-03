import importlib.util
import os
import sys
import unittest


ROOT = os.path.join(os.path.dirname(__file__), "..", "collections", "ansible_collections", "platform", "core", "plugins", "module_utils")
sys.path.insert(0, ROOT)
spec = importlib.util.spec_from_file_location("service_integration_resolution", os.path.join(ROOT, "service_integration_resolution.py"))
INTEGRATIONS = importlib.util.module_from_spec(spec)
sys.modules["service_integration_resolution"] = INTEGRATIONS
spec.loader.exec_module(INTEGRATIONS)


class ServiceIntegrationResolutionTests(unittest.TestCase):
    def state(self):
        return {"endpointGroups": {"asutp": {"address": {"domain": "asutp.scada.local", "wildcard": False}}}, "serviceDeployments": {
            "bind-main": {"serviceType": "bind", "configuration": {"zone": "scada.local"}},
            "haproxy-main": {"serviceType": "haproxy", "endpointGroup": "asutp"},
            "postgres-a": {"serviceType": "postgresql", "endpointGroup": "asutp", "haproxy": {"deploymentRef": "haproxy-main"}},
            "postgres-b": {"serviceType": "postgresql", "endpointGroup": "asutp", "haproxy": {"deploymentRef": "haproxy-main"}},
        }}

    def test_no_matching_source_is_a_deterministic_no_op(self):
        result = INTEGRATIONS.resolve_service_integrations(self.state(), ["kafka"])
        self.assertEqual([], result["integrations"]["dnsDeployments"])
        self.assertEqual([], result["integrations"]["haproxyDeployments"])

    def test_endpoint_and_haproxy_relations_deduplicate_providers(self):
        result = INTEGRATIONS.resolve_service_integrations(self.state(), ["postgresql"])
        self.assertEqual(["bind-main"], result["integrations"]["dnsDeployments"])
        self.assertEqual(["haproxy-main"], result["integrations"]["haproxyDeployments"])

    def test_relations_preserve_source_identity_for_read_only_consumers(self):
        relations = INTEGRATIONS.service_integration_relations(self.state(), ["postgresql"])
        self.assertEqual(["postgres-a", "postgres-b"], [item["sourceDeploymentId"] for item in relations])
        self.assertEqual(["bind-main"], relations[0]["dnsDeploymentIds"])
        self.assertEqual("haproxy-main", relations[0]["haproxyDeploymentId"])

    def test_haproxy_source_does_not_reconcile_itself(self):
        result = INTEGRATIONS.resolve_service_integrations(self.state(), ["haproxy"])
        self.assertEqual(["bind-main"], result["integrations"]["dnsDeployments"])
        self.assertEqual([], result["integrations"]["haproxyDeployments"])


if __name__ == "__main__":
    unittest.main()

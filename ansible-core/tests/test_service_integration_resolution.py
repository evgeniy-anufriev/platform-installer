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
    def placements(self):
        return {"node1": {"vip": {}, "haproxy-main": {}},
                "node2": {"haproxy-main": {}}}

    def test_selection_uses_keepalived_overlap_and_ignores_legacy_reference(self):
        state = self.state()
        state["serviceDeployments"]["postgres-a"]["haproxy"]["deploymentRef"] = "missing"
        state["serviceDeployments"]["other-proxy"] = {"serviceType": "haproxy", "endpointGroup": "other"}
        state["serviceDeployments"]["second-proxy"] = {"serviceType": "haproxy", "endpointGroup": "asutp"}
        placements = self.placements()
        placements["node1"].update({"other-proxy": {}, "second-proxy": {}})
        result = INTEGRATIONS.resolve_service_integrations(state, ["postgresql"], inventory_deployments=placements)
        self.assertEqual(["haproxy-main", "second-proxy"], result["integrations"]["haproxyDeployments"])
        self.assertEqual(["node1"], result["integrations"]["haproxyHosts"])
        self.assertEqual({"haproxy-main": ["node1"], "second-proxy": ["node1"]},
                         result["integrations"]["sources"][0]["haproxyHostsByDeployment"])

    def test_missing_provider_does_not_block_dns_or_service_installation(self):
        result = INTEGRATIONS.resolve_service_integrations(self.state(), ["postgresql"], inventory_deployments={})
        self.assertEqual("PASS", result["status"])
        self.assertEqual(["bind-main"], result["integrations"]["dnsDeployments"])
        self.assertEqual([], result["integrations"]["haproxyDeployments"])
        self.assertEqual(["postgres-a", "postgres-b"], result["integrations"]["missingHAProxySources"])

    def state(self):
        return {"endpointGroups": {"asutp": {"address": {"domain": "asutp.scada.local", "wildcard": False}}}, "serviceDeployments": {
            "bind-main": {"serviceType": "bind", "configuration": {"zone": "scada.local"}},
            "haproxy-main": {"serviceType": "haproxy", "endpointGroup": "asutp"},
            "vip": {"serviceType": "keepalived", "endpointGroupRef": "asutp"},
            "postgres-a": {"serviceType": "postgresql", "endpointGroup": "asutp", "haproxy": {"deploymentRef": "haproxy-main"}},
            "postgres-b": {"serviceType": "postgresql", "endpointGroup": "asutp", "haproxy": {"deploymentRef": "haproxy-main"}},
        }}

    def test_no_matching_source_is_a_deterministic_no_op(self):
        result = INTEGRATIONS.resolve_service_integrations(self.state(), ["kafka"])
        self.assertEqual([], result["integrations"]["dnsDeployments"])
        self.assertEqual([], result["integrations"]["haproxyDeployments"])

    def test_endpoint_and_haproxy_relations_deduplicate_providers(self):
        result = INTEGRATIONS.resolve_service_integrations(self.state(), ["postgresql"], inventory_deployments=self.placements())
        self.assertEqual(["bind-main"], result["integrations"]["dnsDeployments"])
        self.assertEqual(["haproxy-main"], result["integrations"]["haproxyDeployments"])

    def test_relations_preserve_source_identity_for_read_only_consumers(self):
        relations = INTEGRATIONS.service_integration_relations(self.state(), ["postgresql"], inventory_deployments=self.placements())
        self.assertEqual(["postgres-a", "postgres-b"], [item["sourceDeploymentId"] for item in relations])
        self.assertEqual(["bind-main"], relations[0]["dnsDeploymentIds"])
        self.assertEqual(["haproxy-main"], relations[0]["haproxyDeploymentIds"])

    def test_haproxy_source_does_not_reconcile_itself(self):
        result = INTEGRATIONS.resolve_service_integrations(self.state(), ["haproxy"])
        self.assertEqual(["bind-main"], result["integrations"]["dnsDeployments"])
        self.assertEqual([], result["integrations"]["haproxyDeployments"])

    def test_source_deployment_selector_returns_only_its_provider_relations(self):
        result = INTEGRATIONS.resolve_service_integrations(
            self.state(), [], source_deployment_id="postgres-b", inventory_deployments=self.placements())
        self.assertEqual("PASS", result["status"])
        self.assertEqual(["postgres-b"], [item["sourceDeploymentId"]
                                           for item in result["integrations"]["sources"]])
        self.assertEqual(["bind-main"], result["integrations"]["dnsDeployments"])
        self.assertEqual(["haproxy-main"], result["integrations"]["haproxyDeployments"])

    def test_unknown_source_deployment_fails_closed(self):
        result = INTEGRATIONS.resolve_service_integrations(
            self.state(), [], source_deployment_id="missing")
        self.assertEqual("BLOCKED", result["status"])
        self.assertEqual("SERVICE_INTEGRATION_SOURCE_NOT_FOUND", result["findings"][0]["code"])


if __name__ == "__main__":
    unittest.main()

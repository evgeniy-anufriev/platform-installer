import copy
import importlib.util
import os
import sys
import unittest


ROOT = os.path.join(os.path.dirname(__file__), "..", "collections", "ansible_collections", "platform", "core", "plugins", "module_utils")
sys.path.insert(0, ROOT)


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ENDPOINTS = load_module("service_endpoint_resolution", "service_endpoint_resolution.py")


def catalog():
    return {"definitions": {
        "postgresql": {"endpoint": {}},
        "kafka": {"listeners": {"client": {"protocol": "tcp", "defaultPort": 9092}}},
        "test-http": {"endpoint": {}},
    }}


def topology(service_type="postgresql", deployment_id="postgres-main", group="asutp"):
    return {
        "endpointGroups": {
            "asutp": {"address": {"domain": "asutp.scada.local", "wildcard": True, "vip": "192.168.6.112"}},
            "dmz": {"address": {"domain": "dmz.scada.local", "wildcard": False, "vip": "192.168.6.111"}},
        },
        "serviceDeployments": {
            deployment_id: {"serviceType": service_type, "endpointGroup": group},
        },
    }


class ServiceEndpointResolutionTests(unittest.TestCase):
    def resolve(self, value=None):
        value = value or topology()
        return ENDPOINTS.resolve_service_endpoints(value, catalog())

    def test_postgresql_endpoint_uses_group(self):
        result = self.resolve()
        self.assertEqual("PASS", result["status"])
        endpoint = result["endpoints"]["postgres-main"]
        self.assertEqual("postgres-main.asutp.scada.local", endpoint["fqdn"])
        self.assertEqual("192.168.6.112", endpoint["address"])
        self.assertEqual(["postgres-main.asutp.scada.local"], endpoint["sanDnsNames"])
        self.assertEqual(["*.asutp.scada.local"], endpoint["wildcardDnsNames"])
        self.assertEqual(["192.168.6.112"], endpoint["sanIpAddresses"])

    def test_domain_or_vip_change_changes_endpoint_fingerprint(self):
        first = self.resolve()
        value = topology()
        value["endpointGroups"]["asutp"]["address"]["vip"] = "192.168.6.113"
        second = self.resolve(value)
        self.assertNotEqual(first["endpointFingerprint"], second["endpointFingerprint"])

    def test_missing_group_is_blocked(self):
        value = topology(group="missing")
        result = self.resolve(value)
        self.assertEqual("ENDPOINT_GROUP_NOT_FOUND", result["findings"][0]["code"])

    def test_invalid_domain_and_vip_are_blocked(self):
        value = topology()
        value["endpointGroups"]["asutp"]["address"]["domain"] = "not a domain"
        self.assertEqual("ENDPOINT_GROUP_DOMAIN_INVALID", self.resolve(value)["findings"][0]["code"])
        value = topology()
        value["endpointGroups"]["asutp"]["address"]["vip"] = "2001:db8::1"
        self.assertEqual("ENDPOINT_GROUP_VIP_INVALID", self.resolve(value)["findings"][0]["code"])

    def test_deployment_id_must_be_dns_label(self):
        value = topology(deployment_id="Postgres_Main")
        result = self.resolve(value)
        self.assertEqual("ENDPOINT_DEPLOYMENT_ID_NOT_DNS_LABEL", result["findings"][0]["code"])

    def test_kafka_assignment_is_explicitly_unsupported(self):
        result = self.resolve(topology(service_type="kafka"))
        self.assertEqual("ENDPOINT_SERVICE_UNSUPPORTED", result["findings"][0]["code"])

    def test_synthetic_service_proves_generic_resolution(self):
        value = topology(service_type="test-http", deployment_id="web-main", group="dmz")
        result = self.resolve(value)
        endpoint = result["endpoints"]["web-main"]
        self.assertEqual(("web-main.dmz.scada.local", "192.168.6.111"), (endpoint["fqdn"], endpoint["address"]))

    def test_resolution_is_deterministic_and_does_not_mutate_inputs(self):
        value = topology()
        original_value = copy.deepcopy(value)
        self.assertEqual(self.resolve(value), self.resolve(value))
        self.assertEqual(original_value, value)


if __name__ == "__main__":
    unittest.main()

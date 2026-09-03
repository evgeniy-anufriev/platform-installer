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


DNS = load_module("dns_resolution", "dns_resolution.py")


def catalog():
    return {"definitions": {
        "bind": {"endpoint": None},
        "postgresql": {"endpoint": {}},
        "keepalived": {"endpointProvider": {}},
    }}


def desired(wildcard=True):
    return {
        "endpointGroups": {"asutp": {"address": {"domain": "asutp.scada.local", "wildcard": wildcard}}},
        "serviceDeployments": {
            "dns-main": {"serviceType": "bind", "configuration": {"zone": "scada.local", "defaultTtl": 300}},
            "postgres-main": {"serviceType": "postgresql", "endpointGroup": "asutp"},
            "keepalived-asutp": {"serviceType": "keepalived", "endpointGroupRef": "asutp", "virtualAddresses": [
                {"address": "192.0.2.111", "interface": "eth1"}, {"address": "192.0.2.112", "interface": "eth2"},
            ]},
        },
    }


def hosts(reverse=False):
    value = {
        "node1": {"ansible_host": "192.0.2.1"}, "node2": {"ansible_host": "192.0.2.2"}, "node3": {"ansible_host": "192.0.2.3"},
    }
    return dict(reversed(list(value.items()))) if reverse else value


def placement():
    return {"node1": {"dns-main": {"roles": ["primary"]}}, "node2": {"dns-main": {"roles": ["secondary"]}}, "node3": {"dns-main": {"roles": ["secondary"]}}}


class DnsResolutionTests(unittest.TestCase):
    def resolve(self, state=None, inventory_hosts=None, inventory_placement=None):
        return DNS.resolve_dns_zones(state or desired(), catalog(), inventory_hosts or hosts(), inventory_placement or placement())

    def test_primary_and_two_secondaries_resolve_all_records(self):
        result = self.resolve()
        self.assertEqual("PASS", result["status"], result["findings"])
        zone = result["zones"]["dns-main"]
        self.assertEqual("node1.scada.local", zone["mname"])
        self.assertEqual(["node2", "node3"], [item["hostId"] for item in zone["secondaries"]])
        records = {(item["owner"], item["type"]): item["values"] for item in zone["records"]}
        self.assertEqual(["192.0.2.1"], records[("node1.scada.local.", "A")])
        self.assertEqual(["192.0.2.111", "192.0.2.112"], records[("postgres-main.asutp.scada.local.", "A")])
        self.assertEqual(["192.0.2.111", "192.0.2.112"], records[("*.asutp.scada.local.", "A")])

    def test_primary_cardinality_and_role_are_closed(self):
        inventory = placement()
        inventory["node1"]["dns-main"]["roles"] = ["primary", "secondary"]
        codes = [item["code"] for item in self.resolve(inventory_placement=inventory)["findings"]]
        self.assertIn("DNS_PARTICIPANT_ROLE_INVALID", codes)
        self.assertIn("DNS_PRIMARY_COUNT_INVALID", codes)

    def test_missing_or_ambiguous_provider_is_blocked(self):
        state = desired()
        del state["serviceDeployments"]["keepalived-asutp"]
        self.assertIn("DNS_ENDPOINT_ADDRESS_UNRESOLVED", [item["code"] for item in self.resolve(state)["findings"]])
        state = desired()
        state["serviceDeployments"]["keepalived-other"] = copy.deepcopy(state["serviceDeployments"]["keepalived-asutp"])
        self.assertIn("DNS_ENDPOINT_PROVIDER_AMBIGUOUS", [item["code"] for item in self.resolve(state)["findings"]])

    def test_wildcard_and_zone_boundary_are_enforced(self):
        result = self.resolve(desired(wildcard=False))
        owners = [item["owner"] for item in result["zones"]["dns-main"]["records"]]
        self.assertNotIn("*.asutp.scada.local.", owners)
        state = desired()
        state["endpointGroups"]["asutp"]["address"]["domain"] = "other.example.com"
        self.assertIn("DNS_ENDPOINT_GROUP_OUTSIDE_ZONE", [item["code"] for item in self.resolve(state)["findings"]])

    def test_host_validation_and_determinism(self):
        invalid = hosts()
        invalid["Node_1"] = invalid.pop("node1")
        self.assertIn("DNS_HOST_ID_INVALID", [item["code"] for item in self.resolve(inventory_hosts=invalid)["findings"]])
        first = self.resolve()
        second = self.resolve(inventory_hosts=hosts(reverse=True), inventory_placement=dict(reversed(list(placement().items()))))
        self.assertEqual(first, second)

    def test_same_domain_exact_endpoint_groups_use_their_own_providers(self):
        state = desired(wildcard=False)
        state["endpointGroups"]["asutp-b"] = {"address": {"domain": "asutp.scada.local", "wildcard": False}}
        state["serviceDeployments"]["postgres-b"] = {"serviceType": "postgresql", "endpointGroup": "asutp-b"}
        state["serviceDeployments"]["keepalived-b"] = {"serviceType": "keepalived", "endpointGroupRef": "asutp-b", "virtualAddresses": [{"address": "192.0.2.113", "interface": "eth1"}]}
        result = self.resolve(state)
        self.assertEqual("PASS", result["status"], result["findings"])
        records = {item["owner"]: item["values"] for item in result["zones"]["dns-main"]["records"]}
        self.assertEqual(["192.0.2.111", "192.0.2.112"], records["postgres-main.asutp.scada.local."])
        self.assertEqual(["192.0.2.113"], records["postgres-b.asutp.scada.local."])

    def test_same_domain_conflicting_wildcards_are_blocked(self):
        state = desired(wildcard=True)
        state["endpointGroups"]["asutp-b"] = {"address": {"domain": "asutp.scada.local", "wildcard": True}}
        state["serviceDeployments"]["postgres-b"] = {"serviceType": "postgresql", "endpointGroup": "asutp-b"}
        state["serviceDeployments"]["keepalived-b"] = {"serviceType": "keepalived", "endpointGroupRef": "asutp-b", "virtualAddresses": [{"address": "192.0.2.113", "interface": "eth1"}]}
        self.assertIn("DNS_RECORD_COLLISION", [item["code"] for item in self.resolve(state)["findings"]])

    def test_removed_endpoint_is_absent_from_the_rebuilt_full_zone_model(self):
        state = desired(wildcard=False)
        del state["serviceDeployments"]["postgres-main"]
        result = self.resolve(state)
        self.assertEqual("PASS", result["status"], result["findings"])
        owners = [item["owner"] for item in result["zones"]["dns-main"]["records"]]
        self.assertNotIn("postgres-main.asutp.scada.local.", owners)


if __name__ == "__main__":
    unittest.main()

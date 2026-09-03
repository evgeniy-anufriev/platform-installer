import importlib.util
import os
import sys
import unittest


ROOT = os.path.join(os.path.dirname(__file__), "..", "collections", "ansible_collections", "platform", "core", "plugins", "module_utils")
sys.path.insert(0, ROOT)
spec = importlib.util.spec_from_file_location("pki_resolution", os.path.join(ROOT, "pki_resolution.py"))
pki = importlib.util.module_from_spec(spec)
sys.modules["pki_resolution"] = pki
spec.loader.exec_module(pki)


class PkiResolutionTests(unittest.TestCase):
    defaults = {
        "authorityValidityDays": 3650,
        "leafValidityDays": 365,
        "keyAlgorithm": "RSA",
        "keySize": 3072,
        "usages": ["serverAuth"],
        "scope": "HOST",
        "targetRoot": "/etc/platform-installer/pki",
        "sanPolicy": {"includeHostDns": True, "includeHostIp": True, "includeEndpointFqdns": True, "includeEndpointWildcard": False, "includeEndpointVip": False},
        "subject": {"C": "", "ST": "", "L": "", "O": "", "OU": ""},
    }

    def topology(self, scope="HOST"):
        return {
            "certificateAuthorities": {"platform-ca": {"mode": "MANAGED", "commonName": "Platform CA"}},
            "certificateProfiles": {"infrastructure": {"authorityRef": "platform-ca", "sanPolicy": {}}},
            "tlsProfiles": {"platform-tls": {"certificateProfileRef": "infrastructure", "storePasswordSecretRef": "runtime:pki-password", "scope": scope}},
            "serviceDeployments": {
                "service-a": {"serviceType": "kafka", "endpointGroup": "asutp", "configuration": {"tlsProfile": "platform-tls"}, "members": {
                    "member-1": {"host": "node1", "roles": ["server"]},
                    "member-2": {"host": "node2", "roles": ["server"]},
                }},
                "keepalived-asutp": {"endpointGroupRef": "asutp", "virtualAddresses": [
                    {"address": "192.0.2.70", "interface": "eth0"},
                    {"address": "192.0.2.71", "interface": "eth1"},
                ]},
            },
        }

    def test_host_scope_is_default_and_deterministic(self):
        hosts = {"node1": {"ansible_host": "192.0.2.11"}, "node2": {"ansible_host": "192.0.2.12"}}
        first = pki.resolve_certificate_requests("project-a", self.topology(), hosts, self.defaults)
        second = pki.resolve_certificate_requests("project-a", self.topology(), hosts, self.defaults)
        self.assertEqual("PASS", first["status"])
        self.assertEqual(first, second)
        self.assertEqual(2, len(first["requests"]))
        self.assertEqual(["192.0.2.11"], first["requests"][0]["ipAddresses"])
        self.assertIn("certificateRequestFingerprint", first["requests"][0])
        self.assertIn("materializationFingerprint", first["materializationPlans"][0])
        self.assertEqual("runtime:pki-password", first["materializationPlans"][0]["storePasswordSecretRef"])

    def test_member_and_deployment_scopes_are_distinct(self):
        hosts = {"node1": {"ansible_host": "192.0.2.11"}, "node2": {"ansible_host": "192.0.2.12"}}
        self.assertEqual(2, len(pki.resolve_certificate_requests("p", self.topology("MEMBER"), hosts, self.defaults)["requests"]))
        deployment = pki.resolve_certificate_requests("p", self.topology("DEPLOYMENT"), hosts, self.defaults)
        self.assertEqual(1, len(deployment["requests"]))
        self.assertEqual(["192.0.2.11", "192.0.2.12"], deployment["requests"][0]["ipAddresses"])

    def test_unknown_tls_profile_blocks_without_partial_plan(self):
        topology = self.topology()
        topology["serviceDeployments"]["service-a"]["configuration"]["tlsProfile"] = "unknown"
        out = pki.resolve_certificate_requests("p", topology, {"node1": {}, "node2": {}}, self.defaults)
        self.assertEqual("BLOCKED", out["status"])
        self.assertEqual([], out["requests"])
        self.assertEqual("TLS_PROFILE_NOT_FOUND", out["findings"][0]["code"])

    def test_service_tls_profile_is_used_for_ssl_listeners(self):
        topology = self.topology()
        deployment = topology["serviceDeployments"]["service-a"]
        deployment["configuration"]["listeners"] = {
            "CLIENT_SSL": {"purpose": "client", "securityProtocol": "SSL", "port": 9092}
        }
        out = pki.resolve_certificate_requests("p", topology, {"node1": {"ansible_host": "192.0.2.11"}, "node2": {"ansible_host": "192.0.2.12"}}, self.defaults)
        self.assertEqual("PASS", out["status"])
        self.assertEqual("platform-tls", out["materializationPlans"][0]["tlsProfileId"])

    def test_request_change_has_a_new_fingerprint(self):
        hosts = {"node1": {"ansible_host": "192.0.2.11"}, "node2": {"ansible_host": "192.0.2.12"}}
        first = pki.resolve_certificate_requests("p", self.topology(), hosts, self.defaults)["requests"][0]
        changed = self.topology()
        changed["certificateProfiles"]["infrastructure"]["validityDays"] = 90
        second = pki.resolve_certificate_requests("p", changed, hosts, self.defaults)["requests"][0]
        self.assertNotEqual(first["certificateRequestFingerprint"], second["certificateRequestFingerprint"])

    def test_resolver_requires_role_supplied_policy_defaults(self):
        out = pki.resolve_certificate_requests("p", self.topology(), {"node1": {}, "node2": {}})
        self.assertEqual("BLOCKED", out["status"])
        self.assertEqual("PKI_DEFAULTS_INVALID", out["findings"][0]["code"])

    def test_endpoint_sans_are_selected_by_existing_profile_policy(self):
        topology = self.topology("DEPLOYMENT")
        topology["certificateProfiles"]["infrastructure"]["sanPolicy"] = {
            "includeHostDns": False,
            "includeHostIp": False,
            "includeEndpointFqdns": True,
            "includeEndpointWildcard": True,
            "includeEndpointVip": True,
        }
        endpoints = {"endpoints": {"service-a": {
            "endpointGroupId": "asutp",
            "sanDnsNames": ["service-a.asutp.scada.local"],
            "wildcardDnsNames": ["*.asutp.scada.local"],
        }}}
        out = pki.resolve_certificate_requests("p", topology, {"node1": {}, "node2": {}}, self.defaults, endpoints)
        request = out["requests"][0]
        self.assertEqual(["*.asutp.scada.local", "service-a.asutp.scada.local"], request["dnsNames"])
        self.assertEqual(["192.0.2.70", "192.0.2.71"], request["ipAddresses"])

    def test_deployment_scope_covers_all_host_endpoints_on_shared_tls_entrypoint(self):
        topology = self.topology("DEPLOYMENT")
        topology["certificateProfiles"]["infrastructure"]["sanPolicy"] = {
            "includeHostDns": False,
            "includeHostIp": False,
            "includeEndpointFqdns": True,
            "includeEndpointWildcard": False,
            "includeEndpointVip": False,
        }
        endpoints = {
            "endpoints": {"service-a": {"sanDnsNames": ["service-a.asutp.scada.local"]}},
            "hostEndpoints": {
                "service-a--node1": {
                    "serviceDeploymentId": "service-a", "hostId": "node1",
                    "sanDnsNames": ["service-a-node1.asutp.scada.local"],
                },
                "service-a--node2": {
                    "serviceDeploymentId": "service-a", "hostId": "node2",
                    "sanDnsNames": ["service-a-node2.asutp.scada.local"],
                },
            },
        }
        out = pki.resolve_certificate_requests(
            "p", topology, {"node1": {}, "node2": {}}, self.defaults, endpoints
        )
        self.assertEqual(
            [
                "service-a-node1.asutp.scada.local",
                "service-a-node2.asutp.scada.local",
                "service-a.asutp.scada.local",
            ],
            out["requests"][0]["dnsNames"],
        )

    def test_same_host_tls_identity_is_shared_across_service_consumers(self):
        topology = self.topology("HOST")
        topology["certificateProfiles"]["infrastructure"]["sanPolicy"] = {
            "includeHostDns": False,
            "includeHostIp": False,
            "includeEndpointFqdns": True,
            "includeEndpointWildcard": False,
            "includeEndpointVip": False,
        }
        topology["serviceDeployments"]["haproxy"] = {
            "serviceType": "haproxy",
            "endpointGroup": "asutp",
            "configuration": {"tlsProfile": "platform-tls"},
            "members": {"member-3": {"host": "node1", "roles": ["server"]}},
        }
        endpoints = {"endpoints": {
            "service-a": {"endpointGroupId": "asutp", "sanDnsNames": ["postgres.asutp.scada.local"]},
            "haproxy": {"endpointGroupId": "asutp", "sanDnsNames": ["haproxy.asutp.scada.local"]},
        }}
        out = pki.resolve_certificate_requests(
            "p", topology,
            {"node1": {"ansible_host": "192.0.2.11"}, "node2": {"ansible_host": "192.0.2.12"}},
            self.defaults, endpoints,
        )
        self.assertEqual("PASS", out["status"])
        self.assertEqual(2, len(out["requests"]))
        node1 = next(request for request in out["requests"] if request["id"] == "platform-tls--node1")
        self.assertEqual({"service-a", "haproxy"}, {consumer["deploymentId"] for consumer in node1["consumers"]})
        self.assertEqual(["haproxy.asutp.scada.local", "postgres.asutp.scada.local"], node1["dnsNames"])
        self.assertEqual(1, len([plan for plan in out["materializationPlans"] if plan["requestId"] == "platform-tls--node1"]))

    def test_pki_wildcard_policy_is_independent_from_dns_wildcard_publication(self):
        topology = self.topology("DEPLOYMENT")
        topology["certificateProfiles"]["infrastructure"]["sanPolicy"] = {
            "includeHostDns": False,
            "includeHostIp": False,
            "includeEndpointFqdns": True,
            "includeEndpointWildcard": True,
            "includeEndpointVip": False,
        }
        endpoints = {"endpoints": {"service-a": {
            "endpointGroupId": "asutp", "sanDnsNames": ["service-a.asutp.scada.local"],
            "wildcardDnsNames": ["*.asutp.scada.local"],
        }}}
        out = pki.resolve_certificate_requests("p", topology, {"node1": {}, "node2": {}}, self.defaults, endpoints)
        self.assertIn("*.asutp.scada.local", out["requests"][0]["dnsNames"])

    def test_dns_wildcard_does_not_add_a_certificate_wildcard_without_pki_policy(self):
        topology = self.topology("DEPLOYMENT")
        topology["certificateProfiles"]["infrastructure"]["sanPolicy"] = {
            "includeHostDns": False,
            "includeHostIp": False,
            "includeEndpointFqdns": True,
            "includeEndpointWildcard": False,
            "includeEndpointVip": False,
        }
        endpoints = {"endpoints": {"service-a": {
            "endpointGroupId": "asutp", "sanDnsNames": ["service-a.asutp.scada.local"],
            "wildcardDnsNames": ["*.asutp.scada.local"],
        }}}
        out = pki.resolve_certificate_requests("p", topology, {"node1": {}, "node2": {}}, self.defaults, endpoints)
        self.assertNotIn("*.asutp.scada.local", out["requests"][0]["dnsNames"])

    def test_same_domain_pki_wildcards_are_valid_for_distinct_exact_endpoint_groups(self):
        topology = self.topology("DEPLOYMENT")
        topology["serviceDeployments"]["service-b"] = {
            "serviceType": "postgresql", "configuration": {"tlsProfile": "platform-tls"},
            "members": {"member-3": {"host": "node3", "roles": ["server"]}},
        }
        topology["certificateProfiles"]["infrastructure"]["sanPolicy"] = {
            "includeHostDns": False,
            "includeHostIp": False,
            "includeEndpointFqdns": True,
            "includeEndpointWildcard": True,
            "includeEndpointVip": False,
        }
        endpoints = {"endpoints": {
            "service-a": {"endpointGroupId": "asutp-a", "sanDnsNames": ["service-a.asutp.scada.local"], "wildcardDnsNames": ["*.asutp.scada.local"]},
            "service-b": {"endpointGroupId": "asutp-b", "sanDnsNames": ["service-b.asutp.scada.local"], "wildcardDnsNames": ["*.asutp.scada.local"]},
        }}
        out = pki.resolve_certificate_requests("p", topology, {"node1": {}, "node2": {}, "node3": {}}, self.defaults, endpoints)
        self.assertEqual("PASS", out["status"])
        self.assertEqual(2, len(out["requests"]))
        self.assertTrue(all("*.asutp.scada.local" in request["dnsNames"] for request in out["requests"]))

if __name__ == "__main__":
    unittest.main()

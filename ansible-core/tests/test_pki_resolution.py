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
                "service-a": {"configuration": {"tlsProfile": "platform-tls"}, "members": {
                    "member-1": {"host": "node1", "roles": ["server"]},
                    "member-2": {"host": "node2", "roles": ["server"]},
                }}
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


if __name__ == "__main__":
    unittest.main()

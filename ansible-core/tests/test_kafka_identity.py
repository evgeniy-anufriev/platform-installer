import importlib.util
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..", "collections", "ansible_collections", "platform", "core", "plugins", "module_utils")
spec = importlib.util.spec_from_file_location("kafka_identity", os.path.join(ROOT, "kafka_identity.py"))
identity = importlib.util.module_from_spec(spec)
sys.modules["kafka_identity"] = identity
spec.loader.exec_module(identity)


class KafkaIdentityTests(unittest.TestCase):
    def test_generates_complete_new_identity_set_once(self):
        values = iter([b"a" * 16, b"b" * 16, b"c" * 16])
        result = identity.materialize_kafka_identities("k", {}, {"c1": {"roles": ["controller"]}, "c2": {"roles": ["controller"]}}, {"c1": {"state": "UNINITIALIZED"}, "c2": {"state": "UNINITIALIZED"}}, lambda _: next(values))
        self.assertTrue(result["changed"])
        self.assertEqual(2, len(result["patch"]["memberIdentities"]))
        self.assertIn("clusterId", result["patch"]["deploymentIdentity"])

    def test_recovers_and_then_is_a_noop(self):
        metadata = {"c1": {"initialized": True, "clusterId": "cluster", "directoryId": "directory"}}
        first = identity.materialize_kafka_identities("k", {}, {"c1": {"roles": ["controller"]}}, metadata)
        persisted = {"identity": first["patch"]["deploymentIdentity"]}
        members = {"c1": {"roles": ["controller"], "identity": first["patch"]["memberIdentities"]["c1"]}}
        second = identity.materialize_kafka_identities("k", persisted, members, metadata)
        self.assertFalse(second["changed"])

    def test_mismatch_is_blocked_without_patch(self):
        result = identity.materialize_kafka_identities("k", {"identity": {"clusterId": "one"}}, {"c1": {"roles": ["controller"]}}, {"c1": {"initialized": True, "clusterId": "two"}})
        self.assertEqual("BLOCKED", result["status"])

    def test_discovery_requires_exact_member_set_and_known_state(self):
        self.assertEqual([], identity.validate_kafka_discovery(
            ["c1", "b1"],
            [{"memberId": "c1", "state": "UNINITIALIZED"}, {"memberId": "b1", "state": "INITIALIZED"}],
        ))
        findings = identity.validate_kafka_discovery(
            ["c1", "b1"],
            [{"memberId": "c1", "state": "UNKNOWN"}, {"memberId": "c1", "state": "UNKNOWN"}, {"memberId": "x", "state": "INITIALIZED"}],
        )
        codes = {finding["code"] for finding in findings}
        self.assertIn("KAFKA_IDENTITY_DISCOVERY_DUPLICATE", codes)
        self.assertIn("KAFKA_IDENTITY_DISCOVERY_INCOMPLETE", codes)
        self.assertIn("KAFKA_IDENTITY_DISCOVERY_UNKNOWN_MEMBER", codes)
        self.assertIn("KAFKA_IDENTITY_DISCOVERY_UNKNOWN", codes)


if __name__ == "__main__":
    unittest.main()

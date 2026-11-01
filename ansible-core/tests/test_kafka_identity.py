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
    def test_static_fresh_allocates_cluster_only(self):
        result = identity.materialize_kafka_identities('k', {'configuration': {'quorumMode': 'static'}},
            {'c': {'roles': ['controller']}}, {'c': {'state': 'UNINITIALIZED'}}, lambda _: b'a' * 16)
        self.assertEqual('PASS', result['status'])
        self.assertIn('clusterId', result['patch']['deploymentIdentity'])
        self.assertEqual({}, result['patch']['memberIdentities'])

    def test_static_repeat_ignores_unused_pregenerated_directory_id(self):
        result = identity.materialize_kafka_identities('k',
            {'configuration': {'quorumMode': 'static'}, 'identity': {'clusterId': 'cluster'}},
            {'c': {'roles': ['controller'], 'identity': {'directoryId': 'old-generated'}}},
            {'c': {'state': 'INITIALIZED', 'clusterId': 'cluster', 'directoryId': 'assigned-by-kafka'}})
        self.assertEqual('PASS', result['status'])
        self.assertFalse(result['changed'])

    def test_default_static_and_explicit_dynamic_keep_distinct_directory_rules(self):
        members = {'c': {'roles': ['controller'], 'identity': {'directoryId': 'generated'}}}
        metadata = {'c': {'state': 'INITIALIZED', 'clusterId': 'cluster', 'directoryId': 'disk'}}
        deployment = {'identity': {'clusterId': 'cluster'}}
        static = identity.materialize_kafka_identities('k', deployment, members, metadata, default_quorum_mode='static')
        self.assertEqual('PASS', static['status'])
        dynamic = identity.materialize_kafka_identities('k', dict(deployment, configuration={'quorumMode': 'dynamic'}),
            members, metadata, default_quorum_mode='static')
        self.assertEqual('BLOCKED', dynamic['status'])
        self.assertEqual('KAFKA_DIRECTORY_ID_METADATA_MISMATCH', dynamic['findings'][0]['code'])

    def test_static_still_blocks_cluster_conflicts_and_missing_controller(self):
        deployment = {'configuration': {'quorumMode': 'static'}, 'identity': {'clusterId': 'expected'}}
        members = {'c': {'roles': ['controller']}}
        conflict = identity.materialize_kafka_identities('k', deployment, members,
            {'c': {'state': 'INITIALIZED', 'clusterId': 'different'}})
        self.assertEqual('KAFKA_CLUSTER_ID_METADATA_MISMATCH', conflict['findings'][0]['code'])
        missing = identity.materialize_kafka_identities('k', deployment, members, {'other': {'state': 'UNINITIALIZED'}})
        self.assertEqual('KAFKA_IDENTITY_DISCOVERY_INCOMPLETE', missing['findings'][0]['code'])

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

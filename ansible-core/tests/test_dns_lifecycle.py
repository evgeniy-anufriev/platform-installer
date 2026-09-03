import importlib.util
import os
import sys
import unittest


ROOT = os.path.join(os.path.dirname(__file__), "..", "collections", "ansible_collections", "platform", "core", "plugins", "module_utils")
spec = importlib.util.spec_from_file_location("dns_lifecycle", os.path.join(ROOT, "dns_lifecycle.py"))
LIFECYCLE = importlib.util.module_from_spec(spec)
sys.modules["dns_lifecycle"] = LIFECYCLE
spec.loader.exec_module(LIFECYCLE)


def zones():
    return {
        "bind-main": {
            "zone": "scada.local",
            "contentFingerprint": "sha256:new-content",
            "primary": {"hostId": "node1"},
            "secondaries": [{"hostId": "node2"}, {"hostId": "node3"}],
        }
    }


def recovery(**overrides):
    value = {
        "zone": "scada.local",
        "historicalContentFingerprint": "sha256:old-content",
        "observedSerials": {"node1": 1, "node2": 2, "node3": 2},
    }
    value.update(overrides)
    return {"bind-main": value}


class DnsLifecycleRecoveryTests(unittest.TestCase):
    def test_verified_divergent_runtime_recovery_advances_once(self):
        result = LIFECYCLE.recover_dns_lifecycle({}, zones(), recovery())
        self.assertEqual("PASS", result["status"])
        self.assertEqual(3, result["generatedState"]["serviceDeployments"]["bind-main"]["dns"]["currentSerial"])
        self.assertEqual("sha256:new-content", result["generatedState"]["serviceDeployments"]["bind-main"]["dns"]["contentFingerprint"])

    def test_new_root_serial_one_is_not_published_as_a_rollback(self):
        state = {"serviceDeployments": {"bind-main": {"dns": {"contentFingerprint": "sha256:new-content", "currentSerial": 1}}}}
        result = LIFECYCLE.recover_dns_lifecycle(state, zones(), recovery())
        self.assertEqual("PASS", result["status"])
        self.assertEqual(3, result["generatedState"]["serviceDeployments"]["bind-main"]["dns"]["currentSerial"])

    def test_same_content_cannot_adopt_observed_serial_floor(self):
        result = LIFECYCLE.recover_dns_lifecycle({}, zones(), recovery(historicalContentFingerprint="sha256:new-content"))
        self.assertEqual("BLOCKED", result["status"])
        self.assertEqual("BIND_LIFECYCLE_RECOVERY_NOT_A_NEW_REVISION", result["findings"][0]["code"])

    def test_missing_historical_fingerprint_fails_closed(self):
        result = LIFECYCLE.recover_dns_lifecycle({}, zones(), recovery(historicalContentFingerprint=""))
        self.assertEqual("BLOCKED", result["status"])
        self.assertEqual("BIND_LIFECYCLE_RECOVERY_HISTORICAL_FINGERPRINT_REQUIRED", result["findings"][0]["code"])

    def test_participant_set_is_closed(self):
        result = LIFECYCLE.recover_dns_lifecycle({}, zones(), recovery(observedSerials={"node1": 1, "node2": 2}))
        self.assertEqual("BLOCKED", result["status"])
        self.assertEqual("BIND_LIFECYCLE_RECOVERY_PARTICIPANTS_MISMATCH", result["findings"][0]["code"])

    def test_existing_generated_serial_above_audited_floor_fails_closed(self):
        state = {"serviceDeployments": {"bind-main": {"dns": {"currentSerial": 4}}}}
        result = LIFECYCLE.recover_dns_lifecycle(state, zones(), recovery())
        self.assertEqual("BLOCKED", result["status"])
        self.assertEqual("BIND_LIFECYCLE_RECOVERY_SERIAL_REGRESSION", result["findings"][0]["code"])

    def test_next_unchanged_reconcile_retains_recovered_serial(self):
        recovered = LIFECYCLE.recover_dns_lifecycle({}, zones(), recovery())["generatedState"]
        repeated = LIFECYCLE.recover_dns_lifecycle(recovered, zones(), {})["generatedState"]
        self.assertEqual(3, repeated["serviceDeployments"]["bind-main"]["dns"]["currentSerial"])
        self.assertEqual(recovered, repeated)


if __name__ == "__main__":
    unittest.main()

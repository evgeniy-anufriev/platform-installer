import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import execution_secret_lease
from execution_lifecycle import LifecycleError


def digest(letter): return "sha256:" + letter * 64


def request(request_id="1" * 32):
    return {"requestId": request_id, "startAttemptId": "2" * 32, "projectIdentity": "project-1", "projectRevision": digest("a"), "planFingerprint": digest("b"), "executionManifestDigest": digest("c"), "runtimeRelease": {"bundleDigest": digest("d"), "coreVersion": "core", "catalogDigest": digest("e"), "planningProtocol": "v1alpha1"}}


def payload(password="secret"):
    return {"apiVersion": execution_secret_lease.PAYLOAD_VERSION, "kind": "TargetCredentialLeasePayload", "username": "operator", "password": password, "privateKey": None, "sudoPassword": None}


class ExecutionSecretLeaseTests(unittest.TestCase):
    def test_complete_put_is_idempotent_and_never_persists_request_secret(self):
        with tempfile.TemporaryDirectory() as root:
            first = execution_secret_lease.put(root, request(), payload())
            second = execution_secret_lease.put(root, request(), payload())
            self.assertEqual("STORED", first["status"])
            self.assertEqual("ALREADY_STORED", second["status"])
            self.assertEqual(first["leaseId"], second["leaseId"])
            request_record = Path(root, "secret-leases", "requests", "1" * 32 + ".json").read_text(encoding="utf-8")
            self.assertNotIn("secret", request_record)
            self.assertIn("payloadDigest", request_record)

    def test_partial_or_conflicting_put_publishes_no_replacement(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(LifecycleError, "PAYLOAD_INVALID"):
                execution_secret_lease.put(root, request(), {"apiVersion": execution_secret_lease.PAYLOAD_VERSION})
            self.assertFalse(Path(root, "secret-leases", "requests").exists())
            execution_secret_lease.put(root, request(), payload())
            with self.assertRaisesRegex(LifecycleError, "REQUEST_ID_CONFLICT"):
                execution_secret_lease.put(root, request(), payload("different"))

    def test_attached_lease_requires_exact_binding_and_run(self):
        with tempfile.TemporaryDirectory() as root:
            stored = execution_secret_lease.put(root, request(), payload())
            self.assertTrue(execution_secret_lease.attach(root, stored["leaseId"], request(), "installer-123"))
            self.assertFalse(execution_secret_lease.attach(root, stored["leaseId"], request(), "installer-123"))
            self.assertTrue(execution_secret_lease.payload_path(root, stored["leaseId"], "installer-123").endswith("payload.json"))
            with self.assertRaisesRegex(LifecycleError, "NOT_ATTACHED"):
                execution_secret_lease.payload_path(root, stored["leaseId"], "installer-foreign")
            self.assertTrue(execution_secret_lease.cleanup_run(root, "installer-123"))
            self.assertFalse(execution_secret_lease.cleanup_run(root, "installer-123"))
            self.assertFalse(Path(root, "secret-leases", "leases", stored["leaseId"]).exists())

    def test_invalid_identity_or_payload_is_closed(self):
        with tempfile.TemporaryDirectory() as root:
            bad = request(); bad["projectIdentity"] = "-invalid"
            with self.assertRaisesRegex(LifecycleError, "REQUEST_INVALID"):
                execution_secret_lease.put(root, bad, payload())
            malformed = payload(); malformed["password"] = None; malformed["privateKey"] = None
            with self.assertRaisesRegex(LifecycleError, "PAYLOAD_INVALID"):
                execution_secret_lease.put(root, request(), malformed)

    def test_start_attempt_is_durable_and_conflicts_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            binding = {"projectIdentity": "project-1", "planFingerprint": digest("a")}
            run, known = execution_secret_lease.attempt(root, "4" * 32, binding, "installer-123")
            self.assertEqual(("installer-123", False), (run, known))
            self.assertEqual(("installer-123", True), execution_secret_lease.attempt(root, "4" * 32, binding))
            with self.assertRaisesRegex(LifecycleError, "START_ATTEMPT_CONFLICT"):
                execution_secret_lease.attempt(root, "4" * 32, {"projectIdentity": "other"})

    def test_plan_lookup_is_direct_and_never_scans_runs(self):
        with tempfile.TemporaryDirectory() as root:
            manifest = {"projectIdentity": "project-1", "planFingerprint": digest("b"), "runtimeRelease": request()["runtimeRelease"]}
            execution_secret_lease.register_plan(root, "installer-123", digest("c"), manifest)
            resolved = execution_secret_lease.resolve_plan(root, {"projectIdentity": "project-1", "planFingerprint": digest("b"), "executionManifestDigest": digest("c")})
            self.assertEqual("installer-123", resolved["runId"])
            with self.assertRaisesRegex(LifecycleError, "MANIFEST_MISSING"):
                execution_secret_lease.resolve_plan(root, {"projectIdentity": "project-1", "planFingerprint": digest("b"), "executionManifestDigest": digest("d")})


if __name__ == "__main__":
    unittest.main()

import json
import os
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import execution_secret_lease
import execution_protocol
from execution_lifecycle import LifecycleError


def digest(letter): return "sha256:" + letter * 64


def request(request_id="1" * 32):
    return {"requestId": request_id, "startAttemptId": "2" * 32, "projectIdentity": "project-1", "projectRevision": digest("a"), "planFingerprint": digest("b"), "executionManifestDigest": digest("c"), "runtimeRelease": {"bundleDigest": digest("d"), "coreVersion": "core", "catalogDigest": digest("e"), "planningProtocol": "v1alpha1"}}


def payload(password="secret"):
    return {"apiVersion": execution_secret_lease.PAYLOAD_VERSION, "kind": "TargetCredentialLeasePayload", "username": "operator", "password": password, "privateKey": None, "sudoPassword": None}


def pki_payload(store_password):
    value = payload()
    value.update({"apiVersion": execution_secret_lease.PKI_PAYLOAD_VERSION, "pkiStorePassword": store_password})
    return value


def runtime_secret_payload(values, store_password=None):
    value = payload()
    value.update({"apiVersion": execution_secret_lease.RUNTIME_SECRET_PAYLOAD_VERSION, "pkiStorePassword": store_password, "runtimeSecretValues": values})
    return value


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

    def test_controller_can_project_only_attached_target_username(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertIsNone(execution_secret_lease.target_username_for_run(root, "installer-123"))
            stored = execution_secret_lease.put(root, request(), payload())
            self.assertTrue(execution_secret_lease.attach(root, stored["leaseId"], request(), "installer-123"))
            self.assertEqual("operator", execution_secret_lease.target_username_for_run(root, "installer-123"))
            self.assertTrue(execution_secret_lease.cleanup_run(root, "installer-123"))
            self.assertIsNone(execution_secret_lease.target_username_for_run(root, "installer-123"))

    def test_invalid_identity_or_payload_is_closed(self):
        with tempfile.TemporaryDirectory() as root:
            bad = request(); bad["projectIdentity"] = "-invalid"
            with self.assertRaisesRegex(LifecycleError, "REQUEST_INVALID"):
                execution_secret_lease.put(root, bad, payload())
            malformed = payload(); malformed["password"] = None; malformed["privateKey"] = None
            with self.assertRaisesRegex(LifecycleError, "PAYLOAD_INVALID"):
                execution_secret_lease.put(root, request(), malformed)

    def test_pki_payload_accepts_exact_utf8_byte_bound_and_staged_validation(self):
        with tempfile.TemporaryDirectory() as root:
            stored = execution_secret_lease.put(root, request(), pki_payload("\u044f" * 2048))
            execution_secret_lease.validate_staged_pki_store_password(root, stored["leaseId"])
            for invalid in ("", "a" * 4097):
                with self.subTest(length=len(invalid)):
                    with self.assertRaisesRegex(LifecycleError, "PAYLOAD_INVALID"):
                        execution_secret_lease.put(root, request("%032x" % (len(invalid) + 7)), pki_payload(invalid))
            legacy = execution_secret_lease.put(root, request("9" * 32), payload())
            with self.assertRaisesRegex(LifecycleError, "PKI_STORE_PASSWORD_RUNTIME_SECRET_REQUIRED"):
                execution_secret_lease.validate_staged_pki_store_password(root, legacy["leaseId"])

    def test_runtime_secret_payload_requires_closed_bounded_values(self):
        with tempfile.TemporaryDirectory() as root:
            valid = runtime_secret_payload({"postgresql-admin-password": "\u044f" * 2048}, "pki")
            stored = execution_secret_lease.put(root, request(), valid)
            self.assertTrue(stored["leaseId"])
            invalid = [
                runtime_secret_payload({}),
                runtime_secret_payload({"invalid_ref": "value"}),
                runtime_secret_payload({"postgresql-admin-password": ""}),
                runtime_secret_payload({"postgresql-admin-password": "a" * 4097}),
                runtime_secret_payload({"postgresql-admin-password": "a", "postgresql-monitor-password": "b" * 65536}),
            ]
            for index, candidate in enumerate(invalid):
                with self.subTest(index=index), self.assertRaisesRegex(LifecycleError, "PAYLOAD_INVALID"):
                    execution_secret_lease.put(root, request("%032x" % (index + 9)), candidate)

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
            self.assertEqual("installer-123", resolved["stagingId"])
            with self.assertRaisesRegex(LifecycleError, "MANIFEST_MISSING"):
                execution_secret_lease.resolve_plan(root, {"projectIdentity": "project-1", "planFingerprint": digest("b"), "executionManifestDigest": digest("d")})

    def test_node_owned_start_commits_attempt_and_attachment_before_launch(self):
        with tempfile.TemporaryDirectory() as root:
            stage = "installer-111"
            release = request()["runtimeRelease"]
            manifest = {"projectIdentity": "project-1", "planFingerprint": digest("b"), "runtimeRelease": release, "operations": []}
            Path(root, "runs", stage).mkdir(parents=True)
            Path(root, "runs", stage, "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            manifest_digest = execution_protocol.digest(manifest)
            execution_secret_lease.register_plan(root, stage, manifest_digest, manifest)
            metadata = request(); metadata["executionManifestDigest"] = manifest_digest
            stored = execution_secret_lease.put(root, metadata, payload())
            start_request = {"apiVersion": "platform.installer/execution-start/v1alpha2", "kind": "StartExecutionRequest", "startAttemptId": metadata["startAttemptId"], "projectIdentity": metadata["projectIdentity"], "projectRevision": metadata["projectRevision"], "planFingerprint": metadata["planFingerprint"], "executionManifestDigest": manifest_digest, "runtimeRelease": release, "leaseId": stored["leaseId"]}
            observed = []
            def launch(value, *_args, **kwargs):
                run_id = value["runId"]
                observed.append(run_id)
                self.assertNotEqual(stage, run_id)
                kwargs["prelaunch"]({}, None)
                self.assertEqual((run_id, True), execution_secret_lease.attempt(root, metadata["startAttemptId"], {"projectIdentity": metadata["projectIdentity"], "projectRevision": metadata["projectRevision"], "planFingerprint": metadata["planFingerprint"], "executionManifestDigest": manifest_digest, "runtimeRelease": release, "leaseId": stored["leaseId"]}))
                self.assertTrue(execution_secret_lease.payload_path(root, stored["leaseId"], run_id).endswith("payload.json"))
                return {"idempotent": False}
            with mock.patch.object(execution_protocol, "start", side_effect=launch):
                result = execution_protocol._start_v2(start_request, root, "/release", "/controller", "")
            self.assertEqual("STARTED", result["status"])
            self.assertEqual(observed[0], result["runId"])
            retry = execution_protocol._start_v2(start_request, root, "/release", "/controller", "")
            self.assertEqual("ALREADY_STARTED", retry["status"])
            self.assertEqual(result["runId"], retry["runId"])

    def test_post_commit_launch_failure_retains_one_authoritative_run(self):
        with tempfile.TemporaryDirectory() as root:
            stage = "installer-222"
            release = request()["runtimeRelease"]
            manifest = {"projectIdentity": "project-1", "planFingerprint": digest("b"), "runtimeRelease": release, "operations": []}
            Path(root, "runs", stage).mkdir(parents=True)
            Path(root, "runs", stage, "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            manifest_digest = execution_protocol.digest(manifest)
            execution_secret_lease.register_plan(root, stage, manifest_digest, manifest)
            metadata = request(); metadata["executionManifestDigest"] = manifest_digest
            stored = execution_secret_lease.put(root, metadata, payload())
            start_request = {"apiVersion": "platform.installer/execution-start/v1alpha2", "kind": "StartExecutionRequest", "startAttemptId": metadata["startAttemptId"], "projectIdentity": metadata["projectIdentity"], "projectRevision": metadata["projectRevision"], "planFingerprint": metadata["planFingerprint"], "executionManifestDigest": manifest_digest, "runtimeRelease": release, "leaseId": stored["leaseId"]}
            with mock.patch.object(execution_protocol.subprocess, "check_call", side_effect=execution_protocol.subprocess.CalledProcessError(1, "systemd-run")):
                result = execution_protocol._start_v2(start_request, root, "/release", "/controller", "")
            self.assertEqual("STARTED", result["status"])
            self.assertEqual("FAILED", json.loads(Path(root, "runs", result["runId"], "status.json").read_text(encoding="utf-8"))["state"])
            retry = execution_protocol._start_v2(start_request, root, "/release", "/controller", "")
            self.assertEqual(("ALREADY_STARTED", result["runId"]), (retry["status"], retry["runId"]))

    def test_every_post_commit_launch_exception_is_terminal_and_idempotent(self):
        for failure in (OSError("spawn failed"), RuntimeError("launch wrapper failed")):
            with self.subTest(type=type(failure).__name__), tempfile.TemporaryDirectory() as root:
                stage = "installer-333"
                release = request()["runtimeRelease"]
                manifest = {"projectIdentity": "project-1", "planFingerprint": digest("b"), "runtimeRelease": release, "operations": []}
                Path(root, "runs", stage).mkdir(parents=True)
                Path(root, "runs", stage, "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
                manifest_digest = execution_protocol.digest(manifest)
                execution_secret_lease.register_plan(root, stage, manifest_digest, manifest)
                metadata = request(); metadata["executionManifestDigest"] = manifest_digest
                stored = execution_secret_lease.put(root, metadata, payload())
                start_request = {"apiVersion": "platform.installer/execution-start/v1alpha2", "kind": "StartExecutionRequest", "startAttemptId": metadata["startAttemptId"], "projectIdentity": metadata["projectIdentity"], "projectRevision": metadata["projectRevision"], "planFingerprint": metadata["planFingerprint"], "executionManifestDigest": manifest_digest, "runtimeRelease": release, "leaseId": stored["leaseId"]}
                with mock.patch.object(execution_protocol.subprocess, "check_call", side_effect=failure):
                    result = execution_protocol._start_v2(start_request, root, "/release", "/controller", "")
                self.assertEqual("FAILED", json.loads(Path(root, "runs", result["runId"], "status.json").read_text(encoding="utf-8"))["state"])
                retry = execution_protocol._start_v2(start_request, root, "/release", "/controller", "")
                self.assertEqual(("ALREADY_STARTED", result["runId"]), (retry["status"], retry["runId"]))

    def test_pre_commit_failure_rolls_back_journal_and_retries_cleanly(self):
        with tempfile.TemporaryDirectory() as root:
            stage = "installer-444"
            release = request()["runtimeRelease"]
            manifest = {"projectIdentity": "project-1", "planFingerprint": digest("b"), "runtimeRelease": release, "operations": []}
            Path(root, "runs", stage).mkdir(parents=True)
            Path(root, "runs", stage, "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            manifest_digest = execution_protocol.digest(manifest)
            execution_secret_lease.register_plan(root, stage, manifest_digest, manifest)
            metadata = request(); metadata["executionManifestDigest"] = manifest_digest
            stored = execution_secret_lease.put(root, metadata, payload())
            start_request = {"apiVersion": "platform.installer/execution-start/v1alpha2", "kind": "StartExecutionRequest", "startAttemptId": metadata["startAttemptId"], "projectIdentity": metadata["projectIdentity"], "projectRevision": metadata["projectRevision"], "planFingerprint": metadata["planFingerprint"], "executionManifestDigest": manifest_digest, "runtimeRelease": release, "leaseId": stored["leaseId"]}
            with mock.patch.object(execution_secret_lease, "commit_start", side_effect=LifecycleError("LEASE_EXPIRED")), mock.patch.object(execution_protocol.subprocess, "check_call") as launch:
                with self.assertRaisesRegex(LifecycleError, "LEASE_EXPIRED"):
                    execution_protocol._start_v2(start_request, root, "/release", "/controller", "")
                launch.assert_not_called()
            self.assertFalse(Path(root, "secret-leases", "attempts", metadata["startAttemptId"] + ".json").exists())
            self.assertFalse(any(Path(root, "runs", stage, name).exists() for name in ("metadata.json", "status.json", "events.jsonl")))
            with mock.patch.object(execution_protocol.subprocess, "check_call"):
                retry = execution_protocol._start_v2(start_request, root, "/release", "/controller", "")
            self.assertEqual("STARTED", retry["status"])

    def test_commit_start_faults_before_publication_are_recoverable(self):
        for fail_at in (2, 3, 4):
            with self.subTest(write=fail_at), tempfile.TemporaryDirectory() as root:
                metadata = request()
                stored = execution_secret_lease.put(root, metadata, payload())
                binding = {"projectIdentity": metadata["projectIdentity"], "projectRevision": metadata["projectRevision"], "planFingerprint": metadata["planFingerprint"], "executionManifestDigest": metadata["executionManifestDigest"], "runtimeRelease": metadata["runtimeRelease"], "leaseId": stored["leaseId"]}
                lease_binding = dict(metadata)
                original = execution_secret_lease._write
                calls = [0]
                def fail_once(path, value):
                    calls[0] += 1
                    if calls[0] == fail_at:
                        raise OSError("injected durable write failure")
                    return original(path, value)
                with mock.patch.object(execution_secret_lease, "_write", side_effect=fail_once):
                    with self.assertRaises(OSError):
                        execution_secret_lease.commit_start(root, metadata["startAttemptId"], binding, "installer-555", "installer-stage", stored["leaseId"], lease_binding)
                self.assertEqual((None, False), execution_secret_lease.attempt(root, metadata["startAttemptId"], binding))
                self.assertIsNone(execution_secret_lease.prepared_start(root, metadata["startAttemptId"], binding))
                record = execution_secret_lease._read(Path(root, "secret-leases", "leases", stored["leaseId"], "record.json"))
                self.assertEqual("STAGED", record["state"])
                self.assertTrue(execution_secret_lease.commit_start(root, metadata["startAttemptId"], binding, "installer-556", "installer-stage", stored["leaseId"], lease_binding))
                self.assertEqual(("installer-556", True), execution_secret_lease.attempt(root, metadata["startAttemptId"], binding))

    def test_prepared_restart_recovers_staging_before_retry(self):
        with tempfile.TemporaryDirectory() as root:
            stage, run_id = "installer-stage", "installer-666"
            release = request()["runtimeRelease"]
            manifest = {"projectIdentity": "project-1", "planFingerprint": digest("b"), "runtimeRelease": release, "operations": []}
            Path(root, "runs", run_id).mkdir(parents=True)
            Path(root, "runs", run_id, "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            Path(root, "runs", run_id, "metadata.json").write_text("{}", encoding="utf-8")
            Path(root, "runs", run_id, "status.json").write_text("{}", encoding="utf-8")
            manifest_digest = execution_protocol.digest(manifest)
            execution_secret_lease.register_plan(root, stage, manifest_digest, manifest)
            metadata = request(); metadata["executionManifestDigest"] = manifest_digest
            stored = execution_secret_lease.put(root, metadata, payload())
            binding = {"projectIdentity": metadata["projectIdentity"], "projectRevision": metadata["projectRevision"], "planFingerprint": metadata["planFingerprint"], "executionManifestDigest": manifest_digest, "runtimeRelease": release, "leaseId": stored["leaseId"]}
            record_path = Path(root, "secret-leases", "leases", stored["leaseId"], "record.json")
            record = execution_secret_lease._read(record_path); record.update({"state": "ATTACHED", "runId": run_id}); execution_secret_lease._write(record_path, record)
            execution_secret_lease._write(Path(root, "secret-leases", "attached", run_id + ".json"), {"leaseId": stored["leaseId"]})
            execution_secret_lease._write(Path(root, "secret-leases", "prepared", metadata["startAttemptId"] + ".json"), {"state": "PREPARED", "binding": binding, "runId": run_id, "stagingId": stage, "leaseId": stored["leaseId"], "leaseBinding": metadata})
            start_request = {"apiVersion": "platform.installer/execution-start/v1alpha2", "kind": "StartExecutionRequest", "startAttemptId": metadata["startAttemptId"], "projectIdentity": metadata["projectIdentity"], "projectRevision": metadata["projectRevision"], "planFingerprint": metadata["planFingerprint"], "executionManifestDigest": manifest_digest, "runtimeRelease": release, "leaseId": stored["leaseId"]}
            with mock.patch.object(execution_protocol.subprocess, "check_call"):
                result = execution_protocol._start_v2(start_request, root, "/release", "/controller", "")
            self.assertEqual("STARTED", result["status"])
            self.assertNotEqual(run_id, result["runId"])
            self.assertFalse(Path(root, "secret-leases", "prepared", metadata["startAttemptId"] + ".json").exists())

    def test_stale_prepared_marker_never_rolls_back_published_run(self):
        with tempfile.TemporaryDirectory() as root:
            release = request()["runtimeRelease"]
            metadata = request()
            binding = {"projectIdentity": metadata["projectIdentity"], "projectRevision": metadata["projectRevision"], "planFingerprint": metadata["planFingerprint"], "executionManifestDigest": metadata["executionManifestDigest"], "runtimeRelease": release, "leaseId": None}
            run_id = "installer-777"
            Path(root, "runs", run_id).mkdir(parents=True)
            execution_secret_lease.attempt(root, metadata["startAttemptId"], binding, run_id)
            execution_secret_lease._write(Path(root, "secret-leases", "prepared", metadata["startAttemptId"] + ".json"), {"state": "PREPARED", "binding": binding, "runId": run_id, "stagingId": "installer-stage", "leaseId": None, "leaseBinding": None})
            start_request = {"apiVersion": "platform.installer/execution-start/v1alpha2", "kind": "StartExecutionRequest", "startAttemptId": metadata["startAttemptId"], "projectIdentity": metadata["projectIdentity"], "projectRevision": metadata["projectRevision"], "planFingerprint": metadata["planFingerprint"], "executionManifestDigest": metadata["executionManifestDigest"], "runtimeRelease": release}
            response = execution_protocol._start_v2(start_request, root, "/release", "/controller", "")
            self.assertEqual(("ALREADY_STARTED", run_id), (response["status"], response["runId"]))
            self.assertTrue(Path(root, "runs", run_id).is_dir())

    def test_post_commit_prepared_cleanup_failure_preserves_authoritative_run(self):
        with tempfile.TemporaryDirectory() as root:
            stage = "installer-888"
            release = request()["runtimeRelease"]
            manifest = {"projectIdentity": "project-1", "planFingerprint": digest("b"), "runtimeRelease": release, "operations": []}
            Path(root, "runs", stage).mkdir(parents=True)
            Path(root, "runs", stage, "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            manifest_digest = execution_protocol.digest(manifest)
            execution_secret_lease.register_plan(root, stage, manifest_digest, manifest)
            metadata = request(); metadata["executionManifestDigest"] = manifest_digest
            stored = execution_secret_lease.put(root, metadata, payload())
            binding = {"projectIdentity": metadata["projectIdentity"], "projectRevision": metadata["projectRevision"], "planFingerprint": metadata["planFingerprint"], "executionManifestDigest": manifest_digest, "runtimeRelease": release, "leaseId": stored["leaseId"]}
            start_request = {"apiVersion": "platform.installer/execution-start/v1alpha2", "kind": "StartExecutionRequest", "startAttemptId": metadata["startAttemptId"], "projectIdentity": metadata["projectIdentity"], "projectRevision": metadata["projectRevision"], "planFingerprint": metadata["planFingerprint"], "executionManifestDigest": manifest_digest, "runtimeRelease": release, "leaseId": stored["leaseId"]}
            original_unlink = execution_secret_lease.os.unlink
            prepared_suffix = os.path.join("prepared", metadata["startAttemptId"] + ".json")
            def fail_prepared_cleanup(path):
                if os.fspath(path).endswith(prepared_suffix):
                    raise OSError("injected post-commit marker cleanup failure")
                return original_unlink(path)
            with mock.patch.object(execution_secret_lease.os, "unlink", side_effect=fail_prepared_cleanup), mock.patch.object(execution_protocol.subprocess, "check_call") as launch:
                first = execution_protocol._start_v2(start_request, root, "/release", "/controller", "")
            self.assertEqual("STARTED", first["status"])
            run_id = first["runId"]
            self.assertEqual((run_id, True), execution_secret_lease.attempt(root, metadata["startAttemptId"], binding))
            self.assertTrue(Path(root, "secret-leases", "prepared", metadata["startAttemptId"] + ".json").exists())
            self.assertTrue(Path(root, "runs", run_id, "metadata.json").exists())
            record = execution_secret_lease._read(Path(root, "secret-leases", "leases", stored["leaseId"], "record.json"))
            self.assertEqual(("ATTACHED", run_id), (record["state"], record["runId"]))
            retry = execution_protocol._start_v2(start_request, root, "/release", "/controller", "")
            self.assertEqual(("ALREADY_STARTED", run_id), (retry["status"], retry["runId"]))
            self.assertEqual(1, launch.call_count)
            self.assertTrue(Path(root, "runs", run_id).is_dir())


if __name__ == "__main__":
    unittest.main()

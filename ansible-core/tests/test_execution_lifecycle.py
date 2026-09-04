import json
import sys
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
from execution_lifecycle import Journal, LifecycleError, digest, recover, retain
import execution_controller
import execution_protocol


def metadata(run_id="run-1", project="project-1"):
    manifest = {"projectIdentity": project, "planFingerprint": "sha256:" + "a" * 64, "runtimeRelease": {"bundleDigest": "sha256:" + "c" * 64}, "operations": []}
    return {"runId": run_id, "projectIdentity": project, "planFingerprint": manifest["planFingerprint"], "manifestDigest": digest(manifest), "runtimeRelease": manifest["runtimeRelease"]["bundleDigest"], "unit": "platform-installer-run-%s.service" % run_id}


def subprocess_completed(returncode):
    return execution_protocol.subprocess.CompletedProcess([], returncode)


class ExecutionLifecycleTests(unittest.TestCase):
    def test_core_operation_returns_blocked_plan_without_manifest(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as release:
            journal = Journal(root, "run-1")
            Path(journal.directory, "project", "inventory").mkdir(parents=True)
            Path(journal.directory, "project", "inventory", "hosts.yml").write_text("all: {}\n", encoding="utf-8")
            Path(release, "ansible-core", "playbooks").mkdir(parents=True)
            plan = {"status": "BLOCKED", "findings": [{"code": "PROJECT_VALIDATION_BLOCKED"}]}

            def completed(_command, **kwargs):
                self.assertEqual("platform.core.deployment_plan_json", kwargs["env"]["ANSIBLE_CALLBACKS_ENABLED"])
                Path(kwargs["env"]["PLATFORM_DEPLOYMENT_PLAN_OUTPUT"]).write_text(json.dumps(plan), encoding="utf-8")
                return subprocess_completed(0)

            with mock.patch.object(execution_protocol.subprocess, "run", side_effect=completed):
                result = execution_protocol.core_operation(
                    {"runId": "run-1", "runtimeRelease": {}}, root, release, "BuildDeploymentPlan"
                )
            self.assertEqual(plan, result["deploymentPlan"])
            self.assertIsNone(result["executionManifestDigest"])

    def test_core_operation_returns_safe_structured_diagnostic(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as release:
            journal = Journal(root, "run-1")
            Path(journal.directory, "project", "inventory").mkdir(parents=True)
            Path(journal.directory, "project", "inventory", "hosts.yml").write_text("all: {}\n", encoding="utf-8")
            Path(release, "ansible-core", "playbooks").mkdir(parents=True)
            diagnostic = {"errorCode": "PROJECT_SNAPSHOT_INPUT_INVALID", "findings": [{"code": "PROJECT_SNAPSHOT_INPUT_INVALID", "safeMessage": "Project snapshot inputs could not be loaded"}]}

            def failed(_command, **kwargs):
                Path(kwargs["env"]["PLATFORM_CORE_DIAGNOSTIC_OUTPUT"]).write_text(json.dumps(diagnostic), encoding="utf-8")
                return subprocess_completed(2)

            with mock.patch.object(execution_protocol.subprocess, "run", side_effect=failed):
                with self.assertRaises(execution_protocol.CoreOperationError) as caught:
                    execution_protocol.core_operation(
                        {"runId": "run-1", "runtimeRelease": {}}, root, release, "BuildDeploymentPlan"
                    )
            self.assertEqual("PROJECT_SNAPSHOT_INPUT_INVALID", caught.exception.code)
            self.assertEqual(diagnostic, caught.exception.diagnostic)

    def test_journal_has_monotonic_replay_and_one_terminal_result(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            journal.initialize(metadata())
            manifest = {"projectIdentity": "project-1", "planFingerprint": metadata()["planFingerprint"], "runtimeRelease": {"bundleDigest": metadata()["runtimeRelease"]}, "operations": []}
            Path(journal.directory, "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            journal.transition("RUNNING", "running")
            journal.terminal("SUCCEEDED", "", "done")
            self.assertEqual([1, 2], [item["sequence"] for item in journal.events()])
            self.assertEqual([], journal.events(2))
            self.assertEqual("SUCCEEDED", journal.terminal("FAILED", "X", "no")["state"])

    def test_tampered_run_id_and_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(LifecycleError, "RUN_ID_INVALID"):
                Journal(root, "../escape")
            journal = Journal(root, "run-1")
            journal.initialize(metadata())
            manifest = {"projectIdentity": "project-1", "planFingerprint": metadata()["planFingerprint"], "runtimeRelease": {"bundleDigest": metadata()["runtimeRelease"]}, "operations": []}
            Path(journal.directory, "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (Path(journal.metadata_path)).unlink()
            Path(journal.metadata_path).symlink_to("/etc/passwd")
            with self.assertRaisesRegex(LifecycleError, "SYMLINK"):
                journal.metadata()

    def test_missing_owned_unit_recovers_once_as_interrupted(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            journal.initialize(metadata())
            manifest = {"projectIdentity": "project-1", "planFingerprint": metadata()["planFingerprint"], "runtimeRelease": {"bundleDigest": metadata()["runtimeRelease"]}, "operations": []}
            Path(journal.directory, "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            journal.transition("RUNNING", "running")
            self.assertEqual(["run-1"], recover(root, lambda _unit, _metadata: False))
            self.assertEqual([], recover(root, lambda _unit, _metadata: False))
            self.assertEqual("INTERRUPTED", journal.status()["state"])

    def test_terminal_result_is_exactly_once_under_a_race(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            journal.initialize(metadata())
            threads = [threading.Thread(target=journal.terminal, args=(state, "", state)) for state in ("SUCCEEDED", "CANCELLED")]
            for item in threads: item.start()
            for item in threads: item.join()
            self.assertIn(journal.terminal("FAILED", "", "")["state"], ("SUCCEEDED", "CANCELLED"))

    def test_controller_registry_rejects_unknown_or_tampered_operation_before_dispatch(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            journal.initialize(metadata())
            with self.assertRaisesRegex(LifecycleError, "OPERATION_UNKNOWN"):
                execution_controller._dispatch(root, journal, {"operations": [{"operationId": "evil", "operation": "RunCommand"}]}, [False])
            with self.assertRaisesRegex(LifecycleError, "MANIFEST_INVALID"):
                execution_controller._dispatch(root, journal, {"operations": [{"operationId": "same", "operation": "PKI_APPLY"}, {"operationId": "same", "operation": "PKI_APPLY"}]}, [False])

    def test_service_dispatch_requires_existing_runtime_projection(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1"); journal.initialize(metadata())
            with self.assertRaisesRegex(LifecycleError, "RUNTIME_PROJECTION_MISSING"):
                execution_controller._dispatch(root, journal, {"operations": [{"operationId": "apply:kafka", "operation": "SERVICE_APPLY", "serviceType": "kafka"}]}, [False])

    def test_controller_uses_prepared_execution_identity_and_known_hosts(self):
        environment = execution_controller._environment("/runtime/release")
        self.assertIn("IdentityFile=/var/lib/platform-installer/execution/identities/default/id_ed25519", environment["ANSIBLE_SSH_ARGS"])
        self.assertIn("UserKnownHostsFile=/var/lib/platform-installer/execution/known_hosts", environment["ANSIBLE_SSH_ARGS"])
        self.assertIn("StrictHostKeyChecking=yes", environment["ANSIBLE_SSH_ARGS"])

    def test_service_projection_binding_is_verified_before_controller_start(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            journal.initialize(metadata())
            projection = {
                "apiVersion": "platform.installer/runtime-projection/v1alpha1",
                "platform_execution_run_id": "run-1",
                "platform_execution_project_identity": "project-1",
                "platform_execution_plan_fingerprint": metadata()["planFingerprint"],
                "platform_execution_requirements_fingerprint": "sha256:" + "a" * 64,
                "platform_resolved_artifact_sources_by_target": {},
            }
            Path(journal.directory, "runtime-projection.json").write_text(json.dumps(projection), encoding="utf-8")
            manifest = {"operations": [{"operation": "SERVICE_APPLY", "serviceType": "kafka"}]}
            execution_controller._validate_runtime_projection(journal, metadata(), manifest)
            projection["platform_execution_run_id"] = "other-run"
            Path(journal.directory, "runtime-projection.json").write_text(json.dumps(projection), encoding="utf-8")
            with self.assertRaisesRegex(LifecycleError, "RUNTIME_PROJECTION_MISMATCH"):
                execution_controller._validate_runtime_projection(journal, metadata(), manifest)

    def test_retention_only_removes_verified_terminal_runs(self):
        with tempfile.TemporaryDirectory() as root:
            for run_id in ("run-1", "run-2", "run-3"):
                journal = Journal(root, run_id); journal.initialize(metadata(run_id)); manifest = {"projectIdentity": "project-1", "planFingerprint": metadata(run_id)["planFingerprint"], "runtimeRelease": {"bundleDigest": metadata(run_id)["runtimeRelease"]}, "operations": []}; Path(journal.directory, "manifest.json").write_text(json.dumps(manifest), encoding="utf-8"); journal.terminal("SUCCEEDED", "", "done")
            active = Journal(root, "run-active"); active.initialize(metadata("run-active")); manifest = {"projectIdentity": "project-1", "planFingerprint": metadata("run-active")["planFingerprint"], "runtimeRelease": {"bundleDigest": metadata("run-active")["runtimeRelease"]}, "operations": []}; Path(active.directory, "manifest.json").write_text(json.dumps(manifest), encoding="utf-8"); active.transition("RUNNING", "running")
            self.assertEqual(["run-2", "run-1"], retain(root, 1))
            self.assertTrue(Path(active.directory).is_dir())

    def test_existing_cancelled_terminal_cannot_be_replaced_by_controller_failure(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1"); journal.initialize(metadata())
            journal.terminal("CANCELLED", "EXECUTION_CANCELLED", "cancelled")
            self.assertEqual("CANCELLED", journal.terminal("FAILED", "EXECUTION_OPERATION_FAILED", "late child exit")["state"])

    def test_active_run_conflict_leaves_no_second_journal(self):
        with tempfile.TemporaryDirectory() as root:
            def stage(run_id):
                journal = Journal(root, run_id); Path(journal.directory).mkdir(parents=True, exist_ok=True)
                manifest = {"projectIdentity": "project-1", "planFingerprint": "sha256:" + "a" * 64, "runtimeRelease": {"bundleDigest": "sha256:" + "b" * 64}, "operations": [{"operationId": "core:delay", "operation": "CORE_DELAY"}]}
                Path(journal.directory, "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
                return {"runId": run_id, "projectIdentity": manifest["projectIdentity"], "planFingerprint": manifest["planFingerprint"], "runtimeRelease": manifest["runtimeRelease"]}
            first, second = stage("run-1"), stage("run-2")
            with mock.patch.object(execution_protocol.subprocess, "check_call"):
                execution_protocol.start(first, root, "/release", "/controller")
                with self.assertRaisesRegex(LifecycleError, "ACTIVE_RUN_EXISTS:run-1"):
                    execution_protocol.start(second, root, "/release", "/controller")
            self.assertFalse(Path(root, "runs", "run-2", "metadata.json").exists())

    def test_cancel_ownership_rejects_tampered_manifest_before_unit_call(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1"); journal.initialize(metadata())
            Path(journal.directory, "manifest.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(LifecycleError, "OWNERSHIP_INVALID"):
                execution_protocol.owned(journal)


if __name__ == "__main__":
    unittest.main()

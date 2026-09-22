import hashlib
import io
import json
import os
import sys
from pathlib import Path
import tarfile
import tempfile
import threading
import unittest
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
from execution_lifecycle import Journal, LifecycleError, digest, recover, retain
import execution_lifecycle
import execution_controller
import execution_protocol


def metadata(run_id="run-1", project="project-1"):
    manifest = {"projectIdentity": project, "planFingerprint": "sha256:" + "a" * 64, "runtimeRelease": {"bundleDigest": "sha256:" + "c" * 64}, "operations": []}
    return {"runId": run_id, "projectIdentity": project, "planFingerprint": manifest["planFingerprint"], "manifestDigest": digest(manifest), "runtimeRelease": manifest["runtimeRelease"]["bundleDigest"], "unit": "platform-installer-run-%s.service" % run_id}


def subprocess_completed(returncode):
    return execution_protocol.subprocess.CompletedProcess([], returncode)


def runtime_evidence():
    return {
        "bundleDigest": "sha256:" + "e" * 64,
        "coreVersion": "test-core",
        "catalogDigest": "sha256:" + "f" * 64,
        "protocol": "test-protocol",
    }


class ExecutionLifecycleTests(unittest.TestCase):
    def test_terminal_status_is_published_before_result_becomes_observable(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            journal.initialize(metadata())
            original_open = execution_lifecycle.os.open

            def checked_open(path, *args, **kwargs):
                if path == journal.result_path:
                    self.assertEqual("SUCCEEDED", journal.status()["state"])
                return original_open(path, *args, **kwargs)

            with mock.patch.object(execution_lifecycle.os, "open", side_effect=checked_open):
                result = journal.terminal("SUCCEEDED", "", "done")
            self.assertEqual("SUCCEEDED", result["state"])
            self.assertEqual("SUCCEEDED", journal.status()["state"])

    def test_protocol_rejects_malformed_candidate_request_as_typed_json(self):
        script = str(TOOLS / "execution_protocol.py")
        bundle_digest = "sha256:" + "a" * 64
        valid = {
            "apiVersion": execution_protocol.SNAPSHOT_REQUEST_VERSION,
            "kind": "BuildProjectSnapshotRequest",
            "requestId": "0" * 32,
            "projectIdentity": "project-1",
            "candidateProjectRevision": "sha256:" + "b" * 64,
            "projectArchiveDigest": "sha256:" + "c" * 64,
            "artifactLockDigest": bundle_digest,
            "catalogLockDigest": "sha256:" + "d" * 64,
            "installerOwnedLogicalPaths": [],
            "projectContract": "v2alpha1",
            "snapshotContract": "v1alpha1",
            "editContract": "v1alpha2",
        }
        malformed_requests = ["not-an-object", [], {}]
        for field, value in (("requestId", 0), ("requestId", "g" * 32), ("projectIdentity", "-invalid"),
                             ("candidateProjectRevision", 0), ("projectArchiveDigest", "sha256:short"),
                             ("installerOwnedLogicalPaths", [0])):
            malformed_requests.append(dict(valid, **{field: value}))
        for malformed in malformed_requests:
            with self.subTest(snapshot_request=malformed), tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as release:
                request_value = {
                    "apiVersion": "platform.installer/execution-runtime/v1alpha1",
                    "operation": "BuildProjectSnapshot",
                    "runId": "installer-malformed-request",
                    "runtimeRelease": {"bundleDigest": bundle_digest},
                    "snapshotRequest": malformed,
                }
                completed = execution_protocol.subprocess.run(
                    [sys.executable, script, "--state-root", root, "--runtime-release", release,
                     "--controller", str(Path(release, "unused-controller.py")), "--bundle-digest", bundle_digest],
                    input=json.dumps(request_value), text=True, capture_output=True, check=False,
                )
                self.assertEqual(2, completed.returncode)
                self.assertEqual("", completed.stderr)
                self.assertEqual("PROJECT_SNAPSHOT_REQUEST_INVALID", json.loads(completed.stdout)["error"])

    def _candidate_project_protocol_error(self, project_content):
        script = str(TOOLS / "execution_protocol.py")
        bundle_digest = "sha256:" + "a" * 64
        catalog_digest = "sha256:" + "d" * 64
        archive_digest = "sha256:" + "c" * 64
        request_id = "0" * 32
        run_id = "installer-malformed-project"
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as release:
            journal = Journal(root, run_id)
            project = Path(journal.directory, "project")
            Path(project, "inventory").mkdir(parents=True)
            Path(project, "inventory", "hosts.yml").write_text("all: {hosts: {}}\n", encoding="utf-8")
            Path(project, "ansible.cfg").write_bytes(execution_protocol.APPROVED_CANDIDATE_ANSIBLE_CONFIG)
            Path(project, "project.yml").write_bytes(project_content)
            Path(journal.directory, "project-archive.digest").write_text(archive_digest + "\n", encoding="ascii")
            Path(journal.directory, execution_protocol.SNAPSHOT_OWNER_FILE).write_text(json.dumps({
                "kind": "candidate", "runId": run_id, "requestId": request_id,
                "archiveDigest": archive_digest,
            }), encoding="ascii")
            Path(release, "manifest.yaml").write_text(
                "coreVersion: test-core\ncatalogDigest: %s\nbootstrapProtocol: test-protocol\n" % catalog_digest,
                encoding="utf-8",
            )
            request_value = {
                "apiVersion": "platform.installer/execution-runtime/v1alpha1",
                "operation": "BuildProjectSnapshot",
                "runId": run_id,
                "runtimeRelease": {"bundleDigest": bundle_digest},
                "snapshotRequest": {
                    "apiVersion": execution_protocol.SNAPSHOT_REQUEST_VERSION,
                    "kind": "BuildProjectSnapshotRequest",
                    "requestId": request_id,
                    "projectIdentity": "project-1",
                    "candidateProjectRevision": "sha256:" + "b" * 64,
                    "projectArchiveDigest": archive_digest,
                    "artifactLockDigest": bundle_digest,
                    "catalogLockDigest": catalog_digest,
                    "installerOwnedLogicalPaths": [],
                    "projectContract": "v2alpha1",
                    "snapshotContract": "v1alpha1",
                    "editContract": "v1alpha2",
                },
            }
            completed = execution_protocol.subprocess.run(
                [sys.executable, script, "--state-root", root, "--runtime-release", release,
                 "--controller", str(Path(release, "unused-controller.py")), "--bundle-digest", bundle_digest],
                input=json.dumps(request_value), text=True, capture_output=True, check=False,
            )
            return completed

    def test_protocol_rejects_malformed_candidate_project_as_typed_json(self):
        for project_content in (b"metadata: [\n", b"\xff"):
            with self.subTest(project_content=project_content):
                completed = self._candidate_project_protocol_error(project_content)
                self.assertEqual(2, completed.returncode)
                self.assertEqual("", completed.stderr)
                self.assertEqual("PROJECT_SNAPSHOT_PROJECT_INVALID", json.loads(completed.stdout)["error"])

    def test_snapshot_uses_fixed_controller_playbook_and_removes_request_staging(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as release:
            Path(release, "catalog").mkdir()
            journal = Journal(root, "run-1")
            Path(journal.directory, "project", "inventory").mkdir(parents=True)
            Path(journal.directory, "project", "inventory", "hosts.yml").write_text("all: {hosts: {}}\n", encoding="utf-8")
            Path(journal.directory, "project", "project.yml").write_text("apiVersion: platform.installer/project/v2alpha1\n", encoding="utf-8")
            Path(journal.directory, execution_protocol.SNAPSHOT_OWNER_FILE).write_text(json.dumps({"kind": "readonly", "runId": "run-1"}), encoding="ascii")
            snapshot = {"projectRevision": "sha256:" + "a" * 64, "status": "PASS"}

            def completed(command, **kwargs):
                self.assertIn("project-snapshot.yml", command[-3])
                self.assertEqual("platform.core.project_snapshot_json", kwargs["env"]["ANSIBLE_CALLBACKS_ENABLED"])
                self.assertEqual([], json.loads(Path(command[-1][1:]).read_text(encoding="utf-8"))["platform_installer_owned_paths"])
                Path(kwargs["env"]["PLATFORM_PROJECT_SNAPSHOT_OUTPUT"]).write_text(json.dumps(snapshot), encoding="utf-8")
                return subprocess_completed(0)

            with mock.patch.object(execution_protocol.subprocess, "run", side_effect=completed):
                result = execution_protocol.snapshot({"runId": "run-1", "runtimeRelease": {}}, root, release, runtime_evidence())
            self.assertEqual(snapshot, result["projectSnapshot"])
            self.assertEqual(runtime_evidence(), result["runtimeEvidence"])
            self.assertFalse(Path(journal.directory).exists())

    def test_snapshot_does_not_remove_foreign_run_without_owner_marker(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as release:
            journal = Journal(root, "run-foreign")
            Path(journal.directory).mkdir(parents=True)
            sentinel = Path(journal.directory, "result.json")
            sentinel.write_text('{"status":"RUNNING"}\n', encoding="utf-8")
            with self.assertRaisesRegex(LifecycleError, "PROJECT_SNAPSHOT_STAGING_NOT_OWNED"):
                execution_protocol.snapshot({"runId": "run-foreign", "runtimeRelease": {}, "snapshotRequest": {"requestId": "malformed"}}, root, release, runtime_evidence())
            self.assertTrue(sentinel.is_file())

    def test_snapshot_cleanup_rechecks_owned_directory_identity(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-owned")
            Path(journal.directory).mkdir(parents=True)
            Path(journal.directory, execution_protocol.SNAPSHOT_OWNER_FILE).write_text(
                json.dumps({"kind": "readonly", "runId": "run-owned"}), encoding="ascii"
            )
            sentinel = Path(journal.directory, "result.json")
            sentinel.write_text('{"status":"RUNNING"}\n', encoding="utf-8")
            identity = (1, 2)
            with mock.patch.object(execution_protocol, "_snapshot_stage_identity", side_effect=[identity, None]):
                self.assertFalse(execution_protocol._cleanup_snapshot_staging(journal.directory, journal, identity))
            self.assertTrue(sentinel.is_file())

    def test_candidate_snapshot_uses_project_config_and_verifies_identity(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as release:
            Path(release, "catalog").mkdir()
            journal = Journal(root, "run-1")
            project = Path(journal.directory, "project")
            Path(project, "inventory").mkdir(parents=True)
            Path(project, "inventory", "hosts.yml").write_text("all: {hosts: {node1: {ansible_host: 192.0.2.10}}}\n", encoding="utf-8")
            Path(project, "ansible.cfg").write_bytes(execution_protocol.APPROVED_CANDIDATE_ANSIBLE_CONFIG)
            artifact = "sha256:" + "b" * 64
            catalog = "sha256:" + "c" * 64
            Path(release, "manifest.yaml").write_text("catalogDigest: %s\n" % catalog, encoding="utf-8")
            Path(project, "project.yml").write_text("metadata:\n  id: project-1\nartifactLock:\n  digest: %s\ncatalogLock:\n  digest: %s\n" % (artifact, catalog), encoding="utf-8")
            archive = "sha256:" + "d" * 64
            Path(journal.directory, "project-archive.digest").write_text(archive + "\n", encoding="ascii")
            revision = "sha256:" + "a" * 64
            request = {
                "apiVersion": execution_protocol.SNAPSHOT_REQUEST_VERSION, "kind": "BuildProjectSnapshotRequest",
                "requestId": "0" * 32, "projectIdentity": "project-1", "candidateProjectRevision": revision,
                "projectArchiveDigest": archive, "artifactLockDigest": artifact, "catalogLockDigest": catalog,
                "installerOwnedLogicalPaths": ["inventory/group_vars/all/platform-installer.yml"],
                "projectContract": "v2alpha1", "snapshotContract": "v1alpha1", "editContract": "v1alpha2",
            }

            def completed(command, **kwargs):
                self.assertNotIn("-i", command)
                self.assertEqual(str(Path(project, "ansible.cfg")), kwargs["env"]["ANSIBLE_CONFIG"])
                self.assertEqual(str(project), kwargs["cwd"])
                self.assertEqual(request["installerOwnedLogicalPaths"], json.loads(Path(command[-1][1:]).read_text(encoding="utf-8"))["platform_installer_owned_paths"])
                Path(kwargs["env"]["PLATFORM_PROJECT_SNAPSHOT_OUTPUT"]).write_text(json.dumps({"projectRevision": revision, "status": "PASS"}), encoding="utf-8")
                return subprocess_completed(0)

            with mock.patch.object(execution_protocol.subprocess, "run", side_effect=completed):
                result = execution_protocol.core_operation({"runId": "run-1", "runtimeRelease": {}, "snapshotRequest": request}, root, release, "BuildProjectSnapshot", runtime_evidence())
            self.assertEqual(revision, result["projectSnapshot"]["projectRevision"])
            self.assertEqual(runtime_evidence(), result["runtimeEvidence"])

    def _candidate_archive(self, path, members):
        with tarfile.open(path, "w:") as archive:
            for name, content, member_type in members:
                info = tarfile.TarInfo(name)
                info.type = member_type
                info.size = len(content) if member_type == tarfile.REGTYPE else 0
                archive.addfile(info, io.BytesIO(content) if member_type == tarfile.REGTYPE else None)
        return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def test_candidate_archive_preflight_and_safe_extraction(self):
        with tempfile.TemporaryDirectory() as state_root, tempfile.TemporaryDirectory() as transfer:
            run_id = "installer-candidate-safe"
            archive_path = Path(transfer, "project.tar")
            members = [
                ("project.yml", b"metadata: {id: project-1}\n", tarfile.REGTYPE),
                ("ansible.cfg", execution_protocol.APPROVED_CANDIDATE_ANSIBLE_CONFIG, tarfile.REGTYPE),
                ("inventory/hosts.yml", b"all: {hosts: {}}\n", tarfile.REGTYPE),
                ("inventory/group_vars/all/platform-installer.yml", b"platform: true\n", tarfile.REGTYPE),
            ]
            expected = self._candidate_archive(archive_path, members)
            with mock.patch.object(execution_protocol, "_candidate_archive_path", return_value=str(archive_path)):
                execution_protocol.stage_candidate_archive(str(archive_path), run_id, "0" * 32, expected, state_root)
            project = Path(state_root, "runs", run_id, "project")
            self.assertEqual(b"platform: true\n", Path(project, "inventory", "group_vars", "all", "platform-installer.yml").read_bytes())
            self.assertEqual(expected, Path(state_root, "runs", run_id, "project-archive.digest").read_text(encoding="ascii").strip())
            marker = json.loads(Path(state_root, "runs", run_id, execution_protocol.SNAPSHOT_OWNER_FILE).read_text(encoding="ascii"))
            self.assertEqual({"kind": "candidate", "runId": run_id, "requestId": "0" * 32, "archiveDigest": expected}, marker)
            self.assertFalse(Path(project, ".project-staging").exists())

    def test_candidate_exception_cleanup_preserves_replaced_owned_directory(self):
        with tempfile.TemporaryDirectory() as state_root, tempfile.TemporaryDirectory() as transfer:
            run_id = "installer-candidate-cleanup-race"
            request_id = "0" * 32
            archive_path = Path(transfer, "project.tar")
            members = [
                ("project.yml", b"metadata: {id: project-1}\n", tarfile.REGTYPE),
                ("ansible.cfg", execution_protocol.APPROVED_CANDIDATE_ANSIBLE_CONFIG, tarfile.REGTYPE),
                ("inventory/hosts.yml", b"all: {hosts: {}}\n", tarfile.REGTYPE),
            ]
            expected = self._candidate_archive(archive_path, members)
            identity = (1, 2)
            with mock.patch.object(execution_protocol, "_candidate_archive_path", return_value=str(archive_path)), \
                    mock.patch.object(execution_protocol, "_candidate_members", side_effect=LifecycleError("INJECTED")), \
                    mock.patch.object(execution_protocol, "_snapshot_stage_identity", side_effect=[identity, identity, None]):
                with self.assertRaisesRegex(LifecycleError, "INJECTED"):
                    execution_protocol.stage_candidate_archive(str(archive_path), run_id, request_id, expected, state_root)
            self.assertTrue(Path(state_root, "runs", run_id, execution_protocol.SNAPSHOT_OWNER_FILE).is_file())

    def test_candidate_archive_copy_rejects_same_inode_same_size_mutation(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root, "project.tar")
            source.write_bytes(b"verified archive bytes")
            expected = "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()
            original_info = source.stat()
            source.write_bytes(b"mutated!!archive bytes")
            mutated_info = source.stat()
            self.assertEqual((original_info.st_dev, original_info.st_ino, original_info.st_size),
                             (mutated_info.st_dev, mutated_info.st_ino, mutated_info.st_size))
            with self.assertRaisesRegex(LifecycleError, "PROJECT_SNAPSHOT_ARCHIVE_DIGEST_MISMATCH"):
                execution_protocol._copy_verified_candidate_archive(
                    str(source), str(Path(root, "verified.tar")), expected, original_info
                )

    def test_candidate_archive_rejects_malicious_members_and_config_without_staging(self):
        base = [
            ("project.yml", b"metadata: {id: project-1}\n", tarfile.REGTYPE),
            ("ansible.cfg", execution_protocol.APPROVED_CANDIDATE_ANSIBLE_CONFIG, tarfile.REGTYPE),
            ("inventory/hosts.yml", b"all: {hosts: {}}\n", tarfile.REGTYPE),
        ]
        cases = {
            "traversal": base + [("inventory/group_vars/../../escape.yml", b"x\n", tarfile.REGTYPE)],
            "hardlink": base + [("inventory/host_vars/node.yml", b"", tarfile.LNKTYPE)],
            "case-collision": base + [("inventory/group_vars/A.yml", b"a\n", tarfile.REGTYPE), ("inventory/group_vars/a.yml", b"b\n", tarfile.REGTYPE)],
            "plugin-config": [(name, b"[defaults]\nstrategy_plugins = ./plugins\n" if name == "ansible.cfg" else content, kind) for name, content, kind in base],
        }
        for name, members in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as state_root, tempfile.TemporaryDirectory() as transfer:
                run_id = "installer-candidate-" + name
                archive_path = Path(transfer, "project.tar")
                expected = self._candidate_archive(archive_path, members)
                with mock.patch.object(execution_protocol, "_candidate_archive_path", return_value=str(archive_path)):
                    with self.assertRaises((execution_protocol.LifecycleError, tarfile.TarError)):
                        execution_protocol.stage_candidate_archive(str(archive_path), run_id, "0" * 32, expected, state_root)
                self.assertFalse(Path(state_root, "runs", run_id).exists())

    def test_candidate_snapshot_rejects_config_changed_after_staging(self):
        with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as release:
            Path(project, "ansible.cfg").write_text("[defaults]\ncallback_plugins = ./plugins\n", encoding="utf-8")
            with self.assertRaisesRegex(execution_protocol.LifecycleError, "PROJECT_CANDIDATE_ANSIBLE_CONFIG_UNSAFE"):
                execution_protocol._candidate_ansible_environment(project, release, str(Path(project, "snapshot.json")))

    def test_candidate_ansible_environment_drops_inherited_plugin_overrides(self):
        with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as release:
            Path(project, "ansible.cfg").write_bytes(execution_protocol.APPROVED_CANDIDATE_ANSIBLE_CONFIG)
            with mock.patch.dict(execution_protocol.os.environ, {"ANSIBLE_STRATEGY_PLUGINS": "/tmp/untrusted", "ANSIBLE_CALLBACK_PLUGINS": "/tmp/untrusted"}):
                environment = execution_protocol._candidate_ansible_environment(project, release, str(Path(project, "snapshot.json")))
            self.assertNotIn("ANSIBLE_STRATEGY_PLUGINS", environment)
            self.assertNotIn("ANSIBLE_CALLBACK_PLUGINS", environment)

    def test_core_operation_returns_blocked_plan_without_manifest(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as release:
            journal = Journal(root, "run-1")
            Path(journal.directory, "project", "inventory").mkdir(parents=True)
            Path(journal.directory, "project", "inventory", "hosts.yml").write_text("all: {}\n", encoding="utf-8")
            Path(release, "ansible-core", "playbooks").mkdir(parents=True)
            Path(release, "manifest.yaml").write_text("artifactSources: []\n", encoding="utf-8")
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
            Path(release, "manifest.yaml").write_text("artifactSources: []\n", encoding="utf-8")
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

    def test_generic_source_authority_invocation_does_not_shadow_resolution_fact(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            journal.initialize(metadata())
            Path(journal.directory, "runtime-projection.json").write_text("{}", encoding="utf-8")
            command = execution_controller._command(root, journal, {"operation": "SERVICE_APPLY", "serviceType": "kafka", "serviceDeployment": "kafka", "requiresArtifactSources": True})
            self.assertIn("platform_artifact_source_authority_active=true", command)
            self.assertNotIn("platform_resolved_artifact_sources={}", command)

    def test_controller_uses_prepared_execution_identity_and_known_hosts(self):
        environment = execution_controller._environment("/runtime/release")
        self.assertIn("IdentityFile=/var/lib/platform-installer/execution/identities/default/id_ed25519", environment["ANSIBLE_SSH_ARGS"])
        self.assertIn("UserKnownHostsFile=/var/lib/platform-installer/execution/known_hosts", environment["ANSIBLE_SSH_ARGS"])
        self.assertIn("StrictHostKeyChecking=yes", environment["ANSIBLE_SSH_ARGS"])

    def test_service_projection_binding_is_verified_before_controller_start(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            manifest = {"operations": [{"operation": "PKI_APPLY", "operationId": "pki:apply"}, {"operation": "SERVICE_APPLY", "operationId": "apply:kafka", "serviceType": "kafka", "serviceDeployment": "kafka", "requiresArtifactSources": True}, {"operation": "SERVICE_VERIFY", "operationId": "verify:kafka", "serviceType": "kafka", "serviceDeployment": "kafka", "requiresArtifactSources": True}], "artifactRequirements": [{"id": "kafka:kafka-binary", "serviceDeployment": "kafka", "requirementId": "kafka-binary"}], "artifactSourceAuthorities": [{"requirement": {"id": "kafka:kafka-binary", "serviceDeployment": "kafka", "requirementId": "kafka-binary"}}]}
            current = metadata(); current["manifestDigest"] = digest(manifest)
            journal.initialize(current)
            execution_controller._materialize_runtime_projection(journal, current, manifest)
            execution_controller._validate_runtime_projection(journal, current, manifest)
            projection = json.loads(Path(journal.directory, "runtime-projection.json").read_text(encoding="utf-8"))
            self.assertEqual(projection["platform_project_root"], os.path.join(journal.directory, "project"))
            self.assertEqual(projection["platform_project_manifest_path"], os.path.join(journal.directory, "project", "project.yml"))
            self.assertIn("kafka-binary", projection["platform_artifact_source_authorities_by_deployment"]["kafka"])
            projection["platform_execution_run_id"] = "other-run"
            Path(journal.directory, "runtime-projection.json").write_text(json.dumps(projection), encoding="utf-8")
            with self.assertRaisesRegex(LifecycleError, "RUNTIME_PROJECTION_MISMATCH"):
                execution_controller._validate_runtime_projection(journal, current, manifest)

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

import base64
import errno
import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
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
import execution_target_trust


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
    def test_deployment_plan_order_request_is_versioned_and_closed(self):
        base = {
            "apiVersion": "platform.installer/execution-runtime/v1alpha2",
            "operation": "BuildDeploymentPlan",
            "runId": "run-1",
            "project": "/var/lib/platform-installer/project",
            "runtimeRelease": {"bundleDigest": "sha256:" + "a" * 64},
            "deploymentOrder": ["bind-main", "vault-ha"],
        }

        def parse(value):
            with mock.patch.object(execution_protocol.sys, "stdin", io.StringIO(json.dumps(value))):
                return execution_protocol.request()

        self.assertEqual(base, parse(base))
        empty = dict(base, deploymentOrder=[])
        self.assertEqual([], parse(empty)["deploymentOrder"])
        cases = [
            (dict(base, apiVersion="platform.installer/execution-runtime/v1alpha1"), "DEPLOYMENT_ORDER_REQUEST_VERSION_REQUIRED"),
            ({key: value for key, value in base.items() if key != "deploymentOrder"}, "DEPLOYMENT_ORDER_REQUEST_INVALID"),
            (dict(base, deploymentOrder=None), "DEPLOYMENT_ORDER_REQUEST_INVALID"),
            (dict(base, deploymentOrder=["bind-main", "bind-main"]), "DEPLOYMENT_ORDER_REQUEST_INVALID"),
            (dict(base, deploymentOrder=["bind-main", 1]), "DEPLOYMENT_ORDER_REQUEST_INVALID"),
            (dict(base, extra=True), "DEPLOYMENT_ORDER_REQUEST_INVALID"),
        ]
        for value, code in cases:
            with self.subTest(code=code, value=value), self.assertRaises(execution_protocol.LifecycleError) as caught:
                parse(value)
            self.assertEqual(code, str(caught.exception))

    def test_staged_host_trust_survives_authoritative_hex_run_id(self):
        with tempfile.TemporaryDirectory() as root:
            runs = Path(root, "runs")
            runs.mkdir(mode=0o700)
            staging = runs / "installer-123456"
            staging.mkdir(mode=0o700)
            manifest = {
                "projectIdentity": "project-1", "projectRevision": "sha256:" + "1" * 64,
                "planFingerprint": "sha256:" + "2" * 64,
                "runtimeRelease": {"bundleDigest": "sha256:" + "3" * 64},
                "operations": [{"operation": "PKI_APPLY"}],
                "targetConnections": {"node1": {"address": "192.0.2.1", "port": 22,
                                                "mode": "ssh", "unsupportedOptions": False}},
            }
            path = staging / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            path.chmod(0o600)
            kind = "ssh-ed25519"
            key = base64.b64encode(len(kind).to_bytes(4, "big") + kind.encode() + b"a" * 32).decode()
            execution_target_trust.stage(root, {
                "stagingId": staging.name, "projectIdentity": manifest["projectIdentity"],
                "projectRevision": manifest["projectRevision"],
                "planFingerprint": manifest["planFingerprint"],
                "runtimeRelease": manifest["runtimeRelease"],
                "manifestDigest": digest(manifest),
                "approvals": [{"hostId": "node1", "address": "192.0.2.1", "port": 22,
                               "keyType": kind, "publicKey": key}],
            })
            run = runs / ("installer-" + "a1" * 16)
            staging.rename(run)
            self.assertEqual(str(run / "known_hosts"),
                             execution_target_trust.verify(root, run.name, manifest))

    def test_controller_admits_clickhouse_as_a_closed_service_type(self):
        self.assertTrue(execution_controller._safe_service("clickhouse"))
        self.assertFalse(execution_controller._safe_service("clickhouse-extra"))

    def test_controller_output_preparation_failure_terminates_committed_run(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            record = metadata()
            journal.initialize(record)
            manifest = {"projectIdentity": record["projectIdentity"],
                        "planFingerprint": record["planFingerprint"],
                        "runtimeRelease": {"bundleDigest": record["runtimeRelease"]}, "operations": []}
            Path(journal.directory, "manifest.json").write_text(json.dumps(manifest))
            args = ["controller", "--state-root", root, "--run-id", "run-1",
                    "--runtime-release", root, "--bundle-digest", record["runtimeRelease"]]
            with mock.patch.object(sys, "argv", args), \
                    mock.patch.object(execution_controller, "_materialize_runtime_projection",
                                      side_effect=execution_controller.execution_secret_output.OutputWireError("OUTPUT_ACCESS_DENIED")), \
                    mock.patch.object(execution_controller.execution_secret_lease, "cleanup_run") as cleanup, \
                    mock.patch.object(execution_controller, "_dispatch") as dispatch:
                self.assertEqual(2, execution_controller.main())
            self.assertEqual("FAILED", journal.status()["state"])
            self.assertEqual(record, journal.metadata())
            result = json.loads(Path(journal.result_path).read_text(encoding="utf-8"))
            self.assertEqual("EXECUTION_CONTROLLER_PREPARATION_FAILED", result["error"]["code"])
            self.assertIn("diagnostic: OUTPUT_ACCESS_DENIED", result["error"]["summary"])
            cleanup.assert_called_once_with(root, "run-1")
            dispatch.assert_not_called()

    def test_controller_preparation_diagnostic_never_persists_raw_exception_text(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            record = metadata()
            journal.initialize(record)
            manifest = {"projectIdentity": record["projectIdentity"],
                        "planFingerprint": record["planFingerprint"],
                        "runtimeRelease": {"bundleDigest": record["runtimeRelease"]}, "operations": []}
            Path(journal.directory, "manifest.json").write_text(json.dumps(manifest))
            args = ["controller", "--state-root", root, "--run-id", "run-1",
                    "--runtime-release", root, "--bundle-digest", record["runtimeRelease"]]
            raw = "sensitive-path-and-value-must-not-be-recorded"
            with mock.patch.object(sys, "argv", args), \
                    mock.patch.object(execution_controller, "_materialize_runtime_projection",
                                      side_effect=ValueError(raw)), \
                    mock.patch.object(execution_controller.execution_secret_lease, "cleanup_run"), \
                    mock.patch.object(execution_controller, "_dispatch") as dispatch:
                self.assertEqual(2, execution_controller.main())
            result_text = Path(journal.result_path).read_text(encoding="utf-8")
            result = json.loads(result_text)
            self.assertEqual("EXECUTION_CONTROLLER_PREPARATION_FAILED", result["error"]["code"])
            self.assertIn("diagnostic: EXECUTION_CONTROLLER_PREPARATION_VALUE_ERROR", result["error"]["summary"])
            self.assertNotIn(raw, result_text)
            dispatch.assert_not_called()

    def test_controller_preparation_diagnostic_classifies_os_errors_without_paths(self):
        error = OSError(errno.EACCES, "private path must not be logged")
        self.assertEqual("EXECUTION_CONTROLLER_PREPARATION_EACCES",
                         execution_controller._preparation_diagnostic_code(error))

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

    def test_fast_configuration_preview_uses_fixed_target_free_playbook(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as release:
            journal = Journal(root, "run-preview")
            project = Path(journal.directory, "project")
            Path(project, "inventory").mkdir(parents=True)
            revision = "sha256:" + "a" * 64
            preview = {"apiVersion": "platform.installer/service-configuration-preview/v1alpha1", "kind": "ServiceConfigurationPreview", "projectRevision": revision, "services": {}}

            def completed(command, **kwargs):
                self.assertIn("-i", command)
                self.assertTrue(command[-3].endswith("service-configuration-preview.yml"))
                self.assertEqual("platform.core.project_snapshot_json", kwargs["env"]["ANSIBLE_CALLBACKS_ENABLED"])
                Path(kwargs["env"]["PLATFORM_PROJECT_SNAPSHOT_OUTPUT"]).write_text(json.dumps(preview), encoding="utf-8")
                return subprocess_completed(0)

            with mock.patch.object(execution_protocol.subprocess, "run", side_effect=completed):
                result = execution_protocol.core_operation({"runId": "run-preview", "runtimeRelease": {}}, root, release, "BuildServiceConfigurationPreview", runtime_evidence())
            self.assertEqual(preview, result["serviceConfigurationPreview"])
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
                    {"runId": "run-1", "runtimeRelease": {}, "deploymentOrder": []}, root, release, "BuildDeploymentPlan"
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
                        {"runId": "run-1", "runtimeRelease": {}, "deploymentOrder": []}, root, release, "BuildDeploymentPlan"
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
            secret_name = ".runtime-secret-inputs-" + hashlib.sha256(b"apply:vault").hexdigest() + ".json"
            secret_path = Path(journal.directory, secret_name)
            secret_path.write_text('{"value":"secret-canary"}', encoding="utf-8")
            foreign = Path(root, "foreign-secret-target")
            foreign.write_text("foreign", encoding="utf-8")
            symlink_path = Path(journal.directory, ".runtime-secret-inputs-" + hashlib.sha256(b"verify:vault").hexdigest() + ".json")
            symlink_path.symlink_to(foreign)
            non_regular_path = Path(journal.directory, ".runtime-secret-inputs-" + hashlib.sha256(b"other:vault").hexdigest() + ".json")
            non_regular_path.mkdir()
            runtime_dir = Path(journal.directory, ".ansible-runtime")
            runtime_dir.mkdir(mode=0o700)
            key_path = runtime_dir / "target-key-12345678.pem"
            key_path.write_text("synthetic-private-key", encoding="utf-8")
            bootstrap_path = runtime_dir / "bootstrap-12345678.json"
            bootstrap_path.write_text("{}", encoding="utf-8")
            connection_input = Path(journal.directory, ".ansible-runtime-credentials.json")
            connection_input.write_text("synthetic", encoding="utf-8")
            self.assertEqual(["run-1"], recover(root, lambda _unit, _metadata: False))
            self.assertEqual([], recover(root, lambda _unit, _metadata: False))
            self.assertEqual("INTERRUPTED", journal.status()["state"])
            self.assertFalse(secret_path.exists())
            self.assertTrue(symlink_path.is_symlink())
            self.assertEqual("foreign", foreign.read_text(encoding="utf-8"))
            self.assertTrue(non_regular_path.is_dir())
            self.assertFalse(key_path.exists())
            self.assertFalse(bootstrap_path.exists())
            self.assertFalse(connection_input.exists())

    def test_cancel_missing_controller_removes_typed_secret_input_file(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            journal.initialize(metadata())
            manifest = {"projectIdentity": "project-1", "planFingerprint": metadata()["planFingerprint"], "runtimeRelease": {"bundleDigest": metadata()["runtimeRelease"]}, "operations": []}
            Path(journal.directory, "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            journal.transition("RUNNING", "running")
            secret_path = Path(journal.directory, ".runtime-secret-inputs-" + hashlib.sha256(b"apply:vault").hexdigest() + ".json")
            secret_path.write_text('{"value":"secret-canary"}', encoding="utf-8")
            runtime_dir = Path(journal.directory, ".ansible-runtime")
            runtime_dir.mkdir(mode=0o700)
            key_path = runtime_dir / "target-key-12345678.pem"
            key_path.write_text("synthetic-private-key", encoding="utf-8")
            connection_input = Path(journal.directory, ".ansible-runtime-credentials.json")
            connection_input.write_text("synthetic", encoding="utf-8")
            with mock.patch.object(execution_protocol, "active", return_value=False):
                result = execution_protocol.cancel({"runId": "run-1"}, root)
                repeated = execution_protocol.cancel({"runId": "run-1"}, root)
            self.assertEqual("INTERRUPTED", result["run"]["state"])
            self.assertTrue(repeated["idempotent"])
            self.assertFalse(secret_path.exists())
            self.assertFalse(key_path.exists())
            self.assertFalse(connection_input.exists())

    def test_cancel_active_unit_cleans_key_only_after_confirmed_stop(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            journal.initialize(metadata())
            manifest = {"projectIdentity": "project-1", "planFingerprint": metadata()["planFingerprint"], "runtimeRelease": {"bundleDigest": metadata()["runtimeRelease"]}, "operations": []}
            Path(journal.directory, "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            journal.transition("RUNNING", "running")
            runtime_dir = Path(journal.directory, ".ansible-runtime")
            runtime_dir.mkdir(mode=0o700)
            key_path = runtime_dir / "target-key-12345678.pem"
            key_path.write_text("synthetic-private-key", encoding="utf-8")
            bootstrap_path = runtime_dir / "bootstrap-12345678.json"
            bootstrap_path.write_text("{}", encoding="utf-8")
            connection_input = Path(journal.directory, ".ansible-runtime-credentials.json")
            connection_input.write_text("synthetic", encoding="utf-8")
            def stopped(_command, **_kwargs):
                self.assertTrue(key_path.exists())
                self.assertEqual("CANCELLED", journal.status()["state"])
            with mock.patch.object(execution_protocol, "active", side_effect=[True, False, False]), mock.patch.object(execution_protocol.subprocess, "check_call", side_effect=stopped) as stop:
                result = execution_protocol.cancel({"runId": "run-1"}, root)
                repeated = execution_protocol.cancel({"runId": "run-1"}, root)
            self.assertEqual(1, stop.call_count)
            self.assertFalse(result["idempotent"])
            self.assertEqual("CANCELLED", repeated["run"]["state"])
            self.assertTrue(repeated["idempotent"])
            self.assertFalse(key_path.exists())
            self.assertFalse(bootstrap_path.exists())
            self.assertFalse(connection_input.exists())

    def test_cancel_stop_failure_retains_key_until_unit_is_inactive(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            journal.initialize(metadata())
            manifest = {"projectIdentity": "project-1", "planFingerprint": metadata()["planFingerprint"], "runtimeRelease": {"bundleDigest": metadata()["runtimeRelease"]}, "operations": []}
            Path(journal.directory, "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            journal.transition("RUNNING", "running")
            runtime_dir = Path(journal.directory, ".ansible-runtime")
            runtime_dir.mkdir(mode=0o700)
            key_path = runtime_dir / "target-key-12345678.pem"
            key_path.write_text("synthetic-private-key", encoding="utf-8")
            with mock.patch.object(execution_protocol, "active", side_effect=[True, True, False]), mock.patch.object(execution_protocol.subprocess, "check_call", side_effect=[subprocess.CalledProcessError(1, "systemctl"), None]) as stop:
                with self.assertRaises(subprocess.CalledProcessError):
                    execution_protocol.cancel({"runId": "run-1"}, root)
                self.assertTrue(key_path.exists())
                repeated = execution_protocol.cancel({"runId": "run-1"}, root)
            self.assertEqual(2, stop.call_count)
            self.assertTrue(repeated["idempotent"])
            self.assertFalse(key_path.exists())

    def test_unit_status_query_failure_cannot_authorize_cancel_cleanup(self):
        current = metadata()
        unit = current["unit"]
        result = subprocess.CompletedProcess([], 1, stdout="inactive")
        with mock.patch.object(execution_protocol.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(LifecycleError, "EXECUTION_UNIT_STATUS_UNAVAILABLE"):
                execution_protocol.active(unit, current)
        with mock.patch.object(execution_protocol.subprocess, "run", side_effect=OSError("systemd unavailable")):
            with self.assertRaisesRegex(LifecycleError, "EXECUTION_UNIT_STATUS_UNAVAILABLE"):
                execution_protocol.active(unit, current)
        for state, expected in (("active", True), ("deactivating", True), ("inactive", False), ("failed", False)):
            with self.subTest(state=state), mock.patch.object(execution_protocol.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout=state + "\n")):
                self.assertEqual(expected, execution_protocol.active(unit, current))

    def test_cancel_status_query_failure_retains_key_then_retry_cleans_after_inactive(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            journal.initialize(metadata())
            manifest = {"projectIdentity": "project-1", "planFingerprint": metadata()["planFingerprint"], "runtimeRelease": {"bundleDigest": metadata()["runtimeRelease"]}, "operations": []}
            Path(journal.directory, "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            journal.transition("RUNNING", "running")
            runtime_dir = Path(journal.directory, ".ansible-runtime")
            runtime_dir.mkdir(mode=0o700)
            key_path = runtime_dir / "target-key-12345678.pem"
            key_path.write_text("synthetic-private-key", encoding="utf-8")
            connection_input = Path(journal.directory, ".ansible-runtime-credentials.json")
            connection_input.write_text("synthetic", encoding="utf-8")
            with mock.patch.object(execution_protocol, "active", side_effect=[LifecycleError("EXECUTION_UNIT_STATUS_UNAVAILABLE"), True, LifecycleError("EXECUTION_UNIT_STATUS_UNAVAILABLE"), False]), mock.patch.object(execution_protocol.subprocess, "check_call") as stop:
                with self.assertRaisesRegex(LifecycleError, "EXECUTION_UNIT_STATUS_UNAVAILABLE"):
                    execution_protocol.cancel({"runId": "run-1"}, root)
                self.assertEqual("RUNNING", journal.status()["state"])
                self.assertTrue(key_path.exists())
                with self.assertRaisesRegex(LifecycleError, "EXECUTION_UNIT_STATUS_UNAVAILABLE"):
                    execution_protocol.cancel({"runId": "run-1"}, root)
                self.assertEqual("CANCELLED", journal.status()["state"])
                self.assertTrue(key_path.exists())
                repeated = execution_protocol.cancel({"runId": "run-1"}, root)
            self.assertEqual(1, stop.call_count)
            self.assertTrue(repeated["idempotent"])
            self.assertFalse(key_path.exists())
            self.assertFalse(connection_input.exists())

    def test_cancel_failed_stop_get_retains_key_until_confirmed_inactive(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            journal.initialize(metadata())
            manifest = {"projectIdentity": "project-1", "planFingerprint": metadata()["planFingerprint"], "runtimeRelease": {"bundleDigest": metadata()["runtimeRelease"]}, "operations": []}
            Path(journal.directory, "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            journal.transition("RUNNING", "running")
            runtime_dir = Path(journal.directory, ".ansible-runtime")
            runtime_dir.mkdir(mode=0o700)
            key_path = runtime_dir / "target-key-12345678.pem"
            key_path.write_text("synthetic-private-key", encoding="utf-8")
            connection_input = Path(journal.directory, ".ansible-runtime-credentials.json")
            connection_input.write_text("synthetic", encoding="utf-8")
            lease_request = {"requestId": "1" * 32, "startAttemptId": "2" * 32,
                             "projectIdentity": "project-1", "projectRevision": "sha256:" + "a" * 64,
                             "planFingerprint": metadata()["planFingerprint"],
                             "executionManifestDigest": metadata()["manifestDigest"],
                             "runtimeRelease": {"bundleDigest": metadata()["runtimeRelease"],
                                                "coreVersion": "test-core", "catalogDigest": "sha256:" + "b" * 64,
                                                "planningProtocol": "v1alpha1"}}
            lease_payload = {"apiVersion": execution_protocol.execution_secret_lease.PAYLOAD_VERSION,
                             "kind": "TargetCredentialLeasePayload", "username": "test-operator",
                             "password": "synthetic-password", "privateKey": None, "sudoPassword": None}
            stored = execution_protocol.execution_secret_lease.put(root, lease_request, lease_payload)
            self.assertTrue(execution_protocol.execution_secret_lease.attach(root, stored["leaseId"], lease_request, "run-1"))
            payload_path = Path(execution_protocol.execution_secret_lease.payload_path(root, stored["leaseId"], "run-1"))
            status_unavailable = LifecycleError("EXECUTION_UNIT_STATUS_UNAVAILABLE")
            with mock.patch.object(execution_protocol, "active", side_effect=[True, True, True, status_unavailable, status_unavailable, False, False]), mock.patch.object(execution_protocol.subprocess, "check_call", side_effect=subprocess.CalledProcessError(1, "systemctl")):
                with self.assertRaises(subprocess.CalledProcessError):
                    execution_protocol.cancel({"runId": "run-1"}, root)
                self.assertEqual("CANCELLED", journal.status()["state"])
                self.assertTrue(key_path.exists())
                self.assertEqual("CANCELLED", execution_protocol.get({"runId": "run-1"}, root)["run"]["state"])
                self.assertTrue(key_path.exists())
                self.assertTrue(connection_input.exists())
                self.assertTrue(payload_path.exists())
                self.assertEqual("test-operator", execution_protocol.execution_secret_lease.target_username_for_run(root, "run-1"))
                with self.assertRaisesRegex(LifecycleError, "EXECUTION_UNIT_STATUS_UNAVAILABLE"):
                    execution_protocol.get({"runId": "run-1"}, root)
                self.assertTrue(key_path.exists())
                self.assertTrue(connection_input.exists())
                self.assertTrue(payload_path.exists())
                self.assertEqual("test-operator", execution_protocol.execution_secret_lease.target_username_for_run(root, "run-1"))
                self.assertEqual("CANCELLED", execution_protocol.get({"runId": "run-1"}, root)["run"]["state"])
            self.assertFalse(key_path.exists())
            self.assertFalse(connection_input.exists())
            self.assertFalse(payload_path.exists())
            self.assertIsNone(execution_protocol.execution_secret_lease.target_username_for_run(root, "run-1"))

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

    def test_concurrent_pki_apply_for_same_project_is_rejected_until_deploy_finishes(self):
        with tempfile.TemporaryDirectory() as root:
            first = Journal(root, "run-first")
            second = Journal(root, "run-second")
            first.initialize(metadata("run-first", "same-project"))
            second.initialize(metadata("run-second", "same-project"))
            operation = {"operationId": "pki:apply", "operation": "PKI_APPLY", "phaseId": "apply"}
            manifest = {"operations": [operation]}
            entered_ansible = threading.Event()
            finish_ansible = threading.Event()
            first_result = []

            def wait_for_pki(_process, _stopped, _capture=False):
                entered_ansible.set()
                if threading.current_thread().name == "first-pki-apply":
                    if not finish_ansible.wait(5):
                        raise AssertionError("first PKI apply did not finish its simulated materialize+deploy interval")
                return 0, "", None

            def run_first():
                try:
                    first_result.append(execution_controller._dispatch(root, first, manifest, [False]))
                except Exception as error:  # surfaced in the owning test thread
                    first_result.append(error)

            with mock.patch.object(execution_controller, "_command", return_value=["ansible-playbook", "pki-apply.yml"]), \
                 mock.patch.object(execution_controller.execution_target_trust, "verify", return_value="/tmp/known_hosts"), \
                 mock.patch.object(execution_controller.execution_secret_lease, "ansible_connection_credentials_for_run", return_value=None), \
                 mock.patch.object(execution_controller.subprocess, "Popen", return_value=object()) as launch, \
                 mock.patch.object(execution_controller, "_wait_for_operation", side_effect=wait_for_pki):
                thread = threading.Thread(target=run_first, name="first-pki-apply")
                thread.start()
                self.assertTrue(entered_ansible.wait(5), "first PKI apply did not enter the protected operation")
                with self.assertRaisesRegex(LifecycleError, "PKI_APPLY_ALREADY_RUNNING"):
                    execution_controller._dispatch(root, second, manifest, [False])
                self.assertEqual(1, launch.call_count, "the rejected operation must not launch Ansible")
                finish_ansible.set()
                thread.join(5)
                self.assertFalse(thread.is_alive())
            self.assertEqual(["SUCCEEDED"], first_result)
            self.assertTrue(Path(root, "projects", "same-project", ".pki-apply.lock").is_file())
            # The advisory lock is released after the operation even though its
            # protected lock-file inode remains for the next run.
            retry_lock = execution_controller._acquire_project_pki_apply_lock(second)
            os.close(retry_lock)

    def test_reissue_uses_the_same_project_pki_lock(self):
        with tempfile.TemporaryDirectory() as root:
            first = Journal(root, "run-first")
            second = Journal(root, "run-second")
            first.initialize(metadata("run-first", "same-project"))
            second.initialize(metadata("run-second", "same-project"))
            descriptor = execution_controller._acquire_project_pki_apply_lock(first)
            operation = {"operationId": "pki:reissue", "operation": "PKI_REISSUE", "phaseId": "pki",
                         "reissueRequests": [{"requestId": "tls--node1", "expectedOldFingerprint": "sha256:" + "a" * 64,
                                              "desiredFingerprint": "sha256:" + "b" * 64, "recoveryFingerprint": None}]}
            try:
                with mock.patch.object(execution_controller, "_command", return_value=["ansible-playbook"]), \
                     mock.patch.object(execution_controller.execution_target_trust, "verify", return_value="/tmp/known_hosts"), \
                     mock.patch.object(execution_controller.subprocess, "Popen") as launch:
                    with self.assertRaisesRegex(LifecycleError, "PKI_APPLY_ALREADY_RUNNING"):
                        execution_controller._dispatch(root, second, {"operations": [operation]}, [False])
                    launch.assert_not_called()
            finally:
                os.close(descriptor)

    def test_reissue_command_selects_only_manifest_bound_request_ids(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            journal.initialize(metadata())
            (Path(journal.directory) / "runtime-projection.json").write_text("{}", encoding="utf-8")
            operation = {"operationId": "pki:reissue", "operation": "PKI_REISSUE",
                         "reissueRequests": [{"requestId": "tls--node1"}]}
            command = execution_controller._command(root, journal, operation)
            self.assertIn("pki-reissue.yml", " ".join(command))
            self.assertEqual('{"platform_pki_reissue_request_ids":["tls--node1"]}', command[-1])

    @unittest.skipUnless(shutil.which("ansible"), "real Ansible CLI is required")
    def test_reissue_command_extra_var_arrives_as_ansible_list(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            journal.initialize(metadata())
            (Path(journal.directory) / "runtime-projection.json").write_text("{}", encoding="utf-8")
            operation = {"operationId": "pki:reissue", "operation": "PKI_REISSUE",
                         "reissueRequests": [{"requestId": "tls--node1"}]}
            extra = execution_controller._command(root, journal, operation)[-1]
            result = subprocess.run(
                ["ansible", "localhost", "-i", "localhost,", "-c", "local", "-m", "debug",
                 "-a", "msg={{ platform_pki_reissue_request_ids | type_debug }}", "-e", extra],
                capture_output=True, text=True, timeout=30, check=False)
            self.assertEqual(0, result.returncode, result.stderr[-2000:])
            self.assertIn('"msg": "list"', result.stdout)

    def test_reissue_rechecks_marker_under_lock_before_launch(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            journal.initialize(metadata())
            request_dir = Path(root, "pki", "project-1", "requests", "tls--node1")
            request_dir.mkdir(parents=True)
            (request_dir / "request-fingerprint").write_text("sha256:" + "c" * 64 + "\n", encoding="ascii")
            for name in ("leaf.key", "leaf.crt"):
                (request_dir / name).write_bytes(b"test")
            authority_dir = Path(root, "pki", "project-1", "authorities", "platform-ca")
            authority_dir.mkdir(parents=True)
            (authority_dir / "authority-fingerprint").write_text("sha256:" + "d" * 64 + "\n", encoding="ascii")
            for name in ("ca.key", "ca.crt"):
                (authority_dir / name).write_bytes(b"test")
            operation = {"operationId": "pki:reissue", "operation": "PKI_REISSUE", "phaseId": "pki",
                         "reissueRequests": [{"requestId": "tls--node1", "expectedOldFingerprint": "sha256:" + "a" * 64,
                                              "desiredFingerprint": "sha256:" + "b" * 64, "recoveryFingerprint": None,
                                              "authorityId": "platform-ca", "authorityFingerprint": "sha256:" + "d" * 64}]}
            with mock.patch.object(execution_controller, "_command", return_value=["ansible-playbook"]), \
                 mock.patch.object(execution_controller.execution_target_trust, "verify", return_value="/tmp/known_hosts"), \
                 mock.patch.object(execution_controller.subprocess, "Popen") as launch:
                with self.assertRaisesRegex(LifecycleError, "PKI_REISSUE_PLAN_STALE"):
                    execution_controller._dispatch(root, journal, {"operations": [operation]}, [False])
                launch.assert_not_called()

    def test_pki_apply_locks_are_independent_between_projects(self):
        with tempfile.TemporaryDirectory() as root:
            first = Journal(root, "run-first")
            second = Journal(root, "run-second")
            first.initialize(metadata("run-first", "project-one"))
            second.initialize(metadata("run-second", "project-two"))
            first_lock = execution_controller._acquire_project_pki_apply_lock(first)
            try:
                second_lock = execution_controller._acquire_project_pki_apply_lock(second)
                os.close(second_lock)
                with self.assertRaisesRegex(LifecycleError, "PKI_APPLY_ALREADY_RUNNING"):
                    execution_controller._acquire_project_pki_apply_lock(first)
            finally:
                os.close(first_lock)

    def test_pki_apply_lock_rejects_symlink_substitution(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            journal.initialize(metadata())
            execution_controller._generated_state_path(root, "project-1")
            lock_path = Path(root, "projects", "project-1", ".pki-apply.lock")
            target = Path(root, "foreign-lock")
            target.write_text("", encoding="utf-8")
            lock_path.symlink_to(target)
            with self.assertRaisesRegex(LifecycleError, "PKI_APPLY_LOCK_UNAVAILABLE"):
                execution_controller._acquire_project_pki_apply_lock(journal)
            self.assertEqual("", target.read_text(encoding="utf-8"))

    def test_service_dispatch_requires_existing_runtime_projection(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1"); journal.initialize(metadata())
            with self.assertRaisesRegex(LifecycleError, "RUNTIME_PROJECTION_MISSING"):
                execution_controller._dispatch(root, journal, {"operations": [{"operationId": "apply:kafka", "operation": "SERVICE_APPLY", "serviceType": "kafka"}]}, [False])

    def test_redis_is_an_admitted_generic_service_operation(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1"); journal.initialize(metadata())
            operation = {"operationId": "apply:redis-main", "operation": "SERVICE_APPLY", "serviceType": "redis", "serviceDeployment": "redis-main", "targets": ["node1"]}
            projection_id = hashlib.sha256(operation["operationId"].encode("utf-8")).hexdigest()
            Path(journal.directory, ".runtime-projection-" + projection_id + ".json").write_text("{}", encoding="utf-8")
            command = execution_controller._command("/runtime/release", journal, operation)
            self.assertEqual("/runtime/release/services/redis/playbooks/apply.yml", command[3])
            self.assertIn("platform_execution_service_deployment=redis-main", command)
            self.assertEqual("localhost:node1", command[command.index("--limit") + 1])
            self.assertEqual("SERVICE_APPLY", operation["operation"])

    def test_service_limit_rejects_missing_broad_or_conflicting_targets(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1"); journal.initialize(metadata())
            base = {"operationId": "verify:docker", "operation": "SERVICE_VERIFY", "serviceType": "docker", "serviceDeployment": "docker"}
            digest_id = hashlib.sha256(base["operationId"].encode("utf-8")).hexdigest()
            Path(journal.directory, ".runtime-projection-" + digest_id + ".json").write_text("{}", encoding="utf-8")
            for targets in (None, [], ["all"], ["localhost"], ["node1", "node1"], ["node1:node2"], ["node2", "node1"], ["node1", 2]):
                with self.subTest(targets=targets):
                    operation = dict(base)
                    if targets is not None:
                        operation["targets"] = targets
                    with self.assertRaisesRegex(LifecycleError, "EXECUTION_MANIFEST_INVALID"):
                        execution_controller._command("/runtime/release", journal, operation)
            operation = dict(base, targets=["node1"], roleVariablesPrefix="platform_docker_",
                             roleVariablesByHost={"node2": {"platform_docker_mode": "create-user"}})
            with self.assertRaisesRegex(LifecycleError, "EXECUTION_MANIFEST_INVALID"):
                execution_controller._command("/runtime/release", journal, operation)
            operation["targets"] = ["node1", "node2", "node3"]
            operation["roleVariablesByHost"] = {
                host: {"platform_docker_mode": "create-user"} for host in operation["targets"]
            }
            command = execution_controller._command("/runtime/release", journal, operation)
            self.assertEqual("localhost:node1:node2:node3", command[command.index("--limit") + 1])

    def test_generic_source_authority_invocation_does_not_shadow_resolution_fact(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            journal.initialize(metadata())
            operation = {"operationId": "apply:kafka", "operation": "SERVICE_APPLY", "serviceType": "kafka", "serviceDeployment": "kafka", "targets": ["node1"], "requiresArtifactSources": True}
            digest_id = hashlib.sha256(operation["operationId"].encode("utf-8")).hexdigest()
            Path(journal.directory, ".runtime-projection-" + digest_id + ".json").write_text("{}", encoding="utf-8")
            command = execution_controller._command(root, journal, operation)
            self.assertIn("platform_artifact_source_authority_active=true", command)
            self.assertNotIn("platform_resolved_artifact_sources={}", command)

    def test_controller_uses_prepared_execution_identity_and_known_hosts(self):
        environment = execution_controller._environment("/runtime/release")
        self.assertIn("IdentityFile=/var/lib/platform-installer/execution/identities/default/id_ed25519", environment["ANSIBLE_SSH_ARGS"])
        self.assertIn("UserKnownHostsFile=/var/lib/platform-installer/execution/known_hosts", environment["ANSIBLE_SSH_ARGS"])
        self.assertIn("StrictHostKeyChecking=yes", environment["ANSIBLE_SSH_ARGS"])

    def test_controller_wraps_password_lease_only_in_ephemeral_runner_and_removes_input(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1"); journal.initialize(metadata())
            operation = {"operation": "CORE_DELAY", "operationId": "core:delay", "phaseId": "apply"}
            captured = {}

            class Completed(object):
                returncode = 0
                stdout = type("Out", (), {"fileno": lambda self: 0, "close": lambda self: None})()
                def poll(self): return 0

            def opened(command, **_kwargs):
                captured["command"] = command
                credential_path = Path(command[command.index("--credentials-file") + 1])
                captured["credentials"] = json.loads(credential_path.read_text(encoding="utf-8"))
                self.assertEqual(0o600, stat.S_IMODE(credential_path.stat().st_mode))
                return Completed()

            with mock.patch.object(execution_controller, "_command", return_value=["ansible-playbook", "site.yml"]), mock.patch.object(execution_controller.execution_secret_lease, "ansible_connection_credentials_for_run", return_value={"ansible_password": "test", "ansible_become_password": "test"}), mock.patch.object(execution_controller.subprocess, "Popen", side_effect=opened), mock.patch.object(execution_controller, "_wait_for_operation", return_value=(0, "", None)):
                self.assertEqual("SUCCEEDED", execution_controller._dispatch("/runtime/release", journal, {"operations": [operation]}, [False]))
            self.assertEqual({"ansible_password": "test", "ansible_become_password": "test"}, captured["credentials"])
            self.assertFalse(Path(journal.directory, ".ansible-runtime-credentials.json").exists())

    def test_controller_private_key_lease_disables_missing_prepared_identity(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1"); journal.initialize(metadata())
            operation = {"operation": "CORE_DELAY", "operationId": "core:delay", "phaseId": "apply"}
            captured = {}
            def opened(command, **kwargs):
                captured["command"] = command
                captured["env"] = kwargs["env"]
                credential_path = Path(command[command.index("--credentials-file") + 1])
                captured["credentials"] = json.loads(credential_path.read_text(encoding="utf-8"))
                self.assertEqual(0o600, stat.S_IMODE(credential_path.stat().st_mode))
                return object()
            with mock.patch.object(execution_controller, "_command", return_value=["ansible-playbook", "site.yml"]), mock.patch.object(execution_controller.execution_secret_lease, "ansible_connection_credentials_for_run", return_value={"privateKey": "synthetic-private-key"}), mock.patch.object(execution_controller.subprocess, "Popen", side_effect=opened), mock.patch.object(execution_controller, "_wait_for_operation", return_value=(0, "", None)):
                self.assertEqual("SUCCEEDED", execution_controller._dispatch("/runtime/release", journal, {"operations": [operation]}, [False]))
            self.assertEqual({"privateKey": "synthetic-private-key"}, captured["credentials"])
            self.assertNotIn("IdentityFile=", captured["env"]["ANSIBLE_SSH_ARGS"])
            self.assertIn("StrictHostKeyChecking=yes", captured["env"]["ANSIBLE_SSH_ARGS"])
            self.assertNotIn("ANSIBLE_PRIVATE_KEY_FILE", captured["env"])
            self.assertFalse(Path(journal.directory, ".ansible-runtime-credentials.json").exists())

    def test_output_reservation_terminal_recovery_finishes_ready_publication(self):
        for terminal_before_crash in (False, True):
            with self.subTest(terminal_before_crash=terminal_before_crash), tempfile.TemporaryDirectory() as root:
                os.chmod(root,0o700)
                journal=Journal(root,"run-1")
                manifest={"projectIdentity":"project-1","planFingerprint":metadata()["planFingerprint"],
                    "runtimeRelease":{"bundleDigest":metadata()["runtimeRelease"]},
                    "operations":[{"operation":"SERVICE_APPLY","operationId":"apply:vault","serviceDeployment":"vault-ha","roleVariablesPrefix":"platform_vault_"}],
                    "artifactRequirements":[],"artifactSourceAuthorities":[],
                    "runtimeSecretOutputs":[{"protocol":"SecretOutputDelivery/v1alpha1","serviceDeployment":"vault-ha","entries":["admin-token","unseal-shares"]}]}
                current=metadata();current["manifestDigest"]=digest(manifest)
                journal.initialize(current)
                Path(journal.directory,"manifest.json").write_text(json.dumps(manifest))
                execution_controller._materialize_runtime_projection(journal,current,manifest)
                storage=execution_controller.execution_secret_output
                package,generation=storage.load_package_identity(journal.directory,"project-1","vault-ha",journal.run_id)
                directory=Path(root,"secret-outputs",package)
                for name,data in (("admin-token",b"synthetic-token"),("unseal-shares",b'{"keys":["synthetic-share"]}'),("init-response.json",b'{}')):
                    (directory/name).write_bytes(data);(directory/name).chmod(0o600)
                self.assertFalse((directory/"metadata.json").exists())
                journal.transition("RUNNING","running")
                if terminal_before_crash: journal.terminal("FAILED","TEST_FAILURE","synthetic failure")
                recover(root,lambda _unit,_metadata:False)
                validator,schema_path=execution_controller._output_schema_validator(None)
                self.assertEqual("READY",json.loads((directory/"metadata.json").read_text())["state"])
                self.assertTrue(storage.fetch(root,package,"project-1",generation,validator,schema_path))
                storage.acknowledge(root,"project-1",package,generation,"e"*32,
                    {"admin-token":"sha256:"+"c"*64,"unseal-shares":"sha256:"+"d"*64})
                recover(root,lambda _unit,_metadata:False)
                self.assertEqual("DELIVERED",json.loads((directory/"metadata.json").read_text())["state"])
                self.assertTrue(Path(journal.directory).exists())
                for name in ("admin-token","unseal-shares","init-response.json"):
                    self.assertFalse((directory/name).exists())

    def test_reservation_without_directory_preserves_journal_until_empty_recovery(self):
        with tempfile.TemporaryDirectory() as root:
            os.chmod(root,0o700)
            journal=Journal(root,"run-1")
            manifest={"projectIdentity":"project-1","planFingerprint":metadata()["planFingerprint"],
                "runtimeRelease":{"bundleDigest":metadata()["runtimeRelease"]},"operations":[],
                "runtimeSecretOutputs":[{"protocol":"SecretOutputDelivery/v1alpha1","serviceDeployment":"vault-ha","entries":["admin-token","unseal-shares"]}]}
            current=metadata();current["manifestDigest"]=digest(manifest)
            journal.initialize(current)
            Path(journal.directory,"manifest.json").write_text(json.dumps(manifest))
            storage=execution_controller.execution_secret_output
            package,generation=storage.prepare_package_identity(root,journal.directory,"project-1","vault-ha",journal.run_id,current["runtimeRelease"])
            journal.terminal("FAILED","TEST_FAILURE","synthetic failure")
            self.assertFalse(Path(root,"secret-outputs",package).exists())
            self.assertTrue(execution_lifecycle._secret_output_retention_pending(root,journal))
            recover(root,lambda _unit,_metadata:False)
            self.assertFalse(execution_lifecycle._secret_output_retention_pending(root,journal))
            self.assertTrue(Path(root,"secret-outputs",package,"no-output.json").exists())

    def test_output_custody_is_shared_by_apply_verify_and_capture(self):
        with tempfile.TemporaryDirectory() as root:
            os.chmod(root, 0o700)
            journal = Journal(root, "run-1")
            manifest = {"operations": [{"operation": operation, "operationId": operation.lower()+":vault", "serviceDeployment": "vault-ha", "roleVariablesPrefix": "platform_vault_"} for operation in ("SERVICE_APPLY", "SERVICE_VERIFY")],
                        "artifactRequirements": [], "artifactSourceAuthorities": [],
                        "runtimeSecretOutputs": [{"protocol": "SecretOutputDelivery/v1alpha1", "serviceDeployment": "vault-ha", "entries": ["admin-token", "unseal-shares"]}]}
            current = metadata()
            current["manifestDigest"] = digest(manifest)
            journal.initialize(current)
            execution_controller._materialize_runtime_projection(journal, current, manifest)
            directories = []
            for operation in manifest["operations"]:
                name = ".runtime-projection-"+hashlib.sha256(operation["operationId"].encode()).hexdigest()+".json"
                projection = json.loads(Path(journal.directory, name).read_text())
                directories.append(projection["platform_vault_bootstrap_output_dir"])
            self.assertEqual(directories[0], directories[1])
            output = Path(directories[0])
            self.assertEqual(Path(root,"secret-outputs"), output.parent)
            for name, content in (("admin-token", b"synthetic-token"), ("unseal-shares", b'{"keys":["synthetic-share"]}'), ("init-response.json", b'{}')):
                (output/name).write_bytes(content)
                (output/name).chmod(0o600)
            # Capture failure cannot delete the last recoverable material.
            with mock.patch.object(execution_controller.execution_secret_output, "publish", side_effect=OSError("injected capture failure")):
                with self.assertRaises(OSError):
                    execution_controller._capture_secret_outputs(journal, manifest, None)
            self.assertTrue((output/"admin-token").exists())
            execution_controller._capture_secret_outputs(journal, manifest, None)
            result = {"state":"SUCCEEDED"}
            execution_controller._complete_secret_outputs(journal,manifest,result)
            ack = execution_controller.execution_secret_output.acknowledge(root,"project-1",output.name,1,"e"*32,
                {"admin-token":"sha256:"+"c"*64,"unseal-shares":"sha256:"+"d"*64})
            self.assertEqual("DELIVERED",ack["state"])
            self.assertTrue(Path(journal.directory).exists())
            self.assertFalse(Path(journal.directory,"project","secrets").exists())
            for name in ("admin-token","unseal-shares","init-response.json"):
                self.assertFalse((output/name).exists())

    def test_service_projection_binding_is_verified_before_controller_start(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            plans = [{"id": "scope--node1", "requestId": "scope", "tlsProfileId": "tls", "authorityId": "ca", "hostId": "node1", "targetDirectory": "/etc/platform/project/scope", "formats": ["PEM", "PKCS12_KEYSTORE", "PKCS12_TRUSTSTORE"], "keyAlias": "platform-scope", "trustAlias": "platform-ca-ca", "storePasswordSecretRef": "runtime:pki-store-password", "materializationFingerprint": digest("scope")}]
            manifest = {"operations": [{"operation": "PKI_APPLY", "operationId": "pki:apply"}, {"operation": "SERVICE_APPLY", "operationId": "apply:kafka", "serviceType": "kafka", "serviceDeployment": "kafka", "roleVariablesPrefix": "platform_kafka_", "requiresArtifactSources": True}, {"operation": "SERVICE_VERIFY", "operationId": "verify:kafka", "serviceType": "kafka", "serviceDeployment": "kafka", "roleVariablesPrefix": "platform_kafka_", "requiresArtifactSources": True}], "artifactRequirements": [{"id": "kafka:kafka-binary", "serviceDeployment": "kafka", "requirementId": "kafka-binary"}], "artifactSourceAuthorities": [{"requirement": {"id": "kafka:kafka-binary", "serviceDeployment": "kafka", "requirementId": "kafka-binary"}}], "pkiMaterializationPlans": plans}
            current = metadata(); current["manifestDigest"] = digest(manifest)
            journal.initialize(current)
            execution_controller._materialize_runtime_projection(journal, current, manifest)
            execution_controller._validate_runtime_projection(journal, current, manifest)
            projection = json.loads(Path(journal.directory, "runtime-projection.json").read_text(encoding="utf-8"))
            self.assertEqual(projection["platform_project_root"], os.path.join(journal.directory, "project"))
            self.assertEqual(projection["platform_project_manifest_path"], os.path.join(journal.directory, "project", "project.yml"))
            self.assertEqual(projection["platform_generated_state_path"], os.path.join(root, "projects", "project-1", "generated", "platform-state.yml"))
            self.assertIn("kafka-binary", projection["platform_artifact_source_authorities_by_deployment"]["kafka"])
            self.assertEqual(plans, projection["platform_pki_materialization_plans"])
            projection["platform_execution_run_id"] = "other-run"
            Path(journal.directory, "runtime-projection.json").write_text(json.dumps(projection), encoding="utf-8")
            with self.assertRaisesRegex(LifecycleError, "RUNTIME_PROJECTION_MISMATCH"):
                execution_controller._validate_runtime_projection(journal, current, manifest)

    def test_runtime_projection_rejects_malformed_or_tampered_pki_materialization_plans(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            valid = {"id": "scope--node1", "requestId": "scope", "tlsProfileId": "tls", "authorityId": "ca", "hostId": "node1", "targetDirectory": "/etc/platform/project/scope", "formats": ["PEM", "PKCS12_KEYSTORE", "PKCS12_TRUSTSTORE"], "keyAlias": "platform-scope", "trustAlias": "platform-ca-ca", "storePasswordSecretRef": None, "materializationFingerprint": digest("scope")}
            manifest = {"operations": [{"operation": "SERVICE_APPLY", "operationId": "apply:haproxy", "serviceType": "haproxy", "serviceDeployment": "haproxy", "roleVariablesPrefix": "platform_haproxy_"}], "artifactRequirements": [], "artifactSourceAuthorities": [], "pkiMaterializationPlans": [valid]}
            current = metadata(); current["manifestDigest"] = digest(manifest)
            journal.initialize(current)
            execution_controller._materialize_runtime_projection(journal, current, manifest)
            projection_path = Path(journal.directory, "runtime-projection.json")
            projection = json.loads(projection_path.read_text(encoding="utf-8"))
            projection["platform_pki_materialization_plans"] = []
            projection_path.write_text(json.dumps(projection), encoding="utf-8")
            with self.assertRaisesRegex(LifecycleError, "RUNTIME_PROJECTION_MISMATCH"):
                execution_controller._validate_runtime_projection(journal, current, manifest)
            invalid = dict(valid); invalid["targetDirectory"] = "relative"
            invalid_manifest = dict(manifest); invalid_manifest["pkiMaterializationPlans"] = [invalid]
            with self.assertRaisesRegex(LifecycleError, "EXECUTION_MANIFEST_INVALID"):
                execution_controller._materialize_runtime_projection(journal, current, invalid_manifest)

    def test_runtime_projection_resolves_v3_service_values_by_requirement_ref_and_projects_runtime_ref(self):
        """The lease payload and service configuration intentionally use distinct keys."""
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            manifest = {
                "operations": [{"operation": "SERVICE_APPLY", "operationId": "apply:postgres", "serviceType": "postgresql", "serviceDeployment": "postgres", "roleVariablesPrefix": "platform_postgresql_"}],
                "artifactRequirements": [], "artifactSourceAuthorities": [], "pkiMaterializationPlans": [],
                "runtimeSecretRequirements": [{"requirementRef": "postgresql-admin-password", "purpose": "SERVICE_PASSWORD", "hosts": ["node1"], "runtimeReference": "runtime:postgresql-admin-password", "serviceDeployment": "postgres"}],
            }
            current = metadata(); current["manifestDigest"] = digest(manifest)
            journal.initialize(current)
            values = {"postgresql-admin-password": "test-only-value"}
            with mock.patch.object(execution_controller.execution_secret_lease, "target_username_for_run", return_value="qa"), mock.patch.object(execution_controller.execution_secret_lease, "runtime_secret_values_for_run", return_value=values):
                execution_controller._materialize_runtime_projection(journal, current, manifest)
            projection_name = ".runtime-projection-" + hashlib.sha256(b"apply:postgres").hexdigest() + ".json"
            projection = json.loads(Path(journal.directory, projection_name).read_text(encoding="utf-8"))
            path = projection["platform_postgresql_secret_files"]["runtime:postgresql-admin-password"]
            self.assertEqual("test-only-value", Path(path).read_text(encoding="utf-8"))
            self.assertNotIn("postgresql-admin-password", projection["platform_postgresql_secret_files"])

    def test_generated_state_path_is_stable_per_project_not_run(self):
        with tempfile.TemporaryDirectory() as root:
            first = execution_controller._generated_state_path(root, metadata("run-1")["projectIdentity"])
            second = execution_controller._generated_state_path(root, metadata("run-2")["projectIdentity"])
            other = execution_controller._generated_state_path(root, metadata("run-3", "project-2")["projectIdentity"])
            self.assertEqual(first, second)
            self.assertNotEqual(first, other)
            self.assertNotIn("run-1", first)
            self.assertNotIn("run-2", second)

    def test_generated_state_path_rejects_symlink_or_untrusted_file(self):
        with tempfile.TemporaryDirectory() as root:
            path = execution_controller._generated_state_path(root, "project-1")
            self.assertTrue(path.endswith("projects/project-1/generated/platform-state.yml"))
            Path(path).write_text("state", encoding="utf-8")
            os.chmod(path, 0o644)
            with self.assertRaisesRegex(LifecycleError, "GENERATED_STATE_UNSAFE"):
                execution_controller._generated_state_path(root, "project-1")
            os.unlink(path)
            target = os.path.join(root, "foreign-state.yml")
            Path(target).write_text("foreign", encoding="utf-8")
            os.symlink(target, path)
            with self.assertRaisesRegex(LifecycleError, "GENERATED_STATE_UNSAFE"):
                execution_controller._generated_state_path(root, "project-1")

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

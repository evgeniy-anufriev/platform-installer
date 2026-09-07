#!/usr/bin/env python3
"""Fixed JSON protocol for the activated Execution Node runtime.

stdin and stdout are the protocol.  The only subprocesses are the fixed
systemd controller and fixed systemctl ownership checks below.
"""
from __future__ import print_function

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
import yaml

from execution_lifecycle import ACTIVE, Journal, LifecycleError, digest, recover, validate_ownership


OPERATIONS = ("GetCapabilities", "ValidateProject", "BuildProjectSnapshot", "BuildDeploymentPlan", "StartExecution", "GetExecution", "GetEvents", "CancelExecution")
SNAPSHOT_REQUEST_VERSION = "platform.installer/project-snapshot-request/v1alpha1"
SNAPSHOT_OWNER_FILE = ".snapshot-owner.json"
MAX_CANDIDATE_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_CANDIDATE_FILES = 4096
MAX_CANDIDATE_FILE_BYTES = 4 * 1024 * 1024
MAX_CANDIDATE_TOTAL_BYTES = 64 * 1024 * 1024
MAX_CANDIDATE_PATH_BYTES = 512
APPROVED_CANDIDATE_ANSIBLE_CONFIG = (
    b"# Managed by Platform Installer.\n"
    b"# This is standard Ansible configuration; formatting may be normalized.\n"
    b"[defaults]\n"
    b"inventory = ./inventory/hosts.yml\n"
    b"retry_files_enabled = False\n"
    b"host_key_checking = True\n"
    b"interpreter_python = auto_silent\n"
    b"hash_behaviour = merge\n"
)


class CoreOperationError(LifecycleError):
    def __init__(self, code, diagnostic=None):
        super().__init__(code)
        self.code = code
        self.diagnostic = diagnostic if isinstance(diagnostic, dict) else None


def reply(payload):
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")))


def unit_name(run_id):
    return "platform-installer-run-%s.service" % run_id


def active(unit, metadata):
    if not isinstance(metadata, dict) or metadata.get("unit") != unit:
        return False
    return subprocess.call(["systemctl", "is-active", "--quiet", unit], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def owned(journal):
    """Verify the complete non-PID ownership tuple before querying/stopping."""
    return validate_ownership(journal)


def request():
    value = json.load(sys.stdin)
    if not isinstance(value, dict) or value.get("apiVersion") != "platform.installer/execution-runtime/v1alpha1":
        raise LifecycleError("EXECUTION_PROTOCOL_INVALID")
    if value.get("operation") not in OPERATIONS:
        raise LifecycleError("EXECUTION_OPERATION_UNSUPPORTED")
    return value


def _validated_snapshot_request(value):
    snapshot_request = value.get("snapshotRequest")
    if snapshot_request is None:
        return None
    required = {"apiVersion", "kind", "requestId", "projectIdentity", "candidateProjectRevision", "projectArchiveDigest", "artifactLockDigest", "catalogLockDigest", "installerOwnedLogicalPaths", "projectContract", "snapshotContract", "editContract"}
    if not isinstance(snapshot_request, dict) or set(snapshot_request) != required or snapshot_request.get("apiVersion") != SNAPSHOT_REQUEST_VERSION or snapshot_request.get("kind") != "BuildProjectSnapshotRequest" or snapshot_request.get("projectContract") != "v2alpha1" or snapshot_request.get("snapshotContract") != "v1alpha1" or snapshot_request.get("editContract") != "v1alpha2":
        raise LifecycleError("PROJECT_SNAPSHOT_REQUEST_INVALID")
    request_id = snapshot_request.get("requestId")
    project_identity = snapshot_request.get("projectIdentity")
    if not isinstance(request_id, str) or re.fullmatch(r"[0-9a-f]{32}", request_id) is None:
        raise LifecycleError("PROJECT_SNAPSHOT_REQUEST_INVALID")
    if not isinstance(project_identity, str) or re.fullmatch(r"[a-z0-9][a-z0-9-]{0,127}", project_identity) is None:
        raise LifecycleError("PROJECT_SNAPSHOT_REQUEST_INVALID")
    for field in ("candidateProjectRevision", "projectArchiveDigest", "artifactLockDigest", "catalogLockDigest"):
        field_value = snapshot_request.get(field)
        if not isinstance(field_value, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", field_value) is None:
            raise LifecycleError("PROJECT_SNAPSHOT_REQUEST_INVALID")
    owned_paths = snapshot_request.get("installerOwnedLogicalPaths")
    owned_pattern = re.compile(r"^(ansible\.cfg|inventory/hosts\.yml|inventory/group_vars/all/platform-installer\.yml|inventory/host_vars/[a-z0-9][a-z0-9-]{0,62}/platform-installer\.yml)$")
    if not isinstance(owned_paths, list) or len(owned_paths) > 1026 or any(not isinstance(item, str) or owned_pattern.fullmatch(item) is None for item in owned_paths) or len(set(owned_paths)) != len(owned_paths):
        raise LifecycleError("PROJECT_SNAPSHOT_REQUEST_INVALID")
    return snapshot_request


def _candidate_logical_path(name):
    if not isinstance(name, str) or not name or "\\" in name or ":" in name or "\x00" in name:
        return False
    try:
        encoded = name.encode("utf-8")
    except UnicodeEncodeError:
        return False
    if len(encoded) > MAX_CANDIDATE_PATH_BYTES or name.startswith("/"):
        return False
    parts = name.split("/")
    if any(not part or part in (".", "..") or any(ord(character) < 32 for character in part) for part in parts):
        return False
    if name in ("project.yml", "ansible.cfg", "inventory/hosts.yml"):
        return True
    if len(parts) < 3 or parts[0] != "inventory" or parts[1] not in ("group_vars", "host_vars"):
        return False
    return os.path.splitext(parts[-1])[1].lower() in (".yml", ".yaml", ".json")


def _candidate_members(archive):
    members = archive.getmembers()
    if len(members) > MAX_CANDIDATE_FILES:
        raise LifecycleError("PROJECT_CANDIDATE_LIMIT_EXCEEDED")
    total = 0
    names = set()
    folded = set()
    for member in members:
        if not member.isreg() or member.linkname or member.sparse is not None or not _candidate_logical_path(member.name):
            raise LifecycleError("PROJECT_CANDIDATE_ARCHIVE_UNSAFE")
        if member.size < 0 or member.size > MAX_CANDIDATE_FILE_BYTES:
            raise LifecycleError("PROJECT_CANDIDATE_LIMIT_EXCEEDED")
        total += member.size
        if total > MAX_CANDIDATE_TOTAL_BYTES:
            raise LifecycleError("PROJECT_CANDIDATE_LIMIT_EXCEEDED")
        folded_name = member.name.casefold()
        if member.name in names or folded_name in folded:
            raise LifecycleError("PROJECT_CANDIDATE_CASE_COLLISION")
        names.add(member.name)
        folded.add(folded_name)
    if not {"project.yml", "ansible.cfg", "inventory/hosts.yml"}.issubset(names):
        raise LifecycleError("PROJECT_CANDIDATE_ARCHIVE_INCOMPLETE")
    return members


def _safe_candidate_parent(root, logical):
    current = root
    for part in logical.split("/")[:-1]:
        current = os.path.join(current, part)
        try:
            os.mkdir(current, 0o700)
        except FileExistsError:
            if os.path.islink(current) or not os.path.isdir(current):
                raise LifecycleError("PROJECT_CANDIDATE_EXTRACTION_UNSAFE")
    return current


def _write_all(descriptor, value):
    offset = 0
    while offset < len(value):
        written = os.write(descriptor, value[offset:])
        if written <= 0:
            raise OSError("short write")
        offset += written


def _candidate_archive_path(run_id):
    return os.path.join("/var/tmp/platform-installer/execution-plan", run_id, "project.tar")


def _write_snapshot_owner(journal, value):
    path = os.path.join(journal.directory, SNAPSHOT_OWNER_FILE)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        _write_all(descriptor, json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii"))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _snapshot_stage_identity(value, journal):
    try:
        directory_info = os.lstat(journal.directory)
        if not os.path.isdir(journal.directory) or os.path.islink(journal.directory):
            return None
    except OSError:
        return None
    path = os.path.join(journal.directory, SNAPSHOT_OWNER_FILE)
    try:
        info = os.lstat(path)
        if not os.path.isfile(path) or os.path.islink(path) or info.st_size > 1024:
            return None
        with open(path, "r", encoding="ascii") as stream:
            marker = json.load(stream)
    except (OSError, ValueError, UnicodeError):
        return None
    request = value.get("snapshotRequest")
    if request is None:
        expected = {"kind": "readonly", "runId": value.get("runId")}
    elif isinstance(request, dict):
        expected = {"kind": "candidate", "runId": value.get("runId"), "requestId": request.get("requestId"), "archiveDigest": request.get("projectArchiveDigest")}
    else:
        return None
    if marker != expected:
        return None
    try:
        verified = os.lstat(journal.directory)
    except OSError:
        return None
    identity = (directory_info.st_dev, directory_info.st_ino)
    return identity if identity == (verified.st_dev, verified.st_ino) else None


def _cleanup_snapshot_staging(value, journal, expected_identity):
    if expected_identity is None or _snapshot_stage_identity(value, journal) != expected_identity:
        return False
    # Repeat the marker and directory identity proof immediately before the
    # recursive delete. A mismatch is preserved for operator diagnostics.
    if _snapshot_stage_identity(value, journal) != expected_identity:
        return False
    shutil.rmtree(journal.directory)
    return True


def _copy_verified_candidate_archive(source_path, destination_path, expected_digest, expected_info):
    source_flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        source_flags |= os.O_NOFOLLOW
    source = os.open(source_path, source_flags)
    destination = None
    try:
        opened_info = os.fstat(source)
        expected_identity = (expected_info.st_dev, expected_info.st_ino, expected_info.st_size)
        if (opened_info.st_dev, opened_info.st_ino, opened_info.st_size) != expected_identity:
            raise LifecycleError("PROJECT_CANDIDATE_ARCHIVE_REPLACED")
        destination = os.open(destination_path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
        archive_digest = hashlib.sha256()
        copied = 0
        while True:
            block = os.read(source, min(1024 * 1024, MAX_CANDIDATE_ARCHIVE_BYTES + 1 - copied))
            if not block:
                break
            copied += len(block)
            if copied > MAX_CANDIDATE_ARCHIVE_BYTES:
                raise LifecycleError("PROJECT_CANDIDATE_ARCHIVE_UNSAFE")
            archive_digest.update(block)
            _write_all(destination, block)
        final_info = os.fstat(source)
        if copied != opened_info.st_size or (final_info.st_dev, final_info.st_ino, final_info.st_size) != expected_identity:
            raise LifecycleError("PROJECT_CANDIDATE_ARCHIVE_REPLACED")
        if "sha256:" + archive_digest.hexdigest() != expected_digest:
            raise LifecycleError("PROJECT_SNAPSHOT_ARCHIVE_DIGEST_MISMATCH")
        os.fsync(destination)
    finally:
        os.close(source)
        if destination is not None:
            os.close(destination)


def stage_candidate_archive(archive_path, run_id, request_id, expected_digest, state_root):
    journal = Journal(state_root, run_id)
    expected_archive = _candidate_archive_path(run_id)
    if os.path.abspath(archive_path) != expected_archive or not re.fullmatch(r"[0-9a-f]{32}", request_id or "") or not re.fullmatch(r"sha256:[0-9a-f]{64}", expected_digest or ""):
        raise LifecycleError("PROJECT_CANDIDATE_STAGING_INVALID")
    archive_info = os.lstat(archive_path)
    if not os.path.isfile(archive_path) or os.path.islink(archive_path) or archive_info.st_size > MAX_CANDIDATE_ARCHIVE_BYTES:
        raise LifecycleError("PROJECT_CANDIDATE_ARCHIVE_UNSAFE")
    if os.path.lexists(journal.directory):
        raise LifecycleError("PROJECT_CANDIDATE_STAGING_EXISTS")

    cleanup_value = {"runId": run_id, "snapshotRequest": {"requestId": request_id, "projectArchiveDigest": expected_digest}}
    stage_identity = None
    try:
        os.makedirs(journal.directory, mode=0o700)
        _write_snapshot_owner(journal, {"kind": "candidate", "runId": run_id, "requestId": request_id, "archiveDigest": expected_digest})
        stage_identity = _snapshot_stage_identity(cleanup_value, journal)
        if stage_identity is None:
            raise LifecycleError("PROJECT_CANDIDATE_STAGING_NOT_OWNED")
        verified_archive = os.path.join(journal.directory, ".candidate-archive.tar")
        _copy_verified_candidate_archive(archive_path, verified_archive, expected_digest, archive_info)
        temporary = os.path.join(journal.directory, ".project-staging")
        os.mkdir(temporary, 0o700)
        with tarfile.open(verified_archive, mode="r:") as archive:
            members = _candidate_members(archive)
            config_member = next(member for member in members if member.name == "ansible.cfg")
            config_stream = archive.extractfile(config_member)
            if config_stream is None or config_stream.read(MAX_CANDIDATE_FILE_BYTES + 1) != APPROVED_CANDIDATE_ANSIBLE_CONFIG:
                raise LifecycleError("PROJECT_CANDIDATE_ANSIBLE_CONFIG_UNSAFE")
            for member in members:
                source = archive.extractfile(member)
                if source is None:
                    raise LifecycleError("PROJECT_CANDIDATE_ARCHIVE_UNSAFE")
                parent = _safe_candidate_parent(temporary, member.name)
                target = os.path.join(parent, member.name.rsplit("/", 1)[-1])
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
                if hasattr(os, "O_NOFOLLOW"):
                    flags |= os.O_NOFOLLOW
                descriptor = os.open(target, flags, 0o600)
                try:
                    remaining = member.size
                    while remaining:
                        block = source.read(min(1024 * 1024, remaining))
                        if not block:
                            raise LifecycleError("PROJECT_CANDIDATE_ARCHIVE_TRUNCATED")
                        _write_all(descriptor, block)
                        remaining -= len(block)
                    if source.read(1):
                        raise LifecycleError("PROJECT_CANDIDATE_ARCHIVE_UNSAFE")
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        os.remove(verified_archive)
        os.replace(temporary, os.path.join(journal.directory, "project"))
        digest_path = os.path.join(journal.directory, "project-archive.digest")
        descriptor = os.open(digest_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            _write_all(descriptor, (expected_digest + "\n").encode("ascii"))
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except Exception:
        if stage_identity is not None:
            _cleanup_snapshot_staging(cleanup_value, journal, stage_identity)
        raise


def _fixed_ansible_environment(**values):
    environment = {}
    for key in ("PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "TEMP", "TMP"):
        if key in os.environ:
            environment[key] = os.environ[key]
    environment.update(values)
    environment["ANSIBLE_NOCOLOR"] = "1"
    return environment


def _candidate_ansible_environment(project, release, output_path):
    candidate_config = os.path.join(project, "ansible.cfg")
    if os.path.islink(candidate_config) or not os.path.isfile(candidate_config) or Path(candidate_config).read_bytes() != APPROVED_CANDIDATE_ANSIBLE_CONFIG:
        raise LifecycleError("PROJECT_CANDIDATE_ANSIBLE_CONFIG_UNSAFE")
    return _fixed_ansible_environment(
        ANSIBLE_CONFIG=candidate_config,
        ANSIBLE_COLLECTIONS_PATH=os.path.join(release, "ansible-core", "collections"),
        ANSIBLE_CALLBACKS_ENABLED="platform.core.project_snapshot_json",
        PLATFORM_PROJECT_SNAPSHOT_OUTPUT=output_path,
    )


def start(value, state_root, runtime_release, controller, active_bundle_digest=""):
    run_id = value.get("runId")
    journal = Journal(state_root, run_id)
    manifest_path = os.path.join(journal.directory, "manifest.json")
    if not os.path.isfile(manifest_path) or os.path.islink(manifest_path):
        raise LifecycleError("EXECUTION_MANIFEST_MISSING")
    with open(manifest_path, "r", encoding="utf-8") as stream:
        manifest = json.load(stream)
    expected = ("projectIdentity", "planFingerprint", "runtimeRelease")
    if any(manifest.get(key) != value.get(key) for key in expected):
        raise LifecycleError("EXECUTION_IDENTITY_MISMATCH")
    if manifest.get("runtimeRelease", {}).get("bundleDigest") != value.get("runtimeRelease", {}).get("bundleDigest"):
        raise LifecycleError("EXECUTION_RUNTIME_RELEASE_MISMATCH")
    if active_bundle_digest and value.get("runtimeRelease", {}).get("bundleDigest") != active_bundle_digest:
        raise LifecycleError("EXECUTION_RUNTIME_RELEASE_MISMATCH")
    if not isinstance(manifest.get("operations"), list):
        raise LifecycleError("EXECUTION_MANIFEST_INVALID")
    metadata = {"runId": run_id, "projectIdentity": value["projectIdentity"], "planFingerprint": value["planFingerprint"], "manifestDigest": digest(manifest), "runtimeRelease": value["runtimeRelease"]["bundleDigest"], "unit": unit_name(run_id)}
    os.makedirs(state_root, mode=0o700, exist_ok=True)
    active_lock = os.open(os.path.join(state_root, ".active-runs.lock"), os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(active_lock, fcntl.LOCK_EX)
    lock = journal.lock()
    try:
        if os.path.exists(journal.metadata_path):
            journal.initialize(metadata)
            owned(journal)
            return {"run": journal.status(), "idempotent": True}
        runs = os.path.join(state_root, "runs")
        for candidate in os.listdir(runs):
            if candidate == run_id: continue
            other = Journal(state_root, candidate)
            try:
                status, other_meta = other.status(), other.metadata()
                if status.get("state") in ACTIVE and other_meta.get("projectIdentity") == metadata["projectIdentity"]:
                    raise LifecycleError("ACTIVE_RUN_EXISTS:%s" % candidate)
            except FileNotFoundError:
                continue
        journal.initialize(metadata)
        journal.transition("STARTING", "Detached controller accepted")
        # The bundle intentionally stores content with deterministic bytes, not
        # host executable bits.  Interpreter and controller are both fixed by
        # this node-side protocol, never supplied by a client.
        subprocess.check_call(["systemd-run", "--unit=" + metadata["unit"], "--collect", "--property=KillMode=control-group", "--property=NoNewPrivileges=yes", sys.executable, controller, "--state-root", state_root, "--run-id", run_id, "--runtime-release", runtime_release, "--bundle-digest", metadata["runtimeRelease"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"run": journal.status(), "idempotent": False, "runtimeRelease": runtime_release}
    finally:
        os.close(lock)
        os.close(active_lock)


def core_operation(value, state_root, runtime_release, operation):
    """Run one fixed Core playbook against already trusted run staging."""
    journal = Journal(state_root, value["runId"])
    project = os.path.join(journal.directory, "project")
    if not os.path.isdir(project) or os.path.islink(project):
        raise LifecycleError("EXECUTION_PROJECT_STAGING_MISSING")
    release = os.path.realpath(runtime_release)
    if not os.path.isdir(release) or os.path.islink(runtime_release):
        raise LifecycleError("EXECUTION_RUNTIME_RELEASE_INVALID")
    if operation == "ValidateProject":
        playbook, inventory = "validate.yml", os.path.join(project, "inventory", "hosts.yml")
        extra = {"platform_project_manifest_path": os.path.join(project, "project.yml"), "platform_validation_artifact": os.path.join(journal.directory, "validation.json")}
    elif operation == "BuildProjectSnapshot":
        playbook, inventory = "project-snapshot.yml", os.path.join(project, "inventory", "hosts.yml")
        snapshot_request = _validated_snapshot_request(value)
        if snapshot_request is None:
            owned_paths = []
        else:
            owned_paths = snapshot_request.get("installerOwnedLogicalPaths")
            archive_digest_path = os.path.join(journal.directory, "project-archive.digest")
            if not os.path.isfile(archive_digest_path) or os.path.islink(archive_digest_path):
                raise LifecycleError("PROJECT_SNAPSHOT_ARCHIVE_DIGEST_MISSING")
            with open(archive_digest_path, "r", encoding="ascii") as stream:
                if stream.read().strip() != snapshot_request.get("projectArchiveDigest"):
                    raise LifecycleError("PROJECT_SNAPSHOT_ARCHIVE_DIGEST_MISMATCH")
            manifest_path = os.path.join(project, "project.yml")
            try:
                with open(manifest_path, "r", encoding="utf-8") as stream:
                    manifest = yaml.safe_load(stream)
            except (OSError, UnicodeError, yaml.YAMLError):
                raise LifecycleError("PROJECT_SNAPSHOT_PROJECT_INVALID")
            metadata = manifest.get("metadata") if isinstance(manifest, dict) else None
            artifact_lock = manifest.get("artifactLock") if isinstance(manifest, dict) else None
            catalog_lock = manifest.get("catalogLock") if isinstance(manifest, dict) else None
            if not isinstance(metadata, dict) or not isinstance(artifact_lock, dict) or not isinstance(catalog_lock, dict) or metadata.get("id") != snapshot_request.get("projectIdentity") or artifact_lock.get("digest") != snapshot_request.get("artifactLockDigest") or catalog_lock.get("digest") != snapshot_request.get("catalogLockDigest"):
                raise LifecycleError("PROJECT_SNAPSHOT_IDENTITY_MISMATCH")
            try:
                with open(os.path.join(release, "manifest.yaml"), "r", encoding="utf-8") as stream:
                    release_manifest = yaml.safe_load(stream)
            except (OSError, UnicodeError, yaml.YAMLError):
                raise LifecycleError("EXECUTION_RUNTIME_RELEASE_INVALID")
            if not isinstance(release_manifest, dict) or release_manifest.get("catalogDigest") != snapshot_request.get("catalogLockDigest"):
                raise LifecycleError("PROJECT_SNAPSHOT_RUNTIME_MISMATCH")
        extra = {"platform_project_root": project, "platform_project_manifest_path": os.path.join(project, "project.yml"), "platform_service_catalog_path": os.path.join(release, "catalog", "service-catalog.yml"), "platform_installer_owned_paths": owned_paths}
    else:
        # Core remains target-free (the playbook runs on localhost), but it must
        # load the staged project inventory so snapshot receives its canonical
        # desired state, groups and host variables.
        playbook, inventory = "deployment-plan-machine.yml", os.path.join(project, "inventory", "hosts.yml")
        extra = {"platform_project_root": project, "platform_project_manifest_path": os.path.join(project, "project.yml"), "platform_service_catalog_path": os.path.join(release, "catalog", "service-catalog.yml"), "platform_execution_runtime_release": value["runtimeRelease"]}
    diagnostic_path = os.path.join(journal.directory, "core-diagnostic.json")
    descriptor, vars_path = tempfile.mkstemp(prefix=".execution-vars-", dir=journal.directory)
    try:
        os.write(descriptor, json.dumps(extra, ensure_ascii=True, sort_keys=True).encode("utf-8")); os.close(descriptor)
        os.chmod(vars_path, 0o600)
        if operation == "BuildProjectSnapshot":
            candidate = value.get("snapshotRequest") is not None
            if candidate:
                environment = _candidate_ansible_environment(project, release, os.path.join(journal.directory, "project-snapshot.json"))
            else:
                environment = dict(os.environ, ANSIBLE_CONFIG=os.path.join(release, "ansible-core", "ansible.cfg"), ANSIBLE_COLLECTIONS_PATH=os.path.join(release, "ansible-core", "collections"), ANSIBLE_CALLBACKS_ENABLED="platform.core.project_snapshot_json", PLATFORM_PROJECT_SNAPSHOT_OUTPUT=os.path.join(journal.directory, "project-snapshot.json"))
        else:
            environment = dict(os.environ, ANSIBLE_CONFIG=os.path.join(release, "ansible-core", "ansible.cfg"), ANSIBLE_COLLECTIONS_PATH=os.path.join(release, "ansible-core", "collections"), ANSIBLE_CALLBACKS_ENABLED="platform.core.deployment_plan_json", PLATFORM_DEPLOYMENT_PLAN_OUTPUT=os.path.join(journal.directory, "deployment-plan.json"), PLATFORM_EXECUTION_MANIFEST_OUTPUT=os.path.join(journal.directory, "manifest.json"), PLATFORM_CORE_DIAGNOSTIC_OUTPUT=diagnostic_path)
        command = ["ansible-playbook"]
        if operation != "BuildProjectSnapshot" or value.get("snapshotRequest") is None:
            command.extend(["-i", inventory])
        command.extend([os.path.join(release, "ansible-core", "playbooks", playbook), "-e", "@" + vars_path])
        completed = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=environment,
            cwd=project if operation == "BuildProjectSnapshot" and value.get("snapshotRequest") is not None else None,
        )
        if completed.returncode:
            if operation == "BuildProjectSnapshot":
                snapshot_path = os.path.join(journal.directory, "project-snapshot.json")
                if os.path.isfile(snapshot_path) and not os.path.islink(snapshot_path):
                    with open(snapshot_path, "r", encoding="utf-8") as stream:
                        snapshot_error = json.load(stream)
                    if isinstance(snapshot_error, dict) and isinstance(snapshot_error.get("adapterError"), dict):
                        raise CoreOperationError(snapshot_error["adapterError"].get("code") or "PROJECT_SNAPSHOT_FAILED", {"findings": [snapshot_error["adapterError"]]})
            diagnostic = None
            if os.path.isfile(diagnostic_path) and not os.path.islink(diagnostic_path):
                with open(diagnostic_path, "r", encoding="utf-8") as stream:
                    diagnostic = json.load(stream)
            code = diagnostic.get("errorCode") if isinstance(diagnostic, dict) else None
            raise CoreOperationError(code or "CORE_OPERATION_FAILED", diagnostic)
    finally:
        if os.path.exists(vars_path): os.unlink(vars_path)
    if operation == "BuildProjectSnapshot":
        snapshot_path = os.path.join(journal.directory, "project-snapshot.json")
        if not os.path.isfile(snapshot_path) or os.path.islink(snapshot_path):
            raise LifecycleError("PROJECT_SNAPSHOT_RESPONSE_MISSING")
        with open(snapshot_path, "r", encoding="utf-8") as stream:
            snapshot = json.load(stream)
        if isinstance(snapshot, dict) and isinstance(snapshot.get("adapterError"), dict):
            raise CoreOperationError(snapshot["adapterError"].get("code") or "PROJECT_SNAPSHOT_FAILED", {"findings": [snapshot["adapterError"]]})
        if not isinstance(snapshot, dict) or not snapshot.get("projectRevision"):
            raise LifecycleError("PROJECT_SNAPSHOT_RESPONSE_INVALID")
        request_value = value.get("snapshotRequest")
        if request_value is not None and snapshot.get("projectRevision") != request_value.get("candidateProjectRevision"):
            raise LifecycleError("PROJECT_SNAPSHOT_REVISION_MISMATCH")
        return {"projectSnapshot": snapshot}
    if operation == "BuildDeploymentPlan":
        with open(os.path.join(journal.directory, "deployment-plan.json"), "r", encoding="utf-8") as stream:
            plan = json.load(stream)
        if plan.get("status") == "BLOCKED":
            return {"deploymentPlan": plan, "executionManifestDigest": None}
        if plan.get("status") != "EXECUTABLE" or not os.path.isfile(os.path.join(journal.directory, "manifest.json")):
            raise LifecycleError("EXECUTION_MANIFEST_MISSING")
        with open(os.path.join(journal.directory, "manifest.json"), "r", encoding="utf-8") as stream:
            return {"deploymentPlan": plan, "executionManifestDigest": digest(json.load(stream))}
    return {"validation": "PASS"}


def snapshot(value, state_root, runtime_release):
    """Return a Core snapshot and remove the request-owned staging directory."""
    journal = Journal(state_root, value["runId"])
    stage_identity = _snapshot_stage_identity(value, journal)
    if stage_identity is None:
        raise LifecycleError("PROJECT_SNAPSHOT_STAGING_NOT_OWNED")
    try:
        return core_operation(value, state_root, runtime_release, "BuildProjectSnapshot")
    finally:
        _cleanup_snapshot_staging(value, journal, stage_identity)


def get(value, state_root):
    journal = Journal(state_root, value["runId"])
    metadata = owned(journal)
    recover(state_root, active)
    result = {"run": journal.status(), "metadata": metadata}
    if os.path.exists(journal.result_path):
        with open(journal.result_path, "r", encoding="utf-8") as stream:
            result["result"] = json.load(stream)
    return result


def events(value, state_root):
    journal = Journal(state_root, value["runId"])
    owned(journal)
    after = value.get("afterSequence", 0)
    if isinstance(after, bool) or not isinstance(after, int) or after < 0:
        raise LifecycleError("EXECUTION_EVENTS_INPUT_INVALID")
    limit = value.get("limit")
    if limit is None:
        selected = journal.events(after)
        return {"run": journal.status(), "events": selected, "nextSequence": selected[-1]["sequence"] if selected else after, "hasMore": False}
    page = journal.event_page(after, limit)
    page["run"] = journal.status()
    return page


def cancel(value, state_root):
    journal = Journal(state_root, value["runId"])
    lock = journal.lock()
    try:
        metadata, status = owned(journal), journal.status()
        if status.get("state") not in ACTIVE:
            return {"run": status, "idempotent": True}
        if not active(metadata.get("unit"), metadata):
            journal.terminal("INTERRUPTED", "CONTROLLER_INTERRUPTED", "Owned controller is no longer active")
            return {"run": journal.status(), "idempotent": True}
        # Commit cancellation before asking systemd to terminate the whole
        # owned cgroup.  The controller can then never race a child SIGTERM
        # into a contradictory FAILED terminal result.
        journal.terminal("CANCELLED", "EXECUTION_CANCELLED", "Cancellation requested")
        subprocess.check_call(["systemctl", "stop", metadata["unit"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"run": journal.status(), "idempotent": False}
    finally:
        os.close(lock)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", default="/var/lib/platform-installer/execution")
    parser.add_argument("--runtime-release", required=True)
    parser.add_argument("--controller", required=True)
    parser.add_argument("--bundle-digest", default="")
    parser.add_argument("--stage-candidate-archive")
    parser.add_argument("--stage-run-id")
    parser.add_argument("--stage-request-id")
    parser.add_argument("--expected-archive-digest")
    parser.add_argument("--cleanup-snapshot-run-id")
    parser.add_argument("--cleanup-request-id")
    parser.add_argument("--cleanup-archive-digest")
    args = parser.parse_args()
    if args.stage_candidate_archive is not None:
        if not args.stage_run_id or not args.stage_request_id or not args.expected_archive_digest:
            raise LifecycleError("PROJECT_CANDIDATE_STAGING_INVALID")
        stage_candidate_archive(args.stage_candidate_archive, args.stage_run_id, args.stage_request_id, args.expected_archive_digest, args.state_root)
        return reply({"status": "STAGED"})
    if args.cleanup_snapshot_run_id is not None:
        if not args.cleanup_request_id or not args.cleanup_archive_digest:
            raise LifecycleError("PROJECT_CANDIDATE_CLEANUP_INVALID")
        cleanup_value = {"runId": args.cleanup_snapshot_run_id, "snapshotRequest": {"requestId": args.cleanup_request_id, "projectArchiveDigest": args.cleanup_archive_digest}}
        journal = Journal(args.state_root, args.cleanup_snapshot_run_id)
        identity = _snapshot_stage_identity(cleanup_value, journal)
        if identity is None or not _cleanup_snapshot_staging(cleanup_value, journal, identity):
            raise LifecycleError("PROJECT_CANDIDATE_CLEANUP_NOT_OWNED")
        return reply({"status": "CLEANED"})
    value = request()
    operation = value["operation"]
    if operation == "GetCapabilities": return reply({"supportedOperations": list(OPERATIONS), "projectSnapshotRequestVersions": [SNAPSHOT_REQUEST_VERSION]})
    if operation in ("ValidateProject", "BuildDeploymentPlan"): return reply(core_operation(value, args.state_root, args.runtime_release, operation))
    if operation == "BuildProjectSnapshot":
        candidate = _validated_snapshot_request(value)
        if candidate is not None:
            runtime_release = value.get("runtimeRelease")
            if not isinstance(runtime_release, dict):
                raise LifecycleError("PROJECT_SNAPSHOT_REQUEST_INVALID")
            if candidate.get("artifactLockDigest") != args.bundle_digest or runtime_release.get("bundleDigest") != args.bundle_digest:
                raise LifecycleError("PROJECT_SNAPSHOT_RUNTIME_MISMATCH")
        return reply(snapshot(value, args.state_root, args.runtime_release))
    if operation == "StartExecution": return reply(start(value, args.state_root, args.runtime_release, args.controller, args.bundle_digest))
    if operation == "GetExecution": return reply(get(value, args.state_root))
    if operation == "GetEvents": return reply(events(value, args.state_root))
    if operation == "CancelExecution": return reply(cancel(value, args.state_root))
    raise LifecycleError("EXECUTION_OPERATION_NOT_IMPLEMENTED")


if __name__ == "__main__":
    try: main()
    except CoreOperationError as error:
        payload = {"apiVersion": "platform.installer/execution-runtime/v1alpha1", "status": "FAILED", "error": error.code}
        if error.diagnostic:
            payload["diagnostic"] = error.diagnostic
        reply(payload)
        raise SystemExit(2)
    except (OSError, ValueError, LifecycleError, subprocess.CalledProcessError, tarfile.TarError) as error:
        reply({"apiVersion": "platform.installer/execution-runtime/v1alpha1", "status": "FAILED", "error": str(error).split("\n", 1)[0][:256]})
        raise SystemExit(2)

"""Private, narrow target-credential lease storage for the Execution Node.

This is deliberately not a secret manager.  It only persists one closed
credential payload long enough for a run that has atomically attached it.
Neither callers nor diagnostics receive payload bytes or filesystem paths.
"""
from __future__ import absolute_import, division, print_function

import fcntl
import hashlib
import json
import os
import re
import tempfile
import time
from datetime import datetime, timezone

from execution_lifecycle import LifecycleError


LEASE_PROTOCOL = "PutRuntimeSecretLease/v1alpha1"
PAYLOAD_VERSION = "TargetCredentialLeasePayload/v1alpha1"
MAX_PAYLOAD_BYTES = 1088 * 1024
STAGED_TTL_SECONDS = 30 * 60
_ID = re.compile(r"^[0-9a-f]{32}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_PROJECT = re.compile(r"^[a-z0-9][a-z0-9-]{0,127}$")


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def _parse_stamp(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise LifecycleError("LEASE_RECORD_INVALID")
    return datetime.fromisoformat(value[:-1] + "+00:00")


def _root(state_root):
    return os.path.join(os.path.realpath(state_root), "secret-leases")


def _mkdir(path):
    os.makedirs(path, mode=0o700, exist_ok=True)
    if os.path.islink(path) or not os.path.isdir(path):
        raise LifecycleError("LEASE_STORAGE_INVALID")
    os.chmod(path, 0o700)


def _write(path, value):
    parent = os.path.dirname(path)
    _mkdir(parent)
    fd, temporary = tempfile.mkstemp(prefix=".lease-", dir=parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _read(path):
    if os.path.islink(path):
        raise LifecycleError("LEASE_STORAGE_INVALID")
    with open(path, "r", encoding="utf-8") as stream:
        return json.load(stream)


def _locked(state_root):
    root = _root(state_root)
    _mkdir(root)
    fd = os.open(os.path.join(root, ".lock"), os.O_CREAT | os.O_RDWR, 0o600)
    os.fchmod(fd, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def _safe_id(value):
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _binding(value):
    required = ("requestId", "startAttemptId", "projectIdentity", "projectRevision", "planFingerprint", "executionManifestDigest", "runtimeRelease")
    if not isinstance(value, dict) or set(value) != set(required):
        raise LifecycleError("LEASE_REQUEST_INVALID")
    if not _safe_id(value["requestId"]) or not _safe_id(value["startAttemptId"]) or not isinstance(value["projectIdentity"], str) or _PROJECT.fullmatch(value["projectIdentity"]) is None:
        raise LifecycleError("LEASE_REQUEST_INVALID")
    for name in ("projectRevision", "planFingerprint", "executionManifestDigest"):
        if not isinstance(value[name], str) or _DIGEST.fullmatch(value[name]) is None:
            raise LifecycleError("LEASE_REQUEST_INVALID")
    release = value["runtimeRelease"]
    if not isinstance(release, dict) or set(release) != {"bundleDigest", "coreVersion", "catalogDigest", "planningProtocol"}:
        raise LifecycleError("LEASE_REQUEST_INVALID")
    if not _DIGEST.fullmatch(release.get("bundleDigest", "")) or not _DIGEST.fullmatch(release.get("catalogDigest", "")) or not isinstance(release.get("coreVersion"), str) or not release["coreVersion"] or len(release["coreVersion"]) > 256 or not isinstance(release.get("planningProtocol"), str) or not release["planningProtocol"] or len(release["planningProtocol"]) > 256:
        raise LifecycleError("LEASE_REQUEST_INVALID")
    return value


def _payload(value):
    if not isinstance(value, dict) or set(value) != {"apiVersion", "kind", "username", "password", "privateKey", "sudoPassword"} or value.get("apiVersion") != PAYLOAD_VERSION or value.get("kind") != "TargetCredentialLeasePayload":
        raise LifecycleError("LEASE_PAYLOAD_INVALID")
    username = value.get("username")
    password, key, sudo = value.get("password"), value.get("privateKey"), value.get("sudoPassword")
    if not isinstance(username, str) or not username or len(username.encode("utf-8")) > 255:
        raise LifecycleError("LEASE_PAYLOAD_INVALID")
    if (password is None) == (key is None) or (password is not None and (not isinstance(password, str) or not password)) or (key is not None and (not isinstance(key, str) or not key)) or (sudo is not None and (not isinstance(sudo, str) or not sudo)):
        raise LifecycleError("LEASE_PAYLOAD_INVALID")
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_PAYLOAD_BYTES:
        raise LifecycleError("LEASE_PAYLOAD_TOO_LARGE")
    return encoded


def _request_path(root, request_id): return os.path.join(root, "requests", request_id + ".json")
def _lease_dir(root, lease_id): return os.path.join(root, "leases", lease_id)


def put(state_root, request_value, payload_value):
    """Store a complete bounded payload, or return the original lease by request id."""
    request = _binding(request_value)
    payload = _payload(payload_value)
    payload_digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    lock = _locked(state_root)
    try:
        root = _root(state_root)
        request_path = _request_path(root, request["requestId"])
        if os.path.exists(request_path):
            existing = _read(request_path)
            if not isinstance(existing, dict) or existing.get("binding") != request or existing.get("payloadDigest") != payload_digest or not _safe_id(existing.get("leaseId")):
                raise LifecycleError("REQUEST_ID_CONFLICT")
            record = _read(os.path.join(_lease_dir(root, existing["leaseId"]), "record.json"))
            if record.get("state") != "STAGED":
                raise LifecycleError("LEASE_NOT_STAGED")
            return {"requestId": request["requestId"], "startAttemptId": request["startAttemptId"], "status": "ALREADY_STORED", "leaseId": existing["leaseId"], "stagedExpiresAt": record["stagedExpiresAt"]}
        lease_id = os.urandom(16).hex()
        directory = _lease_dir(root, lease_id)
        _mkdir(directory)
        expires = _stamp(datetime.fromtimestamp(time.time() + STAGED_TTL_SECONDS, timezone.utc).replace(microsecond=0))
        record = {"binding": request, "payloadDigest": payload_digest, "state": "STAGED", "stagedExpiresAt": expires}
        _write(os.path.join(directory, "record.json"), record)
        fd = os.open(os.path.join(directory, "payload.json"), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            os.write(fd, payload); os.fsync(fd)
        finally:
            os.close(fd)
        _write(request_path, {"binding": request, "payloadDigest": payload_digest, "leaseId": lease_id})
        return {"requestId": request["requestId"], "startAttemptId": request["startAttemptId"], "status": "STORED", "leaseId": lease_id, "stagedExpiresAt": expires}
    finally:
        os.close(lock)


def attach(state_root, lease_id, binding, run_id):
    """Transition a matching non-expired STAGED lease to ATTACHED under one lock."""
    if not _safe_id(lease_id) or not isinstance(run_id, str) or not run_id:
        raise LifecycleError("LEASE_ATTACH_INVALID")
    lock = _locked(state_root)
    try:
        record_path = os.path.join(_lease_dir(_root(state_root), lease_id), "record.json")
        record = _read(record_path)
        if record.get("binding") != binding:
            raise LifecycleError("LEASE_BINDING_MISMATCH")
        if record.get("state") == "ATTACHED" and record.get("runId") == run_id:
            return False
        if record.get("state") != "STAGED":
            raise LifecycleError("LEASE_NOT_STAGED")
        if _parse_stamp(record.get("stagedExpiresAt")) <= _now():
            record["state"] = "REMOVED"; _write(record_path, record)
            raise LifecycleError("LEASE_EXPIRED")
        record.update({"state": "ATTACHED", "runId": run_id})
        _write(record_path, record)
        _write(os.path.join(_root(state_root), "attached", run_id + ".json"), {"leaseId": lease_id})
        return True
    finally:
        os.close(lock)


def payload_path(state_root, lease_id, run_id):
    """Return an internal path only after attachment validation (controller use)."""
    if not _safe_id(lease_id):
        raise LifecycleError("LEASE_ATTACH_INVALID")
    record = _read(os.path.join(_lease_dir(_root(state_root), lease_id), "record.json"))
    if record.get("state") != "ATTACHED" or record.get("runId") != run_id:
        raise LifecycleError("LEASE_NOT_ATTACHED")
    return os.path.join(_lease_dir(_root(state_root), lease_id), "payload.json")


def cleanup_run(state_root, run_id):
    """Remove one terminal run's attached payload through its private index."""
    if not isinstance(run_id, str) or not run_id:
        raise LifecycleError("LEASE_ATTACH_INVALID")
    lock = _locked(state_root)
    try:
        root = _root(state_root)
        attached = os.path.join(root, "attached", run_id + ".json")
        if not os.path.exists(attached):
            return False
        value = _read(attached)
        lease_id = value.get("leaseId") if isinstance(value, dict) else None
        if not _safe_id(lease_id):
            raise LifecycleError("LEASE_STORAGE_INVALID")
        directory = _lease_dir(root, lease_id)
        record = _read(os.path.join(directory, "record.json"))
        if record.get("state") != "ATTACHED" or record.get("runId") != run_id:
            raise LifecycleError("LEASE_STORAGE_INVALID")
        for name in ("payload.json", "record.json"):
            path = os.path.join(directory, name)
            if os.path.exists(path) and not os.path.islink(path):
                os.unlink(path)
        os.rmdir(directory)
        os.unlink(attached)
        return True
    finally:
        os.close(lock)


def register_plan(state_root, run_id, manifest_digest, manifest):
    """Persist the opaque run staging selected by one executable Core plan."""
    if not isinstance(manifest, dict) or not isinstance(run_id, str) or not run_id or not _DIGEST.fullmatch(manifest_digest or ""):
        raise LifecycleError("EXECUTION_MANIFEST_INVALID")
    binding = {"projectIdentity": manifest.get("projectIdentity"), "planFingerprint": manifest.get("planFingerprint"), "runtimeRelease": manifest.get("runtimeRelease")}
    if not isinstance(binding["projectIdentity"], str) or _PROJECT.fullmatch(binding["projectIdentity"]) is None or not _DIGEST.fullmatch(binding["planFingerprint"] or "") or not isinstance(binding["runtimeRelease"], dict):
        raise LifecycleError("EXECUTION_MANIFEST_INVALID")
    key = hashlib.sha256((manifest_digest + "\n" + binding["projectIdentity"] + "\n" + binding["planFingerprint"]).encode("ascii")).hexdigest()
    lock = _locked(state_root)
    try:
        _write(os.path.join(_root(state_root), "plans", key + ".json"), {"runId": run_id, "executionManifestDigest": manifest_digest, "binding": binding})
    finally:
        os.close(lock)


def resolve_plan(state_root, request):
    """Resolve one private staged manifest without scanning execution journals."""
    manifest_digest = request.get("executionManifestDigest") if isinstance(request, dict) else ""
    project = request.get("projectIdentity") if isinstance(request, dict) else ""
    fingerprint = request.get("planFingerprint") if isinstance(request, dict) else ""
    if not _DIGEST.fullmatch(manifest_digest or "") or not isinstance(project, str) or not isinstance(fingerprint, str):
        raise LifecycleError("START_REQUEST_INVALID")
    key = hashlib.sha256((manifest_digest + "\n" + project + "\n" + fingerprint).encode("ascii")).hexdigest()
    try:
        value = _read(os.path.join(_root(state_root), "plans", key + ".json"))
    except OSError:
        raise LifecycleError("EXECUTION_MANIFEST_MISSING")
    if not isinstance(value, dict) or value.get("executionManifestDigest") != manifest_digest or value.get("binding", {}).get("projectIdentity") != project or value.get("binding", {}).get("planFingerprint") != fingerprint:
        raise LifecycleError("EXECUTION_MANIFEST_MISSING")
    return value


def attempt(state_root, start_attempt_id, binding, run_id=None):
    """Read or durably bind one Start idempotency key without secret data."""
    if not _safe_id(start_attempt_id) or not isinstance(binding, dict):
        raise LifecycleError("START_REQUEST_INVALID")
    lock = _locked(state_root)
    try:
        path = os.path.join(_root(state_root), "attempts", start_attempt_id + ".json")
        if os.path.exists(path):
            current = _read(path)
            if not isinstance(current, dict) or current.get("binding") != binding or not isinstance(current.get("runId"), str) or not current["runId"]:
                raise LifecycleError("START_ATTEMPT_CONFLICT")
            return current["runId"], True
        if not isinstance(run_id, str) or not run_id:
            return None, False
        _write(path, {"binding": binding, "runId": run_id})
        return run_id, False
    finally:
        os.close(lock)

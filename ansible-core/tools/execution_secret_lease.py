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


LEASE_PROTOCOL = "PutRuntimeSecretLease/v1alpha2"
LEGACY_LEASE_PROTOCOL = "PutRuntimeSecretLease/v1alpha1"
PAYLOAD_VERSION = "TargetCredentialLeasePayload/v1alpha1"
PKI_PAYLOAD_VERSION = "TargetCredentialLeasePayload/v1alpha2"
RUNTIME_SECRET_PAYLOAD_VERSION = "TargetCredentialLeasePayload/v1alpha3"
TYPED_RUNTIME_SECRET_PAYLOAD_VERSION = "TargetCredentialLeasePayload/v1alpha4"
MAX_PAYLOAD_BYTES = 1088 * 1024
MAX_PKI_STORE_PASSWORD_BYTES = 4096
MAX_RUNTIME_SECRET_VALUES = 16
MAX_RUNTIME_SECRET_VALUE_BYTES = 4096
MAX_RUNTIME_SECRET_TOTAL_BYTES = 65536
MAX_TYPED_RUNTIME_SECRET_INPUTS = 16
MAX_TYPED_RUNTIME_SECRET_TOTAL_BYTES = 65536
MAX_TYPED_SHARE_ARRAY_BYTES = 32768
_TYPED_INPUT_OPERATIONS = {
    "SERVICE_ADMIN_TOKEN": ["SERVICE_APPLY", "SERVICE_VERIFY"],
    "SERVICE_UNSEAL_SHARES": ["SERVICE_APPLY"],
}
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
    base = {"apiVersion", "kind", "username", "password", "privateKey", "sudoPassword"}
    v2 = base | {"pkiStorePassword"}
    v3 = v2 | {"runtimeSecretValues"}
    v4 = v3 | {"runtimeSecretInputs"}
    if not isinstance(value, dict) or set(value) not in (base, v2, v3, v4) or value.get("apiVersion") not in (PAYLOAD_VERSION, PKI_PAYLOAD_VERSION, RUNTIME_SECRET_PAYLOAD_VERSION, TYPED_RUNTIME_SECRET_PAYLOAD_VERSION) or value.get("kind") != "TargetCredentialLeasePayload":
        raise LifecycleError("LEASE_PAYLOAD_INVALID")
    versions = {PAYLOAD_VERSION: base, PKI_PAYLOAD_VERSION: v2, RUNTIME_SECRET_PAYLOAD_VERSION: v3, TYPED_RUNTIME_SECRET_PAYLOAD_VERSION: v4}
    if set(value) != versions[value["apiVersion"]]:
        raise LifecycleError("LEASE_PAYLOAD_INVALID")
    username = value.get("username")
    password, key, sudo = value.get("password"), value.get("privateKey"), value.get("sudoPassword")
    if not isinstance(username, str) or not username or len(username.encode("utf-8")) > 255:
        raise LifecycleError("LEASE_PAYLOAD_INVALID")
    if (password is None) == (key is None) or (password is not None and (not isinstance(password, str) or not password)) or (key is not None and (not isinstance(key, str) or not key)) or (sudo is not None and (not isinstance(sudo, str) or not sudo)):
        raise LifecycleError("LEASE_PAYLOAD_INVALID")
    if value.get("apiVersion") == PKI_PAYLOAD_VERSION:
        store = value.get("pkiStorePassword")
        if store is not None:
            if not isinstance(store, str):
                raise LifecycleError("LEASE_PAYLOAD_INVALID")
            try: size = len(store.encode("utf-8", "strict"))
            except UnicodeError: raise LifecycleError("LEASE_PAYLOAD_INVALID")
            if size < 1 or size > MAX_PKI_STORE_PASSWORD_BYTES:
                raise LifecycleError("LEASE_PAYLOAD_INVALID")
    if value.get("apiVersion") in (RUNTIME_SECRET_PAYLOAD_VERSION, TYPED_RUNTIME_SECRET_PAYLOAD_VERSION):
        store = value.get("pkiStorePassword")
        if store is not None:
            if not isinstance(store, str):
                raise LifecycleError("LEASE_PAYLOAD_INVALID")
            try: size = len(store.encode("utf-8", "strict"))
            except UnicodeError: raise LifecycleError("LEASE_PAYLOAD_INVALID")
            if size < 1 or size > MAX_PKI_STORE_PASSWORD_BYTES:
                raise LifecycleError("LEASE_PAYLOAD_INVALID")
        values = value.get("runtimeSecretValues")
        if not isinstance(values, dict) or len(values) > MAX_RUNTIME_SECRET_VALUES or (value.get("apiVersion") == RUNTIME_SECRET_PAYLOAD_VERSION and not values):
            raise LifecycleError("LEASE_PAYLOAD_INVALID")
        total = 0
        for reference, secret in values.items():
            if not isinstance(reference, str) or re.fullmatch(r"[a-z][a-z0-9-]{0,63}", reference) is None or not isinstance(secret, str):
                raise LifecycleError("LEASE_PAYLOAD_INVALID")
            try: size = len(secret.encode("utf-8", "strict"))
            except UnicodeError: raise LifecycleError("LEASE_PAYLOAD_INVALID")
            if size < 1 or size > MAX_RUNTIME_SECRET_VALUE_BYTES:
                raise LifecycleError("LEASE_PAYLOAD_INVALID")
            total += size
            if total > MAX_RUNTIME_SECRET_TOTAL_BYTES:
                raise LifecycleError("LEASE_PAYLOAD_INVALID")
    if value.get("apiVersion") == TYPED_RUNTIME_SECRET_PAYLOAD_VERSION:
        inputs = value.get("runtimeSecretInputs")
        if not isinstance(inputs, list) or len(inputs) > MAX_TYPED_RUNTIME_SECRET_INPUTS:
            raise LifecycleError("LEASE_PAYLOAD_INVALID")
        seen, total = set(), 0
        for item in inputs:
            if not isinstance(item, dict) or set(item) != {"requirementRef", "purpose", "serviceDeployment", "operations", "value"}:
                raise LifecycleError("LEASE_PAYLOAD_INVALID")
            reference, purpose, deployment, operations = (item.get("requirementRef"), item.get("purpose"), item.get("serviceDeployment"), item.get("operations"))
            if (not isinstance(reference, str) or re.fullmatch(r"[a-z][a-z0-9-]{0,63}", reference) is None or
                    not isinstance(purpose, str) or purpose not in _TYPED_INPUT_OPERATIONS or
                    not isinstance(deployment, str) or len(deployment) > 128 or re.fullmatch(r"[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*", deployment) is None or
                    operations != _TYPED_INPUT_OPERATIONS.get(purpose) or (deployment, reference) in seen):
                raise LifecycleError("LEASE_PAYLOAD_INVALID")
            seen.add((deployment, reference))
            secret = item.get("value")
            if purpose == "SERVICE_ADMIN_TOKEN":
                if not isinstance(secret, str):
                    raise LifecycleError("LEASE_PAYLOAD_INVALID")
                try: size = len(secret.encode("utf-8", "strict"))
                except UnicodeError: raise LifecycleError("LEASE_PAYLOAD_INVALID")
                if not 1 <= size <= 4096:
                    raise LifecycleError("LEASE_PAYLOAD_INVALID")
            elif purpose == "SERVICE_UNSEAL_SHARES":
                if not isinstance(secret, list) or not 1 <= len(secret) <= 255 or any(not isinstance(share, str) for share in secret) or len(set(secret)) != len(secret):
                    raise LifecycleError("LEASE_PAYLOAD_INVALID")
                for share in secret:
                    try: size = len(share.encode("utf-8", "strict"))
                    except UnicodeError: raise LifecycleError("LEASE_PAYLOAD_INVALID")
                    if not 1 <= size <= 128:
                        raise LifecycleError("LEASE_PAYLOAD_INVALID")
                    total += size
                encoded_shares = json.dumps(secret, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
                if len(encoded_shares) > MAX_TYPED_SHARE_ARRAY_BYTES:
                    raise LifecycleError("LEASE_PAYLOAD_INVALID")
                total += len(encoded_shares)
            else:
                raise LifecycleError("LEASE_PAYLOAD_INVALID")
            if purpose == "SERVICE_ADMIN_TOKEN":
                total += size
            if total > MAX_TYPED_RUNTIME_SECRET_TOTAL_BYTES:
                raise LifecycleError("LEASE_PAYLOAD_INVALID")
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_PAYLOAD_BYTES:
        raise LifecycleError("LEASE_PAYLOAD_TOO_LARGE")
    return encoded


def pki_store_password(state_root, lease_id, run_id):
    """Return one attached PKI-bearing v2/v3 secret, never a path."""
    path = payload_path(state_root, lease_id, run_id)
    try:
        with open(path, "rb") as stream:
            raw = stream.read(MAX_PAYLOAD_BYTES + 1)
        value = json.loads(raw.decode("utf-8", "strict"))
    except (OSError, UnicodeError, ValueError):
        raise LifecycleError("LEASE_PAYLOAD_INVALID")
    _payload(value)
    if value.get("apiVersion") not in (PKI_PAYLOAD_VERSION, RUNTIME_SECRET_PAYLOAD_VERSION, TYPED_RUNTIME_SECRET_PAYLOAD_VERSION) or value.get("pkiStorePassword") is None:
        raise LifecycleError("PKI_STORE_PASSWORD_RUNTIME_SECRET_REQUIRED")
    return value["pkiStorePassword"]


def pki_store_password_for_run(state_root, run_id):
    """Resolve the one private attached v2 password for a controller run."""
    attached = _read(os.path.join(_root(state_root), "attached", run_id + ".json"))
    lease_id = attached.get("leaseId") if isinstance(attached, dict) else None
    if not _safe_id(lease_id):
        raise LifecycleError("PKI_STORE_PASSWORD_RUNTIME_SECRET_REQUIRED")
    return pki_store_password(state_root, lease_id, run_id)


def target_username_for_run(state_root, run_id):
    """Return only the attached target-login name for controller projection.

    The value is safe connection metadata, unlike the password/private-key
    fields that must remain inside the private lease.  A run without a lease
    keeps the established persistent-identity execution behavior.
    """
    attached_path = os.path.join(_root(state_root), "attached", run_id + ".json")
    if not os.path.exists(attached_path):
        return None
    attached = _read(attached_path)
    lease_id = attached.get("leaseId") if isinstance(attached, dict) else None
    if not _safe_id(lease_id):
        raise LifecycleError("LEASE_ATTACH_INVALID")
    path = payload_path(state_root, lease_id, run_id)
    try:
        with open(path, "rb") as stream:
            raw = stream.read(MAX_PAYLOAD_BYTES + 1)
        value = json.loads(raw.decode("utf-8", "strict"))
    except (OSError, UnicodeError, ValueError):
        raise LifecycleError("LEASE_PAYLOAD_INVALID")
    _payload(value)
    return value["username"]


def ansible_connection_credentials_for_run(state_root, run_id):
    """Return only attached target SSH/sudo credentials to the controller.

    The fixed runner consumes these in a private, per-operation workspace;
    PKI and service secrets never cross this adapter.
    """
    attached_path = os.path.join(_root(state_root), "attached", run_id + ".json")
    if not os.path.exists(attached_path):
        return None
    value = _attached_payload_for_run(state_root, run_id)
    password = value.get("password")
    result = {"ansible_password": password} if password is not None else {"privateKey": value["privateKey"]}
    if value.get("sudoPassword") is not None:
        result["ansible_become_password"] = value["sudoPassword"]
    return result


def runtime_secret_values_for_run(state_root, run_id):
    """Return attached bounded service values only to the controller process."""
    value = _attached_payload_for_run(state_root, run_id)
    values = value.get("runtimeSecretValues") if value.get("apiVersion") in (RUNTIME_SECRET_PAYLOAD_VERSION, TYPED_RUNTIME_SECRET_PAYLOAD_VERSION) else None
    if not isinstance(values, dict): raise LifecycleError("RUNTIME_SECRET_VALUES_REQUIRED")
    return values


def _attached_payload_for_run(state_root, run_id):
    attached = _read(os.path.join(_root(state_root), "attached", run_id + ".json"))
    lease_id = attached.get("leaseId") if isinstance(attached, dict) else None
    if not _safe_id(lease_id):
        raise LifecycleError("LEASE_ATTACH_INVALID")
    path = payload_path(state_root, lease_id, run_id)
    try:
        with open(path, "rb") as stream:
            raw = stream.read(MAX_PAYLOAD_BYTES + 1)
        value = json.loads(raw.decode("utf-8", "strict"))
    except (OSError, UnicodeError, ValueError):
        raise LifecycleError("LEASE_PAYLOAD_INVALID")
    _payload(value)
    return value


def _validate_typed_secret_requirements(requirements):
    if not isinstance(requirements, list) or len(requirements) > MAX_TYPED_RUNTIME_SECRET_INPUTS:
        raise LifecycleError("EXECUTION_MANIFEST_INVALID")
    expected = {}
    for requirement in requirements:
        fields = {"requirementRef", "purpose", "serviceDeployment", "manifestRequirementRef", "hosts", "requiredWhen", "operations"}
        if not isinstance(requirement, dict) or set(requirement) != fields:
            raise LifecycleError("EXECUTION_MANIFEST_INVALID")
        reference, purpose = requirement.get("requirementRef"), requirement.get("purpose")
        manifest_reference = requirement.get("manifestRequirementRef")
        deployment, hosts = requirement.get("serviceDeployment"), requirement.get("hosts")
        key = (deployment, reference)
        if (not isinstance(reference, str) or re.fullmatch(r"[a-z][a-z0-9-]{0,63}", reference) is None or
                not isinstance(manifest_reference, str) or re.fullmatch(r"[a-z][a-z0-9-]{0,63}", manifest_reference) is None or
                purpose not in _TYPED_INPUT_OPERATIONS or
                not isinstance(deployment, str) or len(deployment) > 128 or re.fullmatch(r"[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*", deployment) is None or
                not isinstance(hosts, list) or len(hosts) > 256 or any(not isinstance(host, str) or not host for host in hosts) or len(set(hosts)) != len(hosts) or
                requirement.get("requiredWhen") != {"SERVICE_ADMIN_TOKEN": "INITIALIZED", "SERVICE_UNSEAL_SHARES": "SEALED"}[purpose] or
                requirement.get("operations") != _TYPED_INPUT_OPERATIONS.get(purpose) or key in expected):
            raise LifecycleError("EXECUTION_MANIFEST_INVALID")
        expected[key] = requirement
    return expected


def _validate_typed_secret_payload(values, requirements):
    expected = _validate_typed_secret_requirements(requirements)
    provided = values.get("runtimeSecretInputs", []) if values.get("apiVersion") == TYPED_RUNTIME_SECRET_PAYLOAD_VERSION else []
    if provided and values.get("apiVersion") != TYPED_RUNTIME_SECRET_PAYLOAD_VERSION:
        raise LifecycleError("RUNTIME_SECRET_INPUTS_UNEXPECTED")
    seen = set()
    for item in provided:
        key = (item["serviceDeployment"], item["requirementRef"])
        requirement = expected.get(key)
        if (key in seen or requirement is None or
                any(item[name] != requirement[name] for name in ("requirementRef", "purpose", "serviceDeployment", "operations"))):
            raise LifecycleError("RUNTIME_SECRET_INPUTS_MISMATCH")
        seen.add(key)
    return provided


def validate_staged_runtime_secret_inputs(state_root, lease_id, requirements):
    """Bind supplied v1alpha4 values to the exact digest-protected Core manifest.

    Conditional inputs may be absent: Core cannot observe initialized/sealed
    target state. The service role enforces those runtime prerequisites before
    mutating service configuration.
    """
    if not _safe_id(lease_id):
        raise LifecycleError("RUNTIME_SECRET_INPUTS_REQUIRED")
    record = _read(os.path.join(_lease_dir(_root(state_root), lease_id), "record.json"))
    if record.get("state") != "STAGED":
        raise LifecycleError("LEASE_NOT_STAGED")
    try:
        with open(os.path.join(_lease_dir(_root(state_root), lease_id), "payload.json"), "rb") as stream:
            raw = stream.read(MAX_PAYLOAD_BYTES + 1)
        value = json.loads(raw.decode("utf-8", "strict"))
    except (OSError, UnicodeError, ValueError):
        raise LifecycleError("LEASE_PAYLOAD_INVALID")
    _payload(value)
    typed = _validate_typed_secret_payload(value, requirements)
    if (requirements or typed) and value.get("apiVersion") != TYPED_RUNTIME_SECRET_PAYLOAD_VERSION:
        raise LifecycleError("RUNTIME_SECRET_INPUTS_REQUIRED")
    return typed


def runtime_secret_inputs_for_operation(state_root, run_id, deployment, operation, requirements):
    """Return only the attached typed values allowed for this deployment/action."""
    expected = _validate_typed_secret_requirements(requirements)
    value = _attached_payload_for_run(state_root, run_id)
    provided = _validate_typed_secret_payload(value, requirements)
    result = []
    for item in provided:
        if item["serviceDeployment"] == deployment and operation in item["operations"]:
            result.append({"requirementRef": item["requirementRef"], "purpose": item["purpose"], "value": item["value"]})
    if any((deployment, item["requirementRef"]) not in expected for item in result):
        raise LifecycleError("RUNTIME_SECRET_INPUTS_MISMATCH")
    return result


def validate_staged_pki_store_password(state_root, lease_id, allow_service_values=False, allow_typed_inputs=False):
    """Prove a staged lease carries the one closed v2 PKI value without
    returning it.  Start uses this before its durable commit."""
    if not _safe_id(lease_id):
        raise LifecycleError("PKI_STORE_PASSWORD_RUNTIME_SECRET_REQUIRED")
    record = _read(os.path.join(_lease_dir(_root(state_root), lease_id), "record.json"))
    if record.get("state") != "STAGED":
        raise LifecycleError("LEASE_NOT_STAGED")
    try:
        with open(os.path.join(_lease_dir(_root(state_root), lease_id), "payload.json"), "rb") as stream:
            raw = stream.read(MAX_PAYLOAD_BYTES + 1)
        value = json.loads(raw.decode("utf-8", "strict"))
    except (OSError, UnicodeError, ValueError):
        raise LifecycleError("LEASE_PAYLOAD_INVALID")
    _payload(value)
    if value.get("apiVersion") not in (PKI_PAYLOAD_VERSION, RUNTIME_SECRET_PAYLOAD_VERSION, TYPED_RUNTIME_SECRET_PAYLOAD_VERSION) or value.get("pkiStorePassword") is None:
        raise LifecycleError("PKI_STORE_PASSWORD_RUNTIME_SECRET_REQUIRED")
    if value.get("apiVersion") in (RUNTIME_SECRET_PAYLOAD_VERSION, TYPED_RUNTIME_SECRET_PAYLOAD_VERSION) and value.get("runtimeSecretValues") and not allow_service_values:
        raise LifecycleError("RUNTIME_SECRET_VALUES_UNEXPECTED")
    if value.get("apiVersion") == TYPED_RUNTIME_SECRET_PAYLOAD_VERSION and value.get("runtimeSecretInputs") and not allow_typed_inputs:
        raise LifecycleError("RUNTIME_SECRET_INPUTS_UNEXPECTED")


def validate_staged_payload_without_pki_store_password(state_root, lease_id, allow_typed_inputs=False, allow_service_values=False):
    """Reject a secret-bearing v2 lease when the private manifest did not
    attest the closed PKI requirement."""
    if not _safe_id(lease_id):
        raise LifecycleError("LEASE_PAYLOAD_INVALID")
    record = _read(os.path.join(_lease_dir(_root(state_root), lease_id), "record.json"))
    if record.get("state") != "STAGED":
        raise LifecycleError("LEASE_NOT_STAGED")
    try:
        with open(os.path.join(_lease_dir(_root(state_root), lease_id), "payload.json"), "rb") as stream:
            raw = stream.read(MAX_PAYLOAD_BYTES + 1)
        value = json.loads(raw.decode("utf-8", "strict"))
    except (OSError, UnicodeError, ValueError):
        raise LifecycleError("LEASE_PAYLOAD_INVALID")
    _payload(value)
    if value.get("apiVersion") in (PKI_PAYLOAD_VERSION, RUNTIME_SECRET_PAYLOAD_VERSION, TYPED_RUNTIME_SECRET_PAYLOAD_VERSION) and value.get("pkiStorePassword") is not None:
        raise LifecycleError("PKI_STORE_PASSWORD_UNEXPECTED")
    if value.get("apiVersion") in (RUNTIME_SECRET_PAYLOAD_VERSION, TYPED_RUNTIME_SECRET_PAYLOAD_VERSION) and value.get("runtimeSecretValues") and not allow_service_values:
        raise LifecycleError("RUNTIME_SECRET_VALUES_UNEXPECTED")
    if value.get("apiVersion") == TYPED_RUNTIME_SECRET_PAYLOAD_VERSION and value.get("runtimeSecretInputs") and not allow_typed_inputs:
        raise LifecycleError("RUNTIME_SECRET_INPUTS_UNEXPECTED")


def validate_staged_runtime_secret_values(state_root, lease_id, requirements):
    """Prove the v1alpha3 key set before attaching a service-secret lease."""
    if not _safe_id(lease_id) or not isinstance(requirements, list) or not requirements:
        raise LifecycleError("RUNTIME_SECRET_VALUES_REQUIRED")
    record = _read(os.path.join(_lease_dir(_root(state_root), lease_id), "record.json"))
    if record.get("state") != "STAGED":
        raise LifecycleError("LEASE_NOT_STAGED")
    try:
        with open(os.path.join(_lease_dir(_root(state_root), lease_id), "payload.json"), "rb") as stream:
            raw = stream.read(MAX_PAYLOAD_BYTES + 1)
        value = json.loads(raw.decode("utf-8", "strict"))
    except (OSError, UnicodeError, ValueError):
        raise LifecycleError("LEASE_PAYLOAD_INVALID")
    _payload(value)
    values = value.get("runtimeSecretValues") if value.get("apiVersion") in (RUNTIME_SECRET_PAYLOAD_VERSION, TYPED_RUNTIME_SECRET_PAYLOAD_VERSION) else None
    expected = {item.get("requirementRef") for item in requirements if isinstance(item, dict)}
    if not expected or len(expected) != len(requirements) or not isinstance(values, dict) or set(values) != expected:
        raise LifecycleError("RUNTIME_SECRET_VALUES_REQUIRED")


def _request_path(root, request_id): return os.path.join(root, "requests", request_id + ".json")
def _lease_dir(root, lease_id): return os.path.join(root, "leases", lease_id)
def _prepared_path(root, start_attempt_id): return os.path.join(root, "prepared", start_attempt_id + ".json")


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


def register_plan(state_root, staging_id, manifest_digest, manifest):
    """Persist opaque pre-start staging selected by one executable Core plan.

    A staging id is deliberately not an execution run id.  Only Start v2 on
    the Execution Node allocates an authoritative run id.
    """
    if not isinstance(manifest, dict) or not isinstance(staging_id, str) or not staging_id or not _DIGEST.fullmatch(manifest_digest or ""):
        raise LifecycleError("EXECUTION_MANIFEST_INVALID")
    binding = {"projectIdentity": manifest.get("projectIdentity"), "planFingerprint": manifest.get("planFingerprint"), "runtimeRelease": manifest.get("runtimeRelease")}
    if not isinstance(binding["projectIdentity"], str) or _PROJECT.fullmatch(binding["projectIdentity"]) is None or not _DIGEST.fullmatch(binding["planFingerprint"] or "") or not isinstance(binding["runtimeRelease"], dict):
        raise LifecycleError("EXECUTION_MANIFEST_INVALID")
    key = hashlib.sha256((manifest_digest + "\n" + binding["projectIdentity"] + "\n" + binding["planFingerprint"]).encode("ascii")).hexdigest()
    lock = _locked(state_root)
    try:
        _write(os.path.join(_root(state_root), "plans", key + ".json"), {"stagingId": staging_id, "executionManifestDigest": manifest_digest, "binding": binding})
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


def prepared_start(state_root, start_attempt_id, attempt_binding):
    """Read one uncommitted private Start transaction without mutating it."""
    if not _safe_id(start_attempt_id) or not isinstance(attempt_binding, dict):
        raise LifecycleError("START_REQUEST_INVALID")
    lock = _locked(state_root)
    try:
        path = _prepared_path(_root(state_root), start_attempt_id)
        if not os.path.exists(path):
            return None
        value = _read(path)
        if not isinstance(value, dict) or value.get("state") != "PREPARED" or value.get("binding") != attempt_binding or not isinstance(value.get("runId"), str) or not isinstance(value.get("stagingId"), str):
            raise LifecycleError("START_ATTEMPT_CONFLICT")
        return value
    finally:
        os.close(lock)


def _rollback_prepared_locked(root, start_attempt_id, attempt_binding):
    path = _prepared_path(root, start_attempt_id)
    if not os.path.exists(path):
        return False
    prepared = _read(path)
    if not isinstance(prepared, dict) or prepared.get("state") != "PREPARED" or prepared.get("binding") != attempt_binding:
        raise LifecycleError("START_ATTEMPT_CONFLICT")
    attempt_path = os.path.join(root, "attempts", start_attempt_id + ".json")
    if os.path.exists(attempt_path):
        # G already happened: the immutable mapping is authoritative and
        # must never be rolled back by recovery.
        return False
    lease_id = prepared.get("leaseId")
    if lease_id is not None:
        if not _safe_id(lease_id):
            raise LifecycleError("LEASE_STORAGE_INVALID")
        record_path = os.path.join(_lease_dir(root, lease_id), "record.json")
        record = _read(record_path)
        if record.get("binding") != prepared.get("leaseBinding"):
            raise LifecycleError("LEASE_BINDING_MISMATCH")
        if record.get("state") == "ATTACHED" and record.get("runId") == prepared.get("runId"):
            record.pop("runId", None); record["state"] = "STAGED"
            _write(record_path, record)
        attached = os.path.join(root, "attached", prepared["runId"] + ".json")
        if os.path.exists(attached):
            index = _read(attached)
            if index.get("leaseId") != lease_id:
                raise LifecycleError("LEASE_STORAGE_INVALID")
            os.unlink(attached)
    os.unlink(path)
    return True


def rollback_prepared_start(state_root, start_attempt_id, attempt_binding):
    """Undo only a private PREPARED transaction with no published mapping."""
    lock = _locked(state_root)
    try:
        return _rollback_prepared_locked(_root(state_root), start_attempt_id, attempt_binding)
    finally:
        os.close(lock)


def commit_start(state_root, start_attempt_id, attempt_binding, run_id, staging_id, lease_id=None, lease_binding=None):
    """Prepare lease state, then publish attempt->run as the final commit.

    The private PREPARED record makes each pre-commit write recoverable.  The
    attempt mapping is deliberately the only authoritative commit point.
    """
    if not _safe_id(start_attempt_id) or not isinstance(attempt_binding, dict) or not isinstance(run_id, str) or not run_id or not isinstance(staging_id, str) or not staging_id:
        raise LifecycleError("START_REQUEST_INVALID")
    lock = _locked(state_root)
    try:
        root = _root(state_root)
        attempt_path = os.path.join(root, "attempts", start_attempt_id + ".json")
        if os.path.exists(attempt_path):
            existing = _read(attempt_path)
            if existing.get("binding") != attempt_binding or existing.get("runId") != run_id:
                raise LifecycleError("START_ATTEMPT_CONFLICT")
            return False
        prepared_path = _prepared_path(root, start_attempt_id)
        if os.path.exists(prepared_path):
            raise LifecycleError("START_ATTEMPT_CONFLICT")
        if lease_id is not None:
            if not _safe_id(lease_id) or not isinstance(lease_binding, dict):
                raise LifecycleError("LEASE_ATTACH_INVALID")
            record_path = os.path.join(_lease_dir(root, lease_id), "record.json")
            record = _read(record_path)
            if record.get("binding") != lease_binding or record.get("state") != "STAGED":
                raise LifecycleError("LEASE_BINDING_MISMATCH")
            if _parse_stamp(record.get("stagedExpiresAt")) <= _now():
                raise LifecycleError("LEASE_EXPIRED")
        prepared = {"state": "PREPARED", "binding": attempt_binding, "runId": run_id, "stagingId": staging_id, "leaseId": lease_id, "leaseBinding": lease_binding}
        _write(prepared_path, prepared)
        try:
            if lease_id is not None:
                record.update({"state": "ATTACHED", "runId": run_id})
                _write(record_path, record)
                _write(os.path.join(root, "attached", run_id + ".json"), {"leaseId": lease_id})
                # Verify every durable precondition before publication.
                if _read(record_path).get("state") != "ATTACHED" or _read(os.path.join(root, "attached", run_id + ".json")).get("leaseId") != lease_id:
                    raise LifecycleError("LEASE_STORAGE_INVALID")
            # Final durable publication: after this write the identity is
            # authoritative and must not be returned to staging.
            _write(attempt_path, {"binding": attempt_binding, "runId": run_id})
        except Exception:
            _rollback_prepared_locked(root, start_attempt_id, attempt_binding)
            raise
        try:
            os.unlink(prepared_path)
        except OSError:
            # The mapping is already authoritative; a stale private recovery
            # record cannot change that and is ignored by normal retries.
            pass
        return True
    finally:
        os.close(lock)

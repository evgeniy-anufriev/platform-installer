#!/usr/bin/env python3
"""Fixed Execution Node controller.  It never accepts a command or playbook."""
from __future__ import print_function

import argparse
import hashlib
import json
import os
import re
import select
import signal
import stat
import subprocess
import sys
import time
import tempfile

from execution_lifecycle import EXECUTION_STATE_ROOT, Journal, LifecycleError, digest, retain
import execution_secret_lease


SERVICE_TYPES = frozenset(("kafka", "keepalived", "postgresql", "bind", "haproxy", "dns-client"))
PROJECT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,127}$")
MAX_GENERATED_STATE_BYTES = 1024 * 1024
MAX_PKI_MATERIALIZATION_PLANS = 4096
MAX_PKI_PLAN_STRING_BYTES = 4096
MAX_OPERATION_FAILURE_CAPTURE_BYTES = 32768
OPERATION_ERROR_CODE = re.compile(br'(?:"error_code"\s*:\s*"|error_code\s*[=:]\s*)([A-Z][A-Z0-9_]{2,127})')
_PKI_PLAN_FIELDS = frozenset(("id", "requestId", "tlsProfileId", "authorityId", "hostId", "targetDirectory", "formats", "keyAlias", "trustAlias", "storePasswordSecretRef", "materializationFingerprint"))
_PKI_PLAN_FORMATS = ("PEM", "PKCS12_KEYSTORE", "PKCS12_TRUSTSTORE")


def _safe_pki_plan_string(value):
    return isinstance(value, str) and 0 < len(value.encode("utf-8")) <= MAX_PKI_PLAN_STRING_BYTES and not any(ord(character) < 32 for character in value)


def _operation_error_code(output):
    """Return only the final bounded machine error token from child output."""
    matches = OPERATION_ERROR_CODE.findall(output if isinstance(output, bytes) else b"")
    return matches[-1].decode("ascii") if matches else ""


def _wait_for_operation(process, stopped):
    """Drain child output without persisting it or allowing an output flood.

    The retained rolling window exists only in memory and is reduced to a
    strictly-shaped ``error_code`` token before it reaches the journal.
    """
    captured = bytearray()
    descriptor = process.stdout.fileno()
    while True:
        if stopped[0]:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
            return None
        readable, _, _ = select.select([descriptor], [], [], 0.1)
        if readable:
            chunk = os.read(descriptor, 8192)
            if chunk:
                captured.extend(chunk)
                if len(captured) > MAX_OPERATION_FAILURE_CAPTURE_BYTES:
                    del captured[:-MAX_OPERATION_FAILURE_CAPTURE_BYTES]
            elif process.poll() is not None:
                break
        if process.poll() is not None and not readable:
            break
    try:
        process.stdout.close()
    except OSError:
        pass
    return process.returncode, _operation_error_code(bytes(captured))


def _pki_materialization_plans(manifest):
    """Return the bounded Core-derived plans carried by one private manifest.

    This is intentionally a narrow controller boundary, not another PKI
    resolver.  Core already owns all certificate and SAN semantics; the
    controller only admits the fixed data shape required by the independent
    PKI and service Ansible processes.
    """
    values = manifest.get("pkiMaterializationPlans", [])
    if not isinstance(values, list) or len(values) > MAX_PKI_MATERIALIZATION_PLANS:
        raise LifecycleError("EXECUTION_MANIFEST_INVALID")
    identities = set()
    for value in values:
        if not isinstance(value, dict) or set(value) != _PKI_PLAN_FIELDS:
            raise LifecycleError("EXECUTION_MANIFEST_INVALID")
        for field in ("id", "requestId", "tlsProfileId", "authorityId", "hostId", "targetDirectory", "keyAlias", "trustAlias", "materializationFingerprint"):
            if not _safe_pki_plan_string(value.get(field)):
                raise LifecycleError("EXECUTION_MANIFEST_INVALID")
        if value["id"] in identities or not value["targetDirectory"].startswith("/"):
            raise LifecycleError("EXECUTION_MANIFEST_INVALID")
        identities.add(value["id"])
        if value.get("formats") != list(_PKI_PLAN_FORMATS):
            raise LifecycleError("EXECUTION_MANIFEST_INVALID")
        reference = value.get("storePasswordSecretRef")
        if reference is not None and reference != "runtime:pki-store-password":
            raise LifecycleError("EXECUTION_MANIFEST_INVALID")
    return values


def _terminal(journal, state, code, summary):
    result = journal.terminal(state, code, summary)
    # Lease cleanup is private node maintenance; it never changes the already
    # authoritative terminal execution outcome or emits credential diagnostics.
    secret = os.path.join(journal.directory, ".pki-store-password")
    if os.path.lexists(secret):
        details = os.lstat(secret)
        if not os.path.islink(secret) and os.path.isfile(secret):
            os.unlink(secret)
    for name in os.listdir(journal.directory):
        if not name.startswith(".runtime-secret-"):
            continue
        path = os.path.join(journal.directory, name)
        details = os.lstat(path)
        if not stat.S_ISLNK(details.st_mode) and stat.S_ISREG(details.st_mode):
            os.unlink(path)
    execution_secret_lease.cleanup_run(journal.root, journal.run_id)
    return result


def _safe_service(value):
    return isinstance(value, str) and value in SERVICE_TYPES


def _context_value(operation, key):
    value = operation.get(key)
    return value if isinstance(value, str) else ""


def _generated_state_path(state_root, project_identity):
    """Return the one controller-owned generated-state path for a project.

    This state is deliberately outside ephemeral run workspaces and is never
    derived from a project-supplied pathname. The controller serializes active
    runs, while these checks prevent a substituted filesystem object from being
    supplied to an Ansible service playbook.
    """
    if not isinstance(project_identity, str) or PROJECT_ID.fullmatch(project_identity) is None:
        raise LifecycleError("EXECUTION_PROJECT_ID_INVALID")
    root = os.path.join(state_root, "projects")
    for path in (root, os.path.join(root, project_identity), os.path.join(root, project_identity, "generated")):
        try:
            os.mkdir(path, 0o700)
        except FileExistsError:
            pass
        except OSError:
            raise LifecycleError("EXECUTION_GENERATED_STATE_UNSAFE")
        details = os.lstat(path)
        if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode) or (stat.S_IMODE(details.st_mode) & 0o077):
            raise LifecycleError("EXECUTION_GENERATED_STATE_UNSAFE")
    path = os.path.join(root, project_identity, "generated", "platform-state.yml")
    if os.path.lexists(path):
        details = os.lstat(path)
        if stat.S_ISLNK(details.st_mode) or not stat.S_ISREG(details.st_mode) or details.st_size > MAX_GENERATED_STATE_BYTES or (stat.S_IMODE(details.st_mode) & 0o077):
            raise LifecycleError("EXECUTION_GENERATED_STATE_UNSAFE")
    return path


def _command(release, journal, operation):
    kind = operation.get("operation")
    if kind == "PKI_APPLY":
        projection = os.path.join(journal.directory, "runtime-projection.json")
        if not os.path.isfile(projection) or os.path.islink(projection):
            raise LifecycleError("EXECUTION_RUNTIME_PROJECTION_MISSING")
        return ["ansible-playbook", "-i", os.path.join(journal.directory, "project", "inventory", "hosts.yml"), os.path.join(release, "ansible-core", "playbooks", "pki-apply.yml"), "-e", "@" + projection]
    if kind in ("SERVICE_APPLY", "SERVICE_VERIFY") and _safe_service(operation.get("serviceType")):
        action = "apply" if kind == "SERVICE_APPLY" else "verify"
        operation_id = operation.get("operationId")
        if not isinstance(operation_id, str) or not operation_id:
            raise LifecycleError("EXECUTION_MANIFEST_INVALID")
        projection = os.path.join(journal.directory, ".runtime-projection-" + hashlib.sha256(operation_id.encode("utf-8")).hexdigest() + ".json")
        if not os.path.isfile(projection) or os.path.islink(projection):
            raise LifecycleError("EXECUTION_RUNTIME_PROJECTION_MISSING")
        deployment = operation.get("serviceDeployment")
        if not isinstance(deployment, str) or not deployment or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-" for char in deployment):
            raise LifecycleError("EXECUTION_MANIFEST_INVALID")
        command = ["ansible-playbook", "-i", os.path.join(journal.directory, "project", "inventory", "hosts.yml"), os.path.join(release, "services", operation["serviceType"], "playbooks", action + ".yml"), "-e", "@" + projection]
        if operation.get("requiresArtifactSources") is True:
            command.extend(["-e", "platform_execution_service_deployment=" + deployment, "-e", "platform_artifact_source_authority_active=true"])
        return command
    if kind == "CORE_DELAY" and operation.get("operationId") == "core:delay":
        # A Core-owned, bounded safe fixture used only to prove detached unit
        # and process-group semantics; it is not supplied by a client.
        return [sys.executable, "-c", "import time; time.sleep(8)"]
    raise LifecycleError("EXECUTION_OPERATION_UNKNOWN")


def _environment(release, journal=None, operation=None):
    collections = [os.path.join(release, "ansible-core", "collections")]
    service_root = os.path.join(release, "services")
    if os.path.isdir(service_root):
        collections.extend(os.path.join(service_root, name, "ansible_collections") for name in sorted(os.listdir(service_root)) if os.path.isdir(os.path.join(service_root, name, "ansible_collections")))
    environment = dict(os.environ)
    for inherited in ("ANSIBLE_CALLBACK_PLUGINS", "ANSIBLE_CALLBACK_WHITELIST", "ANSIBLE_CALLBACKS_ENABLED", "ANSIBLE_LOAD_CALLBACK_PLUGINS", "ANSIBLE_STDOUT_CALLBACK"):
        environment.pop(inherited, None)
    environment.update(
        ANSIBLE_CONFIG=os.path.join(release, "ansible-core", "ansible.cfg"),
        ANSIBLE_COLLECTIONS_PATH=os.pathsep.join(collections),
        ANSIBLE_SSH_ARGS=("-o IdentityFile=%s/identities/default/id_ed25519 -o IdentitiesOnly=yes "
                          "-o UserKnownHostsFile=%s/known_hosts -o StrictHostKeyChecking=yes" %
                          (EXECUTION_STATE_ROOT, EXECUTION_STATE_ROOT)))
    if journal is not None and operation is not None:
        environment.update({
            "ANSIBLE_CALLBACKS_ENABLED": "platform.core.execution_events_json",
            "PLATFORM_EXECUTION_RUN_ID": journal.run_id,
            "PLATFORM_EXECUTION_PHASE_ID": _context_value(operation, "phaseId"),
            "PLATFORM_EXECUTION_ACTION_ID": _context_value(operation, "operationId"),
            "PLATFORM_EXECUTION_SERVICE_DEPLOYMENT": _context_value(operation, "serviceDeployment"),
        })
    return environment


def _validate_runtime_projection(journal, metadata, manifest):
    service = any(isinstance(operation, dict) and operation.get("operation") in ("SERVICE_APPLY", "SERVICE_VERIFY")
                  for operation in manifest.get("operations", []))
    if not service:
        return
    projection_path = os.path.join(journal.directory, "runtime-projection.json")
    if os.path.islink(projection_path) or not os.path.isfile(projection_path):
        raise LifecycleError("EXECUTION_RUNTIME_PROJECTION_MISSING")
    with open(projection_path, "r", encoding="utf-8") as stream:
        projection = json.load(stream)
    if not isinstance(projection, dict) or projection.get("apiVersion") != "platform.installer/runtime-projection/v1alpha2":
        raise LifecycleError("EXECUTION_RUNTIME_PROJECTION_INVALID")
    expected_generated_state_path = _generated_state_path(journal.root, metadata.get("projectIdentity"))
    plans = _pki_materialization_plans(manifest)
    if (projection.get("platform_execution_run_id") != metadata.get("runId") or
            projection.get("platform_execution_project_identity") != metadata.get("projectIdentity") or
            projection.get("platform_execution_plan_fingerprint") != metadata.get("planFingerprint") or
            projection.get("platform_execution_manifest_digest") != metadata.get("manifestDigest") or
            not isinstance(projection.get("platform_execution_requirements_fingerprint"), str) or
            not projection["platform_execution_requirements_fingerprint"].startswith("sha256:") or
            projection.get("platform_generated_state_path") != expected_generated_state_path or
            not isinstance(projection.get("platform_artifact_source_authorities_by_deployment"), dict) or
            projection.get("platform_pki_materialization_plans") != plans or
            not isinstance(projection.get("platform_pki_secret_files"), dict)):
        raise LifecycleError("EXECUTION_RUNTIME_PROJECTION_MISMATCH")


def _materialize_runtime_projection(journal, metadata, manifest):
    """Derive the controller-only projection from one digest-bound manifest."""
    operations = manifest.get("operations")
    requirements = manifest.get("artifactRequirements")
    authorities = manifest.get("artifactSourceAuthorities")
    secret_requirements = manifest.get("runtimeSecretRequirements", [])
    plans = _pki_materialization_plans(manifest)
    if not isinstance(operations, list) or not isinstance(requirements, list) or not isinstance(authorities, list) or not isinstance(secret_requirements, list):
        raise LifecycleError("EXECUTION_MANIFEST_INVALID")
    by_deployment = {}
    for authority in authorities:
        requirement = authority.get("requirement") if isinstance(authority, dict) else None
        if not isinstance(requirement, dict):
            raise LifecycleError("EXECUTION_MANIFEST_INVALID")
        deployment, requirement_id = requirement.get("serviceDeployment"), requirement.get("requirementId")
        if not isinstance(deployment, str) or not isinstance(requirement_id, str) or not deployment or not requirement_id:
            raise LifecycleError("EXECUTION_MANIFEST_INVALID")
        scoped = by_deployment.setdefault(deployment, {})
        if requirement_id in scoped:
            raise LifecycleError("EXECUTION_MANIFEST_INVALID")
        scoped[requirement_id] = authority
    required_deployments = set()
    for requirement in requirements:
        if not isinstance(requirement, dict) or not isinstance(requirement.get("serviceDeployment"), str):
            raise LifecycleError("EXECUTION_MANIFEST_INVALID")
        required_deployments.add(requirement["serviceDeployment"])
    for operation in operations:
        if isinstance(operation, dict) and operation.get("operation") in ("SERVICE_APPLY", "SERVICE_VERIFY") and operation.get("requiresArtifactSources") is True:
            if operation.get("serviceDeployment") in required_deployments and operation.get("serviceDeployment") not in by_deployment:
                raise LifecycleError("EXECUTION_MANIFEST_INVALID")
    secret_files = {}
    service_secret_files = {}
    target_username = execution_secret_lease.target_username_for_run(journal.root, journal.run_id)
    pki_requirements = [item for item in secret_requirements if isinstance(item, dict) and item.get("purpose") == "PKI_STORE_PASSWORD"]
    if pki_requirements:
        requirement = pki_requirements[0] if len(pki_requirements) == 1 else None
        if (not isinstance(requirement, dict) or
                set(requirement) != {"requirementRef", "purpose", "hosts", "runtimeReference"} or
                requirement.get("requirementRef") != "pki-store-password" or
                requirement.get("purpose") != "PKI_STORE_PASSWORD" or
                requirement.get("runtimeReference") != "runtime:pki-store-password" or
                not isinstance(requirement.get("hosts"), list)):
            raise LifecycleError("EXECUTION_MANIFEST_INVALID")
        password = execution_secret_lease.pki_store_password_for_run(journal.root, journal.run_id)
        path = os.path.join(journal.directory, ".pki-store-password")
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            os.write(descriptor, password.encode("utf-8")); os.fsync(descriptor)
        finally:
            os.close(descriptor)
        secret_files["runtime:pki-store-password"] = path
    service_requirements = [item for item in secret_requirements if isinstance(item, dict) and item.get("purpose") == "SERVICE_PASSWORD"]
    if service_requirements:
        values = execution_secret_lease.runtime_secret_values_for_run(journal.root, journal.run_id)
        for requirement in service_requirements:
            if set(requirement) != {"requirementRef", "purpose", "hosts", "runtimeReference", "serviceDeployment"}:
                raise LifecycleError("EXECUTION_MANIFEST_INVALID")
            deployment, reference = requirement.get("serviceDeployment"), requirement.get("runtimeReference")
            if not isinstance(deployment, str) or not isinstance(reference, str) or reference not in values:
                raise LifecycleError("EXECUTION_MANIFEST_INVALID")
            path = os.path.join(journal.directory, ".runtime-secret-" + hashlib.sha256((deployment + "\0" + reference).encode("utf-8")).hexdigest())
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            try:
                os.write(descriptor, values[reference].encode("utf-8")); os.fsync(descriptor)
            finally:
                os.close(descriptor)
            service_secret_files.setdefault(deployment, {})[reference] = path
    payload = {
        "apiVersion": "platform.installer/runtime-projection/v1alpha2",
        "platform_execution_run_id": metadata["runId"],
        "platform_execution_project_identity": metadata["projectIdentity"],
        "platform_execution_plan_fingerprint": metadata["planFingerprint"],
        "platform_execution_manifest_digest": metadata["manifestDigest"],
        "platform_execution_requirements_fingerprint": digest(requirements),
        "platform_project_id": metadata["projectIdentity"],
        "platform_project_root": os.path.join(journal.directory, "project"),
        "platform_project_manifest_path": os.path.join(journal.directory, "project", "project.yml"),
        "platform_generated_state_path": _generated_state_path(journal.root, metadata["projectIdentity"]),
        "platform_service_catalog_path": "/var/lib/platform-installer/runtime/current/catalog/service-catalog.yml",
        "platform_artifact_source_authorities_by_deployment": by_deployment,
        "platform_pki_materialization_plans": plans,
        "platform_pki_secret_files": secret_files,
    }
    if target_username is not None:
        payload["ansible_user"] = target_username
    descriptor, temporary = tempfile.mkstemp(prefix=".runtime-projection-", dir=journal.directory)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(payload, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            stream.flush(); os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, os.path.join(journal.directory, "runtime-projection.json"))
        for operation in operations:
            if not isinstance(operation, dict) or operation.get("operation") not in ("SERVICE_APPLY", "SERVICE_VERIFY"):
                continue
            prefix = operation.get("roleVariablesPrefix")
            deployment = operation.get("serviceDeployment")
            operation_id = operation.get("operationId")
            if not isinstance(prefix, str) or re.fullmatch(r"platform_[a-z0-9_]{1,96}_", prefix) is None or not isinstance(deployment, str) or not isinstance(operation_id, str):
                raise LifecycleError("EXECUTION_MANIFEST_INVALID")
            scoped = dict(payload)
            scoped[prefix + "secret_files"] = service_secret_files.get(deployment, {})
            destination = os.path.join(journal.directory, ".runtime-projection-" + hashlib.sha256(operation_id.encode("utf-8")).hexdigest() + ".json")
            descriptor, operation_temporary = tempfile.mkstemp(prefix=".runtime-projection-", dir=journal.directory)
            try:
                with os.fdopen(descriptor, "w") as stream:
                    json.dump(scoped, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":")); stream.flush(); os.fsync(stream.fileno())
                os.chmod(operation_temporary, 0o600); os.replace(operation_temporary, destination)
            finally:
                if os.path.exists(operation_temporary): os.unlink(operation_temporary)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _dispatch(release, journal, manifest, stopped):
    operations = manifest.get("operations")
    if not isinstance(operations, list) or not operations:
        raise LifecycleError("EXECUTION_MANIFEST_NOT_EXECUTABLE")
    identifiers = set()
    for operation in operations:
        if not isinstance(operation, dict) or not isinstance(operation.get("operationId"), str) or operation["operationId"] in identifiers:
            raise LifecycleError("EXECUTION_MANIFEST_INVALID")
        identifiers.add(operation["operationId"])
    commands = [(operation, _command(release, journal, operation)) for operation in operations]
    for operation, command in commands:
        if stopped[0]:
            return "CANCELLED"
        journal.event("ACTION_STARTED", "RUNNING", "Trusted operation started", phaseId=operation.get("phaseId"), actionId=operation["operationId"], serviceDeployment=operation.get("serviceDeployment"))
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=_environment(release, journal, operation))
        completed = _wait_for_operation(process, stopped)
        if completed is None:
            return "CANCELLED"
        returncode, error_code = completed
        journal.emit_task_observability_diagnostic(phaseId=operation.get("phaseId"), actionId=operation["operationId"], serviceDeployment=operation.get("serviceDeployment"))
        if returncode:
            journal.emit_operation_failure_diagnostic(error_code, phaseId=operation.get("phaseId"), actionId=operation["operationId"], serviceDeployment=operation.get("serviceDeployment"))
            raise LifecycleError("EXECUTION_OPERATION_FAILED")
        journal.event("ACTION_COMPLETED", "SUCCESS", "Trusted operation completed", phaseId=operation.get("phaseId"), actionId=operation["operationId"], serviceDeployment=operation.get("serviceDeployment"))
    return "SUCCEEDED"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--runtime-release", required=True)
    parser.add_argument("--bundle-digest", required=True)
    args = parser.parse_args()
    journal = Journal(args.state_root, args.run_id)
    lock = journal.lock()
    try:
        metadata = journal.metadata()
        manifest_path = os.path.join(journal.directory, "manifest.json")
        with open(manifest_path, "r", encoding="utf-8") as stream:
            manifest = json.load(stream)
        if metadata.get("manifestDigest") != digest(manifest):
            return _terminal(journal, "FAILED", "EXECUTION_MANIFEST_TAMPERED", "Private execution manifest digest does not match") and 2
        if manifest.get("projectIdentity") != metadata.get("projectIdentity") or manifest.get("planFingerprint") != metadata.get("planFingerprint") or manifest.get("runtimeRelease", {}).get("bundleDigest") != args.bundle_digest or metadata.get("runtimeRelease") != args.bundle_digest:
            return _terminal(journal, "FAILED", "EXECUTION_IDENTITY_MISMATCH", "Manifest identity does not match run ownership") and 2
        if not os.path.isdir(args.runtime_release) or os.path.islink(args.runtime_release):
            return _terminal(journal, "FAILED", "EXECUTION_RUNTIME_RELEASE_MISMATCH", "Immutable runtime release is unavailable") and 2
        _materialize_runtime_projection(journal, metadata, manifest)
        _validate_runtime_projection(journal, metadata, manifest)
        journal.transition("RUNNING", "Fixed Core controller started")
    finally:
        os.close(lock)
    cancelled = [False]
    def stop(_signal, _frame):
        cancelled[0] = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    journal.event("RUN_STARTED", "RUNNING", "Execution controller is running", planFingerprint=metadata["planFingerprint"])
    if cancelled[0]:
        _terminal(journal, "CANCELLED", "EXECUTION_CANCELLED", "Cancellation requested")
        return 0
    try:
        terminal = _dispatch(args.runtime_release, journal, manifest, cancelled)
        if terminal == "CANCELLED":
            _terminal(journal, "CANCELLED", "EXECUTION_CANCELLED", "Cancellation requested")
        else:
            _terminal(journal, "SUCCEEDED", "", "Execution controller completed")
        retain(args.state_root)
        return 0
    except LifecycleError as error:
        _terminal(journal, "FAILED", str(error), "Trusted operation failed before completion")
        retain(args.state_root)
        return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, LifecycleError) as error:
        print("EXECUTION_CONTROLLER_FAILED: %s" % error, file=sys.stderr)
        raise SystemExit(2)

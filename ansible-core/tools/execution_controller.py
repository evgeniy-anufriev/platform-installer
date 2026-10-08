#!/usr/bin/env python3
"""Fixed Execution Node controller.  It never accepts a command or playbook."""
from __future__ import print_function

import argparse
import errno
import fcntl
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
import execution_secret_output
import execution_target_trust


SERVICE_TYPES = frozenset(("kafka", "keepalived", "postgresql", "bind", "haproxy", "dns-client", "redis", "vault", "clickhouse", "docker"))
PROJECT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,127}$")
MAX_GENERATED_STATE_BYTES = 1024 * 1024
MAX_PKI_MATERIALIZATION_PLANS = 4096
MAX_PKI_PLAN_STRING_BYTES = 4096
MAX_OPERATION_FAILURE_CAPTURE_BYTES = 32768
MAX_ROLE_VARIABLE_HOSTS = 4096
MAX_ROLE_VARIABLES_PER_HOST = 256
MAX_ROLE_VARIABLE_BYTES = 65536
OPERATION_ERROR_CODE = re.compile(br'(?:"error_code"\s*:\s*"|error_code\s*[=:]\s*)([A-Z][A-Z0-9_]{2,127})')
_PKI_PLAN_FIELDS = frozenset(("id", "requestId", "tlsProfileId", "authorityId", "hostId", "targetDirectory", "formats", "keyAlias", "trustAlias", "storePasswordSecretRef", "materializationFingerprint"))
_PKI_PLAN_FORMATS = ("PEM", "PKCS12_KEYSTORE", "PKCS12_TRUSTSTORE")


def _safe_pki_plan_string(value):
    return isinstance(value, str) and 0 < len(value.encode("utf-8")) <= MAX_PKI_PLAN_STRING_BYTES and not any(ord(character) < 32 for character in value)


def _operation_error_code(output):
    """Return a machine token or a coarse fixed diagnostic, never raw output.

    Classification is diagnostic only, not a service rule or retry decision.
    Inspect only the final ordinary Ansible failure record, not earlier task
    output. Censored/no_log results remain opaque.
    """
    output = output[-MAX_OPERATION_FAILURE_CAPTURE_BYTES:] if isinstance(output, bytes) else b""
    matches = OPERATION_ERROR_CODE.findall(output)
    if matches:
        return matches[-1].decode("ascii")
    failures = re.findall(br'^fatal: \[[^\r\n]+\]: (?:FAILED|UNREACHABLE)! => ([^\r\n]*)', output, re.MULTILINE)
    if not failures:
        return ""
    try:
        result = json.loads(failures[-1])
    except (ValueError, UnicodeError):
        return "ANSIBLE_FAILURE_UNCLASSIFIED"
    if not isinstance(result, dict):
        return "ANSIBLE_FAILURE_UNCLASSIFIED"
    if result.get("_ansible_no_log") or "censored" in result:
        return "ANSIBLE_FAILURE_REDACTED"
    message = result.get("msg")
    if not isinstance(message, str):
        return "ANSIBLE_FAILURE_UNCLASSIFIED"
    message = message.lower()
    for code, phrases in (
        ("ANSIBLE_BECOME_TIMEOUT", ("timeout waiting for privilege escalation prompt",)),
        ("ANSIBLE_BECOME_FAILED", ("missing sudo password", "incorrect sudo password", "sudo: a password is required")),
        ("ANSIBLE_SSH_AUTH_FAILED", ("permission denied (publickey", "permission denied (password")),
        ("ANSIBLE_CONNECTION_TIMEOUT", ("connection timed out", "connection timeout")),
        ("ANSIBLE_CONNECTION_LOST", ("connection reset by peer", "connection closed by remote host", "broken pipe")),
        ("ANSIBLE_FILESYSTEM_READ_ONLY", ("read-only file system",)),
        ("ANSIBLE_FILESYSTEM_FULL", ("no space left on device",)),
        ("ANSIBLE_PERMISSION_DENIED", ("permission denied", "operation not permitted")),
    ):
        if any(phrase in message for phrase in phrases):
            return code
    return "ANSIBLE_FAILURE_UNCLASSIFIED"


def _wait_for_operation(process, stopped):
    """Drain child output without persisting it or allowing an output flood.

    The retained rolling window exists only in memory and is reduced to a
    machine error token or fixed coarse failure class before it reaches the
    journal. Raw Ansible messages never cross that boundary.
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


_DIAGNOSTIC_CODE = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")


def _preparation_diagnostic_code(error):
    """Return a safe machine token without exposing exception text or paths."""
    if isinstance(error, (LifecycleError, execution_secret_output.OutputWireError)):
        code = str(error)
        return code if _DIAGNOSTIC_CODE.fullmatch(code) else "EXECUTION_CONTROLLER_PREPARATION_UNCLASSIFIED"
    if isinstance(error, OSError):
        return "EXECUTION_CONTROLLER_PREPARATION_" + errno.errorcode.get(error.errno, "OS_ERROR")
    if isinstance(error, ValueError):
        return "EXECUTION_CONTROLLER_PREPARATION_VALUE_ERROR"
    return "EXECUTION_CONTROLLER_PREPARATION_INTERNAL_ERROR"


def _terminal(journal, state, code, summary):
    result = journal.terminal(state, code, summary)
    # Lease cleanup is private node maintenance; it never changes the already
    # authoritative terminal execution outcome or emits credential diagnostics.
    secret = os.path.join(journal.directory, ".pki-store-password")
    if os.path.lexists(secret):
        details = os.lstat(secret)
        if not os.path.islink(secret) and os.path.isfile(secret):
            os.unlink(secret)
    journal.cleanup_runtime_connection_credentials()
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


def _service_targets(operation):
    """Admit only exact Core-selected inventory host IDs to Ansible --limit."""
    targets = operation.get("targets")
    if (not isinstance(targets, list) or not 1 <= len(targets) <= 256 or
            any(not isinstance(host, str) or re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", host) is None or
                host in ("all", "localhost") for host in targets)):
        raise LifecycleError("EXECUTION_MANIFEST_INVALID")
    if targets != sorted(set(targets)):
        raise LifecycleError("EXECUTION_MANIFEST_INVALID")
    role_variables = _role_variables_by_host(operation)
    if role_variables is not None and set(role_variables) != set(targets):
        raise LifecycleError("EXECUTION_MANIFEST_INVALID")
    return targets


def _role_variables_by_host(operation):
    """Validate the closed Core-derived role-variable projection.

    The controller transports this digest-bound data only.  It never resolves
    settings or interprets service-specific names.
    """
    values = operation.get("roleVariablesByHost")
    if values is None:
        return None
    prefix = operation.get("roleVariablesPrefix")
    if not isinstance(prefix, str) or re.fullmatch(r"platform_[a-z0-9_]{1,96}_", prefix) is None or not isinstance(values, dict) or not values or len(values) > MAX_ROLE_VARIABLE_HOSTS:
        raise LifecycleError("EXECUTION_MANIFEST_INVALID")
    result = {}
    for host, variables in values.items():
        if not isinstance(host, str) or not host or not isinstance(variables, dict) or not variables or len(variables) > MAX_ROLE_VARIABLES_PER_HOST:
            raise LifecycleError("EXECUTION_MANIFEST_INVALID")
        if any(not isinstance(name, str) or not name.startswith(prefix) for name in variables):
            raise LifecycleError("EXECUTION_MANIFEST_INVALID")
        try:
            encoded = json.dumps(variables, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError):
            raise LifecycleError("EXECUTION_MANIFEST_INVALID")
        if len(encoded) > MAX_ROLE_VARIABLE_BYTES:
            raise LifecycleError("EXECUTION_MANIFEST_INVALID")
        result[host] = variables
    return result


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


def _acquire_project_pki_apply_lock(journal):
    """Acquire a crash-released, project-scoped lock for the complete PKI apply.

    The lock is held by the fixed controller while its one pki-apply playbook
    performs both materialization and target deployment. It lives beside the
    controller-owned generated state, never in the portable project or a
    run-specific workspace.
    """
    metadata = journal.metadata()
    project_identity = metadata.get("projectIdentity") if isinstance(metadata, dict) else None
    generated_state = _generated_state_path(journal.root, project_identity)
    project_dir = os.path.dirname(os.path.dirname(generated_state))
    lock_path = os.path.join(project_dir, ".pki-apply.lock")
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError:
        raise LifecycleError("PKI_APPLY_LOCK_UNAVAILABLE")
    try:
        details = os.fstat(descriptor)
        if (not stat.S_ISREG(details.st_mode) or details.st_uid != os.geteuid()):
            raise LifecycleError("PKI_APPLY_LOCK_UNSAFE")
        os.fchmod(descriptor, 0o600)
        details = os.fstat(descriptor)
        if stat.S_IMODE(details.st_mode) != 0o600:
            raise LifecycleError("PKI_APPLY_LOCK_UNSAFE")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise LifecycleError("PKI_APPLY_ALREADY_RUNNING")
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _command(release, journal, operation):
    kind = operation.get("operation")
    if kind in ("PKI_APPLY", "PKI_REISSUE"):
        projection = os.path.join(journal.directory, "runtime-projection.json")
        if not os.path.isfile(projection) or os.path.islink(projection):
            raise LifecycleError("EXECUTION_RUNTIME_PROJECTION_MISSING")
        command = ["ansible-playbook", "-i", os.path.join(journal.directory, "project", "inventory", "hosts.yml"), os.path.join(release, "ansible-core", "playbooks", "pki-reissue.yml" if kind == "PKI_REISSUE" else "pki-apply.yml"), "-e", "@" + projection]
        if kind == "PKI_REISSUE":
            selected = operation.get("reissueRequests")
            if (operation.get("operationId") != "pki:reissue" or not isinstance(selected, list) or
                    not selected or len(selected) > 256 or any(not isinstance(item, dict) or not isinstance(item.get("requestId"), str) for item in selected)):
                raise LifecycleError("EXECUTION_MANIFEST_INVALID")
            command.extend(["-e", json.dumps({"platform_pki_reissue_request_ids": [item["requestId"] for item in selected]}, separators=(",", ":"))])
        return command
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
        targets = _service_targets(operation)
        command = ["ansible-playbook", "-i", os.path.join(journal.directory, "project", "inventory", "hosts.yml"), os.path.join(release, "services", operation["serviceType"], "playbooks", action + ".yml"), "-e", "@" + projection]
        command.extend(["--limit", "localhost:" + ":".join(targets)])
        command.extend(["-e", "platform_execution_service_deployment=" + deployment])
        if operation.get("requiresArtifactSources") is True:
            command.extend(["-e", "platform_artifact_source_authority_active=true"])
        return command
    if kind == "CORE_DELAY" and operation.get("operationId") == "core:delay":
        # A Core-owned, bounded safe fixture used only to prove detached unit
        # and process-group semantics; it is not supplied by a client.
        return [sys.executable, "-c", "import time; time.sleep(8)"]
    raise LifecycleError("EXECUTION_OPERATION_UNKNOWN")


def _environment(release, journal=None, operation=None, leased_private_key=False):
    collections = [os.path.join(release, "ansible-core", "collections")]
    service_root = os.path.join(release, "services")
    if os.path.isdir(service_root):
        collections.extend(os.path.join(service_root, name, "ansible_collections") for name in sorted(os.listdir(service_root)) if os.path.isdir(os.path.join(service_root, name, "ansible_collections")))
    environment = dict(os.environ)
    environment.pop("ANSIBLE_PRIVATE_KEY_FILE", None)
    for inherited in ("ANSIBLE_SSH_ARGS", "ANSIBLE_SSH_COMMON_ARGS", "ANSIBLE_SSH_EXTRA_ARGS",
                      "ANSIBLE_SSH_EXECUTABLE", "ANSIBLE_HOST_KEY_CHECKING", "ANSIBLE_SSH_HOST_KEY_CHECKING"):
        environment.pop(inherited, None)
    for inherited in ("ANSIBLE_CALLBACK_PLUGINS", "ANSIBLE_CALLBACK_WHITELIST", "ANSIBLE_CALLBACKS_ENABLED", "ANSIBLE_LOAD_CALLBACK_PLUGINS", "ANSIBLE_STDOUT_CALLBACK", "ANSIBLE_SKIP_TAGS", "ANSIBLE_RUN_TAGS"):
        environment.pop(inherited, None)
    trust_file = os.path.join(journal.directory, "known_hosts") if journal is not None else os.path.join(EXECUTION_STATE_ROOT, "known_hosts")
    ssh_args = ("-F none -o UserKnownHostsFile=%s -o GlobalKnownHostsFile=none -o KnownHostsCommand=none -o UpdateHostKeys=no -o StrictHostKeyChecking=yes -o IdentitiesOnly=yes" % trust_file)
    if not leased_private_key:
        ssh_args = "-o IdentityFile=%s/identities/default/id_ed25519 %s" % (EXECUTION_STATE_ROOT, ssh_args)
    environment.update(
        ANSIBLE_CONFIG=os.path.join(release, "ansible-core", "ansible.cfg"),
        ANSIBLE_COLLECTIONS_PATH=os.pathsep.join(collections),
        ANSIBLE_SSH_ARGS=ssh_args,
        ANSIBLE_HOST_KEY_CHECKING="True")
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


def _secret_output_declarations(manifest):
    values = manifest.get("runtimeSecretOutputs", [])
    if not isinstance(values, list) or len(values) > 64:
        raise LifecycleError("EXECUTION_MANIFEST_INVALID")
    applies = {item.get("serviceDeployment") for item in manifest.get("operations", [])
               if isinstance(item, dict) and item.get("operation") == "SERVICE_APPLY"}
    seen = set()
    for item in values:
        if (not isinstance(item, dict) or set(item) != {"protocol", "serviceDeployment", "entries"} or
                item.get("protocol") != "SecretOutputDelivery/v1alpha1" or
                not isinstance(item.get("serviceDeployment"), str) or
                item["serviceDeployment"] not in applies or item["serviceDeployment"] in seen or
                item.get("entries") != ["admin-token", "unseal-shares"]):
            raise LifecycleError("EXECUTION_MANIFEST_INVALID")
        seen.add(item["serviceDeployment"])
    return values


def _output_schema_validator(runtime_release):
    bundle_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    module_utils = os.path.join(bundle_root, "ansible-core", "collections", "ansible_collections", "platform", "core", "plugins", "module_utils")
    if module_utils not in sys.path:
        sys.path.insert(0, module_utils)
    from schema_validation import SchemaValidator
    bundle_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    schema_root = os.path.join(bundle_root, "contracts", "secret-output-delivery", "v1alpha1")
    schema_path = os.path.join(schema_root, "metadata.schema.json")
    if not os.path.isfile(schema_path):
        raise LifecycleError("SECRET_OUTPUT_CONTRACT_UNAVAILABLE")
    return SchemaValidator(schema_root), schema_path


def _capture_secret_outputs(journal, manifest, runtime_release):
    declarations = _secret_output_declarations(manifest)
    if not declarations:
        return []
    validator, schema_path = _output_schema_validator(runtime_release)
    project_root = os.path.join(journal.directory, "project")
    metadata = journal.metadata()
    published = []
    for declaration in declarations:
        package = execution_secret_output.publish_retained_outputs(
            journal.root, journal.directory, metadata["projectIdentity"],
            declaration["serviceDeployment"], journal.run_id,
            metadata["runtimeRelease"], validator, schema_path)
        if package is not None:
            published.append((package, journal.run_id))
    return published


def _complete_secret_outputs(journal, manifest, result):
    declarations = _secret_output_declarations(manifest)
    if not declarations:
        return
    terminal_digest = digest(result)
    metadata = journal.metadata()
    validator, schema_path = _output_schema_validator(None)
    for declaration in declarations:
        try:
            execution_secret_output.complete_retained_outputs(
                journal.root, journal.directory, metadata["projectIdentity"],
                declaration["serviceDeployment"], journal.run_id, metadata["runtimeRelease"],
                result["state"], terminal_digest, validator, schema_path)
        except execution_secret_output.OutputWireError:
            # Keep the terminal result authoritative; retention sees the
            # missing completion record and preserves this journal for recovery.
            continue


def _finish_run_with_outputs(journal, state, code, summary, manifest, runtime_release):
    try:
        _capture_secret_outputs(journal, manifest, runtime_release)
    except (LifecycleError, execution_secret_output.OutputWireError, OSError, ValueError):
        # Delivery is a separate observation from the authoritative run result.
        # Preserve the run workspace for recovery instead of deleting the only
        # remaining copy of a potentially generated bootstrap output.
        try:
            journal.event("DIAGNOSTIC", "RUNNING", "Generated secret output is not yet durably available")
        except (LifecycleError, OSError, ValueError):
            pass
    result = _terminal(journal, state, code, summary)
    _complete_secret_outputs(journal, manifest, result)
    return result


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
            deployment, reference, requirement_ref = requirement.get("serviceDeployment"), requirement.get("runtimeReference"), requirement.get("requirementRef")
            # The v1alpha3 lease payload is keyed by the public requirement
            # reference. The runtime reference is a separate private-manifest
            # identity consumed by the role projection, never a payload key.
            if (not isinstance(deployment, str) or not isinstance(reference, str) or
                    not isinstance(requirement_ref, str) or requirement_ref not in values):
                raise LifecycleError("EXECUTION_MANIFEST_INVALID")
            path = os.path.join(journal.directory, ".runtime-secret-" + hashlib.sha256((deployment + "\0" + reference).encode("utf-8")).hexdigest())
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            try:
                os.write(descriptor, values[requirement_ref].encode("utf-8")); os.fsync(descriptor)
            finally:
                os.close(descriptor)
            service_secret_files.setdefault(deployment, {})[reference] = path
    output_directories = {}
    for declaration in _secret_output_declarations(manifest):
        deployment = declaration["serviceDeployment"]
        output_directories[deployment] = execution_secret_output.prepare_retained_output_directory(
            journal.root, journal.directory, metadata["projectIdentity"], deployment, journal.run_id, metadata["runtimeRelease"])
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
            if deployment in output_directories:
                scoped[prefix + "bootstrap_output_dir"] = output_directories[deployment]
            role_variables = _role_variables_by_host(operation)
            if role_variables is not None:
                scoped["platform_execution_role_variables_by_host"] = role_variables
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
    pki_applied_in_run = False
    for operation, command in commands:
        if stopped[0]:
            return "CANCELLED"
        if operation.get("operation") in ("PKI_REISSUE", "PKI_APPLY", "SERVICE_APPLY", "SERVICE_VERIFY"):
            execution_target_trust.verify(journal.root, journal.run_id, manifest)
        if pki_applied_in_run and operation.get("operation") == "SERVICE_APPLY":
            command = command + ["--skip-tags", "platform_installer_pki_materialization"]
        pki_lock_descriptor = (_acquire_project_pki_apply_lock(journal)
                               if operation.get("operation") in ("PKI_REISSUE", "PKI_APPLY") else None)
        credentials_path = None
        secret_inputs_path = None
        try:
            if operation.get("operation") == "PKI_REISSUE":
                bundle_root = release if os.path.isdir(os.path.join(release, "ansible-core")) else os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                module_utils = os.path.join(bundle_root, "ansible-core", "collections", "ansible_collections", "platform", "core", "plugins", "module_utils")
                if module_utils not in sys.path:
                    sys.path.insert(0, module_utils)
                from pki_reissue_state import assert_reissue_unchanged
                try:
                    assert_reissue_unchanged(journal.root, journal.metadata()["projectIdentity"], operation["reissueRequests"])
                except ValueError as error:
                    raise LifecycleError(str(error)) from None
            journal.event("ACTION_STARTED", "RUNNING", "Trusted operation started", phaseId=operation.get("phaseId"), actionId=operation["operationId"], serviceDeployment=operation.get("serviceDeployment"))
            credentials = execution_secret_lease.ansible_connection_credentials_for_run(journal.root, journal.run_id)
            if credentials is not None:
                credentials_path = os.path.join(journal.directory, ".ansible-runtime-credentials.json")
                descriptor = os.open(credentials_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                try:
                    with os.fdopen(descriptor, "w") as stream:
                        json.dump(credentials, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
                        stream.flush(); os.fsync(stream.fileno())
                except Exception:
                    try: os.unlink(credentials_path)
                    except OSError: pass
                    raise
                command = [sys.executable, os.path.join(release, "ansible-core", "tools", "run_with_runtime_credentials.py"), "--credentials-file", credentials_path, "--runtime-dir", os.path.join(journal.directory, ".ansible-runtime"), "--"] + command
            deployment = operation.get("serviceDeployment")
            typed_requirements = manifest.get("runtimeSecretInputs", [])
            if (isinstance(deployment, str) and operation.get("operation") in ("SERVICE_APPLY", "SERVICE_VERIFY")
                    and typed_requirements):
                secret_inputs = execution_secret_lease.runtime_secret_inputs_for_operation(
                    journal.root, journal.run_id, deployment, operation["operation"],
                    typed_requirements)
                if secret_inputs:
                    secret_inputs_path = os.path.join(journal.directory, ".runtime-secret-inputs-" + hashlib.sha256(operation["operationId"].encode("utf-8")).hexdigest() + ".json")
                    secret_descriptor = os.open(secret_inputs_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                    try:
                        with os.fdopen(secret_descriptor, "w", encoding="utf-8") as stream:
                            json.dump({"platform_runtime_secret_inputs": secret_inputs}, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
                            stream.flush(); os.fsync(stream.fileno())
                    except Exception:
                        try: os.unlink(secret_inputs_path)
                        except OSError: pass
                        raise
                    command.extend(["-e", "@" + secret_inputs_path])
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       env=_environment(release, journal, operation, leased_private_key=bool(credentials and "privateKey" in credentials)))
            completed = _wait_for_operation(process, stopped)
        finally:
            for temporary_path in (credentials_path, secret_inputs_path):
                if temporary_path is not None and os.path.lexists(temporary_path):
                    details = os.lstat(temporary_path)
                    if not stat.S_ISLNK(details.st_mode) and stat.S_ISREG(details.st_mode):
                        os.unlink(temporary_path)
            if pki_lock_descriptor is not None:
                os.close(pki_lock_descriptor)
        if completed is None:
            return "CANCELLED"
        returncode, error_code = completed
        journal.emit_task_observability_diagnostic(phaseId=operation.get("phaseId"), actionId=operation["operationId"], serviceDeployment=operation.get("serviceDeployment"))
        if returncode:
            journal.emit_operation_failure_diagnostic(error_code, phaseId=operation.get("phaseId"), actionId=operation["operationId"], serviceDeployment=operation.get("serviceDeployment"))
            raise LifecycleError("EXECUTION_OPERATION_FAILED")
        journal.event("ACTION_COMPLETED", "SUCCESS", "Trusted operation completed", phaseId=operation.get("phaseId"), actionId=operation["operationId"], serviceDeployment=operation.get("serviceDeployment"))
        if operation.get("operation") == "PKI_APPLY":
            pki_applied_in_run = True
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
        _secret_output_declarations(manifest)
        if execution_target_trust.required(manifest):
            execution_target_trust.verify(args.state_root, args.run_id, manifest)
        if not os.path.isdir(args.runtime_release) or os.path.islink(args.runtime_release):
            return _terminal(journal, "FAILED", "EXECUTION_RUNTIME_RELEASE_MISMATCH", "Immutable runtime release is unavailable") and 2
        try:
            _materialize_runtime_projection(journal, metadata, manifest)
            _validate_runtime_projection(journal, metadata, manifest)
            journal.transition("RUNNING", "Fixed Core controller started")
        except (LifecycleError, execution_secret_output.OutputWireError, OSError, ValueError) as error:
            # Identity was verified above and Start is already durable.
            _terminal(journal, "FAILED", "EXECUTION_CONTROLLER_PREPARATION_FAILED",
                      "Controller preparation failed before execution (diagnostic: %s)" %
                      _preparation_diagnostic_code(error))
            return 2
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
            _finish_run_with_outputs(journal, "CANCELLED", "EXECUTION_CANCELLED", "Cancellation requested", manifest, args.runtime_release)
        else:
            _finish_run_with_outputs(journal, "SUCCEEDED", "", "Execution controller completed", manifest, args.runtime_release)
        retain(args.state_root)
        return 0
    except LifecycleError as error:
        _finish_run_with_outputs(journal, "FAILED", str(error), "Trusted operation failed before completion", manifest, args.runtime_release)
        retain(args.state_root)
        return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, LifecycleError) as error:
        print("EXECUTION_CONTROLLER_FAILED: %s" % error, file=sys.stderr)
        raise SystemExit(2)

"""Private, descriptor-bound bootstrap output storage on Linux Execution Nodes.

Only trusted controller calls publish. No request supplies a path or owner.
This foundation does not advertise a protocol or authorize ACK/cleanup yet.
"""
import contextlib
import fcntl
import json
import os
import re
import secrets
import stat
import hashlib

from secret_output_wire import encode_fetch, OutputWireError

_ID = re.compile(r"[0-9a-f]{32}\Z")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_PROJECT = re.compile(r"[a-z0-9][a-z0-9-]{0,127}\Z")
_DEPLOYMENT = re.compile(r"[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*\Z")
_RUN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


def _unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise OutputWireError("OUTPUT_RECOVERY_REQUIRED")
        value[key] = item
    return value


def _reservation(root, package_id):
    try:
        value = json.loads(_read(root, ".reservation-" + package_id + ".json", 2048).decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (OSError, ValueError, UnicodeError, TypeError):
        raise OutputWireError("OUTPUT_RECOVERY_REQUIRED") from None
    fields = {"projectId", "deploymentId", "sourceRunId", "packageId", "generation", "runtimeDigest"}
    if (not isinstance(value, dict) or set(value) != fields or value.get("packageId") != package_id or
            not isinstance(value.get("projectId"), str) or not _PROJECT.fullmatch(value["projectId"]) or
            not isinstance(value.get("deploymentId"), str) or len(value["deploymentId"]) > 128 or not _DEPLOYMENT.fullmatch(value["deploymentId"]) or
            not isinstance(value.get("sourceRunId"), str) or not _RUN.fullmatch(value["sourceRunId"]) or
            type(value.get("generation")) is not int or not 1 <= value["generation"] <= 2147483647 or
            not isinstance(value.get("runtimeDigest"), str) or not _DIGEST.fullmatch(value["runtimeDigest"])):
        raise OutputWireError("OUTPUT_RECOVERY_REQUIRED")
    return dict(value, protocol="SecretOutputDelivery/v1alpha1", state="RESERVED",
                entries=["admin-token", "unseal-shares"])


def _ensure_reservation(root, identity, runtime_digest):
    reservation = dict(identity, runtimeDigest=runtime_digest)
    try:
        _atomic_json(root, ".reservation-" + identity["packageId"] + ".json", reservation)
    except FileExistsError:
        existing = _reservation(root, identity["packageId"])
        if any(existing[key] != value for key, value in reservation.items()):
            raise OutputWireError("OUTPUT_IDENTITY_MISMATCH")


def _record(root, package_id, package):
    try:
        return _metadata(package)
    except FileNotFoundError:
        # Missing metadata is allowed ONLY with a valid immutable reservation.
        return _reservation(root, package_id)


def _package_names(root):
    names = set()
    for name in os.listdir(root):
        if _ID.fullmatch(name):
            names.add(name)
        elif name.startswith(".reservation-") and name.endswith(".json"):
            package_id = name[len(".reservation-"):-len(".json")]
            if _ID.fullmatch(package_id):
                names.add(package_id)
    if len(names) > 4096:
        raise OutputWireError("OUTPUT_RECOVERY_REQUIRED")
    return sorted(names)


def _material_present(package):
    return any(_entry_exists(package, name) for name in ("admin-token", "unseal-shares", "init-response.json"))


def _entry_exists(package, name):
    try:
        info = os.stat(name, dir_fd=package, follow_symlinks=False)
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077 or info.st_nlink != 1:
        raise OutputWireError("OUTPUT_ACCESS_DENIED")
    return True


def _empty_completed(package, metadata):
    try:
        record = json.loads(_read(package, "no-output.json", 2048).decode("utf-8"))
    except FileNotFoundError:
        return False
    return (record == {"packageId": metadata["packageId"], "generation": metadata["generation"],
                       "sourceRunId": metadata["sourceRunId"], "outcome": "NO_OUTPUT"} and
            not _material_present(package) and _completion_matches(package, metadata))


def _mark_recovery_required(package, package_id, generation, source_run_id):
    status = {"packageId": package_id, "generation": generation, "sourceRunId": source_run_id,
              "code": "OUTPUT_RECOVERY_REQUIRED"}
    try:
        _atomic_json(package, "recovery-status.json", status)
    except FileExistsError:
        if json.loads(_read(package, "recovery-status.json", 2048).decode("utf-8")) != status:
            raise OutputWireError("OUTPUT_IDENTITY_MISMATCH")


def _safe_object(fd, directory=False):
    details = os.fstat(fd)
    valid = stat.S_ISDIR(details.st_mode) if directory else stat.S_ISREG(details.st_mode)
    if not valid or details.st_uid != os.geteuid() or details.st_mode & 0o077:
        raise OutputWireError("OUTPUT_ACCESS_DENIED")
    if not directory and details.st_nlink != 1:
        raise OutputWireError("OUTPUT_ACCESS_DENIED")


@contextlib.contextmanager
def _directory(name, parent=None, create=False):
    if create:
        try:
            os.mkdir(name, 0o700, dir_fd=parent)
            if parent is not None:
                os.fsync(parent)
        except FileExistsError:
            pass
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
    try:
        _safe_object(fd, directory=True)
        yield fd
    finally:
        os.close(fd)


@contextlib.contextmanager
def _package(state_root, package_id, create=False, nonblocking=False):
    if not isinstance(package_id, str) or _ID.fullmatch(package_id) is None:
        raise OutputWireError("OUTPUT_REQUEST_INVALID")
    # state_root is an existing trusted execution root, never client input.
    with _directory(state_root) as state:
        with _directory("secret-outputs", state, create=create) as root:
            with _directory(package_id, root, create=create) as package:
                lock = os.open(".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                               0o600, dir_fd=package)
                try:
                    _safe_object(lock)
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0))
                    except BlockingIOError:
                        raise OutputWireError("OUTPUT_BUSY") from None
                    yield package
                finally:
                    os.close(lock)


def _read(package, name, bound, durable=False):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=package)
    try:
        _safe_object(fd)
        if os.fstat(fd).st_size > bound:
            raise OutputWireError("OUTPUT_TRANSFER_FAILED")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(bound + 1)
        if len(data) > bound:
            raise OutputWireError("OUTPUT_TRANSFER_FAILED")
        if durable:
            os.fsync(fd)
        return data
    finally:
        os.close(fd)


def _exclusive(package, name, data):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                 0o600, dir_fd=package)
    try:
        _safe_object(fd)
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(fd)
        os.fsync(package)
    finally:
        os.close(fd)


def _metadata(package):
    return json.loads(_read(package, "metadata.json", 8192).decode("utf-8"), object_pairs_hook=_unique_pairs)


def publish(state_root, metadata, token, shares, validator, schema_path):
    """Publish READY last, after both entries are durable; never overwrite.

    On failure, partial files intentionally remain protected and unadvertised.
    No pathname cleanup can destroy the last bootstrap material. Retry can
    finish identical partial entries; conflicting bytes/identity fail closed.
    """
    try:
        encode_fetch(metadata, token, shares, validator, schema_path)
        with _package(state_root, metadata["packageId"], create=True) as package:
            encoded = json.dumps(metadata, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
            try:
                _exclusive(package, ".binding.json", encoded)
            except FileExistsError:
                if _read(package, ".binding.json", 8192) != encoded:
                    raise OutputWireError("OUTPUT_IDENTITY_MISMATCH")
            try:
                existing = _metadata(package)
            except FileNotFoundError:
                existing = None
            if existing is not None and existing != metadata:
                raise OutputWireError("OUTPUT_IDENTITY_MISMATCH")
            for name, data, bound in (("admin-token", token, 4096), ("unseal-shares", shares, 32768)):
                try:
                    _exclusive(package, name, data)
                except FileExistsError:
                    if _read(package, name, bound, durable=True) != data:
                        raise OutputWireError("OUTPUT_IDENTITY_MISMATCH")
            if existing is None:
                _atomic_json(package, "metadata.json", metadata)
        return dict(metadata)
    except OutputWireError:
        raise
    except (OSError, ValueError, TypeError, KeyError):
        raise OutputWireError("OUTPUT_RECOVERY_REQUIRED") from None


@contextlib.contextmanager
def _deployment_lock(state_root, project_id, deployment_id):
    if not _PROJECT.fullmatch(project_id) or not _DEPLOYMENT.fullmatch(deployment_id):
        raise OutputWireError("OUTPUT_REQUEST_INVALID")
    key = hashlib.sha256((project_id + "\0" + deployment_id).encode("utf-8")).hexdigest()
    with _directory(state_root) as state:
        with _directory("secret-outputs", state, create=True) as root:
            with _directory(".deployment-locks", root, create=True) as locks:
                descriptor = os.open(key, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                                     0o600, dir_fd=locks)
                try:
                    _safe_object(descriptor)
                    fcntl.flock(descriptor, fcntl.LOCK_EX)
                    yield root
                finally:
                    os.close(descriptor)


def prepare_package_identity(state_root, journal_directory, project_id, deployment_id, source_run_id, runtime_digest=None):
    """Durably choose a random package ID and monotonic deployment generation."""
    if (not _PROJECT.fullmatch(project_id) or not _DEPLOYMENT.fullmatch(deployment_id) or
            not isinstance(source_run_id, str) or not _RUN.fullmatch(source_run_id) or
            (runtime_digest is not None and (not isinstance(runtime_digest, str) or not _DIGEST.fullmatch(runtime_digest)))):
        raise OutputWireError("OUTPUT_REQUEST_INVALID")
    binding_name = ".secret-output-identity-" + hashlib.sha256(deployment_id.encode("utf-8")).hexdigest() + ".json"
    with _deployment_lock(state_root, project_id, deployment_id) as output_root:
        journal = os.open(journal_directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            try:
                existing = json.loads(_read(journal, binding_name, 2048).decode("utf-8"))
            except FileNotFoundError:
                existing = None
            if existing is not None:
                if (not isinstance(existing, dict) or set(existing) != {"projectId", "deploymentId", "sourceRunId", "packageId", "generation"} or
                        existing.get("projectId") != project_id or existing.get("deploymentId") != deployment_id or
                        existing.get("sourceRunId") != source_run_id or not _ID.fullmatch(existing.get("packageId", "")) or
                        type(existing.get("generation")) is not int or not 1 <= existing["generation"] <= 2147483647):
                    raise OutputWireError("OUTPUT_RECOVERY_REQUIRED")
                if runtime_digest is not None:
                    _ensure_reservation(output_root, existing, runtime_digest)
                return existing["packageId"], existing["generation"]
            names = _package_names(output_root)
            generation = 0
            for name in names:
                try:
                    with _package(state_root, name, nonblocking=True) as package:
                        metadata = _record(output_root, name, package)
                        empty_completed = metadata.get("state") == "RESERVED" and _empty_completed(package, metadata)
                except FileNotFoundError:
                    metadata = _reservation(output_root, name)
                    empty_completed = False
                except OutputWireError as error:
                    if str(error) == "OUTPUT_BUSY":
                        raise
                    raise OutputWireError("OUTPUT_RECOVERY_REQUIRED") from None
                if metadata.get("projectId") != project_id or metadata.get("deploymentId") != deployment_id:
                    continue
                generation = max(generation, metadata.get("generation", 0))
                if metadata.get("state") == "RESERVED" and not empty_completed:
                    raise OutputWireError("OUTPUT_RECOVERY_REQUIRED")
                if metadata.get("state") in ("READY", "ACKED_CLEANUP_PENDING"):
                    raise OutputWireError("OUTPUT_BUSY")
            if generation >= 2147483647:
                raise OutputWireError("OUTPUT_RECOVERY_REQUIRED")
            identity = {"projectId": project_id, "deploymentId": deployment_id,
                        "sourceRunId": source_run_id, "packageId": secrets.token_hex(16),
                        "generation": generation + 1}
            encoded = json.dumps(identity, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
            temp = ".tmp-" + secrets.token_hex(16)
            _exclusive(journal, temp, encoded)
            os.link(temp, binding_name, src_dir_fd=journal, dst_dir_fd=journal, follow_symlinks=False)
            os.unlink(temp, dir_fd=journal)
            os.fsync(journal)
            if runtime_digest is not None:
                _ensure_reservation(output_root, identity, runtime_digest)
            return identity["packageId"], identity["generation"]
        finally:
            os.close(journal)


def load_package_identity(journal_directory, project_id, deployment_id, source_run_id):
    if not _DEPLOYMENT.fullmatch(deployment_id):
        raise OutputWireError("OUTPUT_REQUEST_INVALID")
    name = ".secret-output-identity-" + hashlib.sha256(deployment_id.encode("utf-8")).hexdigest() + ".json"
    try:
        with _directory(journal_directory) as journal:
            identity = json.loads(_read(journal, name, 2048).decode("utf-8"))
    except (OSError, ValueError, TypeError):
        raise OutputWireError("OUTPUT_NOT_FOUND") from None
    if (not isinstance(identity, dict) or set(identity) != {"projectId", "deploymentId", "sourceRunId", "packageId", "generation"} or
            identity.get("projectId") != project_id or identity.get("deploymentId") != deployment_id or
            identity.get("sourceRunId") != source_run_id or not _ID.fullmatch(identity.get("packageId", "")) or
            type(identity.get("generation")) is not int or not 1 <= identity["generation"] <= 2147483647):
        raise OutputWireError("OUTPUT_RECOVERY_REQUIRED")
    return identity["packageId"], identity["generation"]


def _open_project_output(project_root, deployment_id):
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    project = os.open(project_root, flags)
    try:
        info = os.fstat(project)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
            raise OutputWireError("OUTPUT_ACCESS_DENIED")
        with _directory("secrets", project) as secrets_dir:
            with _directory(deployment_id, secrets_dir) as output_dir:
                present = []
                for name in ("admin-token", "unseal-shares"):
                    try:
                        item = os.stat(name, dir_fd=output_dir, follow_symlinks=False)
                        present.append(True)
                        if not stat.S_ISREG(item.st_mode):
                            raise OutputWireError("OUTPUT_ACCESS_DENIED")
                    except FileNotFoundError:
                        present.append(False)
                if not any(present):
                    return None
                if not all(present):
                    raise OutputWireError("OUTPUT_RECOVERY_REQUIRED")
                token = _read(output_dir, "admin-token", 4096)
                shares = _read(output_dir, "unseal-shares", 32768)
                return token, shares
    finally:
        os.close(project)


def publish_project_outputs(state_root, project_root, project_id, deployment_id,
                            source_run_id, runtime_digest, journal_directory, validator, schema_path):
    """Capture the fixed project/deployment output convention, if complete.

    Missing output directory or both entries means this run generated no output.
    A partial pair is a recovery error and is never advertised as READY.
    """
    try:
        try:
            captured = _open_project_output(project_root, deployment_id)
        except FileNotFoundError:
            return None
        if captured is None:
            return None
        package, generation = prepare_package_identity(
            state_root, journal_directory, project_id, deployment_id, source_run_id)
        token, shares = captured
        metadata = {
            "protocol": "SecretOutputDelivery/v1alpha1", "packageId": package,
            "projectId": project_id, "deploymentId": deployment_id,
            "sourceRunId": source_run_id, "runtimeDigest": runtime_digest,
            "generation": generation, "state": "READY",
            "entries": ["admin-token", "unseal-shares"],
        }
        publish(state_root, metadata, token, shares, validator, schema_path)
        return package
    except OutputWireError:
        raise
    except (OSError, ValueError, TypeError):
        raise OutputWireError("OUTPUT_RECOVERY_REQUIRED") from None


def prepare_retained_output_directory(state_root, journal_directory, project_id, deployment_id, source_run_id, runtime_digest):
    """One protected custody directory for role Apply, Verify and delivery."""
    if not isinstance(runtime_digest, str) or not _DIGEST.fullmatch(runtime_digest):
        raise OutputWireError("OUTPUT_REQUEST_INVALID")
    # Reserve under the existing deployment lock BEFORE directory visibility.
    package_id, generation = prepare_package_identity(
        state_root, journal_directory, project_id, deployment_id, source_run_id, runtime_digest)
    with _package(state_root, package_id, create=True):
        pass
    return os.path.join(state_root, "secret-outputs", package_id)


def publish_retained_outputs(state_root, journal_directory, project_id, deployment_id,
                             source_run_id, runtime_digest, validator, schema_path):
    package_id, generation = load_package_identity(
        journal_directory, project_id, deployment_id, source_run_id)
    with _package(state_root, package_id) as package:
        try:
            token = _read(package, "admin-token", 4096)
            shares = _read(package, "unseal-shares", 32768)
        except FileNotFoundError:
            return None
    metadata = {"protocol": "SecretOutputDelivery/v1alpha1", "packageId": package_id,
                "projectId": project_id, "deploymentId": deployment_id,
                "sourceRunId": source_run_id, "runtimeDigest": runtime_digest,
                "generation": generation, "state": "READY",
                "entries": ["admin-token", "unseal-shares"]}
    publish(state_root, metadata, token, shares, validator, schema_path)
    return package_id


def complete_retained_outputs(state_root, journal_directory, project_id, deployment_id,
                              source_run_id, runtime_digest, terminal_state, result_digest,
                              validator, schema_path):
    package_id, generation = load_package_identity(journal_directory, project_id, deployment_id, source_run_id)
    with _directory(state_root) as state:
        with _directory("secret-outputs", state) as root:
            # Existing published packages retain their state, including ACK.
            try:
                with _package(state_root, package_id) as package:
                    metadata = _record(root, package_id, package)
            except FileNotFoundError:
                metadata = _reservation(root, package_id)
            if metadata.get("projectId") != project_id or metadata.get("deploymentId") != deployment_id or metadata.get("runtimeDigest") != runtime_digest or metadata.get("sourceRunId") != source_run_id or metadata.get("generation") != generation:
                raise OutputWireError("OUTPUT_IDENTITY_MISMATCH")
    if metadata["state"] == "RESERVED":
        with _package(state_root, package_id, create=True) as package:
            # An ACK without metadata is corruption, never an empty reservation.
            if _entry_exists(package, "ack-receipt.json"):
                raise OutputWireError("OUTPUT_RECOVERY_REQUIRED")
            complete = _entry_exists(package, "admin-token") and _entry_exists(package, "unseal-shares")
            partial = _material_present(package)
            if partial and _entry_exists(package, "no-output.json"):
                raise OutputWireError("OUTPUT_RECOVERY_REQUIRED")
            if not complete and partial:
                _mark_recovery_required(package, package_id, generation, source_run_id)
                raise OutputWireError("OUTPUT_RECOVERY_REQUIRED")
            if not complete:
                outcome = {"packageId": package_id, "generation": generation, "sourceRunId": source_run_id,
                           "outcome": "NO_OUTPUT"}
                try:
                    _atomic_json(package, "no-output.json", outcome)
                except FileExistsError:
                    if json.loads(_read(package, "no-output.json", 2048).decode("utf-8")) != outcome:
                        raise OutputWireError("OUTPUT_RECOVERY_REQUIRED")
        if complete:
            try:
                publish_retained_outputs(state_root, journal_directory, project_id, deployment_id,
                                         source_run_id, runtime_digest, validator, schema_path)
            except (OutputWireError, OSError, ValueError, TypeError):
                with _package(state_root, package_id) as package:
                    _mark_recovery_required(package, package_id, generation, source_run_id)
                raise OutputWireError("OUTPUT_RECOVERY_REQUIRED") from None
    mark_producer_completed(state_root, package_id, source_run_id, terminal_state, result_digest)
    return package_id


def _atomic_json(package, name, value):
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    temporary = ".tmp-" + secrets.token_hex(16)
    _exclusive(package, temporary, encoded)
    # linkat is atomic and fails if the destination already exists; unlike
    # replace it cannot overwrite a substituted or foreign receipt.
    os.link(temporary, name, src_dir_fd=package, dst_dir_fd=package, follow_symlinks=False)
    os.unlink(temporary, dir_fd=package)
    os.fsync(package)


def mark_producer_completed(state_root, package_id_value, source_run_id,
                            terminal_state, terminal_result_digest):
    """Durably bind package retention to the already-published terminal result."""
    if (not isinstance(source_run_id, str) or not source_run_id or
            terminal_state not in ("SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED") or
            not isinstance(terminal_result_digest, str) or not _DIGEST.fullmatch(terminal_result_digest)):
        raise OutputWireError("OUTPUT_REQUEST_INVALID")
    try:
        with _package(state_root, package_id_value) as package:
            with _directory(state_root) as state:
                with _directory("secret-outputs", state) as root:
                    metadata = _record(root, package_id_value, package)
            if metadata.get("packageId") != package_id_value or metadata.get("sourceRunId") != source_run_id:
                raise OutputWireError("OUTPUT_IDENTITY_MISMATCH")
            evidence = {"packageId": package_id_value, "generation": metadata["generation"],
                        "sourceRunId": source_run_id, "terminalState": terminal_state,
                        "terminalResultDigest": terminal_result_digest, "producerReleased": True}
            try:
                existing = json.loads(_read(package, "producer-completion.json", 2048).decode("utf-8"))
            except FileNotFoundError:
                existing = None
            if existing is not None:
                if existing != evidence:
                    raise OutputWireError("OUTPUT_IDENTITY_MISMATCH")
                return evidence
            _atomic_json(package, "producer-completion.json", evidence)
            return evidence
    except OutputWireError:
        raise
    except (OSError, ValueError, TypeError, KeyError):
        raise OutputWireError("OUTPUT_RECOVERY_REQUIRED") from None


def producer_completed(state_root, package_id_value, source_run_id):
    """Return true only for exact durable producer-release evidence."""
    try:
        with _package(state_root, package_id_value) as package:
            with _directory(state_root) as state:
                with _directory("secret-outputs", state) as root:
                    metadata = _record(root, package_id_value, package)
            return (metadata.get("sourceRunId") == source_run_id and _completion_matches(package, metadata) and
                    (metadata.get("state") != "RESERVED" or _empty_completed(package, metadata)))
    except (OutputWireError, OSError, ValueError, TypeError, KeyError):
        return False


def _completion_matches(package, metadata):
    try:
        evidence = json.loads(_read(package, "producer-completion.json", 2048).decode("utf-8"))
    except (OSError, ValueError, UnicodeError):
        return False
    return (isinstance(evidence, dict) and set(evidence) == {
                "packageId", "generation", "sourceRunId", "terminalState",
                "terminalResultDigest", "producerReleased"} and
            evidence.get("packageId") == metadata.get("packageId") and
            evidence.get("generation") == metadata.get("generation") and
            evidence.get("sourceRunId") == metadata.get("sourceRunId") and
            evidence.get("terminalState") in ("SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED") and
            isinstance(evidence.get("terminalResultDigest"), str) and
            _DIGEST.fullmatch(evidence["terminalResultDigest"]) is not None and
            evidence.get("producerReleased") is True)


def _replace_metadata_state(package, metadata, state):
    updated = dict(metadata)
    updated["state"] = state
    temporary = ".metadata-" + secrets.token_hex(16)
    _exclusive(package, temporary, json.dumps(updated, ensure_ascii=True, sort_keys=True,
                                               separators=(",", ":")).encode("utf-8"))
    os.replace(temporary, "metadata.json", src_dir_fd=package, dst_dir_fd=package)
    os.fsync(package)
    return updated


def _remove_entry(package, name, bound):
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                             dir_fd=package)
    except FileNotFoundError:
        return
    try:
        _safe_object(descriptor)
        if os.fstat(descriptor).st_size > bound:
            raise OutputWireError("OUTPUT_CLEANUP_FAILED")
        os.unlink(name, dir_fd=package)
        os.fsync(package)
    finally:
        os.close(descriptor)


def list_pending(state_root, project_id, limit, cursor, validator, schema_path):
    if not isinstance(project_id, str) or type(limit) is not int or not 1 <= limit <= 32:
        raise OutputWireError("OUTPUT_REQUEST_INVALID")
    if cursor is not None and (not isinstance(cursor, str) or _ID.fullmatch(cursor) is None):
        raise OutputWireError("OUTPUT_REQUEST_INVALID")
    state = None
    try:
        try:
            state = os.open(state_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            root = os.open("secret-outputs", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                           dir_fd=state)
        except FileNotFoundError:
            response = {"protocol": "SecretOutputDelivery/v1alpha1", "operation": "ListPending",
                        "projectId": project_id, "packages": [], "nextCursor": None}
            if validator.validate(response, schema_path):
                raise OutputWireError("OUTPUT_RECOVERY_REQUIRED")
            return response
        try:
            _safe_object(root, directory=True)
            names = _package_names(root)
            after = [name for name in names if cursor is None or name > cursor]
            items = []
            for name in after:
                try:
                    with _package(state_root, name, nonblocking=True) as package:
                        metadata = _record(root, name, package)
                        if metadata.get("state") == "RESERVED":
                            if metadata.get("projectId") == project_id and _material_present(package):
                                raise OutputWireError("OUTPUT_RECOVERY_REQUIRED")
                            continue
                        if (metadata.get("packageId") == name and metadata.get("projectId") == project_id and
                                metadata.get("state") in ("READY", "ACKED_CLEANUP_PENDING")):
                            if validator.validate(metadata, os.path.join(os.path.dirname(schema_path), "metadata.schema.json")):
                                raise OutputWireError("OUTPUT_RECOVERY_REQUIRED")
                            if metadata.get("state") == "READY" and not _completion_matches(package, metadata):
                                continue
                            items.append(metadata)
                except FileNotFoundError:
                    _reservation(root, name)
                    continue
                except OutputWireError as error:
                    if str(error) == "OUTPUT_BUSY":
                        continue
                    raise
                if len(items) > limit:
                    break
            has_more = len(items) > limit
            selected = items[:limit]
            next_cursor = selected[-1]["packageId"] if has_more and selected else None
            response = {"protocol": "SecretOutputDelivery/v1alpha1", "operation": "ListPending",
                        "projectId": project_id, "packages": selected, "nextCursor": next_cursor}
            if validator.validate(response, schema_path):
                raise OutputWireError("OUTPUT_RECOVERY_REQUIRED")
            return response
        finally:
            os.close(root)
    except OutputWireError:
        raise
    except (OSError, ValueError, TypeError):
        raise OutputWireError("OUTPUT_RECOVERY_REQUIRED") from None
    finally:
        if state is not None:
            os.close(state)


def acknowledge(state_root, project_id, package_id_value, generation, receipt_id,
                ciphertext_digests):
    if (not isinstance(project_id, str) or type(generation) is not int or
            not isinstance(receipt_id, str) or _ID.fullmatch(receipt_id) is None or
            not isinstance(ciphertext_digests, dict) or set(ciphertext_digests) != {"admin-token", "unseal-shares"} or
            any(not isinstance(value, str) or not _DIGEST.fullmatch(value) for value in ciphertext_digests.values())):
        raise OutputWireError("OUTPUT_REQUEST_INVALID")
    try:
        with _package(state_root, package_id_value, nonblocking=True) as package:
            metadata = _metadata(package)
            if (metadata.get("packageId") != package_id_value or metadata.get("projectId") != project_id or
                    metadata.get("generation") != generation):
                raise OutputWireError("OUTPUT_IDENTITY_MISMATCH")
            if not _completion_matches(package, metadata):
                raise OutputWireError("OUTPUT_BUSY")
            receipt = {"packageId": package_id_value, "projectId": project_id,
                       "deploymentId": metadata["deploymentId"], "generation": generation,
                       "receiptId": receipt_id, "ciphertextDigests": dict(ciphertext_digests)}
            try:
                existing = json.loads(_read(package, "ack-receipt.json", 4096).decode("utf-8"))
            except FileNotFoundError:
                existing = None
            if existing is not None and existing != receipt:
                raise OutputWireError("OUTPUT_IDENTITY_MISMATCH")
            if existing is None:
                _atomic_json(package, "ack-receipt.json", receipt)
            if metadata.get("state") != "DELIVERED":
                try:
                    _remove_entry(package, "admin-token", 4096)
                    _remove_entry(package, "unseal-shares", 32768)
                    _remove_entry(package, "init-response.json", 65536)
                    metadata = _replace_metadata_state(package, metadata, "DELIVERED")
                except (OSError, OutputWireError):
                    metadata = _replace_metadata_state(package, metadata, "ACKED_CLEANUP_PENDING")
            return {"protocol": "SecretOutputDelivery/v1alpha1", "operation": "Acknowledge",
                    "projectId": project_id, "packageId": package_id_value,
                    "generation": generation, "receiptId": receipt_id,
                    "state": metadata["state"]}
    except OutputWireError:
        raise
    except (OSError, ValueError, TypeError, KeyError):
        raise OutputWireError("OUTPUT_RECOVERY_REQUIRED") from None


def fetch(state_root, package_id, project_id, generation, validator, schema_path):
    """Trusted runtime caller supplies authenticated owner context via euid.

    Directory/file ownership plus exact project/generation are all required.
    Returned bytes belong solely to the confidential transport, never logs.
    """
    try:
        if type(generation) is not int or not 1 <= generation <= 2147483647:
            raise OutputWireError("OUTPUT_REQUEST_INVALID")
        with _package(state_root, package_id) as package:
            metadata = _metadata(package)
            if metadata.get("packageId") != package_id or metadata.get("projectId") != project_id or metadata.get("generation") != generation:
                raise OutputWireError("OUTPUT_IDENTITY_MISMATCH")
            if not _completion_matches(package, metadata):
                raise OutputWireError("OUTPUT_BUSY")
            token = _read(package, "admin-token", 4096)
            shares = _read(package, "unseal-shares", 32768)
            return encode_fetch(metadata, token, shares, validator, schema_path)
    except OutputWireError:
        raise
    except (OSError, ValueError, TypeError, KeyError):
        raise OutputWireError("OUTPUT_TRANSFER_FAILED") from None

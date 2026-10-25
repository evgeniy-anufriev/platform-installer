"""Private, durable Execution Node lifecycle primitives for UI-BE-04C.

This module deliberately has no Installer, SSH or arbitrary-command API.  The
fixed controller and its local protocol are the only callers.  All inputs are
run-scoped, digest-bound JSON staged by trusted Core/transport code.
"""
from __future__ import absolute_import, division, print_function

import fcntl
import hashlib
import json
import os
import re
import stat
import tempfile
import errno
from datetime import datetime, timezone


API_VERSION = "platform.installer/execution-runtime/v1alpha1"
EXECUTION_STATE_ROOT = "/var/lib/platform-installer/execution"
RUN_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")
TERMINAL = frozenset(("SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED", "CORRUPT_ORPHANED"))
ACTIVE = frozenset(("PENDING", "STARTING", "RUNNING"))
# Detailed Ansible task events are intentionally bounded, but a complete
# cumulative service plan legitimately produces several thousand events.
# Keep the journal finite without truncating normal multi-service runs.
MAX_EVENTS = 16384
MAX_EVENT_PAGE = 512
MAX_EVENT_PAGE_BYTES = 1024 * 1024
MAX_EVENT_BYTES = 64 * 1024
CRITICAL_EVENT_RESERVE = 256
MAX_MESSAGE = 2048
MAX_TASK_NAME = 512
MAX_TASK_ROLE = 256
MAX_TASK_UUID = 128
MAX_HOST = 255
DEFAULT_TERMINAL_RETENTION = 20

EVENT_TYPES = frozenset(("RUN_STARTED", "PHASE_STARTED", "ACTION_STARTED", "TASK_STARTED", "TASK_COMPLETED", "ACTION_COMPLETED", "PHASE_COMPLETED", "RUN_COMPLETED", "DIAGNOSTIC"))
EVENT_STATUSES = frozenset(("PENDING", "RUNNING", "SUCCESS", "CHANGED", "SKIPPED", "FAILED", "CANCELLED", "INTERRUPTED"))
TASK_EVENT_TYPES = frozenset(("TASK_STARTED", "TASK_COMPLETED"))
TASK_EVENT_STATUSES = frozenset(("RUNNING", "SUCCESS", "CHANGED", "SKIPPED", "FAILED"))
TASK_DEGRADATION_REASONS = frozenset(("TASK_EVENT_LIMIT", "TASK_EVENT_WRITE_FAILED", "TASK_EVENT_INVALID"))
RUNTIME_SECRET_INPUT_FILE = re.compile(r"^\.runtime-secret-inputs-[0-9a-f]{64}\.json$")
RUNTIME_CONNECTION_FILE = re.compile(r"^(?:target-key-[A-Za-z0-9_-]{8}\.pem|bootstrap-[A-Za-z0-9_-]{8}\.json)$")
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class LifecycleError(ValueError):
    pass


def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def digest(value):
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def _id(run_id):
    if not isinstance(run_id, str) or not RUN_ID.match(run_id):
        raise LifecycleError("RUN_ID_INVALID")
    return run_id


def _safe_text(value):
    value = value if isinstance(value, str) else ""
    value = ANSI_ESCAPE.sub("", value)
    value = "".join(character if character >= " " else " " for character in value)
    value = value.replace("\x00", " ").replace("\r", " ").replace("\n", " ")
    return value[:MAX_MESSAGE]


def _bounded_text(value, limit):
    return _safe_text(value)[:limit]


def _contained(root, candidate):
    root = os.path.realpath(root)
    candidate = os.path.realpath(candidate)
    return candidate == root or candidate.startswith(root + os.sep)


def _run_dir(root, run_id):
    _id(run_id)
    candidate = os.path.join(root, "runs", run_id)
    if not _contained(os.path.join(root, "runs"), candidate):
        raise LifecycleError("RUN_PATH_INVALID")
    return candidate


def _read(path):
    if os.path.islink(path):
        raise LifecycleError("RUN_JOURNAL_SYMLINK")
    with open(path, "r", encoding="utf-8") as stream:
        return json.load(stream)


def _write(path, value):
    parent = os.path.dirname(path)
    os.makedirs(parent, mode=0o700, exist_ok=True)
    if os.path.islink(parent) or os.path.islink(path):
        raise LifecycleError("RUN_JOURNAL_SYMLINK")
    descriptor, temporary = tempfile.mkstemp(prefix=".journal-", dir=parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _assert_private_path(path, directory=False):
    try:
        details = os.lstat(path)
    except OSError:
        raise LifecycleError("RUN_JOURNAL_INVALID")
    if os.path.islink(path) or details.st_uid != os.geteuid():
        raise LifecycleError("RUN_JOURNAL_OWNERSHIP_INVALID")
    if details.st_mode & 0o077:
        raise LifecycleError("RUN_JOURNAL_PERMISSIONS_INVALID")
    if directory != os.path.isdir(path):
        raise LifecycleError("RUN_JOURNAL_INVALID")


def validate_ownership(journal):
    metadata = journal.metadata()
    manifest_path = os.path.join(journal.directory, "manifest.json")
    if not os.path.isfile(manifest_path) or os.path.islink(manifest_path):
        raise LifecycleError("EXECUTION_OWNERSHIP_INVALID")
    with open(manifest_path, "r", encoding="utf-8") as stream:
        manifest = json.load(stream)
    if metadata.get("runId") != journal.run_id or metadata.get("unit") != "platform-installer-run-%s.service" % journal.run_id or metadata.get("manifestDigest") != digest(manifest) or manifest.get("projectIdentity") != metadata.get("projectIdentity") or manifest.get("planFingerprint") != metadata.get("planFingerprint") or manifest.get("runtimeRelease", {}).get("bundleDigest") != metadata.get("runtimeRelease"):
        raise LifecycleError("EXECUTION_OWNERSHIP_INVALID")
    return metadata


def validate_task_journal_ownership(journal):
    metadata = validate_ownership(journal)
    _assert_private_path(journal.directory, directory=True)
    _assert_private_path(journal.metadata_path)
    _assert_private_path(journal.status_path)
    _assert_private_path(os.path.join(journal.directory, "manifest.json"))
    return metadata


class Journal(object):
    def __init__(self, root, run_id):
        self.root = os.path.realpath(root)
        self.run_id = _id(run_id)
        self.directory = _run_dir(self.root, self.run_id)

    @property
    def metadata_path(self): return os.path.join(self.directory, "metadata.json")
    @property
    def status_path(self): return os.path.join(self.directory, "status.json")
    @property
    def result_path(self): return os.path.join(self.directory, "result.json")
    @property
    def events_path(self): return os.path.join(self.directory, "events.jsonl")
    @property
    def lock_path(self): return os.path.join(self.directory, ".lock")
    @property
    def event_lock_path(self): return os.path.join(self.directory, ".events.lock")
    @property
    def task_observability_path(self): return os.path.join(self.directory, "task-observability.json")
    @property
    def task_observability_reported_path(self): return os.path.join(self.directory, ".task-observability.reported")
    @property
    def task_failure_reported_path(self): return os.path.join(self.directory, ".task-failure-after-truncation.reported")

    def lock(self):
        os.makedirs(self.directory, mode=0o700, exist_ok=True)
        descriptor = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        return descriptor

    def cleanup_runtime_secret_inputs(self):
        """Remove only owned regular files created for typed Ansible inputs."""
        _assert_private_path(self.directory, directory=True)
        application_projections = {'.runtime-projection-' + hashlib.sha256(value.encode()).hexdigest() + '.json'
                                   for value in ('applications:apply', 'applications:verify', 'applications:post-install')}
        for name in os.listdir(self.directory):
            if (RUNTIME_SECRET_INPUT_FILE.fullmatch(name) is None and name not in application_projections and
                    re.fullmatch(r'\.runtime-application-secret-[0-9a-f]{64}', name) is None and
                    re.fullmatch(r'pla-(?:vault-[0-9a-f]{32}|generated-[0-9a-f]{40})', name) is None):
                continue
            path = os.path.join(self.directory, name)
            try:
                details = os.lstat(path)
            except OSError as error:
                if error.errno == errno.ENOENT:
                    continue
                raise
            if stat.S_ISREG(details.st_mode) and details.st_uid == os.geteuid():
                os.unlink(path)

    def cleanup_runtime_connection_credentials(self):
        """Remove only owned, exact temporary connection-credential entries."""
        _assert_private_path(self.directory, directory=True)
        import execution_ssh
        execution_ssh.cleanup(self)
        credentials = os.path.join(self.directory, ".ansible-runtime-credentials.json")
        try:
            details = os.lstat(credentials)
        except FileNotFoundError:
            pass
        else:
            if stat.S_ISREG(details.st_mode) and details.st_uid == os.geteuid():
                os.unlink(credentials)
        runtime_dir = os.path.join(self.directory, ".ansible-runtime")
        if not os.path.lexists(runtime_dir):
            return
        _assert_private_path(runtime_dir, directory=True)
        flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(runtime_dir, flags)
        try:
            details = os.fstat(descriptor)
            if details.st_uid != os.geteuid() or details.st_mode & 0o077:
                raise LifecycleError("RUN_JOURNAL_PERMISSIONS_INVALID")
            for name in os.listdir(descriptor):
                if RUNTIME_CONNECTION_FILE.fullmatch(name) is None:
                    continue
                try:
                    entry = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                if stat.S_ISREG(entry.st_mode) and entry.st_uid == os.geteuid():
                    os.unlink(name, dir_fd=descriptor)
        finally:
            os.close(descriptor)

    def event_lock(self):
        if not os.path.isdir(self.directory) or os.path.islink(self.directory):
            raise LifecycleError("RUN_JOURNAL_INVALID")
        flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(self.event_lock_path, flags, 0o600)
        details = os.fstat(descriptor)
        if details.st_uid != os.geteuid() or details.st_mode & 0o077:
            os.close(descriptor)
            raise LifecycleError("RUN_JOURNAL_OWNERSHIP_INVALID")
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        return descriptor

    def initialize(self, metadata):
        required = ("projectIdentity", "planFingerprint", "manifestDigest", "runtimeRelease", "unit")
        if any(not isinstance(metadata.get(key), str) or not metadata[key] for key in required):
            raise LifecycleError("RUN_METADATA_INVALID")
        if os.path.exists(self.metadata_path):
            current = _read(self.metadata_path)
            if current != metadata:
                raise LifecycleError("RUN_ID_TAMPERED")
            return False
        os.makedirs(self.directory, mode=0o700, exist_ok=True)
        os.chmod(self.directory, 0o700)
        _write(self.metadata_path, metadata)
        _write(self.status_path, {"apiVersion": API_VERSION, "runId": self.run_id, "state": "PENDING", "updatedAt": utcnow(), "sequence": 0})
        return True

    def metadata(self): return _read(self.metadata_path)
    def status(self): return _read(self.status_path)

    def _append_event_locked(self, current, event):
        sequence = max(int(current.get("sequence", 0)), self._last_complete_event_sequence()) + 1
        if sequence > MAX_EVENTS:
            raise LifecycleError("RUN_EVENT_LIMIT")
        event["sequence"] = sequence
        encoded = (json.dumps(event, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        flags = os.O_CREAT | os.O_APPEND | os.O_WRONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(self.events_path, flags, 0o600)
        try:
            os.fchmod(descriptor, 0o600)
            if os.write(descriptor, encoded) != len(encoded):
                raise LifecycleError("RUN_EVENT_WRITE_INCOMPLETE")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        current["sequence"] = sequence
        _write(self.status_path, current)
        return event

    def _last_complete_event_sequence(self):
        if not os.path.exists(self.events_path):
            return 0
        if os.path.islink(self.events_path):
            raise LifecycleError("RUN_JOURNAL_SYMLINK")
        flags = os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(self.events_path, flags)
        with os.fdopen(descriptor, "rb+") as stream:
            content = stream.read()
            complete = content.rfind(b"\n")
            if complete < 0:
                stream.seek(0); stream.truncate(); stream.flush(); os.fsync(stream.fileno())
                return 0
            if complete != len(content) - 1:
                stream.seek(complete + 1); stream.truncate(); stream.flush(); os.fsync(stream.fileno())
                content = content[:complete + 1]
            lines = content.rstrip(b"\n").split(b"\n")
            if not lines:
                return 0
            try:
                return int(json.loads(lines[-1].decode("utf-8")).get("sequence", 0))
            except (UnicodeDecodeError, ValueError, TypeError):
                raise LifecycleError("RUN_EVENT_STREAM_INVALID")

    def _event_locked(self, current, event_type, status, message, fields):
        if event_type not in EVENT_TYPES or status not in EVENT_STATUSES:
            raise LifecycleError("RUN_EVENT_INVALID")
        event = {"apiVersion": "platform.installer/event/v1alpha1", "kind": "ExecutionEvent", "runId": self.run_id, "sequence": 0, "timestamp": utcnow(), "eventType": event_type, "status": status, "safeMessage": _safe_text(message), "redaction": {"applied": True, "fields": []}}
        for key in ("planFingerprint", "phaseId", "actionId", "host", "serviceDeployment"):
            if isinstance(fields.get(key), str) and fields[key]:
                event[key] = _bounded_text(fields[key], MAX_HOST if key == "host" else MAX_MESSAGE)
        return self._append_event_locked(current, event)

    def transition(self, state, message=""):
        event_lock = self.event_lock()
        try:
            return self._transition_locked(state, message)
        finally:
            os.close(event_lock)

    def _transition_locked(self, state, message=""):
        current = self.status()
        if current.get("state") in TERMINAL:
            return current
        if state not in ACTIVE and state not in TERMINAL:
            raise LifecycleError("RUN_STATE_INVALID")
        current.update({"state": state, "updatedAt": utcnow()})
        _write(self.status_path, current)
        event_status = "RUNNING" if state in ACTIVE else ("SUCCESS" if state == "SUCCEEDED" else ("FAILED" if state == "CORRUPT_ORPHANED" else state))
        self._event_locked(current, "DIAGNOSTIC", event_status, message or state, {})
        return current

    def event(self, event_type, status, message, **fields):
        event_lock = self.event_lock()
        try:
            return self._event_locked(self.status(), event_type, status, message, fields)
        finally:
            os.close(event_lock)

    def task_event(self, event_type, status, task_uuid, host="", role="", name="", elapsed_milliseconds=None, no_log=False, failure_result=None, **context):
        event_lock = self.event_lock()
        try:
            validate_task_journal_ownership(self)
            current = self.status()
            if current.get("state") not in ACTIVE:
                raise LifecycleError("TASK_EVENT_RUN_INACTIVE")
            sequence = max(int(current.get("sequence", 0)), self._last_complete_event_sequence())
            if event_type not in TASK_EVENT_TYPES or status not in TASK_EVENT_STATUSES or not isinstance(task_uuid, str) or not task_uuid:
                self._mark_task_observability_locked("TASK_EVENT_INVALID")
                return None
            truncated = sequence >= MAX_EVENTS - CRITICAL_EVENT_RESERVE
            if truncated:
                self._mark_task_observability_locked("TASK_EVENT_LIMIT")
                # Ordinary task progress yields to action and terminal events.
                # Preserve exactly one redacted failed-task identity, however:
                # otherwise a saturated stream makes the only actionable failure
                # diagnosis disappear.  The fixed private marker prevents an
                # unbounded failure flood from consuming the critical reserve.
                if event_type != "TASK_COMPLETED" or status != "FAILED" or sequence >= MAX_EVENTS or os.path.exists(self.task_failure_reported_path):
                    return None
            task = {"uuid": _bounded_text(task_uuid, MAX_TASK_UUID)}
            safe_role = _bounded_text(role, MAX_TASK_ROLE)
            if safe_role:
                task["role"] = safe_role
            redacted_fields = []
            safe_name = _bounded_text(name, MAX_TASK_NAME)
            if safe_name:
                task["name"] = safe_name
            event = {"apiVersion": "platform.installer/event/v1alpha1", "kind": "ExecutionEvent", "runId": self.run_id, "sequence": 0, "timestamp": utcnow(), "eventType": event_type, "status": status, "task": task, "safeMessage": "Ansible task started" if event_type == "TASK_STARTED" else "Ansible task completed", "redaction": {"applied": True, "fields": redacted_fields}}
            safe_host = _bounded_text(host, MAX_HOST)
            if safe_host:
                event["host"] = safe_host
            for key in ("phaseId", "actionId", "serviceDeployment"):
                if isinstance(context.get(key), str) and context[key]:
                    event[key] = _bounded_text(context[key], MAX_MESSAGE)
            if event_type == "TASK_COMPLETED" and isinstance(elapsed_milliseconds, int) and elapsed_milliseconds >= 0:
                event["elapsedMilliseconds"] = elapsed_milliseconds
            if status == "FAILED":
                from execution_task_error import safe_task_error
                event["error"] = safe_task_error(failure_result, no_log)
            committed = self._append_event_locked(current, event)
            if truncated:
                _write(self.task_failure_reported_path, {"reported": True})
            return committed
        except (OSError, ValueError, LifecycleError):
            try:
                self._mark_task_observability_locked("TASK_EVENT_WRITE_FAILED")
            except (OSError, ValueError, LifecycleError):
                pass
            return None
        finally:
            os.close(event_lock)

    def mark_task_observability_degraded(self, reason):
        event_lock = self.event_lock()
        try:
            self._mark_task_observability_locked(reason)
        finally:
            os.close(event_lock)

    def _mark_task_observability_locked(self, reason):
        reason = reason if reason in TASK_DEGRADATION_REASONS else "TASK_EVENT_WRITE_FAILED"
        if os.path.exists(self.task_observability_path):
            return
        _write(self.task_observability_path, {"degraded": True, "reason": reason})

    def emit_task_observability_diagnostic(self, **context):
        event_lock = self.event_lock()
        try:
            if not os.path.exists(self.task_observability_path):
                return None
            try:
                _assert_private_path(self.task_observability_path)
                marker = _read(self.task_observability_path)
            except (OSError, ValueError, LifecycleError):
                return None
            reason = marker.get("reason") if isinstance(marker, dict) else ""
            if not isinstance(marker, dict) or marker.get("degraded") is not True or reason not in TASK_DEGRADATION_REASONS:
                reason = "TASK_EVENT_INVALID"
            try:
                os.replace(self.task_observability_path, self.task_observability_reported_path)
            except OSError:
                return None
            current = self.status()
            if reason == "TASK_EVENT_LIMIT":
                message = "Detailed task observability was truncated"
                code = "TASK_EVENT_STREAM_TRUNCATED"
                summary = "Detailed task events exceeded the configured run limit"
            else:
                message = "Detailed task observability was degraded"
                code = "TASK_EVENT_STREAM_DEGRADED"
                summary = "Detailed task events could not be recorded completely"
            event = {
                "apiVersion": "platform.installer/event/v1alpha1",
                "kind": "ExecutionEvent",
                "runId": self.run_id,
                "sequence": 0,
                "timestamp": utcnow(),
                "eventType": "DIAGNOSTIC",
                "status": "RUNNING",
                "safeMessage": message,
                "error": {"code": code, "summary": summary},
                "redaction": {"applied": True, "fields": []},
            }
            for key in ("phaseId", "actionId", "serviceDeployment"):
                if isinstance(context.get(key), str) and context[key]:
                    event[key] = _bounded_text(context[key], MAX_MESSAGE)
            committed = self._append_event_locked(current, event)
            try:
                os.unlink(self.task_observability_reported_path)
            except OSError:
                pass
            return committed
        finally:
            os.close(event_lock)

    def emit_operation_failure_diagnostic(self, error_code="", **context):
        """Publish one bounded, redacted reason after an Ansible action fails.

        Controller output is never retained.  ``error_code`` is an optional
        machine-shaped token extracted from the bounded in-memory stream; it
        lets an operator distinguish a known Core failure without exposing an
        Ansible result payload, command, variable, diff, or secret.
        """
        event_lock = self.event_lock()
        try:
            current = self.status()
            suffix = " (%s)" % error_code if isinstance(error_code, str) and error_code else ""
            event = {
                "apiVersion": "platform.installer/event/v1alpha1",
                "kind": "ExecutionEvent",
                "runId": self.run_id,
                "sequence": 0,
                "timestamp": utcnow(),
                "eventType": "DIAGNOSTIC",
                "status": "FAILED",
                "safeMessage": "Ansible operation failed",
                "error": {"code": "ANSIBLE_OPERATION_FAILED", "summary": _safe_text("Ansible operation failed" + suffix)},
                "redaction": {"applied": True, "fields": ["stdout", "stderr", "args", "vars", "diff", "invocation", "cmd"]},
            }
            for key in ("phaseId", "actionId", "serviceDeployment"):
                if isinstance(context.get(key), str) and context[key]:
                    event[key] = _bounded_text(context[key], MAX_MESSAGE)
            return self._append_event_locked(current, event)
        finally:
            os.close(event_lock)

    def terminal(self, state, code, summary):
        event_lock = self.event_lock()
        try:
            if state not in TERMINAL:
                raise LifecycleError("RUN_TERMINAL_INVALID")
            if os.path.exists(self.result_path): return _read(self.result_path)
            current = self.status()
            if current.get("state") in TERMINAL and current.get("state") != state:
                raise LifecycleError("RUN_TERMINAL_CONFLICT")
            result = {"apiVersion": API_VERSION, "kind": "ExecutionResult", "runId": self.run_id, "state": state, "completedAt": utcnow(), "error": {"code": code, "summary": _safe_text(summary)} if code else None}
            # A result is the public terminal observation used by callers to
            # begin a later run.  Publish the matching terminal status first:
            # otherwise a caller can observe result.json while start() still
            # correctly admits this journal as RUNNING.
            self._transition_locked(state, summary)
            try:
                descriptor = os.open(self.result_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except OSError:
                return _read(self.result_path)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    json.dump(result, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
                    stream.flush(); os.fsync(stream.fileno())
            except Exception:
                if os.path.exists(self.result_path): os.unlink(self.result_path)
                raise
            return result
        finally:
            os.close(event_lock)

    def events(self, after=0):
        if isinstance(after, bool) or not isinstance(after, int) or after < 0:
            raise LifecycleError("EXECUTION_EVENTS_INPUT_INVALID")
        result = []
        previous = 0
        for _, event in self._event_records():
            sequence = event.get("sequence")
            if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= previous:
                raise LifecycleError("RUN_EVENT_STREAM_INVALID")
            previous = sequence
            if sequence > after: result.append(event)
        return result

    def _event_records(self):
        if not os.path.lexists(self.events_path):
            return
        _assert_private_path(self.events_path)
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(self.events_path, flags)
        with os.fdopen(descriptor, "rb") as stream:
            while True:
                line = stream.readline(MAX_EVENT_BYTES + 1)
                if not line:
                    return
                if len(line) > MAX_EVENT_BYTES:
                    raise LifecycleError("RUN_EVENT_SIZE_INVALID")
                if not line.endswith(b"\n"):
                    return
                try:
                    event = json.loads(line.decode("utf-8"))
                except (UnicodeDecodeError, TypeError, ValueError):
                    raise LifecycleError("RUN_EVENT_STREAM_INVALID")
                yield line, event

    def event_page(self, after, limit):
        if isinstance(after, bool) or not isinstance(after, int) or after < 0 or isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > MAX_EVENT_PAGE:
            raise LifecycleError("EXECUTION_EVENTS_INPUT_INVALID")
        result, size, previous, earliest, has_more = [], 0, 0, 0, False
        if not os.path.lexists(self.events_path):
            return {"events": result, "nextSequence": after, "hasMore": False, "earliestSequence": 0, "historyTruncated": False}
        for line, event in self._event_records():
            sequence = event.get("sequence")
            if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= previous:
                raise LifecycleError("RUN_EVENT_STREAM_INVALID")
            previous = sequence
            if earliest == 0:
                earliest = sequence
            if sequence <= after:
                continue
            encoded_size = len(line)
            if len(result) >= limit or (result and size + encoded_size > MAX_EVENT_PAGE_BYTES):
                has_more = True
                break
            result.append(event)
            size += encoded_size
        return {"events": result, "nextSequence": result[-1]["sequence"] if result else after, "hasMore": has_more, "earliestSequence": earliest, "historyTruncated": earliest > after + 1}


def recover(root, unit_active):
    """Reconcile journals only; never attach to or stop an unverified unit."""
    runs = os.path.join(os.path.realpath(root), "runs")
    if not os.path.isdir(runs): return []
    recovered = []
    for run_id in sorted(os.listdir(runs)):
        try:
            journal = Journal(root, run_id)
            lock = journal.lock()
            try:
                metadata, status = validate_ownership(journal), journal.status()
                if status.get("state") in ACTIVE and not unit_active(metadata.get("unit"), metadata):
                    result = journal.terminal("INTERRUPTED", "CONTROLLER_INTERRUPTED", "Owned controller is no longer active")
                    _complete_recovered_secret_outputs(root, journal, result)
                    journal.cleanup_runtime_secret_inputs()
                    journal.cleanup_runtime_connection_credentials()
                    recovered.append(run_id)
                elif status.get("state") in TERMINAL:
                    # A crash may occur after terminal result but before output
                    # publication/completion. Wait for the owned unit to stop
                    # before touching its runtime credentials or outputs.
                    if not unit_active(metadata.get("unit"), metadata):
                        _complete_recovered_secret_outputs(root, journal, _read(journal.result_path))
                        journal.cleanup_runtime_connection_credentials()
            finally:
                os.close(lock)
        except (OSError, ValueError, LifecycleError):
            # Invalid state is intentionally not attached to any unit.
            continue
    return recovered


def _complete_recovered_secret_outputs(root, journal, result):
    try:
        import execution_secret_output
        from execution_controller import _output_schema_validator
        validator, schema_path = _output_schema_validator(None)
        manifest = _read(os.path.join(journal.directory, "manifest.json"))
        outputs = manifest.get("runtimeSecretOutputs", [])
        if not isinstance(outputs, list) or len(outputs) > 64:
            return
        for output in outputs:
            if (not isinstance(output, dict) or set(output) != {"protocol", "serviceDeployment", "entries"} or
                    output.get("protocol") != "SecretOutputDelivery/v1alpha1" or
                    not isinstance(output.get("serviceDeployment"), str) or
                    output.get("entries") != ["admin-token", "unseal-shares"]):
                return
            try:
                execution_secret_output.complete_retained_outputs(
                    root, journal.directory, manifest["projectIdentity"], output["serviceDeployment"],
                    journal.run_id, journal.metadata()["runtimeRelease"], result["state"], digest(result),
                    validator, schema_path)
            except execution_secret_output.OutputWireError:
                continue
    except (ImportError, OSError, ValueError, KeyError, TypeError):
        return


def retain(root, limit=DEFAULT_TERMINAL_RETENTION):
    """Keep a bounded terminal history without touching active or unsafe runs."""
    if not isinstance(limit, int) or limit < 1:
        raise LifecycleError("RUN_RETENTION_INVALID")
    runs = os.path.join(os.path.realpath(root), "runs")
    if not os.path.isdir(runs) or os.path.islink(runs): return []
    terminal = []
    for run_id in sorted(os.listdir(runs)):
        try:
            journal = Journal(root, run_id)
            if os.path.islink(journal.directory): continue
            status = journal.status()
            metadata = validate_ownership(journal)
            if status.get("state") in TERMINAL and metadata.get("runId") == run_id and os.path.isfile(journal.result_path) and not os.path.islink(journal.result_path):
                if _secret_output_retention_pending(root, journal):
                    continue
                terminal.append((status.get("updatedAt", ""), run_id, journal.directory))
        except (OSError, ValueError, LifecycleError):
            continue
    removed = []
    for _timestamp, run_id, directory in sorted(terminal, reverse=True)[limit:]:
        if not _contained(runs, directory) or os.path.islink(directory): continue
        for base, dirs, files in os.walk(directory, topdown=True, followlinks=False):
            if any(os.path.islink(os.path.join(base, name)) for name in dirs + files):
                break
        else:
            for base, dirs, files in os.walk(directory, topdown=False, followlinks=False):
                for name in files: os.unlink(os.path.join(base, name))
                for name in dirs: os.rmdir(os.path.join(base, name))
            os.rmdir(directory)
            removed.append(run_id)
    return removed


def _secret_output_retention_pending(root, journal):
    """Preserve a run until every declared output package has release evidence."""
    manifest_path = os.path.join(journal.directory, "manifest.json")
    try:
        manifest = _read(manifest_path)
    except (OSError, ValueError, LifecycleError):
        return True
    outputs = manifest.get("runtimeSecretOutputs", [])
    if not isinstance(outputs, list) or len(outputs) > 64:
        return True
    project_id = manifest.get("projectIdentity")
    if not isinstance(project_id, str):
        return bool(outputs)
    try:
        import execution_secret_output
    except ImportError:
        return bool(outputs)
    for output in outputs:
        if (not isinstance(output, dict) or set(output) != {"protocol", "serviceDeployment", "entries"} or
                output.get("protocol") != "SecretOutputDelivery/v1alpha1" or
                not isinstance(output.get("serviceDeployment"), str) or
                output.get("entries") != ["admin-token", "unseal-shares"]):
            return True
        try:
            package, _generation = execution_secret_output.load_package_identity(
                journal.directory, project_id, output["serviceDeployment"], journal.run_id)
        except execution_secret_output.OutputWireError:
            package = None
        if package is None:
            source_dir = os.path.join(journal.directory, "project", "secrets", output["serviceDeployment"])
            if any(os.path.lexists(os.path.join(source_dir, entry))
                   for entry in ("admin-token", "unseal-shares", "init-response.json")):
                return True
            continue
        package_dir = os.path.join(os.path.realpath(root), "secret-outputs", package)
        source_dir = os.path.join(journal.directory, "project", "secrets", output["serviceDeployment"])
        source_present = any(os.path.lexists(os.path.join(source_dir, entry))
                             for entry in ("admin-token", "unseal-shares", "init-response.json"))
        package_present = os.path.lexists(package_dir)
        if source_present and (not package_present or not execution_secret_output.producer_completed(root, package, journal.run_id)):
            return True
        # A durable reservation can precede directory creation. Preserve its
        # journal until READY or explicit empty completion is durable as well.
        if not execution_secret_output.producer_completed(root, package, journal.run_id):
            return True
    return False

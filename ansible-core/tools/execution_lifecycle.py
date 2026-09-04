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
import tempfile
from datetime import datetime, timezone


API_VERSION = "platform.installer/execution-runtime/v1alpha1"
RUN_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")
TERMINAL = frozenset(("SUCCEEDED", "FAILED", "CANCELLED", "INTERRUPTED", "CORRUPT_ORPHANED"))
ACTIVE = frozenset(("PENDING", "STARTING", "RUNNING"))
MAX_EVENTS = 2048
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

    def lock(self):
        os.makedirs(self.directory, mode=0o700, exist_ok=True)
        descriptor = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        return descriptor

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

    def task_event(self, event_type, status, task_uuid, host="", role="", name="", elapsed_milliseconds=None, no_log=False, **context):
        event_lock = self.event_lock()
        try:
            validate_task_journal_ownership(self)
            current = self.status()
            if current.get("state") not in ACTIVE:
                raise LifecycleError("TASK_EVENT_RUN_INACTIVE")
            sequence = max(int(current.get("sequence", 0)), self._last_complete_event_sequence())
            if sequence >= MAX_EVENTS - CRITICAL_EVENT_RESERVE:
                self._mark_task_observability_locked("TASK_EVENT_LIMIT")
                return None
            if event_type not in TASK_EVENT_TYPES or status not in TASK_EVENT_STATUSES or not isinstance(task_uuid, str) or not task_uuid:
                self._mark_task_observability_locked("TASK_EVENT_INVALID")
                return None
            task = {"uuid": _bounded_text(task_uuid, MAX_TASK_UUID)}
            safe_role = _bounded_text(role, MAX_TASK_ROLE)
            if safe_role:
                task["role"] = safe_role
            redacted_fields = []
            if no_log:
                redacted_fields.append("task.name")
            else:
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
                event["error"] = {"code": "ANSIBLE_TASK_FAILED", "summary": "Ansible task failed"}
            return self._append_event_locked(current, event)
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
            self._transition_locked(state, summary)
            return result
        finally:
            os.close(event_lock)

    def events(self, after=0):
        after = int(after)
        result = []
        if not os.path.exists(self.events_path): return result
        if os.path.islink(self.events_path): raise LifecycleError("RUN_JOURNAL_SYMLINK")
        with open(self.events_path, "r", encoding="utf-8") as stream:
            for line in stream:
                if not line.endswith("\n"):
                    break
                event = json.loads(line)
                if int(event.get("sequence", -1)) > after: result.append(event)
        return result


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
                    journal.terminal("INTERRUPTED", "CONTROLLER_INTERRUPTED", "Owned controller is no longer active")
                    recovered.append(run_id)
            finally:
                os.close(lock)
        except (OSError, ValueError, LifecycleError):
            # Invalid state is intentionally not attached to any unit.
            continue
    return recovered


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

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
MAX_MESSAGE = 2048
DEFAULT_TERMINAL_RETENTION = 20


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
    value = value.replace("\x00", " ").replace("\r", " ").replace("\n", " ")
    return value[:MAX_MESSAGE]


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

    def lock(self):
        os.makedirs(self.directory, mode=0o700, exist_ok=True)
        descriptor = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
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

    def transition(self, state, message=""):
        current = self.status()
        if current.get("state") in TERMINAL:
            return current
        if state not in ACTIVE and state not in TERMINAL:
            raise LifecycleError("RUN_STATE_INVALID")
        current.update({"state": state, "updatedAt": utcnow()})
        _write(self.status_path, current)
        self.event("DIAGNOSTIC", "RUNNING" if state in ACTIVE else state, message or state)
        return current

    def event(self, event_type, status, message, **fields):
        current = self.status()
        sequence = int(current.get("sequence", 0)) + 1
        if sequence > MAX_EVENTS:
            raise LifecycleError("RUN_EVENT_LIMIT")
        event = {"apiVersion": "platform.installer/event/v1alpha1", "kind": "ExecutionEvent", "runId": self.run_id, "sequence": sequence, "timestamp": utcnow(), "eventType": event_type, "status": status, "safeMessage": _safe_text(message), "redaction": {"applied": True, "fields": []}}
        event.update({key: value for key, value in fields.items() if isinstance(value, str) and value})
        with open(self.events_path, "a", encoding="utf-8") as stream:
            os.chmod(self.events_path, 0o600)
            stream.write(json.dumps(event, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n")
            stream.flush(); os.fsync(stream.fileno())
        current["sequence"] = sequence
        _write(self.status_path, current)
        return event

    def terminal(self, state, code, summary):
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
        self.transition(state, summary)
        return result

    def events(self, after=0):
        after = int(after)
        result = []
        if not os.path.exists(self.events_path): return result
        if os.path.islink(self.events_path): raise LifecycleError("RUN_JOURNAL_SYMLINK")
        with open(self.events_path, "r", encoding="utf-8") as stream:
            for line in stream:
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

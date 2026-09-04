import json
import multiprocessing
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


TOOLS = Path(__file__).resolve().parents[1] / "tools"
COLLECTIONS = Path(__file__).resolve().parents[1] / "collections"
CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(COLLECTIONS))

import execution_lifecycle
from execution_lifecycle import Journal, digest
from ansible_collections.platform.core.plugins.callback import execution_events_json
from ansible_collections.platform.core.plugins.module_utils.schema_validation import SchemaValidator


def _metadata(run_id="run-1"):
    manifest = {"projectIdentity": "project-1", "planFingerprint": "sha256:" + "a" * 64, "runtimeRelease": {"bundleDigest": "sha256:" + "c" * 64}, "operations": []}
    return manifest, {"runId": run_id, "projectIdentity": "project-1", "planFingerprint": manifest["planFingerprint"], "manifestDigest": digest(manifest), "runtimeRelease": manifest["runtimeRelease"]["bundleDigest"], "unit": "platform-installer-run-%s.service" % run_id}


def _active_journal(root, run_id="run-1"):
    manifest, metadata = _metadata(run_id)
    journal = Journal(root, run_id)
    journal.initialize(metadata)
    manifest_path = Path(journal.directory, "manifest.json")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    os.chmod(manifest_path, 0o600)
    journal.transition("RUNNING", "running")
    return journal


def _write_task_events(root, run_id, prefix, count):
    journal = Journal(root, run_id)
    for index in range(count):
        journal.task_event("TASK_COMPLETED", "SUCCESS", "%s-%d" % (prefix, index), host=prefix, name="safe task", elapsed_milliseconds=index)


class _Role(object):
    def get_name(self):
        return "platform.kafka.kafka_kraft"


class _Task(object):
    def __init__(self, task_uuid="task-1", name="safe task", no_log=False):
        self._uuid = task_uuid
        self._role = _Role()
        self.no_log = no_log
        self._name = name

    def get_name(self):
        return self._name


class _Host(object):
    def get_name(self):
        return "node1"


class _Result(object):
    def __init__(self, task, payload):
        self._task = task
        self._host = _Host()
        self._result = payload


class ExecutionTaskObservabilityTests(unittest.TestCase):
    def assert_events_match_contract(self, events):
        validator = SchemaValidator(CONTRACTS)
        schema = CONTRACTS / "event" / "v1alpha1" / "schema.json"
        for event in events:
            self.assertEqual([], validator.validate(event, schema))

    def test_cross_process_task_events_share_one_monotonic_sequence(self):
        with tempfile.TemporaryDirectory() as root:
            journal = _active_journal(root)
            workers = [multiprocessing.Process(target=_write_task_events, args=(root, "run-1", "node%d" % index, 20)) for index in range(4)]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(10)
                self.assertEqual(0, worker.exitcode)
            events = journal.events()
            self.assertEqual(list(range(1, 82)), [event["sequence"] for event in events])
            self.assertEqual(80, len([event for event in events if event["eventType"] == "TASK_COMPLETED"]))
            self.assert_events_match_contract(events)

    def test_task_capacity_degrades_without_consuming_critical_reserve(self):
        with tempfile.TemporaryDirectory() as root:
            journal = _active_journal(root)
            with mock.patch.object(execution_lifecycle, "MAX_EVENTS", 5), mock.patch.object(execution_lifecycle, "CRITICAL_EVENT_RESERVE", 2):
                self.assertIsNotNone(journal.task_event("TASK_STARTED", "RUNNING", "task-1"))
                self.assertIsNotNone(journal.task_event("TASK_COMPLETED", "SUCCESS", "task-1", host="node1", elapsed_milliseconds=1))
                self.assertIsNone(journal.task_event("TASK_STARTED", "RUNNING", "task-2"))
                journal.event("ACTION_COMPLETED", "SUCCESS", "done", actionId="apply:kafka")
                self.assertEqual("SUCCEEDED", journal.terminal("SUCCEEDED", "", "done")["state"])
            marker = json.loads(Path(journal.task_observability_path).read_text(encoding="utf-8"))
            self.assertEqual({"degraded": True, "reason": "TASK_EVENT_LIMIT"}, marker)
            self.assertEqual(5, journal.status()["sequence"])

    def test_corrupt_orphaned_terminal_uses_contract_valid_failed_event_status(self):
        with tempfile.TemporaryDirectory() as root:
            journal = _active_journal(root)
            journal.terminal("CORRUPT_ORPHANED", "RUN_CORRUPT", "corrupt")
            event = journal.events()[-1]
            self.assertEqual("FAILED", event["status"])
            self.assert_events_match_contract(journal.events())

    def test_incomplete_trailing_event_is_not_replayed_or_reused(self):
        with tempfile.TemporaryDirectory() as root:
            journal = _active_journal(root)
            with open(journal.events_path, "ab") as stream:
                stream.write(b'{"sequence":999')
            event = journal.task_event("TASK_STARTED", "RUNNING", "task-1")
            self.assertEqual(2, event["sequence"])
            self.assertEqual([1, 2], [item["sequence"] for item in journal.events()])

    def test_callback_redacts_no_log_and_never_persists_result_payload(self):
        with tempfile.TemporaryDirectory() as root:
            journal = _active_journal(root)
            callback = execution_events_json.CallbackModule()
            task = _Task(name="rendered secret value", no_log=True)
            result = _Result(task, {"changed": True, "stdout": "secret-output", "cmd": "secret-command", "_ansible_no_log": True})
            environment = {"PLATFORM_EXECUTION_RUN_ID": "run-1", "PLATFORM_EXECUTION_PHASE_ID": "apply", "PLATFORM_EXECUTION_ACTION_ID": "apply:kafka-main", "PLATFORM_EXECUTION_SERVICE_DEPLOYMENT": "kafka-main"}
            with mock.patch.object(execution_events_json, "EXECUTION_STATE_ROOT", root), mock.patch.dict(os.environ, environment, clear=False):
                callback.v2_playbook_on_task_start(task, False)
                callback.v2_runner_on_ok(result)
            events = journal.events()[1:]
            self.assertEqual(["TASK_STARTED", "TASK_COMPLETED"], [event["eventType"] for event in events])
            self.assertEqual("CHANGED", events[1]["status"])
            self.assertEqual("node1", events[1]["host"])
            self.assertNotIn("name", events[0]["task"])
            self.assertEqual(["task.name"], events[1]["redaction"]["fields"])
            self.assert_events_match_contract(events)
            serialized = json.dumps(events)
            for forbidden in ("rendered secret value", "secret-output", "secret-command", "stdout", "cmd"):
                self.assertNotIn(forbidden, serialized)

    def test_callback_sanitizes_display_name_and_failure_is_generic(self):
        with tempfile.TemporaryDirectory() as root:
            journal = _active_journal(root)
            callback = execution_events_json.CallbackModule()
            task = _Task(name="unsafe\n\x1b[31mtask")
            result = _Result(task, {"exception": "private traceback"})
            with mock.patch.object(execution_events_json, "EXECUTION_STATE_ROOT", root), mock.patch.dict(os.environ, {"PLATFORM_EXECUTION_RUN_ID": "run-1"}, clear=False):
                callback.v2_playbook_on_task_start(task, False)
                callback.v2_runner_on_failed(result)
            completed = journal.events()[-1]
            self.assertEqual("FAILED", completed["status"])
            self.assertEqual("ANSIBLE_TASK_FAILED", completed["error"]["code"])
            self.assertEqual("unsafe task", completed["task"]["name"])
            self.assertNotIn("private traceback", json.dumps(completed))
            self.assert_events_match_contract(journal.events())

    def test_event_lock_symlink_is_rejected_without_touching_target(self):
        with tempfile.TemporaryDirectory() as root:
            journal = _active_journal(root)
            target = Path(root, "outside")
            target.write_text("unchanged", encoding="utf-8")
            Path(journal.event_lock_path).unlink()
            Path(journal.event_lock_path).symlink_to(target)
            with self.assertRaises((OSError, execution_lifecycle.LifecycleError)):
                journal.task_event("TASK_STARTED", "RUNNING", "task-1")
            self.assertEqual("unchanged", target.read_text(encoding="utf-8"))

    def test_untrusted_journal_permissions_degrade_task_details(self):
        with tempfile.TemporaryDirectory() as root:
            journal = _active_journal(root)
            os.chmod(journal.metadata_path, 0o644)
            self.assertIsNone(journal.task_event("TASK_STARTED", "RUNNING", "task-1"))
            self.assertEqual(1, journal.status()["sequence"])

    def test_callback_failure_is_non_blocking_and_records_degradation(self):
        with tempfile.TemporaryDirectory() as root:
            journal = _active_journal(root)
            callback = execution_events_json.CallbackModule()
            with mock.patch.object(execution_events_json, "EXECUTION_STATE_ROOT", root), mock.patch.dict(os.environ, {"PLATFORM_EXECUTION_RUN_ID": "run-1"}, clear=False), mock.patch.object(Journal, "task_event", side_effect=OSError("injected")):
                callback.v2_playbook_on_task_start(_Task(), False)
            marker = json.loads(Path(journal.task_observability_path).read_text(encoding="utf-8"))
            self.assertEqual({"degraded": True, "reason": "TASK_EVENT_WRITE_FAILED"}, marker)

    def test_forged_run_id_and_inactive_run_cannot_receive_task_events(self):
        with tempfile.TemporaryDirectory() as root:
            journal = _active_journal(root)
            journal.terminal("SUCCEEDED", "", "done")
            self.assertIsNone(journal.task_event("TASK_STARTED", "RUNNING", "late-task"))
            callback = execution_events_json.CallbackModule()
            with mock.patch.object(execution_events_json, "EXECUTION_STATE_ROOT", root), mock.patch.dict(os.environ, {"PLATFORM_EXECUTION_RUN_ID": "../escape"}, clear=False):
                callback.v2_playbook_on_task_start(_Task(), False)
            self.assertEqual(2, journal.status()["sequence"])


if __name__ == "__main__":
    unittest.main()

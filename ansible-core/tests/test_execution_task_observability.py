import json
import multiprocessing
import os
import shutil
import sys
import tempfile
import threading
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest import mock


TOOLS = Path(__file__).resolve().parents[1] / "tools"
COLLECTIONS = Path(__file__).resolve().parents[1] / "collections"
CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(COLLECTIONS))

import execution_lifecycle
from execution_lifecycle import Journal, digest
import execution_controller
import execution_protocol
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

    def test_event_page_is_bounded_ordered_and_legacy_read_remains_compatible(self):
        with tempfile.TemporaryDirectory() as root:
            journal = _active_journal(root)
            for index in range(5):
                journal.task_event("TASK_COMPLETED", "SUCCESS", "task-%d" % index, host="node1")
            first = journal.event_page(0, 2)
            second = journal.event_page(first["nextSequence"], 2)
            final = journal.event_page(second["nextSequence"], 2)
            self.assertEqual([1, 2], [event["sequence"] for event in first["events"]])
            self.assertEqual([3, 4], [event["sequence"] for event in second["events"]])
            self.assertEqual([5, 6], [event["sequence"] for event in final["events"]])
            self.assertTrue(first["hasMore"])
            self.assertTrue(second["hasMore"])
            self.assertFalse(final["hasMore"])
            self.assertEqual([1, 2, 3, 4, 5, 6], [event["sequence"] for event in journal.events(0)])
            legacy = execution_protocol.events({"runId": "run-1", "afterSequence": 0}, root)
            paged = execution_protocol.events({"runId": "run-1", "afterSequence": 0, "limit": 2}, root)
            self.assertEqual(6, len(legacy["events"]))
            self.assertFalse(legacy["hasMore"])
            self.assertEqual([1, 2], [event["sequence"] for event in paged["events"]])
            self.assertTrue(paged["hasMore"])

    def test_event_page_rejects_invalid_limits_and_corrupt_sequence(self):
        with tempfile.TemporaryDirectory() as root:
            journal = _active_journal(root)
            for invalid in (0, 513, True, "2"):
                with self.assertRaises(execution_lifecycle.LifecycleError):
                    journal.event_page(0, invalid)
                with self.assertRaises(execution_lifecycle.LifecycleError):
                    execution_protocol.events({"runId": "run-1", "afterSequence": 0, "limit": invalid}, root)
            for invalid_after in (-1, True, "0"):
                with self.assertRaises(execution_lifecycle.LifecycleError):
                    journal.event_page(invalid_after, 10)
            with open(journal.events_path, "a", encoding="utf-8") as stream:
                stream.write(json.dumps({"sequence": 1}) + "\n")
            with self.assertRaisesRegex(execution_lifecycle.LifecycleError, "STREAM_INVALID"):
                journal.event_page(0, 10)

    def test_event_page_never_returns_partial_lines_while_writer_appends(self):
        with tempfile.TemporaryDirectory() as root:
            journal = _active_journal(root)
            worker = threading.Thread(target=_write_task_events, args=(root, "run-1", "node1", 40))
            worker.start()
            while worker.is_alive():
                page = journal.event_page(0, 512)
                sequences = [event["sequence"] for event in page["events"]]
                self.assertEqual(sorted(set(sequences)), sequences)
            worker.join()
            final = journal.event_page(0, 512)
            self.assertEqual(list(range(1, 42)), [event["sequence"] for event in final["events"]])

    def test_get_events_rejects_symlinked_remote_journal(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            journal = _active_journal(root)
            target = Path(outside) / "events.jsonl"
            target.write_text("outside\n", encoding="utf-8")
            os.unlink(journal.events_path)
            Path(journal.events_path).symlink_to(target)
            with self.assertRaises(execution_lifecycle.LifecycleError):
                execution_protocol.events({"runId": "run-1", "afterSequence": 0, "limit": 10}, root)
            self.assertEqual("outside\n", target.read_text(encoding="utf-8"))

    def test_event_page_rejects_oversized_line_before_json_decode(self):
        with tempfile.TemporaryDirectory() as root:
            journal = _active_journal(root)
            with open(journal.events_path, "wb") as stream:
                stream.write(b'{"sequence":1,"value":"' + b"x" * execution_lifecycle.MAX_EVENT_BYTES)
            with self.assertRaisesRegex(execution_lifecycle.LifecycleError, "SIZE_INVALID"):
                journal.event_page(0, 10)

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

    def test_controller_environment_enables_only_managed_callback_with_semantic_context(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            inherited = {"ANSIBLE_CALLBACK_PLUGINS": "/untrusted", "ANSIBLE_CALLBACK_WHITELIST": "evil", "ANSIBLE_LOAD_CALLBACK_PLUGINS": "1", "ANSIBLE_STDOUT_CALLBACK": "evil"}
            with mock.patch.dict(os.environ, inherited, clear=False):
                environment = execution_controller._environment("/runtime/release", journal, {
                    "phaseId": "apply", "operationId": "apply:kafka-main", "serviceDeployment": None,
                })
            self.assertEqual("platform.core.execution_events_json", environment["ANSIBLE_CALLBACKS_ENABLED"])
            self.assertEqual("run-1", environment["PLATFORM_EXECUTION_RUN_ID"])
            self.assertEqual("apply", environment["PLATFORM_EXECUTION_PHASE_ID"])
            self.assertEqual("apply:kafka-main", environment["PLATFORM_EXECUTION_ACTION_ID"])
            self.assertEqual("", environment["PLATFORM_EXECUTION_SERVICE_DEPLOYMENT"])
            for removed in inherited:
                self.assertNotIn(removed, environment)

    def test_controller_normalizes_one_degradation_diagnostic_without_failing_action(self):
        class _CompletedProcess(object):
            returncode = 0

            def poll(self):
                return 0

        with tempfile.TemporaryDirectory() as root:
            journal = _active_journal(root)
            journal.mark_task_observability_degraded("TASK_EVENT_LIMIT")
            operation = {"operationId": "apply:kafka-main", "phaseId": "apply", "operation": "SERVICE_APPLY", "serviceType": "kafka", "serviceDeployment": "kafka-main"}
            with mock.patch.object(execution_controller, "_command", return_value=["trusted"]), mock.patch.object(execution_controller.subprocess, "Popen", return_value=_CompletedProcess()), mock.patch.object(execution_controller, "_wait_for_operation", return_value=(0, "")):
                self.assertEqual("SUCCEEDED", execution_controller._dispatch("/runtime/release", journal, {"operations": [operation]}, [False]))
            events = journal.events()
            diagnostics = [event for event in events if event.get("error", {}).get("code") == "TASK_EVENT_STREAM_TRUNCATED"]
            self.assertEqual(1, len(diagnostics))
            self.assertEqual("RUNNING", diagnostics[0]["status"])
            self.assertEqual("apply:kafka-main", diagnostics[0]["actionId"])
            self.assertFalse(Path(journal.task_observability_path).exists())
            self.assertFalse(Path(journal.task_observability_reported_path).exists())
            self.assertEqual("SUCCESS", events[-1]["status"])
            self.assert_events_match_contract(events)
            self.assertIsNone(journal.emit_task_observability_diagnostic(actionId="apply:kafka-main"))

    def test_controller_emits_redacted_failure_code_after_task_stream_truncation(self):
        class _FailedProcess(object):
            returncode = 2

        with tempfile.TemporaryDirectory() as root:
            journal = _active_journal(root)
            journal.mark_task_observability_degraded("TASK_EVENT_LIMIT")
            operation = {"operationId": "apply:kafka-main", "phaseId": "apply", "operation": "SERVICE_APPLY", "serviceType": "kafka", "serviceDeployment": "kafka-main"}
            with mock.patch.object(execution_controller, "_command", return_value=["trusted"]), mock.patch.object(execution_controller.subprocess, "Popen", return_value=_FailedProcess()), mock.patch.object(execution_controller, "_wait_for_operation", return_value=(2, "KAFKA_IDENTITY_MATERIALIZATION_BLOCKED")):
                with self.assertRaisesRegex(execution_lifecycle.LifecycleError, "EXECUTION_OPERATION_FAILED"):
                    execution_controller._dispatch("/runtime/release", journal, {"operations": [operation]}, [False])
            events = journal.events()
            diagnostic = next(event for event in events if event.get("error", {}).get("code") == "ANSIBLE_OPERATION_FAILED")
            self.assertEqual("FAILED", diagnostic["status"])
            self.assertEqual("Ansible operation failed", diagnostic["safeMessage"])
            self.assertEqual("Ansible operation failed (KAFKA_IDENTITY_MATERIALIZATION_BLOCKED)", diagnostic["error"]["summary"])
            self.assertEqual(["stdout", "stderr", "args", "vars", "diff", "invocation", "cmd"], diagnostic["redaction"]["fields"])
            self.assertNotIn("trusted", str(diagnostic))
            self.assert_events_match_contract(events)

    def test_invalid_degradation_marker_does_not_change_execution_result(self):
        with tempfile.TemporaryDirectory() as root:
            journal = _active_journal(root)
            Path(journal.task_observability_path).write_text("not-json", encoding="utf-8")
            os.chmod(journal.task_observability_path, 0o600)
            self.assertIsNone(journal.emit_task_observability_diagnostic(actionId="apply:kafka-main"))
            self.assertEqual("SUCCEEDED", journal.terminal("SUCCEEDED", "", "done")["state"])

    def test_forged_run_id_and_inactive_run_cannot_receive_task_events(self):
        with tempfile.TemporaryDirectory() as root:
            journal = _active_journal(root)
            journal.terminal("SUCCEEDED", "", "done")
            self.assertIsNone(journal.task_event("TASK_STARTED", "RUNNING", "late-task"))
            callback = execution_events_json.CallbackModule()
            with mock.patch.object(execution_events_json, "EXECUTION_STATE_ROOT", root), mock.patch.dict(os.environ, {"PLATFORM_EXECUTION_RUN_ID": "../escape"}, clear=False):
                callback.v2_playbook_on_task_start(_Task(), False)
            self.assertEqual(2, journal.status()["sequence"])


@unittest.skipUnless(os.environ.get("PLATFORM_TEST_CANONICAL_EXECUTION_ROOT") == "1", "requires isolated root-owned RED OS acceptance")
class ControllerTaskStreamAcceptanceTests(unittest.TestCase):
    @contextmanager
    def runtime(self, tasks, callback_fault=None):
        self.assertEqual(0, os.geteuid(), "acceptance requires root-owned canonical journals")
        self.assertIsNotNone(shutil.which("ansible-playbook"), "ansible-playbook prerequisite missing")
        run_id = "exec-obs-01d-%s" % uuid.uuid4().hex
        journal = Journal(execution_lifecycle.EXECUTION_STATE_ROOT, run_id)
        release = tempfile.mkdtemp(prefix="exec-obs-01d-release-", dir="/var/tmp")
        controller_lock = None
        try:
            operation = {"operationId": "verify:qa", "phaseId": "verify", "operation": "SERVICE_VERIFY", "serviceType": "kafka", "serviceDeployment": "qa-only"}
            manifest = {"projectIdentity": "exec-obs-01d-qa", "planFingerprint": "sha256:" + "a" * 64, "runtimeRelease": {"bundleDigest": "sha256:" + "c" * 64}, "operations": [operation]}
            metadata = {"runId": run_id, "projectIdentity": manifest["projectIdentity"], "planFingerprint": manifest["planFingerprint"], "manifestDigest": digest(manifest), "runtimeRelease": manifest["runtimeRelease"]["bundleDigest"], "unit": "platform-installer-run-%s.service" % run_id}
            journal.initialize(metadata)
            # Own the run exactly as the real controller does. Concurrent
            # GetEvents recovery must not classify this isolated QA controller
            # as orphaned merely because _dispatch runs in the test process.
            controller_lock = journal.lock()
            manifest_path = Path(journal.directory, "manifest.json")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            os.chmod(manifest_path, 0o600)
            inventory = Path(journal.directory, "project", "inventory", "hosts.yml")
            inventory.parent.mkdir(parents=True)
            inventory.write_text("all:\n  hosts:\n    node1: {ansible_connection: local}\n    node2: {ansible_connection: local}\n", encoding="utf-8")
            projection = Path(journal.directory, "runtime-projection.json")
            projection.write_text("{}", encoding="utf-8")
            os.chmod(projection, 0o600)
            core = Path(release, "ansible-core")
            core.mkdir(parents=True)
            if callback_fault is None:
                (core / "collections").symlink_to(COLLECTIONS, target_is_directory=True)
            else:
                # Copy only the callback and its stdlib-only writer dependency.
                # Injection executes in the real Ansible child, never in the
                # controller or a shared collection. No production knobs.
                callback = core / "collections" / "ansible_collections" / "platform" / "core" / "plugins" / "callback" / "execution_events_json.py"
                callback.parent.mkdir(parents=True)
                (core / "tools").mkdir()
                shutil.copy2(TOOLS / "execution_lifecycle.py", core / "tools" / "execution_lifecycle.py")
                source = Path(execution_events_json.__file__).read_text(encoding="utf-8")
                marker = str(Path(release, "fault-exercised"))
                if callback_fault == "callback_exception":
                    injection = (
                        "\ndef _qa_context_failure(self):\n"
                        "    open(%r, 'a').close()\n"
                        "    raise RuntimeError('qa-private-injection-payload')\n"
                        "CallbackModule._context = _qa_context_failure\n" % marker
                    )
                elif callback_fault == "detail_writer_failure":
                    injection = (
                        "\n_qa_append = Journal._append_event_locked\n"
                        "def _qa_append_failure(self, current, event):\n"
                        "    if event['eventType'].startswith('TASK_'):\n"
                        "        open(%r, 'a').close()\n"
                        "        raise OSError('qa-private-injection-payload')\n"
                        "    return _qa_append(self, current, event)\n"
                        "Journal._append_event_locked = _qa_append_failure\n" % marker
                    )
                elif callback_fault == "tiny_capacity":
                    injection = (
                        "\nimport execution_lifecycle as _qa_lifecycle\n"
                        "_qa_lifecycle.MAX_EVENTS = 8\n"
                        "_qa_lifecycle.CRITICAL_EVENT_RESERVE = 5\n"
                        "open(%r, 'a').close()\n" % marker
                    )
                else:
                    self.fail("unknown callback fault")
                callback.write_text(source + injection, encoding="utf-8")
            shutil.copy2(Path(__file__).resolve().parents[1] / "ansible.cfg", core / "ansible.cfg")
            playbook = Path(release, "services", "kafka", "playbooks", "verify.yml")
            playbook.parent.mkdir(parents=True)
            playbook.write_text("- hosts: all\n  gather_facts: false\n  tasks:\n" + tasks, encoding="utf-8")
            journal.transition("RUNNING", "running")
            yield release, journal, manifest
        finally:
            if controller_lock is not None:
                os.close(controller_lock)
            if Path(journal.directory).exists():
                shutil.rmtree(journal.directory)
            shutil.rmtree(release)

    def dispatch(self, release, journal, manifest, expected="SUCCEEDED"):
        stopped = [False]
        expired = threading.Event()

        def timeout():
            expired.set()
            stopped[0] = True

        timer = threading.Timer(45, timeout)
        timer.start()
        try:
            try:
                state = execution_controller._dispatch(release, journal, manifest, stopped)
                code = ""
            except execution_lifecycle.LifecycleError as error:
                # _dispatch raises; the controller's outer lifecycle owns the
                # FAILED terminal. Exercise the same boundary without retain(),
                # which could prune journals belonging to unrelated QA runs.
                self.assertEqual("EXECUTION_OPERATION_FAILED", str(error))
                state, code = "FAILED", str(error)
            self.assertFalse(expired.is_set(), "real Ansible acceptance exceeded 45s")
            self.assertEqual(expected, state)
            result = journal.terminal(state, code, "QA trusted operation completed")
            self.assertEqual(result, journal.terminal(state, code, "QA duplicate completion"))
        finally:
            timer.cancel()
            timer.join()
        events = journal.events()
        self.assertEqual(list(range(1, len(events) + 1)), [event["sequence"] for event in events])
        # Existing lifecycle transitions use DIAGNOSTIC, including terminal
        # transitions; do not invent a RUN_COMPLETED production contract here.
        terminals = [event for event in events if event["eventType"] == "DIAGNOSTIC" and event["status"] in ("SUCCESS", "FAILED", "CANCELLED", "INTERRUPTED")]
        self.assertEqual(1, len(terminals))
        self.assertEqual(events[-1], terminals[0])
        self.assertEqual("SUCCESS" if expected == "SUCCEEDED" else "FAILED", terminals[0]["status"])
        self.assertEqual(expected, journal.status()["state"])
        self.assertEqual(expected, json.loads(Path(journal.result_path).read_text(encoding="utf-8"))["state"])
        validator = SchemaValidator(CONTRACTS)
        for event in events:
            self.assertEqual([], validator.validate(event, CONTRACTS / "event" / "v1alpha1" / "schema.json"))
        return events

    def assert_no_payload(self, journal, *sentinels):
        serialized = Path(journal.events_path).read_text(encoding="utf-8")
        serialized += Path(journal.result_path).read_text(encoding="utf-8")
        for forbidden in sentinels + ('"_result"', '"args"', '"vars"', '"stdout"', '"stderr"', '"diff"', '"invocation"', '"cmd"'):
            self.assertNotIn(forbidden, serialized)

    def test_real_ansible_callback_streams_multi_host_results_through_controller(self):
        tasks = "    - name: Safe multi-host task\n      ansible.builtin.debug:\n        msg: safe\n    - name: Safe skipped task\n      ansible.builtin.debug:\n        msg: skipped\n      when: false\n    - name: Safe changed result\n      ansible.builtin.debug:\n        msg: safe\n      changed_when: true\n"
        with self.runtime(tasks) as (release, journal, manifest):
            events = self.dispatch(release, journal, manifest)
            task_events = [event for event in events if event["eventType"].startswith("TASK_")]
            self.assertTrue(task_events)
            starts = [event for event in task_events if event["eventType"] == "TASK_STARTED"]
            completions = [event for event in task_events if event["eventType"] == "TASK_COMPLETED"]
            self.assertEqual(3, len(starts))
            self.assertEqual(6, len(completions))
            self.assertTrue(all("host" not in event for event in starts))
            multi_host = {}
            for event in completions:
                multi_host.setdefault(event["task"]["uuid"], set()).add(event.get("host"))
            self.assertTrue(any(hosts == {"node1", "node2"} for hosts in multi_host.values()))
            self.assertEqual({"SUCCESS", "CHANGED", "SKIPPED"}, {event["status"] for event in completions})
            self.assertTrue(all("elapsedMilliseconds" in event for event in completions))

    def test_real_no_log_success_and_failure_redact_task_identity_and_payload(self):
        for module, expected, task_status in (("debug", "SUCCEEDED", "SUCCESS"), ("fail", "FAILED", "FAILED")):
            with self.subTest(module=module):
                tasks = (
                    '    - name: "{{ qa_private_name }}"\n'
                    '      vars:\n'
                    '        qa_private_name: qa-no-log-rendered-name\n'
                    '      no_log: true\n'
                    '      ansible.builtin.%s:\n'
                    '        msg: qa-no-log-private-payload\n' % module
                )
                with self.runtime(tasks) as (release, journal, manifest):
                    events = self.dispatch(release, journal, manifest, expected)
                    details = [event for event in events if event["eventType"].startswith("TASK_")]
                    starts = [event for event in details if event["eventType"] == "TASK_STARTED"]
                    results = [event for event in details if event["eventType"] == "TASK_COMPLETED"]
                    self.assertEqual(1, len(starts))
                    self.assertEqual(2, len(results))
                    self.assertEqual({"node1", "node2"}, {event["host"] for event in results})
                    self.assertEqual({task_status}, {event["status"] for event in results})
                    for event in details:
                        self.assertEqual(starts[0]["task"]["uuid"], event["task"]["uuid"])
                        self.assertNotIn("name", event["task"])
                        self.assertEqual({"applied": True, "fields": ["task.name"]}, event["redaction"])
                        self.assertIn(event["safeMessage"], ("Ansible task started", "Ansible task completed"))
                    for event in results:
                        self.assertGreaterEqual(event["elapsedMilliseconds"], 0)
                        if expected == "FAILED":
                            self.assertEqual({"code": "ANSIBLE_TASK_FAILED", "summary": "Ansible task failed"}, event["error"])
                    self.assert_no_payload(journal, "qa-no-log-rendered-name", "qa_private_name", "qa-no-log-private-payload")

    def test_real_task_failure_preserves_safe_failed_result_and_one_terminal(self):
        tasks = "    - name: Safe expected failure\n      ansible.builtin.fail:\n        msg: qa-private-failure-payload\n"
        with self.runtime(tasks) as (release, journal, manifest):
            events = self.dispatch(release, journal, manifest, "FAILED")
            results = [event for event in events if event["eventType"] == "TASK_COMPLETED"]
            self.assertEqual(2, len(results))
            self.assertEqual({"node1", "node2"}, {event["host"] for event in results})
            for event in results:
                self.assertEqual("FAILED", event["status"])
                self.assertEqual("Safe expected failure", event["task"]["name"])
                self.assertEqual({"code": "ANSIBLE_TASK_FAILED", "summary": "Ansible task failed"}, event["error"])
            self.assertFalse(any(event["eventType"] == "ACTION_COMPLETED" for event in events))
            self.assert_no_payload(journal, "qa-private-failure-payload")

    def test_real_ansible_succeeds_when_callback_or_detail_writer_fails(self):
        for fault in ("callback_exception", "detail_writer_failure", "tiny_capacity"):
            with self.subTest(fault=fault):
                tasks = "    - name: Safe first task\n      ansible.builtin.debug:\n        msg: safe\n    - name: Safe last task\n      ansible.builtin.debug:\n        msg: safe\n"
                with self.runtime(tasks, callback_fault=fault) as (release, journal, manifest):
                    events = self.dispatch(release, journal, manifest)
                    self.assertTrue(Path(release, "fault-exercised").is_file())
                    diagnostics = [event for event in events if event["eventType"] == "DIAGNOSTIC" and event.get("error", {}).get("code", "").startswith("TASK_EVENT_STREAM_")]
                    # Repeated failed writes must coalesce. Exactly one is
                    # stronger than at-most-one and proves injection was seen.
                    self.assertEqual(1, len(diagnostics))
                    code = "TASK_EVENT_STREAM_TRUNCATED" if fault == "tiny_capacity" else "TASK_EVENT_STREAM_DEGRADED"
                    self.assertEqual(code, diagnostics[0]["error"]["code"])
                    self.assertEqual("RUNNING", diagnostics[0]["status"])
                    self.assertEqual("verify:qa", diagnostics[0]["actionId"])
                    self.assertEqual("ACTION_COMPLETED", events[-2]["eventType"])
                    self.assertEqual("SUCCESS", events[-2]["status"])
                    details = [event for event in events if event["eventType"].startswith("TASK_")]
                    self.assertEqual(1 if fault == "tiny_capacity" else 0, len(details))
                    self.assertLessEqual(len(events), 8)
                    self.assertIsNone(journal.emit_task_observability_diagnostic(actionId="verify:qa"))
                    self.assertEqual(events, journal.events())
                    self.assert_no_payload(journal, "qa-private-injection-payload")

if __name__ == "__main__":
    unittest.main()

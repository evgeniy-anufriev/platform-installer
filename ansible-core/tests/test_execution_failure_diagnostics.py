import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import execution_controller as controller
from execution_lifecycle import Journal
from test_execution_lifecycle import metadata


def failure(message, **extra):
    return b'fatal: [node1]: FAILED! => ' + json.dumps(dict(msg=message, **extra)).encode()


class FailureDiagnosticTests(unittest.TestCase):
    def test_structured_scram_failure_reaches_operation_and_journal(self):
        secret = 'SYNTHETIC_SECRET_NOT_FOR_JOURNAL'
        record = dict(code='APPLICATION_KAFKA_SCRAM_READ_FAILED', rc=1,
                      reason='TIMEOUT', partial_count=2, elapsed_ms=73733)
        self.assertEqual(record['code'], controller._operation_error_code(failure(record)))
        from execution_task_error import safe_task_error
        error = safe_task_error(dict(msg=record, stdout=secret))
        with tempfile.TemporaryDirectory() as root:
            from test_execution_task_observability import _active_journal
            journal = _active_journal(root)
            journal.emit_operation_failure_diagnostic(controller._operation_error_code(failure(record)))
            journal.task_event('TASK_COMPLETED', 'FAILED', 'scram-probe', host='node1',
                               name='SCRAM read', failure_result=dict(msg=record, stdout=secret))
            events = Path(journal.directory, 'events.jsonl').read_text()
            self.assertIn(record['code'], events)
            self.assertIn('reason=TIMEOUT', events)
            self.assertNotIn(secret, events)
        self.assertIn('reason=TIMEOUT', error['summary'])
        self.assertIn('partial_count=2', error['summary'])
        self.assertNotIn(secret, json.dumps(error))

    def test_closed_classes(self):
        cases = {
            "Timeout waiting for privilege escalation prompt": "ANSIBLE_BECOME_TIMEOUT",
            "Missing sudo password": "ANSIBLE_BECOME_FAILED",
            "Permission denied (publickey)": "ANSIBLE_SSH_AUTH_FAILED",
            "Connection timed out": "ANSIBLE_CONNECTION_TIMEOUT",
            "Connection reset by peer": "ANSIBLE_CONNECTION_LOST",
            "Read-only file system": "ANSIBLE_FILESYSTEM_READ_ONLY",
            "No space left on device": "ANSIBLE_FILESYSTEM_FULL",
            "Permission denied": "ANSIBLE_PERMISSION_DENIED",
            "unknown failure SYNTHETIC_SECRET": "ANSIBLE_FAILURE_UNCLASSIFIED",
        }
        for message, expected in cases.items():
            with self.subTest(expected=expected):
                self.assertEqual(expected, controller._operation_error_code(failure(message)))

    def test_final_failure_only_and_no_success_inference(self):
        self.assertEqual("", controller._operation_error_code(b'ok: [node1] => {"msg":"permission denied"}'))
        self.assertEqual("ANSIBLE_FAILURE_UNCLASSIFIED", controller._operation_error_code(
            failure("permission denied") + b'\n' + failure("other")))
        self.assertEqual("ANSIBLE_CONNECTION_TIMEOUT", controller._operation_error_code(
            failure("Connection timed out").replace(b'FAILED!', b'UNREACHABLE!')))

    def test_explicit_core_code_precedence_preserved(self):
        self.assertEqual("CORE_EXPLICIT_FAILURE", controller._operation_error_code(
            b'error_code=CORE_EXPLICIT_FAILURE\n' + failure("permission denied")))

    def test_managed_data_path_guard_codes_are_allowlisted_and_secret_safe(self):
        secret = "SYNTHETIC_SECRET_NOT_FOR_JOURNAL"
        for expected in controller._SAFE_TASK_DIAGNOSTIC_CODES:
            with self.subTest(expected=expected):
                self.assertEqual(expected, controller._operation_error_code(
                    failure(expected + " password=" + secret)))
        for untrusted in (
                "MANAGED_DATA_PATH_STAT_FAILED_SECRET_VALUE=" + secret,
                "MANAGED_DATA_PATH_STAT_FAILED_PERMISSION_DENIED_secret=" + secret,
                "MANAGED_DATA_PATH_STAT_FAILED_PERMISSION_DENIED-extra=" + secret,
                "prefix-MANAGED_DATA_PATH_STAT_FAILED_PERMISSION_DENIED=" + secret):
            with self.subTest(untrusted=untrusted.split("=")[0]):
                self.assertEqual("ANSIBLE_FAILURE_UNCLASSIFIED", controller._operation_error_code(
                    failure(untrusted)))

        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            journal.initialize(metadata())
            expected = "MANAGED_DATA_PATH_STAT_FAILED_PERMISSION_DENIED"
            journal.emit_operation_failure_diagnostic(controller._operation_error_code(
                failure(expected + " password=" + secret)))
            events = Path(journal.directory, 'events.jsonl').read_text()
            self.assertIn(expected, events)
            self.assertNotIn(secret, events)
            self.assertNotIn("password=", events)

    def test_redaction_and_malformed_results(self):
        for extra in ({"_ansible_no_log": True}, {"censored": "hidden"}):
            self.assertEqual("ANSIBLE_FAILURE_REDACTED", controller._operation_error_code(
                failure("permission denied SYNTHETIC_SECRET", **extra)))
        for result in (b'{', b'null', b'[]', b'{"msg":42}', b'\xff'):
            self.assertEqual("ANSIBLE_FAILURE_UNCLASSIFIED", controller._operation_error_code(
                b'fatal: [node1]: FAILED! => ' + result))
        self.assertEqual("", controller._operation_error_code(None))

    def test_capture_bound(self):
        old = failure("permission denied") + b'\n' + b'x' * controller.MAX_OPERATION_FAILURE_CAPTURE_BYTES
        self.assertEqual("", controller._operation_error_code(old))

    def test_real_child_drain_and_safe_journal(self):
        secret = "SYNTHETIC_SECRET_NOT_FOR_JOURNAL"
        text = failure("Permission denied " + secret).decode() + '\n'
        child = subprocess.Popen([sys.executable, '-c', 'import sys;sys.stdout.write(%r);sys.exit(2)' % text],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        status, code, raw_output = controller._wait_for_operation(child, [False])
        self.assertEqual((2, "ANSIBLE_PERMISSION_DENIED"), (status, code))
        self.assertIsNone(raw_output)
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            journal.initialize(metadata())
            journal.emit_operation_failure_diagnostic(code)
            events = Path(journal.directory, 'events.jsonl').read_text()
            self.assertIn(code, events)
            self.assertNotIn(secret, events)
            self.assertNotIn('fatal:', events)

    def test_raw_failure_capture_is_project_scoped_and_private(self):
        project_identity = metadata()["projectIdentity"]
        with tempfile.TemporaryDirectory() as root:
            release = Path(root, "release")
            marker = release / "runtime" / "diagnostics" / "capture-raw-ansible-output-for-project"
            marker.parent.mkdir(parents=True)
            marker.write_text(project_identity + "\n", encoding="ascii")
            first = Journal(root, "run-first")
            first.initialize(metadata(run_id="run-first"))
            second = Journal(root, "run-second")
            second.initialize(metadata(run_id="run-second"))
            self.assertTrue(controller._claim_raw_ansible_failure_capture(str(release), first, project_identity))
            self.assertTrue(controller._raw_failure_capture_authorized(first, project_identity, "run-first"))
            self.assertFalse(controller._raw_failure_capture_authorized(first, project_identity, "run-second"))
            self.assertFalse(controller._claim_raw_ansible_failure_capture(str(release), second, project_identity))
            self.assertFalse(controller._raw_failure_capture_authorized(second, project_identity, "run-second"))
            marker.write_text("another-project\n", encoding="ascii")
            third_root = Path(root, "other-state")
            third_root.mkdir()
            third = Journal(str(third_root), "run-third")
            third.initialize(metadata(run_id="run-third"))
            self.assertFalse(controller._claim_raw_ansible_failure_capture(str(release), third, project_identity))

        secret = "SYNTHETIC_SECRET_RAW_CAPTURE_TEST"
        text = failure("opaque failure " + secret).decode() + "\n"
        child = subprocess.Popen([sys.executable, '-c', 'import sys;sys.stdout.write(%r);sys.exit(2)' % text],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        status, code, raw_output = controller._wait_for_operation(child, [False], capture_failed_output=True)
        self.assertEqual((2, "ANSIBLE_FAILURE_UNCLASSIFIED"), (status, code))
        self.assertIn(secret.encode(), raw_output)
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-raw")
            journal.initialize(metadata(run_id="run-raw"))
            release = Path(root, "release")
            marker = release / "runtime" / "diagnostics" / "capture-raw-ansible-output-for-project"
            marker.parent.mkdir(parents=True)
            marker.write_text(metadata()["projectIdentity"] + "\n", encoding="ascii")
            self.assertTrue(controller._claim_raw_ansible_failure_capture(
                str(release), journal, metadata()["projectIdentity"]))
            operation = {"operationId": "safe-operation-id"}
            controller._write_private_failure_output(journal, operation, raw_output)
            captures = list(Path(journal.directory, "raw-ansible-diagnostics").glob("*.log"))
            self.assertEqual(1, len(captures))
            self.assertEqual(0o600, os.stat(captures[0]).st_mode & 0o777)
            self.assertIn(secret.encode(), captures[0].read_bytes())

    def test_raw_failure_capture_is_bounded_to_tail(self):
        marker = "FINAL_DIAGNOSTIC_MARKER"
        size = controller.MAX_RAW_OPERATION_FAILURE_CAPTURE_BYTES + 4096
        script = 'import sys;sys.stdout.write("x" * %d + %r);sys.exit(2)' % (size, marker)
        child = subprocess.Popen([sys.executable, '-c', script],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        status, _, raw_output = controller._wait_for_operation(child, [False], capture_failed_output=True)
        self.assertEqual(2, status)
        self.assertEqual(controller.MAX_RAW_OPERATION_FAILURE_CAPTURE_BYTES, len(raw_output))
        self.assertTrue(raw_output.endswith(marker.encode()))
        with tempfile.TemporaryDirectory() as root:
            project_identity = metadata()["projectIdentity"]
            journal = Journal(root, "run-bounded")
            journal.initialize(metadata(run_id="run-bounded"))
            release = Path(root, "release")
            permit = release / "runtime" / "diagnostics" / "capture-raw-ansible-output-for-project"
            permit.parent.mkdir(parents=True)
            permit.write_text(project_identity + "\n", encoding="ascii")
            self.assertTrue(controller._claim_raw_ansible_failure_capture(str(release), journal, project_identity))
            controller._write_private_failure_output(journal, {"operationId": "bounded-operation"}, raw_output)
            capture = next(Path(journal.directory, "raw-ansible-diagnostics").glob("*.log"))
            self.assertEqual(controller.MAX_RAW_OPERATION_FAILURE_CAPTURE_BYTES, capture.stat().st_size)
            self.assertEqual(0o600, os.stat(capture).st_mode & 0o777)
            self.assertTrue(capture.read_bytes().endswith(marker.encode()))

    def test_raw_output_is_discarded_for_success_and_cancellation(self):
        success = subprocess.Popen([sys.executable, '-c', 'import sys;sys.stdout.write("SUCCESS_SECRET");sys.exit(0)'],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        status, _, raw_output = controller._wait_for_operation(success, [False], capture_failed_output=True)
        self.assertEqual(0, status)
        self.assertIsNone(raw_output)

        cancelled = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(30)'],
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.assertIsNone(controller._wait_for_operation(cancelled, [True], capture_failed_output=True))


if __name__ == '__main__':
    unittest.main()

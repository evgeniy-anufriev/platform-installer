import json
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
        status, code = controller._wait_for_operation(child, [False])
        self.assertEqual((2, "ANSIBLE_PERMISSION_DENIED"), (status, code))
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, "run-1")
            journal.initialize(metadata())
            journal.emit_operation_failure_diagnostic(code)
            events = Path(journal.directory, 'events.jsonl').read_text()
            self.assertIn(code, events)
            self.assertNotIn(secret, events)
            self.assertNotIn('fatal:', events)


if __name__ == '__main__':
    unittest.main()

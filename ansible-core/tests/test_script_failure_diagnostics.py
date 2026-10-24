"""Script output is untrusted; only numeric diagnostics reach the journal."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils'))
sys.path.insert(0, str(ROOT / 'ansible-core/tools'))
from application_credentials import script_failure
from execution_task_error import safe_task_error


class ScriptFailureDiagnosticsTests(unittest.TestCase):
    def test_failure_is_persisted_in_existing_journal_without_raw_output(self):
        from test_execution_task_observability import _active_journal
        with tempfile.TemporaryDirectory() as root:
            journal = _active_journal(root)
            diagnostic = script_failure({'rc': 1, 'stdout': '{"status":"error","step":12,"http_status":409}'})
            event = journal.task_event('TASK_COMPLETED', 'FAILED', 'script-1',
                                      name='package script probe', failure_result={
                                          'msg': diagnostic, 'stderr': 'private-token'})
            self.assertEqual('APPLICATION_SCRIPT_EXECUTION_FAILED', event['error']['code'])
            persisted = Path(journal.directory, 'events.jsonl').read_text()
            self.assertIn('http_status=409', persisted)
            self.assertNotIn('private-token', persisted)

    def test_safe_failure_survives_journal_projection(self):
        failure = script_failure({'rc': 1, 'stdout': json.dumps({
            'status': 'error', 'step': 12, 'http_status': 409, 'curl_exit': 0,
            'password': 'private-password'}), 'stderr': 'private-token'})
        event = safe_task_error({'msg': failure, 'stderr': 'private-token'})
        self.assertEqual('APPLICATION_SCRIPT_EXECUTION_FAILED', event['code'])
        self.assertIn('step=12; http_status=409; curl_exit=0', event['summary'])
        self.assertNotIn('private', json.dumps(event))
        self.assertEqual('ANSIBLE_FAILURE_REDACTED', safe_task_error({'msg': failure}, True)['code'])

    def test_arbitrary_or_malformed_text_is_withheld(self):
        for output in ('private-password', '[]', '{', 'x' * 2049,
                       '{"status":"error","step":"private-token","http_status":true,"curl_exit":999}'):
            result = script_failure({'rc': 124, 'stdout': output})
            self.assertEqual({'code': 'APPLICATION_SCRIPT_EXECUTION_FAILED', 'rc': 124}, result)

    def test_projection_revalidates_numeric_fields(self):
        event = safe_task_error({'msg': {'code': 'APPLICATION_SCRIPT_EXECUTION_FAILED',
                                      'step': 'private-password', 'http_status': 9999,
                                      'curl_exit': True, 'raw': 'private-token'}})
        self.assertNotIn('private', json.dumps(event))
        self.assertNotIn('http_status=', event['summary'])


if __name__ == '__main__':
    unittest.main()

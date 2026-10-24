import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from execution_task_error import safe_task_error


class TaskErrorTests(unittest.TestCase):
    def test_vault_write_code_is_public_without_private_response(self):
        value = safe_task_error({'msg': 'APPLICATION_VAULT_DOCUMENT_WRITE_FAILED',
                                 'stdout': 'private-token', 'body': 'private-password'})
        self.assertEqual('APPLICATION_VAULT_DOCUMENT_WRITE_FAILED', value['code'])
        self.assertNotIn('private', json.dumps(value))

    def test_known_core_code_without_payload_or_secrets(self):
        code = 'APPLICATION_RUNTIME_DEFERRED_FEATURE'
        for field in ('msg', 'code', 'error_code'):
            result = {field: code, 'stdout': 'private-password', 'invocation': 'private-token'}
            self.assertEqual(code, safe_task_error(result)['code'])
            self.assertNotIn('private', json.dumps(safe_task_error(result)))
            self.assertEqual('ANSIBLE_FAILURE_REDACTED', safe_task_error(result, True)['code'])

    def test_core_code_must_be_exact_and_known(self):
        for value in ('APPLICATION_PRIVATE_PASSWORD', 'APPLICATION_RUNTIME_DEFERRED_FEATURE private',
                      'private APPLICATION_RUNTIME_DEFERRED_FEATURE'):
            self.assertEqual('ANSIBLE_TASK_FAILED', safe_task_error({'msg': value})['code'])

    def test_controller_promotes_only_known_code_from_failure_record(self):
        from execution_controller import _operation_error_code
        code = 'APPLICATION_RUNTIME_DEFERRED_FEATURE'
        payload = {'msg': code, 'stdout': 'private-password'}
        line = ('fatal: [localhost]: FAILED! => ' + json.dumps(payload)).encode()
        self.assertEqual(code, _operation_error_code(line))
        payload['_ansible_no_log'] = True
        line = ('fatal: [localhost]: FAILED! => ' + json.dumps(payload)).encode()
        self.assertEqual('ANSIBLE_FAILURE_REDACTED', _operation_error_code(line))

    def test_failure_reason_and_exit_code_without_secret_text(self):
        error = safe_task_error({'msg': 'No space left on device password=private', 'rc': 2, 'stdout': 'private'})
        self.assertEqual('ANSIBLE_FILESYSTEM_FULL', error['code'])
        self.assertIn('exit code 2', error['summary'])
        self.assertNotIn('private', json.dumps(error))

    def test_no_log_never_classifies_or_emits_exit_status(self):
        for result in ({'_ansible_no_log': True}, {'censored': 'private'}):
            result.update(msg='No space left on device private', rc=42)
            error = safe_task_error(result)
            self.assertEqual('ANSIBLE_FAILURE_REDACTED', error['code'])
            self.assertNotIn('42', json.dumps(error))
            self.assertNotIn('private', json.dumps(error))

    def test_unknown_payload_and_injected_code_are_not_promoted(self):
        for result in (None, {'msg': 'private', 'error_code': 'PRIVATE_TOKEN', 'rc': True}):
            error = safe_task_error(result)
            self.assertEqual('ANSIBLE_TASK_FAILED', error['code'])
            self.assertNotIn('PRIVATE_TOKEN', json.dumps(error))

    def test_assertion_and_unreachable_have_distinct_codes(self):
        self.assertEqual('ANSIBLE_ASSERTION_FAILED', safe_task_error({'assertion': 'private'})['code'])
        self.assertEqual('ANSIBLE_HOST_UNREACHABLE', safe_task_error({'unreachable': True})['code'])

    def test_loop_failure_classifies_nested_message_without_emitting_it(self):
        result = {'msg': 'One or more items failed', 'results': [
            {'failed': False, 'msg': 'permission denied'},
            {'failed': True, 'msg': 'Could not find or access private-path private-password'}]}
        error = safe_task_error(result)
        self.assertEqual('ANSIBLE_FILE_NOT_FOUND', error['code'])
        self.assertNotIn('private', json.dumps(error))
        result['_ansible_no_log'] = True
        self.assertEqual('ANSIBLE_FAILURE_REDACTED', safe_task_error(result)['code'])


if __name__ == '__main__':
    unittest.main()

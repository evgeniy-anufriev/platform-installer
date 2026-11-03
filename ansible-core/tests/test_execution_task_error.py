import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from execution_task_error import safe_task_error


class TaskErrorTests(unittest.TestCase):
    def test_http_health_failure_reasons_and_status_survive_loop_without_secret_text(self):
        for message, status, code in (
            ('Request failed: <urlopen error [Errno 111] Connection refused>', -1, 'ANSIBLE_CONNECTION_REFUSED'),
            ('Request failed: <urlopen error timed out>', -1, 'ANSIBLE_CONNECTION_TIMEOUT'),
            ('The read operation timed out', -1, 'ANSIBLE_CONNECTION_TIMEOUT'),
            ('Name or service not known', -1, 'ANSIBLE_DNS_RESOLUTION_FAILED'),
            ('IP address mismatch, certificate is not valid for 192.0.2.1', -1, 'ANSIBLE_TLS_HOSTNAME_MISMATCH'),
            ('certificate has expired', -1, 'ANSIBLE_TLS_CERTIFICATE_EXPIRED'),
            ('certificate is not yet valid', -1, 'ANSIBLE_TLS_CERTIFICATE_NOT_YET_VALID'),
            ('unable to get local issuer certificate', -1, 'ANSIBLE_TLS_CA_UNTRUSTED'),
            ('ca_path option must be a valid file', -1, 'ANSIBLE_TLS_CA_FILE_INVALID'),
            ('[SSL: WRONG_VERSION_NUMBER] wrong version number', -1, 'ANSIBLE_TLS_HANDSHAKE_FAILED'),
            ('No route to host', -1, 'ANSIBLE_NETWORK_UNREACHABLE'),
            ('Status code was 502 and not [200]', 502, 'ANSIBLE_HTTP_REQUEST_FAILED'),
            ('unclassified private exception', -1, 'ANSIBLE_HTTP_REQUEST_FAILED'),
        ):
            with self.subTest(code=code, message=message):
                child = {'failed': True, 'msg': message + ' private-canary', 'status': status,
                         'content': 'private-body', 'invocation': {'headers': {'X-Vault-Token': 'private-token'}}}
                result = {'msg': 'One or more items failed', 'results': [child]}
                error = safe_task_error(result)
                self.assertEqual(code, error['code'])
                self.assertIn('HTTP status ' + str(status), error['summary'])
                self.assertNotIn('private', json.dumps(error))
                self.assertEqual('ANSIBLE_FAILURE_REDACTED', safe_task_error(result, True)['code'])
        self.assertEqual('ANSIBLE_TASK_FAILED', safe_task_error({'msg': 'checksum does not match private-canary'})['code'])

    def test_dynamic_quorum_failure_has_fixed_russian_diagnostic(self):
        error = safe_task_error({'msg': {'code': 'KAFKA_DYNAMIC_QUORUM_UNSUPPORTED',
                                        'message': 'private-untrusted-output'},
                                 'stdout': 'private-secret'})
        self.assertEqual('KAFKA_DYNAMIC_QUORUM_UNSUPPORTED', error['code'])
        self.assertIn('quorumMode=static', error['summary'])
        self.assertIn('Дистрибутив Kafka', error['summary'])
        self.assertNotIn('private', json.dumps(error))
        self.assertEqual('ANSIBLE_FAILURE_REDACTED', safe_task_error(
            {'msg': {'code': error['code']}}, no_log=True)['code'])

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

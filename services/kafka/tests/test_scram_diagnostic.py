import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('scram_diagnostic', Path(__file__).resolve().parents[1] / 'ansible_collections/platform/kafka/plugins/filter/scram_diagnostic.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
sys.path.insert(0, str(ROOT / 'ansible-core/tools'))
from execution_task_error import safe_task_error, core_error_code


class ScramDiagnosticTests(unittest.TestCase):
    def test_categories_and_safe_projection(self):
        for text, reason in (
            ('TimeoutException', 'TIMEOUT'), ('SSLHandshakeException', 'TLS'),
            ('SaslAuthenticationException', 'AUTHENTICATION'),
            ('ClusterAuthorizationException', 'AUTHORIZATION'),
            ('Connection refused', 'CONNECTION'), ('unknown', 'CLI_FAILURE'),
            ('Error retrieving SCRAM credential configs private', 'PARTIAL_METADATA'),
        ):
            result = module.scram_read_diagnostic(dict(rc=1, stdout=text, stderr='SECRET_SENTINEL', delta='0:01:13.733000', argv=['SECRET_SENTINEL']))
            self.assertEqual(reason, result['reason'])
            self.assertEqual(73733, result['elapsed_ms'])
            error = safe_task_error({'msg': result, 'stdout': 'SECRET_SENTINEL'})
            self.assertEqual('APPLICATION_KAFKA_SCRAM_READ_FAILED', error['code'])
            self.assertIn('reason=' + reason, error['summary'])
            self.assertNotIn('SECRET_SENTINEL', json.dumps([result, error]))
            self.assertEqual(result['code'], core_error_code({'msg': result}))

    def test_rc_zero_partial_and_signed_rc(self):
        result = module.scram_read_diagnostic({'rc': 0, 'stdout': 'Error retrieving SCRAM credential configs secret'})
        self.assertEqual(1, result['partial_count'])
        self.assertEqual(0, result['rc'])
        result = module.scram_read_diagnostic({'rc': -9})
        self.assertIn('rc=-9', safe_task_error({'msg': result})['summary'])

    def test_untrusted_fields_cannot_escape(self):
        for value in (None, [], {'rc': True, 'stderr': [], 'delta': 'private'}, {'rc': 9999999, 'delta': '0:90:00'}):
            result = module.scram_read_diagnostic(value)
            self.assertEqual(-1, result['rc'])
            self.assertNotIn('elapsed_ms', result)
        result = safe_task_error({'msg': dict(code='APPLICATION_KAFKA_SCRAM_READ_FAILED', reason='SECRET_SENTINEL', rc=True, elapsed_ms=9999999999)})
        self.assertNotIn('SECRET_SENTINEL', json.dumps(result))
        self.assertNotIn('rc=', result['summary'])
        self.assertNotIn('elapsed_ms=', result['summary'])


if __name__ == '__main__':
    unittest.main()

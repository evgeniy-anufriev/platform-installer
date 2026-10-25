"""Approved library order reaches native selection even without skipped libraries."""
import copy
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_application_plan import CONTROLLER, LEASE, Journal, DIGEST

ROOT = Path(__file__).resolve().parents[2]


class ApplicationExecutionOrderTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('ansible-playbook'), 'native Ansible required')
    def test_controller_projection_native_selection_preserves_full_and_partial_order(self):
        libraries = {
            'consumer': {'instances': {'frontend': {'connections': {'sso': {
                'serviceType': 'application', 'libraryId': 'provider', 'applicationId': 'identity', 'startupPriority': 0}}}}},
            'provider': {'instances': {'identity': {'startupPriority': 0, 'connections': {}}}},
        }
        for skipped, remove_order in ((False, False), (True, False), (False, True)):
            with self.subTest(skipped=skipped, remove_order=remove_order), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                journal = Journal(str(root), 'run-order')
                Path(journal.directory).mkdir(parents=True)
                (Path(journal.directory)/'runtime-projection.json').write_text(json.dumps({'platform_pki_secret_files': {}}))
                operation = {'operation': 'APPLICATION_LIBRARIES_APPLY', 'operationId': 'applications:apply',
                             'applicationLibraries': ['consumer'] if skipped else ['provider', 'consumer'],
                             'applicationSemanticFingerprint': DIGEST}
                if skipped:
                    from application_selection import execution_scope
                    operation['applicationExecutionScope'] = execution_scope({'applicationLibraries': {'libraries': libraries}},
                                                                             ['provider', 'consumer'], ['provider'])
                manifest = {'operations': [operation], 'applicationSecretRequirements': [], 'runtimeSecretRequirements': []}
                with mock.patch.object(LEASE, 'application_secret_values_for_operation', return_value={}):
                    CONTROLLER._materialize_application_projection(journal, manifest)
                projection = json.loads((Path(journal.directory)/('.runtime-projection-'+hashlib.sha256(b'applications:apply').hexdigest()+'.json')).read_text())
                if remove_order:
                    del projection['platform_application_library_order']
                projection['fixture_snapshot'] = {'snapshot': {'applicationLibraries': {'libraries': copy.deepcopy(libraries)}}}
                (root/'vars.json').write_text(json.dumps(projection))
                (root/'play.yml').write_text('''
- hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - platform.core.prepare_application_selection:
        snapshot_result: "{{ fixture_snapshot }}"
      register: selected
    - ansible.builtin.assert:
        that:
          - selected.status == 'PASS'
          - selected.scope.libraryOrder == ['provider', 'consumer']
          - selected.prepared.snapshot.applicationLibraries.libraries | dict2items | selectattr('key', 'in', selected.scope.installLibraries) | items2dict | platform.core.application_connection_order_findings(selected.scope.libraryOrder) | length == 0
''')
                result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(root/'play.yml'), '-e', '@'+str(root/'vars.json')],
                                        env=dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(ROOT/'ansible-core/collections')),
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
                if remove_order:
                    self.assertNotEqual(0, result.returncode, 'Missing approved order must reproduce the native failure')
                else:
                    self.assertEqual(0, result.returncode, result.stdout[-2000:]+result.stderr[-1000:])


if __name__ == '__main__':
    unittest.main()

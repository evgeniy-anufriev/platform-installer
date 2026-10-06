import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml

CORE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE / 'tools'))
import execution_controller as controller
from execution_lifecycle import LifecycleError

TAG = 'platform_installer_pki_materialization'


class DispatchTests(unittest.TestCase):
    def dispatch(self, operations, outcomes, commands, stopped=None):
        with tempfile.TemporaryDirectory() as root:
            journal = mock.Mock(root=root, run_id='run-test', directory=os.path.join(root, 'run-test'))
            journal.metadata.return_value = {'projectIdentity': 'dispatch-test-project'}
            with mock.patch.object(controller, '_command', side_effect=lambda _r, _j, op: ['ansible-playbook', op['operationId']]), \
                 mock.patch.object(controller, '_environment', return_value={}), \
                 mock.patch.object(controller.execution_target_trust, 'verify', return_value='/run/known_hosts'), \
                 mock.patch.object(controller.execution_secret_lease, 'ansible_connection_credentials_for_run', return_value=None), \
                 mock.patch.object(controller.subprocess, 'Popen', side_effect=lambda cmd, **kw: commands.append(cmd)), \
                 mock.patch.object(controller, '_wait_for_operation', side_effect=outcomes):
                return controller._dispatch('/release', journal, {'operations': operations}, stopped or [False])

    def test_success_is_local_to_dispatch_and_only_affects_later_apply(self):
        operations = [{'operationId': 'before', 'operation': 'SERVICE_APPLY'},
                      {'operationId': 'pki:apply', 'operation': 'PKI_APPLY'},
                      {'operationId': 'after', 'operation': 'SERVICE_APPLY'},
                      {'operationId': 'verify', 'operation': 'SERVICE_VERIFY'}]
        commands = []
        self.assertEqual('SUCCEEDED', self.dispatch(operations, [(0, '')] * 4, commands))
        self.assertEqual(['ansible-playbook', 'before'], commands[0])
        self.assertEqual(['ansible-playbook', 'pki:apply'], commands[1])
        self.assertEqual(['--skip-tags', TAG], commands[2][-2:])
        self.assertEqual(['ansible-playbook', 'verify'], commands[3])
        fresh = []
        self.dispatch([operations[2]], [(0, '')], fresh)
        self.assertEqual([['ansible-playbook', 'after']], fresh)

    def test_failed_or_cancelled_pki_never_launches_service(self):
        operations = [{'operationId': 'pki:apply', 'operation': 'PKI_APPLY'},
                      {'operationId': 'service', 'operation': 'SERVICE_APPLY'}]
        commands = []
        with self.assertRaises(LifecycleError):
            self.dispatch(operations, [(2, '')], commands)
        self.assertEqual([['ansible-playbook', 'pki:apply']], commands)
        commands = []
        self.assertEqual('CANCELLED', self.dispatch(operations, [None], commands))
        self.assertEqual([['ansible-playbook', 'pki:apply']], commands)

    def test_inherited_tag_overrides_are_not_execution_authority(self):
        with mock.patch.dict(os.environ, {'ANSIBLE_SKIP_TAGS': TAG, 'ANSIBLE_RUN_TAGS': 'wrong'}):
            environment = controller._environment('/release')
        self.assertNotIn('ANSIBLE_SKIP_TAGS', environment)
        self.assertNotIn('ANSIBLE_RUN_TAGS', environment)


@unittest.skipUnless(shutil.which('ansible-playbook') and os.name == 'posix', 'RED OS Ansible required')
class IntegrityTests(unittest.TestCase):
    def test_real_ansible_reuses_repairs_and_blocks_missing_source(self):
        import pwd
        import grp
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source' / 'qa'
            files = ['authorities/ca/ca.crt', 'requests/request/leaf.crt',
                     'requests/request/leaf.key', 'requests/request/keystore.p12',
                     'requests/request/truststore.p12']
            destinations = ['ca-chain.pem', 'certificate.pem', 'private-key.pem',
                            'keystore.p12', 'truststore.p12']
            for index, name in enumerate(files):
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(('fixture-material-%d' % index).encode())
            target = root / 'pki-target'
            plan = {'id': 'plan', 'hostId': 'localhost', 'authorityId': 'ca',
                    'requestId': 'request', 'targetDirectory': str(target),
                    'materializationFingerprint': 'sha256:' + 'a' * 64}
            variables = {'platform_pki_project_id': 'qa', 'platform_pki_state_root': str(root / 'source'),
                         'platform_pki_materialization_plans': [plan],
                         'platform_pki_owner': pwd.getpwuid(os.getuid()).pw_name,
                         'platform_pki_group': grp.getgrgid(os.getgid()).gr_name}
            play = [{'hosts': 'localhost', 'connection': 'local', 'gather_facts': False,
                     'vars': variables, 'roles': ['platform.core.pki_deploy'],
                     'post_tasks': [{'ansible.builtin.copy': {'content': '{{ platform_pki_material_changed | default(false) | bool | to_json }}',
                                                              'dest': str(root / 'changed')}}]}]
            path = root / 'play.yml'
            path.write_text(yaml.safe_dump(play), encoding='utf-8')
            environment = dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(CORE / 'collections'),
                               ANSIBLE_CONFIG=str(CORE / 'ansible.cfg'))
            environment.pop('ANSIBLE_SKIP_TAGS', None)
            environment.pop('ANSIBLE_RUN_TAGS', None)

            def invoke(optimized=True, success=True):
                command = ['ansible-playbook', '-i', 'localhost,', str(path)]
                if optimized:
                    command += ['--skip-tags', TAG]
                result = subprocess.run(command, env=environment, text=True,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
                self.assertEqual(success, result.returncode == 0, result.stdout[-2000:])
                return json.loads((root / 'changed').read_text()) if success else None

            self.assertTrue(invoke(optimized=False))
            original = {name: (target / name).stat().st_mtime_ns for name in destinations}
            self.assertFalse(invoke())
            self.assertEqual(original, {name: (target / name).stat().st_mtime_ns for name in destinations})
            for source_name, destination in zip(files, destinations):
                with self.subTest(corrupt=destination):
                    (target / destination).write_bytes(b'corrupt')
                    self.assertTrue(invoke())
                    self.assertEqual((source / source_name).read_bytes(), (target / destination).read_bytes())
            (target / 'private-key.pem').unlink()
            self.assertTrue(invoke())
            (target / 'materialization-fingerprint').write_text('wrong\n')
            self.assertTrue(invoke())
            self.assertEqual(plan['materializationFingerprint'] + '\n',
                             (target / 'materialization-fingerprint').read_text())
            (target / 'private-key.pem').chmod(0o644)
            self.assertTrue(invoke())
            self.assertEqual(0o600, (target / 'private-key.pem').stat().st_mode & 0o777)
            (target / 'private-key.pem').chmod(0)
            # This isolated test is unprivileged: Ansible copy cannot read the
            # destination to repair it. Failing before activation is required.
            invoke(success=False)
            (target / 'private-key.pem').chmod(0o600)
            (source / files[2]).unlink()
            before = (target / 'private-key.pem').read_bytes()
            invoke(success=False)
            self.assertEqual(before, (target / 'private-key.pem').read_bytes())


if __name__ == '__main__':
    unittest.main()

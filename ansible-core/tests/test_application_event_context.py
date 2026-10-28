"""Public deployment identity in actual Ansible callback events."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import yaml
from test_execution_task_observability import _active_journal, _Task, _Result
from ansible_collections.platform.core.plugins.callback.execution_events_json import CallbackModule

ROOT = Path(__file__).resolve().parents[2]


class ApplicationEventContextTests(unittest.TestCase):
    def test_only_identity_selectors_and_infrastructure_precedence(self):
        task = _Task(no_log=True)
        task.get_vars = lambda: {'application_runtime_job': {'instanceId': 'keycloak', 'password': 'NEVER_LOG_THIS'},
                                 'application_library_id': 'szi'}
        callback = CallbackModule()
        with mock.patch.dict(os.environ, {'PLATFORM_EXECUTION_ACTION_ID': 'applications:apply',
                                          'PLATFORM_EXECUTION_SERVICE_DEPLOYMENT': ''}):
            self.assertEqual('keycloak', callback._context(task)['serviceDeployment'])
            task.get_vars = lambda: {'application_instance_id': 'grant-access', 'application_library_id': 'szi'}
            self.assertEqual('grant-access', callback._context(task)['serviceDeployment'])
            task.get_vars = lambda: {'application_library_id': 'sdku'}
            self.assertEqual('sdku', callback._context(task)['serviceDeployment'])
            task.get_vars = lambda: {'application_library_id': 'invalid/path'}
            self.assertEqual('', callback._context(task)['serviceDeployment'])
            task.get_vars = lambda: {}
            self.assertEqual('', callback._context(task)['serviceDeployment'])
            task.get_vars = lambda: {'application_runtime_job': '{{ missing_variable }}', 'application_library_id': 'szi'}
            self.assertEqual('szi', callback._context(task)['serviceDeployment'])
            with mock.patch.dict(os.environ, {'PLATFORM_EXECUTION_SERVICE_DEPLOYMENT': 'qa-kafka'}):
                self.assertEqual('qa-kafka', callback._context(task)['serviceDeployment'])
            with mock.patch.dict(os.environ, {'PLATFORM_EXECUTION_ACTION_ID': 'apply:qa-kafka'}):
                self.assertEqual('', callback._context(task)['serviceDeployment'])

    @unittest.skipUnless(shutil.which('ansible-playbook'), 'native Ansible required')
    def test_native_instance_library_no_log_skipped_failed_and_no_stale_context(self):
        with tempfile.TemporaryDirectory(prefix='qa-application-context-') as directory:
            root = Path(directory)
            journal = _active_journal(str(root/'state'))
            role = root/'roles'/'contextprobe'/'tasks'
            role.mkdir(parents=True)
            (role/'main.yml').write_text(yaml.safe_dump([
                {'name': 'Instance hidden', 'ansible.builtin.debug': {'msg': 'NEVER_LOG_THIS'}, 'no_log': True},
                {'name': 'Instance skipped', 'ansible.builtin.debug': {'msg': 'safe'}, 'when': False},
                {'name': 'Instance failure', 'ansible.builtin.fail': {'msg': 'NEVER_LOG_THIS'},
                 'no_log': True, 'ignore_errors': True},
            ], sort_keys=False))
            (root/'library.yml').write_text(yaml.safe_dump([
                {'name': 'Library context', 'ansible.builtin.debug': {'msg': 'safe'}},
                {'name': 'Include instance', 'ansible.builtin.include_role': {'name': 'contextprobe'},
                 'vars': {'application_runtime_job': '{{ chosen_job }}'},
                 'loop': [{'instanceId': 'keycloak'}, {'instanceId': 'data-manager-sdku'}],
                 'loop_control': {'loop_var': 'chosen_job'}},
                {'name': 'Library after instances', 'ansible.builtin.debug': {'msg': 'safe'}},
            ], sort_keys=False))
            (root/'play.yml').write_text(yaml.safe_dump([{'hosts': 'targets', 'gather_facts': False, 'tasks': [
                {'name': 'General before', 'ansible.builtin.debug': {'msg': 'safe'}},
                {'name': 'Include library', 'ansible.builtin.include_tasks': str(root/'library.yml'),
                 'loop': ['szi'], 'loop_control': {'loop_var': 'application_library_id'}},
                {'name': 'General after', 'ansible.builtin.debug': {'msg': 'safe'}},
            ]}], sort_keys=False))
            (root/'inventory.yml').write_text(yaml.safe_dump({'all': {'children': {'targets': {'hosts': {
                'first': {'ansible_connection': 'local'}, 'second': {'ansible_connection': 'local'}}}}}}))
            env = dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(ROOT/'ansible-core/collections'),
                       ANSIBLE_CALLBACKS_ENABLED='platform.core.execution_events_json',
                       PLATFORM_EXECUTION_STATE_ROOT=str(root/'state'), PLATFORM_EXECUTION_RUN_ID=journal.run_id,
                       PLATFORM_EXECUTION_ACTION_ID='applications:apply', PLATFORM_EXECUTION_SERVICE_DEPLOYMENT='')
            result = subprocess.run(['ansible-playbook', '-i', str(root/'inventory.yml'), str(root/'play.yml')],
                                    env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(0, result.returncode, (result.stdout+result.stderr)[-1500:])
            raw = Path(journal.events_path).read_text()
            self.assertNotIn('NEVER_LOG_THIS', raw)
            events = [json.loads(line) for line in raw.splitlines()]
            for name in ('General before', 'General after'):
                self.assertTrue(all(not e.get('serviceDeployment') for e in events if e.get('task', {}).get('name') == name))
            for name in ('Library context', 'Library after instances'):
                matched = [e for e in events if e.get('task', {}).get('name') == name]
                self.assertTrue(matched)
                self.assertTrue(all(e.get('serviceDeployment') == 'szi' for e in matched), matched)
            for name in ('Instance hidden', 'Instance skipped', 'Instance failure'):
                matched = [e for e in events if e.get('task', {}).get('name') == name]
                self.assertTrue(matched)
                self.assertEqual({'keycloak', 'data-manager-sdku'}, {e.get('serviceDeployment') for e in matched})
                self.assertTrue(any(e['eventType'] == 'TASK_STARTED' for e in matched))
                self.assertTrue(any(e['eventType'] == 'TASK_COMPLETED' for e in matched))

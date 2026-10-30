"""Safe snapshot failure survives Ansible no_log callback censorship."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ansible-core/collections'))
from ansible_collections.platform.core.plugins.callback.project_snapshot_json import CallbackModule
from ansible_collections.platform.core.plugins.action.project_snapshot import ActionModule
from ansible_collections.platform.core.plugins.module_utils.project_snapshot_output import write_snapshot_output, snapshot_failure_published


class SnapshotOutputTests(unittest.TestCase):
    def test_success_keeps_private_result_censored_and_publishes_public_snapshot(self):
        action = object.__new__(ActionModule)
        action._task = SimpleNamespace(args={'resolved_result_variable': 'platform_project_resolution'})
        public = {'status': 'PASS'}
        private = {'snapshot': public, 'execution_configuration': {'password': 'PRIVATE_TEST_SENTINEL'}}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'snapshot.json'
            with patch.dict(os.environ, PLATFORM_PROJECT_SNAPSHOT_OUTPUT=str(path)):
                result = action.run(task_vars={'platform_project_resolution': private})
                self.assertTrue(result['_ansible_no_log'])
                self.assertEqual(public, json.loads(path.read_text()))
                CallbackModule().v2_runner_on_ok(SimpleNamespace(
                    _task=SimpleNamespace(action='platform.core.project_snapshot'),
                    _result={'censored': True}))
                self.assertEqual(public, json.loads(path.read_text()))
                self.assertNotIn('PRIVATE_TEST_SENTINEL', path.read_text())

    def test_invalid_failure_artifacts_are_not_retained(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'snapshot.json'
            with patch.dict(os.environ, PLATFORM_PROJECT_SNAPSHOT_OUTPUT=str(path)):
                for raw in ('invalid JSON', 'x' * 4097,
                            json.dumps({'adapterError': {'code': 'OTHER', 'safeMessage': 'not accepted'}})):
                    path.write_text(raw)
                    self.assertFalse(snapshot_failure_published())
                target = Path(folder) / 'target.json'
                target.write_text(json.dumps({'adapterError': {'code': 'PROJECT_SNAPSHOT_INPUT_INVALID', 'safeMessage': 'safe'}}))
                path.unlink()
                path.symlink_to(target)
                self.assertFalse(snapshot_failure_published())

    def test_censored_callback_retains_public_failure_only(self):
        callback = CallbackModule()
        result = SimpleNamespace(_task=SimpleNamespace(action='platform.core.project_snapshot'),
                                 _result={'censored': 'PRIVATE_TEST_SENTINEL', '_ansible_no_log': True})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'snapshot.json'
            with patch.dict(os.environ, PLATFORM_PROJECT_SNAPSHOT_OUTPUT=str(path)):
                finding = {'code': 'PROJECT_SNAPSHOT_INPUT_INVALID', 'safeMessage': 'Отсутствует обязательный документ.'}
                write_snapshot_output({'adapterError': finding})
                callback.v2_runner_on_failed(result)
                self.assertEqual({'adapterError': finding}, json.loads(path.read_text()))
                self.assertNotIn('PRIVATE_TEST_SENTINEL', path.read_text())
                write_snapshot_output({'snapshot': 'previous success'})
                callback.v2_runner_on_failed(result)
                fallback = json.loads(path.read_text())['adapterError']
                self.assertEqual('PROJECT_SNAPSHOT_INPUT_INVALID', fallback['code'])
                self.assertTrue(fallback['safeMessage'])
                self.assertNotIn('PRIVATE_TEST_SENTINEL', path.read_text())

    @unittest.skipUnless(shutil.which('ansible-playbook'), 'native Ansible required')
    def test_native_success_keeps_private_register_out_of_output(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            output = directory / 'snapshot.json'
            play = directory / 'play.json'
            private = {'snapshot': {'status': 'PASS'},
                       'execution_configuration': {'password': 'PRIVATE_TEST_SENTINEL'}}
            play.write_text(json.dumps([{'hosts': 'localhost', 'gather_facts': False,
                'vars': {'platform_project_resolution': private}, 'tasks': [{
                    'platform.core.project_snapshot': {'resolved_result_variable': 'platform_project_resolution'},
                    'register': 'private_result',
                }, {'ansible.builtin.assert': {'that': [
                    'private_result.execution_configuration.password == "PRIVATE_TEST_SENTINEL"']},
                    'no_log': True}]}]))
            environment = dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
                ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections'),
                ANSIBLE_CALLBACKS_ENABLED='platform.core.project_snapshot_json',
                PLATFORM_PROJECT_SNAPSHOT_OUTPUT=str(output))
            completed = subprocess.run(['ansible-playbook', '-vvv', '-i', 'localhost,', '-c', 'local', str(play)],
                env=environment, capture_output=True, text=True, timeout=45)
            self.assertEqual(0, completed.returncode)
            self.assertEqual({'status': 'PASS'}, json.loads(output.read_text()))
            for content in (completed.stdout, completed.stderr, output.read_text()):
                self.assertNotIn('PRIVATE_TEST_SENTINEL', content)

    @unittest.skipUnless(shutil.which('ansible-playbook'), 'native Ansible required')
    def test_native_no_log_task_preserves_missing_root_reason(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            output = directory / 'snapshot.json'
            play = directory / 'play.json'
            environment = dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
                ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections'),
                ANSIBLE_CALLBACKS_ENABLED='platform.core.project_snapshot_json',
                PLATFORM_PROJECT_SNAPSHOT_OUTPUT=str(output))
            for no_log in (True, False):
                play.write_text(json.dumps([{'hosts': 'localhost', 'gather_facts': False, 'tasks': [{
                    'name': 'Snapshot failure', 'no_log': no_log,
                    'platform.core.project_snapshot': {'project_root': str(directory / 'missing')},
                }]}]))
                completed = subprocess.run(['ansible-playbook', '-i', 'localhost,', '-c', 'local', str(play)],
                    env=environment, capture_output=True, text=True, timeout=45)
                self.assertNotEqual(0, completed.returncode)
                finding = json.loads(output.read_text())['adapterError']
                self.assertEqual('PROJECT_SNAPSHOT_INPUT_INVALID', finding['code'])
                self.assertIn('Папка проекта не существует', finding['safeMessage'])
                self.assertIn('project_snapshot.py:', finding['safeMessage'])
                self.assertNotIn(str(directory), finding['safeMessage'])

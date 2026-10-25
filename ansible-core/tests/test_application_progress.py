"""Actual callback/Ansible boundaries and public progress without extra operations."""
import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml
from test_application_plan import ApplicationPlanTests, application_snapshot
from test_execution_task_observability import _active_journal
from test_execution_task_observability import _Task, _Result
from ansible_collections.platform.core.plugins.callback.execution_events_json import CallbackModule
from application_progress import describe_progress
from application_selection import execution_scope
from infrastructure_verification import scope_plan
from schema_validation import SchemaValidator

ROOT = Path(__file__).resolve().parents[2]


class ApplicationProgressTests(unittest.TestCase):
    def test_callback_only_accepts_closed_nonsecret_markers_in_application_apply(self):
        with tempfile.TemporaryDirectory() as root:
            journal = _active_journal(root)
            environment = dict(PLATFORM_EXECUTION_STATE_ROOT=root, PLATFORM_EXECUTION_RUN_ID=journal.run_id,
                               PLATFORM_EXECUTION_ACTION_ID='applications:apply')
            task = _Task()
            task.action = 'ansible.builtin.debug'
            task.tags = ['platform_application_progress']
            callback = CallbackModule()
            marker = {'id': 'applications:library:valid_library.1', 'state': 'started'}
            with mock.patch.dict(os.environ, environment):
                callback.v2_runner_on_ok(_Result(task, {'msg': marker}))
                callback.v2_runner_on_skipped(_Result(task, {'msg': marker}))
                callback.v2_runner_on_ok(_Result(task, {'msg': dict(marker, secret='MUST_NOT_LEAK')}))
                callback.v2_runner_on_ok(_Result(task, {'msg': dict(marker, id='bad/MUST_NOT_LEAK')}))
                task.no_log = True
                callback.v2_runner_on_ok(_Result(task, {'msg': marker}))
                task.no_log = False
                with mock.patch.dict(os.environ, {'PLATFORM_EXECUTION_ACTION_ID': 'service:apply'}):
                    callback.v2_runner_on_ok(_Result(task, {'msg': marker}))
            text = Path(journal.events_path).read_text()
            self.assertNotIn('MUST_NOT_LEAK', text)
            events = [json.loads(line) for line in text.splitlines()]
            self.assertEqual(1, len([event for event in events if event['eventType'] == 'ACTION_STARTED']))

    def test_plan_steps_are_ordered_display_only_and_fingerprint_bound(self):
        snapshot = application_snapshot()
        result = scope_plan(ApplicationPlanTests().build(snapshot), 'APPLICATION_LIBRARIES_ONLY', '/nonexistent-qa', True)
        manifest = copy.deepcopy(result['executionManifest'])
        before = result['deploymentPlan']['fingerprints']['plan']
        describe_progress(result, execution_scope(snapshot), True)
        self.assertNotEqual(before, result['deploymentPlan']['fingerprints']['plan'])
        manifest['planFingerprint'] = result['executionManifest']['planFingerprint']
        self.assertEqual(manifest, result['executionManifest'])
        self.assertEqual([], SchemaValidator(str(ROOT/'contracts')).validate(
            result['deploymentPlan'], ROOT/'contracts/plan/v1alpha10/schema.json'))
        action = result['deploymentPlan']['phases'][0]['actions'][0]
        self.assertEqual(['applications:prepare', 'applications:library:sdku'], [s['id'] for s in action['progressSteps']])
        # Same input yields the same display metadata/fingerprint.
        repeated = scope_plan(ApplicationPlanTests().build(snapshot), 'APPLICATION_LIBRARIES_ONLY', '/nonexistent-qa', True)
        self.assertEqual(result, describe_progress(repeated, execution_scope(snapshot), True))
        invalid = copy.deepcopy(result['deploymentPlan'])
        invalid['phases'][0]['actions'][0] = json.loads((ROOT/'ansible-core/tests/fixtures/application-progress-service-action.json').read_text())
        self.assertTrue(SchemaValidator(str(ROOT/'contracts')).validate(invalid, ROOT/'contracts/plan/v1alpha10/schema.json'))

    def test_no_application_apply_has_no_steps_or_contract_promotion(self):
        result = {'deploymentPlan': {'apiVersion': 'old', 'phases': []}}
        self.assertEqual(result, describe_progress(copy.deepcopy(result), {'installLibraries': []}))

    @unittest.skipUnless(shutil.which('ansible-playbook'), 'native Ansible required')
    def test_real_two_host_callback_success_failure_and_skipped_markers(self):
        production = yaml.safe_load((ROOT/'ansible-core/playbooks/application-libraries-ordered-library.yml').read_text())
        begin, end = production[0], production[-1]
        for fail_second, selected in ((False, True), (True, True), (False, False)):
            with self.subTest(fail_second=fail_second, selected=selected), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                journal = _active_journal(str(root/'state'))
                tasks = [begin, {'name': 'Exercise both inventory hosts', 'ansible.builtin.assert': {
                    'that': ["not fail_second or inventory_hostname != 'second'"]}}, end]
                play = [{'hosts': 'targets', 'strategy': 'linear', 'any_errors_fatal': True, 'gather_facts': False,
                         'vars': {'application_library_id': 'sdku', 'fail_second': fail_second}, 'tasks': tasks}]
                (root/'play.yml').write_text(yaml.safe_dump(play, allow_unicode=True))
                inventory = {'all': {'hosts': {'localhost': {'ansible_connection': 'local', 'application_selection': {
                    'scope': {'installLibraries': ['sdku'] if selected else []}}}}, 'children': {'targets': {
                    'hosts': {'first': {'ansible_connection': 'local'}, 'second': {'ansible_connection': 'local'}}}}}}
                (root/'inventory.yml').write_text(yaml.safe_dump(inventory))
                env = dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(ROOT/'ansible-core/collections'),
                           ANSIBLE_CALLBACKS_ENABLED='platform.core.execution_events_json',
                           ANSIBLE_LOCALHOST_WARNING='False', PLATFORM_EXECUTION_STATE_ROOT=str(root/'state'),
                           PLATFORM_EXECUTION_RUN_ID=journal.run_id, PLATFORM_EXECUTION_PHASE_ID='applications',
                           PLATFORM_EXECUTION_ACTION_ID='applications:apply')
                completed = subprocess.run(['ansible-playbook', '-i', str(root/'inventory.yml'), str(root/'play.yml')],
                                           env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
                self.assertEqual(fail_second, completed.returncode != 0, completed.stdout[-1800:] + completed.stderr[-800:])
                events = [json.loads(line) for line in Path(journal.events_path).read_text().splitlines()]
                child = [event for event in events if event.get('actionId') == 'applications:library:sdku']
                expected = [] if not selected else ['ACTION_STARTED'] + ([] if fail_second else ['ACTION_COMPLETED'])
                self.assertEqual(expected, [event['eventType'] for event in child])
                if fail_second:
                    self.assertTrue(any(event['eventType'] == 'TASK_COMPLETED' and event['status'] == 'FAILED'
                                        and event.get('host') == 'second' for event in events))


if __name__ == '__main__':
    unittest.main()

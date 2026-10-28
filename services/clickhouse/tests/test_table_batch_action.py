"""Invocation count, input binding and fail-closed batch rendering checks."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from ansible.errors import AnsibleError

SOURCE = Path(__file__).resolve().parents[1] / 'ansible_collections/platform/clickhouse/plugins/action/prepare_application_tables.py'
spec = importlib.util.spec_from_file_location('table_batch_action', SOURCE)
ACTION = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ACTION)


class TableBatchActionTests(unittest.TestCase):
    def probe(self, job, phase, rendered=None, error=None):
        action = object.__new__(ACTION.ActionModule)
        action._task = SimpleNamespace(args=dict(job=job, phase=phase, template_path='/role/templates/batch.json.j2'))
        action._templar = Mock()
        child = action._templar.copy_with_new_env.return_value
        child.template.return_value = rendered
        child.template.side_effect = error
        result = action.run(task_vars={'sentinel': 'ordinary context'})
        return result, action._templar, child

    def test_one_lookup_for_many_tables_in_each_read_or_resource_phase(self):
        tables = [dict(name='t' + str(i)) for i in range(64)]
        job = dict(databases=[dict(name='db', tables=tables)])
        rows = [dict(database='db', definition=t, sql='CREATE TABLE ' + t['name']) for t in tables]
        for phase in ('preflight', 'resources', 'verify'):
            for rendered in (rows, json.dumps(rows)):
                with self.subTest(phase=phase, native=isinstance(rendered, list)):
                    result, templar, child = self.probe(job, phase, rendered)
                    self.assertEqual(dict(changed=False, tables=rows), result)
                    templar.copy_with_new_env.assert_called_once()
                    child.template.assert_called_once()
                    variables = templar.copy_with_new_env.call_args.kwargs['available_variables']
                    self.assertEqual(job, variables['platform_clickhouse_application_job'])

    def test_accounts_and_empty_databases_do_not_invoke_template(self):
        for job, phase in (({}, 'accounts'), (dict(databases=[]), 'resources'),
                           (dict(databases=[dict(name='db'), dict(name='empty', tables=[])]), 'preflight')):
            result, templar, child = self.probe(job, phase)
            self.assertEqual(dict(changed=False, tables=[]), result)
            templar.copy_with_new_env.assert_not_called()
            child.template.assert_not_called()

    def test_invalid_or_incomplete_batch_is_rejected(self):
        job = dict(databases=[dict(name='db', tables=[dict(name='t')])])
        valid = dict(database='db', definition=dict(name='t'), sql='CREATE TABLE t')
        for rendered in ('not json', {}, [], [valid, valid], [dict(valid, sql='')],
                         [dict(valid, database='foreign')], [dict(valid, definition=dict(name='other'))], [None]):
            with self.subTest(rendered=type(rendered).__name__):
                result, _, _ = self.probe(job, 'preflight', rendered)
                self.assertEqual(dict(changed=False, failed=True, msg='CLICKHOUSE_APPLICATION_TABLE_TEMPLATE_INVALID'), result)

    def test_template_failure_has_only_safe_code(self):
        result, _, _ = self.probe(dict(databases=[dict(name='db', tables=[dict(name='t')])]),
            'preflight', error=AnsibleError('PRIVATE_TEMPLATE_CONTEXT'))
        self.assertEqual(dict(changed=False, failed=True, msg='CLICKHOUSE_APPLICATION_TABLE_TEMPLATE_INVALID'), result)

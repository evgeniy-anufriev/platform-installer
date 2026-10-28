"""Render table SQL through the existing Ansible template lookup in one action."""
import json
from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleError


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        values = task_vars or {}
        try:
            job = self._task.args['job']
            if self._task.args['phase'] == 'accounts':
                return dict(changed=False, tables=[])
            if not any(database.get('tables') for database in job['databases']):
                return dict(changed=False, tables=[])
            variables = dict(values, platform_clickhouse_application_job=job,
                             table_template_path=self._task.args['template_path'])
            templar = self._templar.copy_with_new_env(available_variables=variables)
            rendered = templar.template("{{ lookup('ansible.builtin.template', table_template_path, template_vars={'platform_clickhouse_application_job': platform_clickhouse_application_job}) }}")
            # Depending on the Ansible native templating version, JSON may
            # already have been converted into its list representation.
            tables = json.loads(rendered) if isinstance(rendered, str) else rendered
            expected = [(database['name'], table) for database in job['databases']
                        for table in database.get('tables', [])]
            if (not isinstance(tables, list) or len(tables) != len(expected) or
                    any(not isinstance(row, dict) or row.get('database') != database or
                        row.get('definition') != definition or not isinstance(row.get('sql'), str) or
                        not row['sql'].strip() for row, (database, definition) in zip(tables, expected))):
                raise ValueError()
            return dict(changed=False, tables=tables)
        except (AnsibleError, KeyError, TypeError, ValueError):
            return dict(changed=False, failed=True, msg='CLICKHOUSE_APPLICATION_TABLE_TEMPLATE_INVALID')

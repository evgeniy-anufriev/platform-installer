"""Render table SQL through the existing Ansible template lookup in one action."""
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
            tables = []
            for database in job['databases']:
                for table in database.get('tables', []):
                    variables = dict(values, item=[database, table], platform_clickhouse_application_job=job,
                                     table_template_path=self._task.args['template_path'])
                    templar = self._templar.copy_with_new_env(available_variables=variables)
                    sql = templar.template("{{ lookup('ansible.builtin.template', table_template_path, template_vars={'item': item, 'platform_clickhouse_application_job': platform_clickhouse_application_job}) }}")
                    tables.append(dict(database=database['name'], definition=table, sql=sql))
            return dict(changed=False, tables=tables)
        except (AnsibleError, KeyError, TypeError, ValueError):
            return dict(changed=False, failed=True, msg='CLICKHOUSE_APPLICATION_TABLE_TEMPLATE_INVALID')

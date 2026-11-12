"""Assemble nonsecret Vault hook jobs without target contact."""
from ansible.plugins.action import ActionBase
from ansible_collections.platform.core.plugins.module_utils.application_vault import project_vault


class ActionModule(ActionBase):
    TRANSFERS_FILES = False
    _requires_connection = False

    def run(self, tmp=None, task_vars=None):
        try:
            values = task_vars or {}
            args = self._task.args
            prepared = args['snapshot_result'] if 'snapshot_result' in args else values['application_snapshot']
            result = project_vault(values['platform_application_rows'], prepared)
            return dict(result, status='PASS', changed=False)
        except (ValueError, KeyError, TypeError, IndexError) as error:
            code = str(error)
            if not code.startswith('APPLICATION_VAULT_') or not code.replace('_', '').isalnum():
                code = 'APPLICATION_VAULT_INPUT_INVALID'
            return dict(status='BLOCKED', changed=False, code=code, providers=[], libraryJobs=[], instanceJobs=[])

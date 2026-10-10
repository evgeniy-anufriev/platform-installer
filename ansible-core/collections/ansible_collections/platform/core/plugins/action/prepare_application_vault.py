"""Assemble nonsecret Vault hook jobs without target contact."""
from ansible.plugins.action import ActionBase
from ansible_collections.platform.core.plugins.module_utils.application_vault import project_vault


class ActionModule(ActionBase):
    TRANSFERS_FILES = False
    _requires_connection = False

    def run(self, tmp=None, task_vars=None):
        try:
            result = project_vault((task_vars or {})['platform_application_rows'], self._task.args['snapshot_result'])
            return dict(result, status='PASS', changed=False)
        except (ValueError, KeyError, TypeError, IndexError) as error:
            code = str(error)
            if not code.startswith('APPLICATION_VAULT_') or not code.replace('_', '').isalnum():
                code = 'APPLICATION_VAULT_INPUT_INVALID'
            return dict(status='BLOCKED', changed=False, code=code, providers=[], libraryJobs=[], instanceJobs=[])

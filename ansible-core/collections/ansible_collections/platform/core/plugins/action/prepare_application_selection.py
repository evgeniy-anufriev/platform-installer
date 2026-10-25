"""Bind invocation scope to the complete native resolved snapshot."""
from ansible.plugins.action import ActionBase
from ansible_collections.platform.core.plugins.module_utils.application_selection import execution_scope, scoped_snapshot


class ActionModule(ActionBase):
    TRANSFERS_FILES = False
    _requires_connection = False

    def run(self, tmp=None, task_vars=None):
        values = task_vars or {}
        try:
            prepared = dict(self._task.args['snapshot_result'])
            expected = values.get('platform_application_execution_scope')
            scope = execution_scope(prepared['snapshot'],
                                    expected['libraryOrder'] if expected else values.get('platform_application_library_order'),
                                    expected['skippedLibraries'] if expected else values.get('platform_application_skip_libraries'))
            if expected is not None and scope != expected:
                raise ValueError('APPLICATION_LIBRARY_SELECTION_STALE')
            prepared['snapshot'] = scoped_snapshot(prepared['snapshot'], scope)
            return dict(changed=False, status='PASS', prepared=prepared, scope=scope)
        except (ValueError, KeyError, TypeError) as error:
            code = str(error)
            if code not in ('APPLICATION_LIBRARY_ORDER_INVALID', 'APPLICATION_LIBRARY_SELECTION_INVALID', 'APPLICATION_LIBRARY_SELECTION_STALE'):
                code = 'APPLICATION_LIBRARY_SELECTION_INVALID'
            return dict(changed=False, status='BLOCKED', code=code)

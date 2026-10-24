"""Expose native topology before expansion of application ENV/default templates."""
from ansible.plugins.action import ActionBase
from ansible_collections.platform.core.plugins.module_utils.application_connections import provided_connections


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        values = task_vars or {}
        try:
            rows = values.get('platform_application_connection_rows', [])
            hosts = {row['hostId']: {'ansibleHost': values['hostvars'][row['hostId']]['ansible_host']} for row in rows}
            return dict(changed=False, connections=provided_connections(rows, values['platform_desired_state'], hosts))
        except (KeyError, ValueError, TypeError):
            return dict(failed=True, changed=False, msg='APPLICATION_PROVIDED_CONNECTION_INVALID')

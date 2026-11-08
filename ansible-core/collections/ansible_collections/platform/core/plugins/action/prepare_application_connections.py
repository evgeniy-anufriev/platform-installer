"""Expose native topology before expansion of application ENV/default templates."""
from ansible.plugins.action import ActionBase
from ansible.utils.vars import merge_hash
from ansible_collections.platform.core.plugins.module_utils.application_connections import provided_connections
from ansible_collections.platform.core.plugins.module_utils.application_libraries import finding


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        values = task_vars or {}
        placements = {}
        try:
            rows = values.get('platform_application_connection_rows', [])
            hosts = {row['hostId']: {'ansibleHost': values['hostvars'][row['hostId']]['ansible_host']} for row in rows}
            resolved_ports = {(row['libraryId'], row['slotId'], row['hostId']): row['settings']['ports']
                              for row in rows}
            for job in values.get('_application_inputs', {}).get('jobs', []):
                if job['connections'] is None:
                    continue
                key = (job['libraryId'], job['slotId'], job['hostId'])
                if not job['skipConnectionTopology'] and key not in resolved_ports:
                    continue  # Its existing topology diagnostic is already retained.
                ports = resolved_ports.get(key)
                if ports is None:
                    # Only literal port inputs can skip the native topology role.
                    ports = {}
                    for layer in (job['application']['definition'].get('defaults', {}),
                                  job['slot'].get('overrides', {}), job['instance'].get('overrides', {}),
                                  job['hostOverride']):
                        ports = merge_hash(ports, layer.get('ports', {}), recursive=True, list_merge='replace')
                placements.setdefault(job['libraryId'], {}).setdefault(job['slotId'], []).append(dict(
                    hostId=job['hostId'], address=values['hostvars'][job['hostId']].get('ansible_host', job['hostId']),
                    ports=ports))
            for library in placements.values():
                for members in library.values():
                    members.sort(key=lambda row: row['hostId'])
            return dict(changed=False, connections=provided_connections(rows, values['platform_desired_state'], hosts),
                        placements=placements)
        except (KeyError, ValueError, TypeError):
            diagnostic = finding('APPLICATION_PROVIDED_CONNECTION_INVALID', 'applicationLibraryDeployments')
            diagnostic['safeMessage'] = 'Не удалось вычислить предоставляемые подключения приложений. Проверьте настройки подключений библиотеки.'
            return dict(changed=False, connections={}, placements=placements, findings=[diagnostic])

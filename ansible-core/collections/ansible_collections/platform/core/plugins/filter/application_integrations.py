"""Small projections consumed by ordinary provider/Vault coordination tasks."""
from ansible_collections.platform.core.plugins.module_utils.application_integrations import (
    pending_instances, ready_vault_jobs, shared_vault_jobs)
from ansible_collections.platform.core.plugins.module_utils.application_connections import connection_order_findings


class FilterModule:
    def filters(self):
        return {'application_connection_order_findings': connection_order_findings,
                'application_pending_instances': pending_instances,
                'application_ready_vault_jobs': ready_vault_jobs,
                'application_ready_shared_jobs': shared_vault_jobs}

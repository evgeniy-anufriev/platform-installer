"""Prepare shared endpoint hook sources before any target mutation."""
from ansible.plugins.action import ActionBase
from ansible_collections.platform.core.plugins.module_utils.application_endpoints import project_endpoint_sources
from ansible_collections.platform.core.plugins.module_utils.service_endpoint_resolution import resolve_service_endpoints
from ansible_collections.platform.core.plugins.module_utils.haproxy_resolution import resolve_haproxy_backends
from ansible_collections.platform.core.plugins.module_utils.dns_resolution import _provider_addresses, resolve_dns_zones
from ansible_collections.platform.core.plugins.module_utils.service_integration_resolution import resolve_service_integrations


class ActionModule(ActionBase):
    TRANSFERS_FILES = False
    _requires_connection = False

    def run(self, tmp=None, task_vars=None):
        values = task_vars or {}
        try:
            desired = values['platform_desired_state']
            snapshot = self._task.args.get('snapshot')
            hosts = {host: dict(settings, ansible_host=settings['ansibleHost'])
                     for host, settings in snapshot['hosts'].items()} if snapshot else {
                host: {'ansible_host': values['hostvars'][host].get('ansible_host', host),
                       'platformDeployments': values['hostvars'][host].get('platform_deployments', {})}
                for host in values.get('groups', {}).get('platform_targets', [])}
            placements = {host: settings.get('platformDeployments', {}) for host, settings in hosts.items()}
            catalog = self._loader.load_from_file(self._task.args['service_catalog_path'])
            sources = project_endpoint_sources(values.get('platform_application_rows', []), desired, hosts)
            if not sources:
                return {'changed': False, 'status': 'PASS', 'findings': [], 'sources': {}}
            endpoints = resolve_service_endpoints(desired, catalog, inventory_deployments=placements, endpoint_sources=sources)
            backends = resolve_haproxy_backends(desired, catalog, hosts, placements, endpoints, endpoint_sources=sources)
            findings = endpoints['findings'] + backends['findings']
            for source_id in sources:
                relation = resolve_service_integrations(desired, [], source_id, placements, sources)
                findings.extend(relation['findings'])
                addresses, providers = _provider_addresses(
                    desired.get('serviceDeployments', {}), catalog.get('definitions', catalog),
                    sources[source_id]['endpointGroup'], findings)
                if len(providers) == 1 and addresses:
                    sources[source_id]['expectedAddresses'] = addresses
                elif not providers:
                    sources[source_id]['expectedAddresses'] = sorted({
                        hosts[host]['ansible_host'] for host in relation['integrations']['haproxyHosts']
                        if host in hosts})
                if relation['integrations']['dnsDeployments']:
                    dns = resolve_dns_zones(desired, catalog, hosts, placements,
                                            source_deployment_ids=[source_id], include_group_wildcards=False,
                                            endpoint_sources=sources)
                    findings.extend(dns['findings'])
            return {'changed': False, 'status': 'BLOCKED' if findings else 'PASS', 'findings': findings,
                    'sources': {} if findings else sources}
        except (KeyError, TypeError, ValueError, OSError) as error:
            code = str(error)
            if not code.startswith('APPLICATION_') or not code.replace('_', '').isalnum():
                code = 'APPLICATION_ENDPOINT_INPUT_INVALID'
            return {'changed': False, 'status': 'BLOCKED', 'sources': {}, 'findings': [{'code': code}]}

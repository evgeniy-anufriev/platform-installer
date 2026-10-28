"""Target-free batching and native parity with the previous singleton orchestration."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import yaml
from ansible_collections.platform.core.plugins.module_utils.application_endpoints import project_endpoint_sources
from ansible_collections.platform.core.plugins.modules.resolve_endpoint_publications import resolve_batch

ROOT = Path(__file__).resolve().parents[2]


def inputs(count=20):
    state = {'endpointGroups': {'apps': {'address': {'domain': 'apps.example.test'}}},
             'serviceDeployments': {
                 'vip': {'serviceType': 'keepalived', 'endpointGroupRef': 'apps',
                         'virtualAddresses': [{'address': '192.0.2.100', 'interface': 'eth1'}]},
                 'proxy': {'serviceType': 'haproxy', 'endpointGroup': 'apps'},
                 'dns': {'serviceType': 'bind', 'configuration': {'zone': 'example.test', 'defaultTtl': 300}},
                 'vault-main': {'serviceType': 'vault', 'endpointGroup': 'apps'},
                 'clickhouse-main': {'serviceType': 'clickhouse', 'endpointGroup': 'apps'}}}
    hosts = {'node1': {'ansible_host': '192.0.2.1'}, 'node2': {'ansible_host': '192.0.2.2'}}
    placements = {'node1': {'vip': {}, 'proxy': {}, 'dns': {'roles': ['primary']}},
                  'node2': {'vip': {}, 'proxy': {}, 'dns': {'roles': ['secondary']}}}
    catalog = {'definitions': {key: {'endpoint': {}} for key in ['vault', 'clickhouse', 'haproxy']}}
    catalog['definitions'].update({'bind': {'endpoint': None}, 'keepalived': {'endpointProvider': {}}})
    rows = [{'instanceId': f'app-{n}', 'libraryId': 'lib', 'hostId': host,
             'settings': {'ports': {'http': {'published': 18081 + n}},
                          'endpoint': {'enabled': True, 'listener': 'http', 'endpoint_group': 'apps',
                                       'probe': {'path': '/status', 'timeout': 2 + n, 'expected_status': 200}}}}
            for n in range(count) for host in hosts]
    sources = project_endpoint_sources(rows, state, hosts)
    return dict(desired_state=state, service_catalog=catalog, inventory_hosts=hosts,
                inventory_deployments=placements, endpoint_sources=sources,
                source_ids=['vault-main', 'clickhouse-main'] + list(sources))


class EndpointPublicationBatchTests(unittest.TestCase):
    def test_twenty_apps_and_services_preserve_scope_addresses_and_policies(self):
        params = inputs()
        result = resolve_batch(**params)
        self.assertEqual('PASS', result['status'], result['findings'])
        self.assertEqual(22, len(result['sources']))
        for source in result['sources']:
            self.assertEqual(['node1', 'node2'], source['projection']['haproxyHosts'])
            self.assertEqual(['192.0.2.100'], source['expectedAddresses'])
            self.assertEqual([source['sourceId'] + '.apps.example.test'], source['fqdns'])
            self.assertEqual(1, len(source['dnsRecords']))
            if source['sourceId'].startswith('app-'):
                self.assertEqual(params['endpoint_sources'][source['sourceId']]['probe'], source['probe'])
        for selection in [[], ['missing']]:
            with self.assertRaises(ValueError):
                resolve_batch(**dict(params, source_ids=selection))
        subset = resolve_batch(**dict(params, source_ids=['vault-main', 'vault-main']))
        self.assertEqual(['vault-main'], [x['sourceId'] for x in subset['sources']])

    def test_native_batch_matches_original_singleton_service_and_library_tasks(self):
        params = inputs(1)
        with tempfile.TemporaryDirectory(prefix='qa-endpoint-batch-') as directory:
            root = Path(directory)
            catalog = root / 'catalog.yml'
            catalog.write_text(yaml.safe_dump(params['service_catalog']))
            inventory = {'all': {'children': {'platform_targets': {'hosts': {
                host: dict(info, platform_deployments=params['inventory_deployments'][host])
                for host, info in params['inventory_hosts'].items()}}}}}
            inv = root / 'inventory.yml'
            inv.write_text(yaml.safe_dump(inventory))
            variables = dict(platform_desired_state=params['desired_state'],
                platform_endpoint_sources=params['endpoint_sources'], platform_service_catalog_path=str(catalog),
                platform_endpoint_source_ids=sorted(params['source_ids']), _platform_integration_selected_sources=[])
            tasks = [{'ansible.builtin.set_fact': {'platform_endpoint_sources': params['endpoint_sources']}}, dict({'ansible.builtin.include_tasks': str(ROOT / 'services/integrations/tasks/resolve-selected-source.yml'),
                           'loop': '{{ platform_endpoint_source_ids }}',
                           'loop_control': {'loop_var': '_platform_selected_source_id'}}),
                     {'ansible.builtin.set_fact': {'expected_sources': '{{ _platform_integration_selected_sources }}'}},
                     {'platform.core.resolve_endpoint_publications': params, 'register': 'batched'},
                     {'ansible.builtin.assert': {'that': ['batched.sources == expected_sources', 'not batched.changed']}},
                     {'ansible.builtin.include_tasks': str(ROOT / 'services/integrations/tasks/resolve-selected-sources.yml'),
                      'vars': {'platform_endpoint_source_ids': ['app-0']}},
                     {'ansible.builtin.assert': {'that': [
                         "_platform_integration_selected_sources == (expected_sources | selectattr('sourceId', 'equalto', 'app-0') | list)",
                         "platform_service_integration_projection.haproxyHosts == ['node1', 'node2']"]}}]
            play = root / 'play.yml'
            play.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False,
                                                vars=variables, tasks=tasks)], sort_keys=False))
            env = dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
                       ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections'))
            result = subprocess.run(['ansible-playbook', '-i', str(inv), str(play)], env=env,
                                    capture_output=True, text=True, timeout=150)
            self.assertEqual(0, result.returncode, (result.stdout + result.stderr)[-5000:])

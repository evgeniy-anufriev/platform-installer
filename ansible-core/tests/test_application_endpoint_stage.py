"""Production endpoint templates and isolation predicates through real Ansible."""
from pathlib import Path
import os
import json
import shutil
import subprocess
import tempfile
import unittest
import yaml

REPO = Path(__file__).resolve().parents[2]
ROLE = REPO / 'services/haproxy/ansible_collections/platform/haproxy/roles/haproxy'


class EndpointTaskTest(unittest.TestCase):
    def test_original_cli_context_and_limit_through_complete_endpoint_stage(self):
        with tempfile.TemporaryDirectory(prefix='platform-a6-context-') as directory:
            root = Path(directory)
            inventory = {'all': {'children': {'platform_targets': {'hosts': {
                'node1': {'ansible_connection': 'local'},
                'excluded': {'ansible_host': '192.0.2.254', 'ansible_connection': 'ssh'}}}},
                'vars': {'platform_desired_state': {'serviceDeployments': {'bad': {'serviceType': 'not-a-provider'}}}}}}
            (root / 'hosts.yml').write_text(yaml.safe_dump(inventory))
            source = {'endpointGroup': 'apps', 'endpoint': {'fqdn': 'apigateway-sdku.apps.test'},
                      'probe': {'path': '/status', 'expected_status': 200, 'timeout': 1, 'validate_certs': True},
                      'targets': [{'hostId': 'node1', 'address': '127.0.0.1', 'port': 8080, 'serverName': 'node1'}]}
            extra = {'platform_desired_state': {'serviceDeployments': {}, 'endpointGroups': {
                'apps': {'address': {'domain': 'apps.test'}}}},
                'platform_endpoint_sources': {'apigateway-sdku': source},
                'platform_service_catalog_path': str(REPO / 'examples/catalog/service-catalog.yml')}
            (root / 'extra.yml').write_text(yaml.safe_dump(extra))
            command = ['ansible-playbook', '-i', str(root / 'hosts.yml'),
                       str(REPO / 'ansible-core/playbooks/application-libraries-endpoint-stage.yml'),
                       '-e', '@' + str(root / 'extra.yml'), '--limit', 'node1', '--user', 'cli-user',
                       '--private-key', str(root / 'unused-key')]
            env = dict(os.environ, ANSIBLE_CONFIG=str(REPO / 'ansible-core/ansible.cfg'),
                       ANSIBLE_COLLECTIONS_PATH=os.pathsep.join([str(REPO / 'ansible-core/collections')] +
                           [str(path.parent) for path in sorted((REPO / 'services').glob('*/ansible_collections'))]))
            result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=45)
            self.assertNotEqual(0, result.returncode)
            self.assertIn('APPLICATION_ENDPOINT_NOT_PUBLISHED', result.stdout)
            self.assertNotIn('UNREACHABLE', result.stdout)
            source['targets'][0]['hostId'] = 'excluded'
            (root / 'extra.yml').write_text(yaml.safe_dump(extra))
            result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=45)
            self.assertNotEqual(0, result.returncode)
            self.assertIn('APPLICATION_ENDPOINT_HOST_SCOPE_INCOMPLETE', result.stdout)
            self.assertNotIn('UNREACHABLE', result.stdout)

    def test_external_dns_requires_expected_provider_address(self):
        task = yaml.safe_load((REPO / 'services/integrations/tasks/probe-endpoint.yml').read_text())
        dns_assert = next(item for item in task if item.get('name') == 'Require every source endpoint hostname to resolve')
        conditions = dns_assert['ansible.builtin.assert']['that']
        self.assertIn('expected_addresses | length > 0', conditions)
        self.assertIn('actual_addresses == expected_addresses', conditions)

    def test_native_defaults_snapshot_and_two_host_source_projection(self):
        with tempfile.TemporaryDirectory(prefix='platform-a6-native-') as directory:
            root = Path(directory) / 'project'
            shutil.copytree(REPO / 'examples/valid/application-libraries', root)
            desired_path = root / 'inventory/group_vars/all/platform-installer.yml'
            data = json.loads(desired_path.read_text())
            desired = data['platform_desired_state']
            desired['endpointGroups'] = {'apps': {'address': {'domain': 'apps.example.test', 'wildcard': False}}}
            desired['applicationLibraryDeployments']['sdku']['applications']['gateway']['overrides']['endpoint'] = {
                'enabled': True, 'listener': 'http', 'endpoint_group': 'apps', 'probe': {'path': '/status'}}
            desired_path.write_text(json.dumps(data))
            play = [{'hosts': 'localhost', 'connection': 'local', 'gather_facts': False,
                     'vars': {'platform_project_root': str(root), 'platform_contracts_root': str(REPO / 'contracts'),
                              'platform_service_catalog_path': str(REPO / 'examples/catalog/service-catalog.yml')},
                     'tasks': [
                         {'ansible.builtin.include_role': {'name': 'platform.core.resolve_application_libraries'}},
                         {'platform.core.project_snapshot': {'project_root': str(root),
                          'service_catalog_path': str(REPO / 'examples/catalog/service-catalog.yml')}, 'register': 'snapshot'},
                         {'platform.core.prepare_application_endpoints': {'snapshot': '{{ snapshot.snapshot }}',
                          'service_catalog_path': str(REPO / 'examples/catalog/service-catalog.yml')}, 'register': 'endpoint_input'},
                         {'ansible.builtin.assert': {'that': ["endpoint_input.status == 'PASS'",
                          "endpoint_input.sources['apigateway-sdku'].targets | length == 2",
                          "endpoint_input.sources['apigateway-sdku'].endpoint.fqdn == 'apigateway-sdku.apps.example.test'"]}}]}]
            path = Path(directory) / 'qa.yml'
            path.write_text(yaml.safe_dump(play))
            env = dict(os.environ, ANSIBLE_CONFIG=str(REPO / 'ansible-core/ansible.cfg'),
                       ANSIBLE_COLLECTIONS_PATH=os.pathsep.join([str(REPO / 'ansible-core/collections')] +
                           [str(path.parent) for path in sorted((REPO / 'services').glob('*/ansible_collections'))]))
            result = subprocess.run(['ansible-playbook', '-i', str(root / 'inventory/hosts.yml'), str(path)],
                                    env=env, capture_output=True, text=True, timeout=90)
            self.assertEqual(0, result.returncode, result.stdout[-5000:] + result.stderr[-2000:])

    def test_prefix_neighbor_and_longest_domain_routing(self):
        if not shutil.which('ansible-playbook'):
            self.skipTest('Ansible runtime required')
        tasks = yaml.safe_load((ROLE / 'tasks/prepare.yml').read_text())
        names = {'Select exact filenames owned by the partial endpoint source',
                 'Stage proven existing application backends for base provider update',
                 'Retain exact proven backend inventory in base mode',
                 'Select only this source deployment backend for partial integration'}
        tasks = yaml.safe_load((ROLE / 'tasks/partial_scope.yml').read_text()) + [task for task in tasks if task.get('name') in names]
        for task in tasks:
            if 'ansible.builtin.copy' in task:
                task['ansible.builtin.copy'].update(owner=str(os.geteuid()), group=str(os.getegid()))
        with tempfile.TemporaryDirectory(prefix='platform-a6-predicates-') as directory:
            root = Path(directory)
            active, candidate = root / 'active', root / 'candidate'
            active.mkdir()
            (candidate / 'conf.d').mkdir(parents=True)
            selected = '30-backend-apigateway-sdku-child.cfg'
            neighbor = '30-backend-apigateway-sdku-test-child.cfg'
            (active / selected).write_text('selected')
            (active / neighbor).write_text('neighbor preserved')
            backend = {'targetDeploymentId': 'apigateway-sdku', 'providerHostIds': ['localhost'],
                       'configFileName': selected}
            variables = {'platform_haproxy_partial_deployment_id': 'apigateway-sdku',
                         'platform_haproxy_full_reconcile': False,
                         'platform_deployments': {'proxy': {}},
                         'platform_haproxy_runtime_projection': {'backends': {'backends': {'proxy': [backend]}}},
                         '_platform_haproxy_prior_backend_capture': {'previousInventory': [{'name': selected}, {'name': neighbor}]},
                         'platform_haproxy_conf_directory': str(active),
                         'platform_haproxy_candidate_directory': str(candidate),
                         'platform_haproxy_public_port': 443, 'platform_haproxy_pki_directory': '/pki',
                         'platform_desired_state': {'endpointGroups': {
                             'a-parent': {'address': {'domain': 'scada.local'}},
                             'z-child': {'address': {'domain': 'cspa.scada.local'}}}}}
            checks = [
                {'ansible.builtin.assert': {'that': ["platform_haproxy_managed_application_backend_files == ['" + selected + "', '" + neighbor + "']"]}},
                {'ansible.builtin.template': {'src': str(ROLE / 'templates/10-public.cfg.j2'), 'dest': str(root / 'frontend.cfg')}}]
            play = [{'hosts': 'localhost', 'connection': 'local', 'gather_facts': False,
                     'vars': variables, 'tasks': tasks + checks}]
            path = root / 'qa.yml'
            path.write_text(yaml.safe_dump(play))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(path)],
                                    capture_output=True, text=True, timeout=45)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual('neighbor preserved', (candidate / 'conf.d' / neighbor).read_text())
            self.assertFalse((candidate / 'conf.d' / selected).exists())
            text = (root / 'frontend.cfg').read_text()
            self.assertLess(text.index('use_backend %[var(txn.route_host),field(1'), text.index('if a-parent'))
            self.assertLess(text.index('if z-child'), text.index('if a-parent'))


if __name__ == '__main__':
    unittest.main()

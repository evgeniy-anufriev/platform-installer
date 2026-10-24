"""Native defaults/overrides and exports resolve before consumer template expansion."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils'))
from application_libraries import project


@unittest.skipUnless(shutil.which('ansible-playbook'), 'native Ansible required')
class NativeApplicationConnectionsTests(unittest.TestCase):
    def test_exports_parameters_accounts_and_disabled_override_use_native_rows(self):
        with tempfile.TemporaryDirectory(prefix='provided-connections-') as directory:
            root = Path(directory) / 'project'
            shutil.copytree(ROOT / 'examples/valid/application-libraries', root)
            def edit(path, mutate):
                value = json.loads(path.read_text())
                mutate(value)
                path.write_text(json.dumps(value))
            vars_path = root / 'inventory/group_vars/all/platform-installer.yml'
            def desired(data):
                state = data['platform_desired_state']
                state['endpointGroups'] = {'apps': {'address': {'domain': 'apps.example.test'}}}
                state['serviceDeployments']['vault-main']['members'] = {'vault1': {'host': 'node1'}}
                consumer = state['applicationLibraryDeployments']['sdku']
                consumer['bindings']['identity-admin'] = {'providedConnectionRef': {'libraryId': 'cspa', 'name': 'admin'}}
                consumer['applications']['gateway']['overrides']['connections'] = {'identity': {'enabled': True}}
                consumer['applications']['gateway']['overrides']['endpoint'] = {
                    'enabled': True, 'listener': 'http', 'protocol': 'https', 'endpoint_group': 'apps'}
                consumer['provided_connections'] = {}
                provider = state['applicationLibraryDeployments']['cspa']
                provider['applications']['gateway']['overrides']['endpoint'] = {
                    'enabled': True, 'listener': 'http', 'protocol': 'https', 'endpoint_group': 'apps'}
                provider['provided_connections'] = {'admin': {'parameters': {
                    'tenant': 'override', 'override_origin': '{{ library_instance_id }}-override'}}}
                for library in state['applicationLibraryDeployments'].values():
                    library['bindings'] = {key: value for key, value in library['bindings'].items()
                                           if key in ('secrets', 'identity-admin', 'application_pki')}
                    library['resources'] = {}
            edit(vars_path, desired)
            for name in ('cspa', 'sdku'):
                path = root / ('library-packages/%s/1.0.0/roles/library_%s/defaults/main.yml' % (name, name))
                def definition(data, provider=name == 'cspa'):
                    library = data['platform_library_definition']
                    library['connections'] = {'vault': {'library_binding': 'secrets', 'protocol': 'https'},
                                              'identity': {'library_binding': 'identity-admin', 'protocol': 'https'}}
                    library['shared_secrets'] = {}
                    if provider:
                        library['provided_connections'] = {'admin': {
                            'application': 'gateway', 'protocol': 'https', 'parameters': {
                                'tenant': '{{ library_instance_id }}',
                                'origin': 'https://{{ library_instance_id }}.example.test',
                                'nested': {'enabled': True, 'ports': [8443]}},
                            'credentials': {'password': {'source': {'kind': 'runtime_secret_ref', 'ref': 'api-password'}}},
                            'account_provisioner': {'apply_script': 'accounts'},
                            'connection_provisioner': {'apply_script': 'integrate'}}}
                edit(path, definition)
            defaults = root / 'application-packages/apigateway/1.0.0/roles/application_apigateway/defaults/main.yml'
            def application(data):
                app = data['platform_application_definition']
                app['connections'] = ['identity', 'vault']
                settings = app['defaults']
                settings['connections'] = {'identity': {'enabled': False}}
                settings.setdefault('parameters', {})['OPTIONS'] = {'consumer': '{{ library_instance_id }}'}
                settings['accounts'] = {'identity': {'mode': 'managed', 'parameters': {'groups': ['operators']}, 'credentials': {
                    'username': {'source': {'kind': 'literal', 'value': '{{ application_instance_id }}'}},
                    'password': {'source': {'kind': 'runtime_secret_ref', 'ref': 'consumer-password'}}}}}
                settings['environment'] = {'API_ENDPOINT': "{{ application_connections.identity.url if library_instance_id == 'sdku' else 'provider' }}"}
                settings['provisioner']['secret_bindings'] = {'API_PASSWORD': {'source': {'account': 'identity', 'field': 'password'}}}
            edit(defaults, application)
            manifest = root / 'application-packages/apigateway/1.0.0/application.yml'
            probe = root / 'application-packages/apigateway/1.0.0/assets/probe.sh'
            probe.parent.mkdir(exist_ok=True)
            probe.write_text('#!/bin/sh\nprintf \'{"status":"ok","changed":false}\\n\'\n')
            edit(manifest, lambda data: data.update(files=data['files'] + ['assets/probe.sh'], scripts=[{
                'id': 'accounts', 'source': 'assets/probe.sh', 'phase': 'account_apply',
                'execution': 'once', 'secretInputs': {'passwords': {'valueFrom': 'account_batch'}}}, {
                'id': 'integrate', 'source': 'assets/probe.sh', 'phase': 'connection_apply', 'execution': 'once',
                'argv': [{'valueFrom': 'parameter', 'name': 'OPTIONS'}, {'valueFrom': 'endpoint'}],
                'secretInputs': {'token': {'valueFrom': 'provided_connection', 'name': 'admin', 'credential': 'password'}}}]))
            output = Path(directory) / 'rows.json'
            play = Path(directory) / 'resolve.yml'
            play.write_text(json.dumps([dict(hosts='localhost', connection='local', gather_facts=False,
                tasks=[{'ansible.builtin.include_role': {'name': 'platform.core.resolve_application_libraries'}},
                       {'ansible.builtin.copy': {'content': '{{ platform_application_rows | to_json }}',
                                                'dest': str(output), 'mode': '0600'}, 'no_log': True}])]))
            env = dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
                       ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections'))
            def resolve():
                command = ['ansible-playbook', '-i', str(root / 'inventory/hosts.yml'), str(play),
                           '-e', 'platform_project_root=' + str(root), '-e', 'platform_contracts_root=' + str(ROOT / 'contracts')]
                result = subprocess.run(command, capture_output=True, text=True, timeout=90, env=env)
                self.assertEqual(0, result.returncode, 'Native export resolution failed')
                rows = json.loads(output.read_text())
                state = json.loads(vars_path.read_text())['platform_desired_state']
                hosts = {name: {'ansibleHost': address, 'platformDeployments': {'docker': {}}}
                         for name, address in [('node1', '192.0.2.11'), ('node2', '192.0.2.12')]}
                effective = {'services': {'vault-main': {'configuration': {'port': {'value': 8200, 'state': 'RESOLVED'}}}}}
                projection = project(rows, state, effective, {}, hosts)
                self.assertEqual('PASS', projection['status'], projection['findings'])
                return rows, projection['libraries']
            rows, libraries = resolve()
            instance = libraries['sdku']['instances']['apigateway-sdku']
            self.assertEqual('https://apigateway-cspa.apps.example.test', instance['connections']['identity']['url'])
            self.assertEqual({'tenant': 'override', 'origin': 'https://cspa.example.test',
                              'override_origin': 'cspa-override',
                              'nested': {'enabled': True, 'ports': [8443]}},
                             instance['connections']['identity']['parameters'])
            self.assertEqual({'apply_script': 'integrate'}, instance['connections']['identity']['connectionProvisioner'])
            self.assertIn('identity', instance['credentialRequirements'])
            self.assertTrue(instance['agentRequired'])
            self.assertEqual('https://apigateway-cspa.apps.example.test', rows[-1]['settings']['environment']['API_ENDPOINT'])
            edit(vars_path, lambda data: data['platform_desired_state']['applicationLibraryDeployments']['sdku']['applications']['gateway']['overrides']['connections']['identity'].update(enabled=False))
            _, libraries = resolve()
            disabled = libraries['sdku']['instances']['apigateway-sdku']
            self.assertNotIn('identity', disabled['connections'])
            self.assertEqual({}, disabled['credentialRequirements'])
            self.assertEqual({}, disabled['secretBindings'])
            source = {'kind': 'vault_ref', 'binding': 'secrets', 'mount': 'secret', 'document': 'fixture/admin', 'field': 'password'}
            edit(vars_path, lambda data: data['platform_desired_state']['applicationLibraryDeployments']['cspa']['provided_connections']['admin'].update(
                credentials={'password': {'source': source}}))
            _, libraries = resolve()
            self.assertEqual(source, libraries['cspa']['providedConnections']['admin']['credentials']['password']['source'])

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
    def test_templated_library_values_are_reused_only_within_library_and_host(self):
        with tempfile.TemporaryDirectory(prefix='application-library-context-') as directory:
            root = Path(directory) / 'project'
            shutil.copytree(ROOT / 'examples/valid/application-libraries', root)
            second = root / 'application-packages/second/1.0.0'
            shutil.copytree(root / 'application-packages/apigateway/1.0.0', second)
            role = second / 'roles/application_apigateway'
            role.rename(second / 'roles/application_second')
            manifest = second / 'application.yml'
            data = json.loads(manifest.read_text())
            data['name'] = 'second'
            data['files'] = [name.replace('application_apigateway/', 'application_second/') for name in data['files']]
            manifest.write_text(json.dumps(data))
            defaults = second / 'roles/application_second/defaults/main.yml'
            data = json.loads(defaults.read_text())
            data['platform_application_definition']['name'] = 'second'
            defaults.write_text(json.dumps(data))
            vars_path = root / 'inventory/group_vars/all/platform-installer.yml'
            data = json.loads(vars_path.read_text())
            for library, deployment in data['platform_desired_state']['applicationLibraryDeployments'].items():
                deployment['applications']['second'] = {'overrides': {'environment': {'QA_SLOT': 'second'}}}
                deployment['overrides'] = {'environment': {'QA_OVERRIDE': '{{ library_instance_id }}-{{ qa_host_marker }}'}}
                path = root / f'library-packages/{library}/1.0.0/roles/library_{library}/defaults/main.yml'
                definition = json.loads(path.read_text())
                definition['platform_library_definition']['slots']['second'] = {'applicationRef': 'second@1.0.0'}
                definition['platform_library_definition']['defaults'] = {
                    'environment': {'QA_HOST': '{{ qa_host_marker }}',
                                    'QA_RESOURCE': '{{ library_resources.applicationDatabase.parameters.name }}'},
                    'parameters': {'QA_TYPED': {'enabled': True, 'ports': [8443]},
                                   'QA_NUMBER': '{{ [1, 2, 3] | sum }}'},
                }
                definition['platform_library_definition']['resource_defaults'] = {
                    'postgresql': {'databases': {'applicationDatabase': {'name': '{{ library_instance_id }}-{{ qa_host_marker }}'}}},
                }
                path.write_text(json.dumps(definition))
            vars_path.write_text(json.dumps(data))
            for node in ('node1', 'node2'):
                path = root / f'inventory/host_vars/{node}/platform-installer.yml'
                data = json.loads(path.read_text())
                data['platform_application_libraries'] = {'cspa': {}, 'sdku': {}}
                data['qa_host_marker'] = node
                path.write_text(json.dumps(data))
            output = Path(directory) / 'rows.json'
            play = Path(directory) / 'resolve.yml'
            app_defaults = root / 'application-packages/apigateway/1.0.0/roles/application_apigateway/defaults/main.yml'
            broken = json.loads(app_defaults.read_text())
            broken['platform_application_definition']['defaults']['environment']['QA_BAD'] = (
                "{{ qa_missing_value if library_instance_id == 'sdku' else 'ok' }}")
            broken_defaults = Path(directory) / 'broken.yml'
            broken_defaults.write_text(json.dumps(broken))
            play.write_text(json.dumps([dict(hosts='localhost', connection='local', gather_facts=False, tasks=[
                {'ansible.builtin.include_role': {'name': 'platform.core.resolve_application_libraries'}},
                {'ansible.builtin.assert': {'that': ['platform_application_findings | length == 0'],
                                          'fail_msg': '{{ platform_application_findings | to_json }}'}},
                {'ansible.builtin.copy': {'content': '{{ platform_application_rows | to_json }}',
                                         'dest': str(output), 'mode': '0600'}, 'no_log': True},
                {'ansible.builtin.copy': {'src': str(broken_defaults), 'dest': str(app_defaults), 'mode': '0600'},
                 'no_log': True},
                {'ansible.builtin.include_role': {'name': 'platform.core.resolve_application_libraries'}},
                {'ansible.builtin.assert': {'that': [
                    'platform_application_rows | length == 6', 'platform_application_findings | length == 2']}},
            ])]))
            env = dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
                       ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections'))
            result = subprocess.run(['ansible-playbook', '-i', str(root / 'inventory/hosts.yml'), str(play),
                '-e', 'platform_project_root=' + str(root), '-e', 'platform_contracts_root=' + str(ROOT / 'contracts')],
                env=env, capture_output=True, text=True, timeout=120)
            self.assertEqual(0, result.returncode, result.stdout[-5000:] + result.stderr[-1000:])
            shared_task = 'TASK [platform.core.resolve_application_libraries : Вычисление общих значений библиотеки по умолчанию после обработки ресурсов]'
            row_task = 'TASK [platform.core.resolve_application_libraries : Сбор служебной записи рассчитанных параметров для структурированных операций]'
            self.assertEqual(8, result.stdout.count(shared_task))
            self.assertEqual(8, result.stdout.count('TASK [platform.core.resolve_application_libraries : '
                'Сохранение общих настроек библиотеки в контексте узла]'))
            self.assertEqual(14, result.stdout.count(row_task))
            rows = json.loads(output.read_text())
            self.assertEqual(8, len(rows))
            for row in rows:
                expected = row['libraryId'] + '-' + row['hostId']
                self.assertEqual(row['hostId'], row['settings']['environment']['QA_HOST'])
                self.assertEqual(row['libraryId'], row['settings']['environment']['QA_RESOURCE'])
                self.assertEqual(expected, row['resourceDefaults']['postgresql']['databases']['applicationDatabase']['name'])
                self.assertEqual(expected, row['settings']['environment']['QA_OVERRIDE'])
                self.assertEqual({'enabled': True, 'ports': [8443]}, row['settings']['parameters']['QA_TYPED'])
                self.assertEqual(6, row['settings']['parameters']['QA_NUMBER'])
                if row['slotId'] == 'second':
                    self.assertEqual('second', row['settings']['environment']['QA_SLOT'])

    def test_rows_preserve_placement_order_and_clear_between_role_invocations(self):
        with tempfile.TemporaryDirectory(prefix='application-row-order-') as directory:
            root = Path(directory) / 'project'
            shutil.copytree(ROOT / 'examples/valid/application-libraries', root)
            include = {'ansible.builtin.include_role': {'name': 'platform.core.resolve_application_libraries'}}
            ordered_hosts = "platform_application_rows | map(attribute='hostId') | list"
            ordered_libraries = "platform_application_rows | map(attribute='libraryId') | list"
            play = Path(directory) / 'rows.yml'
            defaults = root / 'application-packages/apigateway/1.0.0/roles/application_apigateway/defaults/main.yml'
            restored_defaults = Path(directory) / 'restored-defaults.yml'
            restored_defaults.write_text(defaults.read_text())
            broken_defaults = Path(directory) / 'broken-defaults.yml'
            definition = json.loads(defaults.read_text())
            definition['platform_application_definition']['defaults']['environment']['QA_UNDEFINED'] = (
                "{{ qa_undefined_application_input if library_instance_id == 'sdku' else 'ok' }}")
            broken_defaults.write_text(json.dumps(definition))
            unknown_connection_defaults = Path(directory) / 'unknown-connection.yml'
            definition = json.loads(defaults.read_text())
            definition['platform_application_definition']['connections'] = ['unknown-connection']
            unknown_connection_defaults.write_text(json.dumps(definition))
            tasks = [
                include,
                {'ansible.builtin.assert': {'that': [
                    ordered_hosts + " == ['node1', 'node1', 'node2']",
                    ordered_libraries + " == ['cspa', 'sdku', 'sdku']",
                ]}},
                {'ansible.builtin.copy': {'src': str(broken_defaults), 'dest': str(defaults), 'mode': '0600'},
                 'no_log': True},
                include,
                {'ansible.builtin.assert': {'that': [
                    ordered_libraries + " == ['cspa']",
                    "platform_application_findings | length > 0",
                ]}},
                {'ansible.builtin.copy': {'src': str(unknown_connection_defaults), 'dest': str(defaults), 'mode': '0600'},
                 'no_log': True},
                include,
                {'ansible.builtin.assert': {'that': [
                    'platform_application_rows == []',
                    "platform_application_findings | selectattr('code', 'equalto', 'APPLICATION_INPUT_INVALID') | "
                    "map(attribute='field') | list == ["
                    "'applicationLibraryDeployments.cspa.applications.gateway.placements.node1', "
                    "'applicationLibraryDeployments.sdku.applications.gateway.placements.node1', "
                    "'applicationLibraryDeployments.sdku.applications.gateway.placements.node2']",
                ]}},
                {'ansible.builtin.copy': {'src': str(restored_defaults), 'dest': str(defaults), 'mode': '0600'},
                 'no_log': True},
                include,
                {'ansible.builtin.assert': {'that': [
                    ordered_hosts + " == ['node1', 'node1', 'node2']",
                    ordered_libraries + " == ['cspa', 'sdku', 'sdku']",
                    'platform_application_findings | length == 0',
                ]}},
                {'ansible.builtin.set_fact': {'platform_desired_state': (
                    "{{ platform_desired_state | combine({'applicationLibraryDeployments': {}}) }}")}},
                include,
                {'ansible.builtin.assert': {'that': ['platform_application_rows == []']}},
            ]
            play.write_text(json.dumps([dict(hosts='localhost', connection='local', gather_facts=False, tasks=tasks)]))
            # Replace the desired-state fact in the last invocation, including its empty deployments.
            env = dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
                       ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections'),
                       ANSIBLE_HASH_BEHAVIOUR='replace')
            result = subprocess.run(['ansible-playbook', '-i', str(root / 'inventory/hosts.yml'), str(play),
                '-e', 'platform_project_root=' + str(root), '-e', 'platform_contracts_root=' + str(ROOT / 'contracts')],
                capture_output=True, text=True, timeout=90, env=env)
            self.assertEqual(0, result.returncode, result.stdout[-4000:] + result.stderr[-1000:])
            self.assertEqual(5, result.stdout.count(
                'TASK [platform.core.resolve_application_libraries : Сбор рассчитанных записей приложений в порядке размещений]'))
            self.assertIn('the output has been hidden', result.stdout)

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
                consumer['shared_secrets'] = {'client': {'source': {'kind': 'runtime_secret_ref', 'ref': 'explicit-client'}}}
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
                    library['shared_secrets'] = {'client': {'source': {'kind': 'generated', 'profile': 'client_secret'}}}
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
                settings['provisioner']['secret_bindings']['QA_CLIENT'] = {
                    'requires_connections': ['identity'], 'source': {'library_secret': 'client'}}
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
            def resolve(expected_status='PASS'):
                command = ['ansible-playbook', '-i', str(root / 'inventory/hosts.yml'), str(play),
                           '-e', 'platform_project_root=' + str(root), '-e', 'platform_contracts_root=' + str(ROOT / 'contracts')]
                result = subprocess.run(command, capture_output=True, text=True, timeout=90, env=env)
                self.assertEqual(0, result.returncode, 'Native export resolution failed')
                self.assertEqual(1, result.stdout.count(
                    'TASK [platform.core.resolve_application_libraries : Сбор рассчитанных записей приложений в порядке размещений]'))
                self.assertEqual(1, result.stdout.count(
                    'TASK [platform.core.resolve_application_libraries : Определение топологии подключений по параметрам пакета и установки]'))
                rows = json.loads(output.read_text())
                state = json.loads(vars_path.read_text())['platform_desired_state']
                hosts = {name: {'ansibleHost': address, 'platformDeployments': {'docker': {}}}
                         for name, address in [('node1', '192.0.2.11'), ('node2', '192.0.2.12')]}
                effective = {'services': {'vault-main': {'configuration': {'port': {'value': 8200, 'state': 'RESOLVED'}}}}}
                projection = project(rows, state, effective, {}, hosts)
                self.assertEqual(expected_status, projection['status'], projection['findings'])
                if expected_status != 'PASS':
                    self.assertTrue(any(row['code'] == 'APPLICATION_PROVIDED_CONNECTION_INVALID'
                                        and row['field'].endswith('.connections.identity')
                                        for row in projection['findings']), projection['findings'])
                return rows, projection['libraries']
            rows, libraries = resolve()
            self.assertTrue(all(row['providedConnections'] == {} for row in rows if row['libraryId'] == 'sdku'))
            self.assertEqual(libraries['sdku']['sharedSecretRequirements']['client']['source'],
                             {'kind': 'runtime_secret_ref', 'ref': 'explicit-client'})
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
            edit(vars_path, lambda data: data['platform_desired_state']['applicationLibraryDeployments']['sdku']['applications']['gateway']['overrides']['connections']['identity'].update(enabled=True))
            edit(vars_path, lambda data: data['platform_desired_state']['applicationLibraryDeployments']['sdku']['bindings']['identity-admin']['providedConnectionRef'].update(name='missing'))
            edit(defaults, lambda data: data['platform_application_definition']['defaults']['environment'].update(API_ENDPOINT='fixture'))
            resolve(expected_status='BLOCKED')

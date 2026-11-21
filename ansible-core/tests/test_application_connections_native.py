"""Native defaults/overrides and exports resolve before consumer template expansion."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils'))
from application_libraries import project
sys.path.insert(0, str(ROOT / 'ansible-core/collections'))
from ansible_collections.platform.core.plugins.action.prepare_application_libraries import ActionModule
from ansible_collections.platform.core.plugins.action.prepare_application_connections import ActionModule as ConnectionsAction


class PlacementTemplateTests(unittest.TestCase):
    def test_common_render_requires_equal_typed_inputs_and_keeps_external_reads_fresh(self):
        action = object.__new__(ActionModule)
        action._loader = DataLoader()
        memo = dict(values={}, expressions={}, rendered=0, reused=0)
        expression = '{{ application_parameters.node }}'
        for host in ('one', 'two', 'two'):
            variables = dict(application_parameters={'node': host})
            actual = action._render_common(expression, action._native_templar(variables), variables, memo)
            self.assertEqual(host, actual)
        self.assertEqual(2, memo['rendered'])
        self.assertEqual(1, memo['reused'])
        before = memo['reused']
        for host in ('one', 'two'):
            variables = dict(application_job={'hostId': host},
                application_parameters={'node': '{{ application_job.hostId }}'})
            self.assertEqual(host, action._render_common(expression, action._native_templar(variables), variables, memo))
        self.assertEqual(before, memo['reused'])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, 'input.txt')
            source = "{{ lookup('file', source_path) }}"
            for text in ('first', 'second'):
                path.write_text(text)
                variables = dict(source_path=str(path))
                self.assertEqual(text, action._render_common(source, action._native_templar(variables), variables, memo))
            self.assertEqual(before, memo['reused'])

    def test_common_render_does_not_reuse_custom_filters_or_unknown_aliases(self):
        action = object.__new__(ActionModule)
        action._loader = DataLoader()
        memo = dict(values={}, expressions={}, rendered=0, reused=0)
        calls = []
        for host in ('one', 'two'):
            variables = dict(qa_alias='{{ application_job.hostId }}', application_job={'hostId': host})
            templar = action._native_templar(variables)
            templar.environment.filters['qa_host'] = lambda value: calls.append(value) or value
            self.assertEqual(host, action._render_common('{{ qa_alias | qa_host }}', templar, variables, memo))
        self.assertEqual(['one', 'two'], calls)
        self.assertEqual(0, memo['reused'])
        for host in ('one', 'two'):
            variables = dict(application_name='same')
            templar = action._native_templar(variables)
            templar.environment.filters['upper'] = lambda value: host
            self.assertEqual(host, action._render_common('{{ application_name | upper }}', templar, variables, memo))
        self.assertEqual(0, memo['reused'])

    def test_combined_placement_matches_staged_native_resolution(self):
        action = object.__new__(ActionModule)
        action._loader = DataLoader()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, 'main.yml')
            path.write_text(json.dumps({'platform_application_definition': {
                'identity_environment': ['INSTANCE'], 'defaults': {
                    'parameters': {'number': '{{ 3 * 2 }}', 'ports': [1], 'typed': True},
                    'environment': {'INSTANCE': '{{ application_instance_id }}',
                                    'HOST': '{{ application_job.hostId }}',
                                    'VALUE': '{{ application_parameters.number + 1 }}',
                                    'PEERS': '{{ application_placements | map(attribute="hostId") | list }}'}}}}))
            for host in ('one', 'two'):
                for inherit in (True, False):
                    job = dict(libraryId='lib', slotId='alias', hostId=host, instanceId='alias-lib',
                        skipConnectionTopology=True, connections={},
                        application=dict(defaultsPath=str(path), version='1.0.0', digest='app', name='package'),
                        library=dict(digest='library', definition={}),
                        deployment=dict(libraryRef='lib@1.0.0', runtimeRef='docker', bindings={}),
                        slot=dict(inherit_defaults=inherit, overrides={'parameters': {'ports': [2]}}),
                        instance={'overrides': {'environment': {'LEVEL': 'instance'}}},
                        hostOverride={'parameters': {'host': host}, 'environment': {'LEVEL': host}})
                    variables = dict(application_job=job, application_instance_id='alias-lib',
                        application_name='package', library_instance_id='lib',
                        application_placements=[{'hostId': 'one'}, {'hostId': 'two'}],
                        _application_shared=dict(defaults={'parameters': {'shared': 9}},
                                                 overrides={'parameters': {'ports': [3]}}),
                        _application_library_endpoint={}, _application_resource_defaults={},
                        _application_resources={}, _application_connections={},
                        library_namespace={'platform_library_definition': {'runtime_directory': '~/{{ library_instance_id }}'}})
                    original = json.loads(json.dumps(variables))
                    action._task = SimpleNamespace(args={'application_parameters': True})
                    parameters = action.run(task_vars=variables)['parameters']
                    staged = dict(variables, application_parameters=parameters)
                    action._task = SimpleNamespace(args={'application_defaults': True})
                    staged['_application_defaults'] = action.run(task_vars=staged)
                    action._task = SimpleNamespace(args={'resolved_row': True, 'library_namespace': 'library_namespace'})
                    expected = action.run(task_vars=staged)
                    action._task = SimpleNamespace(args={'placement': True, 'library_namespace': 'library_namespace'})
                    actual = action.run(task_vars=variables)
                    self.assertNotIn('failed', actual)
                    self.assertEqual(expected['row'], actual['row'])
                    self.assertEqual(expected['inherited'], actual['inherited'])
                    self.assertEqual(parameters, actual['parameters'])
                    self.assertEqual(7, actual['row']['settings']['environment']['VALUE'])
                    self.assertEqual(host, actual['row']['settings']['environment']['LEVEL'])
                    self.assertEqual([3] if inherit else [2], actual['parameters']['ports'])
                    self.assertEqual(original, variables)
                    bad = json.loads(path.read_text())
                    bad['platform_application_definition']['defaults']['environment']['BAD'] = '{{ missing.required }}'
                    bad_path = Path(folder, 'bad.yml')
                    bad_path.write_text(json.dumps(bad))
                    broken = dict(variables, application_job=dict(job, application=dict(job['application'], defaultsPath=str(bad_path))))
                    failure = action.run(task_vars=broken)
                    self.assertTrue(failure['failed'])
                    self.assertNotIn('row', failure)
                    self.assertEqual('APPLICATION_INPUT_INVALID', failure['finding']['code'])

    def test_peer_templates_share_compact_context_without_internal_jobs(self):
        action = object.__new__(ActionModule)
        action._loader = DataLoader()
        placements = [dict(hostId='one', address='192.0.2.1', ports={'port-2': {'published': 17800}}),
                      dict(hostId='two', address='192.0.2.2', ports={'port-2': {'published': 17801}})]
        context = dict(application_placements=placements, application_job={'hostId': 'one'},
                       groups={'all': ['localhost', 'two', 'one']})
        for app, field, expected in (
            ('keycloak', 'KC_INITIAL_HOSTS', '192.0.2.1[17800],192.0.2.2[17801]'),
            ('grant-access', 'HZ_NETWORK_JOIN_TCPIP_MEMBERS', '192.0.2.1:17800,192.0.2.2:17801'),
        ):
            path = ROOT / f'examples/szi/application-packages/{app}/1.0.0/roles/application_{app}/defaults/main.yml'
            env = action._loader.load_from_file(str(path))['platform_application_definition']['defaults']['environment']
            self.assertEqual(expected, action._native_templar(context).template(env[field]))
        for app in ('sdku-telemechanics', 'sdku-vtor', 'sdku-knp', 'sdku-status-calculation', 'sdku-tank-farm'):
            path = ROOT / f'examples/sdku/application-packages/{app}/1.0.0/roles/application_{app}/defaults/main.yml'
            env = action._loader.load_from_file(str(path))['platform_application_definition']['defaults']['environment']
            templar = action._native_templar(context)
            self.assertEqual('two=$${SERVER_2_IP}:17801', templar.template(env['EVO_SERVICES_CONSENSUS_SERVICE_OTHER_INSTANCES']))
            self.assertFalse(templar.template(env['EVO_SERVICES_CONSENSUS_SERVICE_MOCK']))
            single = action._native_templar(dict(context, application_placements=placements[:1]))
            self.assertEqual('', single.template(env['EVO_SERVICES_CONSENSUS_SERVICE_OTHER_INSTANCES']))
            self.assertTrue(single.template(env['EVO_SERVICES_CONSENSUS_SERVICE_MOCK']))

    def test_native_lookup_uses_scoped_variables_without_copying_internal_payloads(self):
        class InternalPayload:
            def __deepcopy__(self, memo):
                raise AssertionError('Internal job/result collection traversed')

        action = object.__new__(ActionModule)
        action._loader = DataLoader()
        with tempfile.TemporaryDirectory() as folder:
            template = Path(folder, 'scope.j2')
            template.write_text('{{ marker }}:{{ values | sum }}')
            outer = dict(marker='previous-host', values=[99], _application_resolved=InternalPayload(),
                         _application_inputs=InternalPayload(),
                         application_placements=[{'hostId': 'one'}, {'hostId': 'two'}],
                         _application_resolved_row_0=InternalPayload(),
                         ansible_facts={'_application_resolved': InternalPayload(), 'operator_fact': 7})
            outer['vars'] = outer
            action._templar = Templar(loader=action._loader, variables=outer)
            scoped = action._placement_variables(outer)
            scoped.update(marker='current-host', values=[1, 2, 3])
            templar = action._native_templar(scoped)
            for lookup in ('lookup', 'query', 'q'):
                templar.available_variables['path'] = str(template)
                actual = templar.template("{{ " + lookup + "('template', path) }}")
                self.assertEqual('current-host:6' if lookup == 'lookup' else ['current-host:6'], actual)
            self.assertEqual(7, scoped['ansible_facts']['operator_fact'])
            self.assertIs(scoped, scoped['vars'])
            self.assertNotIn('_application_resolved', scoped['ansible_facts'])
            self.assertIn('_application_inputs', outer)
            self.assertNotIn('_application_inputs', scoped)
            self.assertEqual(['one', 'two'], templar.template(
                "{{ application_placements | map(attribute='hostId') | list }}"))

    def test_compact_placements_reuse_native_ports_and_preserve_literal_override_order(self):
        def job(host, slot='gateway', native=False):
            return dict(libraryId='lib', slotId=slot, hostId=host, connections={},
                skipConnectionTopology=not native,
                application={'definition': {'defaults': {'ports': {'tcp': {'container': 7000, 'published': 7100}}}}},
                slot={'overrides': {'ports': {'tcp': {'published': 7200}}}},
                instance={'overrides': {'ports': {'tcp': {'published': 7300}}}},
                hostOverride={'ports': {'tcp': {'published': 7400}}})
        native_ports = {'tcp': {'container': 9000, 'published': 9900}}
        values = dict(_application_inputs={'jobs': [job('two'), job('one'), job('one', 'native', True)]},
            platform_desired_state={}, hostvars={'one': {'ansible_host': '192.0.2.1'}, 'two': {}},
            platform_application_connection_rows=[dict(libraryId='lib', slotId='native', hostId='one',
                settings={'ports': native_ports})])
        result = object.__new__(ConnectionsAction).run(task_vars=values)
        self.assertNotIn('findings', result)
        members = result['placements']['lib']['gateway']
        self.assertEqual(['one', 'two'], [row['hostId'] for row in members])
        self.assertEqual(['192.0.2.1', 'two'], [row['address'] for row in members])
        self.assertEqual({'container': 7000, 'published': 7400}, members[0]['ports']['tcp'])
        self.assertIs(native_ports, result['placements']['lib']['native'][0]['ports'])
        self.assertNotIn('application', members[0])
        self.assertEqual(7100, values['_application_inputs']['jobs'][0]['application']['definition']['defaults']['ports']['tcp']['published'])

    def test_parameter_stage_preserves_precedence_types_and_deferred_environment(self):
        action = object.__new__(ActionModule)
        action._loader = DataLoader()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, 'main.yml')
            path.write_text(json.dumps({'platform_application_definition': {'defaults': {
                'parameters': {'client': {'name': '{{ application_instance_id }}', 'roles': ['reader']},
                               'ports': [1, 2], 'typed': True},
                'environment': {'DEFER': '{{ intentionally_not_available_yet.required }}'}}}}))
            action._task = SimpleNamespace(args={'application_parameters': True})
            for host in ('one', 'two'):
                job = {'application': {'defaultsPath': str(path)},
                       'slot': {'overrides': {'parameters': {'ports': [3]}}},
                       'instance': {'overrides': {'parameters': {'client': {'roles': ['writer']}}}},
                       'hostOverride': {'parameters': {'host': host}}}
                variables = {'application_job': job, 'application_instance_id': host,
                             '_application_shared': {'defaults': {'parameters': {'shared': 7}},
                                                     'overrides': {'parameters': {'ports': [4]}}}}
                result = action.run(task_vars=variables)
                self.assertNotIn('failed', result)
                self.assertEqual({'client': {'name': host, 'roles': ['writer']}, 'ports': [4],
                                  'typed': True, 'shared': 7, 'host': host}, result['parameters'])
                job['slot']['inherit_defaults'] = False
                result = action.run(task_vars=variables)
                self.assertNotIn('shared', result['parameters'])
                self.assertEqual([3], result['parameters']['ports'])


@unittest.skipUnless(shutil.which('ansible-playbook'), 'native Ansible required')
class NativeApplicationConnectionsTests(unittest.TestCase):
    def test_group_isolates_host_failures_parameters_aliases_and_resource_contexts(self):
        with tempfile.TemporaryDirectory(prefix='application-group-hosts-') as directory:
            root = Path(directory, 'project')
            shutil.copytree(ROOT / 'examples/valid/application-libraries', root)
            app_path = root / 'application-packages/apigateway/1.0.0/roles/application_apigateway/defaults/main.yml'
            original = json.loads(app_path.read_text())
            definition = original['platform_application_definition']
            definition['defaults'].setdefault('parameters', {})['QA_NODE'] = '{{ application_job.hostId }}'
            definition['defaults'].setdefault('environment', {}).update(
                QA_PARAMETER='{{ application_parameters.QA_NODE }}',
                QA_ALIAS='{{ vars.application_job.hostId }}', QA_CONTROLLER='{{ inventory_hostname }}',
                QA_PARAMETER_ALIAS='{{ vars.application_parameters.QA_NODE }}',
                QA_PARAMETER_FACT='{{ ansible_facts.application_parameters.QA_NODE }}')
            app_path.write_text(json.dumps(original))
            library_path = root / 'library-packages/sdku/1.0.0/roles/library_sdku/defaults/main.yml'
            library = json.loads(library_path.read_text())
            membership = root / 'inventory/host_vars/node2/platform-installer.yml'
            host = json.loads(membership.read_text())
            host['platform_application_libraries']['sdku']['overrides']['ports'] = {
                'http': {'container': 8765, 'published': 18765}}
            membership.write_text(json.dumps(host))
            output = Path(directory, 'rows.json')
            play = Path(directory, 'play.yml')
            play.write_text(json.dumps([dict(hosts='localhost', connection='local', gather_facts=False, tasks=[
                {'ansible.builtin.include_role': {'name': 'platform.core.resolve_application_libraries'}},
                {'ansible.builtin.assert': {'that': [
                    'platform_application_rows | length == 2',
                    'platform_application_findings | length == 1',
                    "platform_application_findings[0].field == 'applicationLibraryDeployments.sdku.applications.gateway.placements.' ~ qa_bad_host",
                    "_application_group_result.metrics.placements == 3",
                    "_application_group_result.metrics.instances == 2"]}},
                {'ansible.builtin.copy': {'content': '{{ platform_application_rows | to_json }}',
                                         'dest': str(output), 'mode': '0600'}, 'no_log': True},
            ])]))
            env = dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
                       ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections'))
            for failure_stage in ('environment', 'library'):
                if failure_stage == 'environment':
                    definition['defaults']['environment']['QA_FAIL'] = (
                        "{{ qa_missing.required if library_instance_id == 'sdku' and application_job.hostId == qa_bad_host else 'ok' }}")
                else:
                    definition['defaults']['environment'].pop('QA_FAIL')
                    library['platform_library_definition'].setdefault('resource_defaults', {}).setdefault(
                        'postgresql', {}).setdefault('databases', {})['applicationDatabase'] = {
                            'name': "{{ qa_missing.required if inventory_hostname == qa_bad_host else 'database_' ~ inventory_hostname }}"}
                app_path.write_text(json.dumps(original))
                library_path.write_text(json.dumps(library))
                for bad_host in ('node1', 'node2'):
                    result = subprocess.run(['ansible-playbook', '-i', str(root / 'inventory/hosts.yml'), str(play),
                        '-e', json.dumps(dict(platform_project_root=str(root), qa_bad_host=bad_host,
                                            platform_contracts_root=str(ROOT / 'contracts')))],
                        env=env, capture_output=True, text=True, timeout=90)
                    self.assertEqual(0, result.returncode, result.stdout[-2500:] + result.stderr[-500:])
                    rows = json.loads(output.read_text())
                    self.assertEqual(['cspa', 'sdku'], [row['libraryId'] for row in rows])
                    for row in rows:
                        values = row['settings']['environment']
                        self.assertEqual(row['hostId'], values['QA_PARAMETER'])
                        self.assertEqual(row['hostId'], values['QA_ALIAS'])
                        self.assertEqual(row['hostId'], values['QA_PARAMETER_ALIAS'])
                        self.assertEqual(row['hostId'], values['QA_PARAMETER_FACT'])
                        self.assertEqual('localhost', values['QA_CONTROLLER'])
                        if row['hostId'] == 'node2':
                            self.assertEqual(18765, row['settings']['ports']['http']['published'])

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
            for path in root.glob('application-packages/*/1.0.0/roles/*/defaults/main.yml'):
                definition = json.loads(path.read_text())
                definition['platform_application_definition']['defaults'].setdefault('environment', {})['QA_PEERS'] = (
                    '{{ application_placements | to_json }}')
                path.write_text(json.dumps(definition))
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
            self.assertEqual(2, result.stdout.count('TASK [platform.core.resolve_application_libraries : '
                'Расчёт общих и серверных настроек приложений]'))
            self.assertEqual(2, result.stdout.count('TASK [platform.core.resolve_application_libraries : '
                'Сохранение строк размещений и библиотечных контекстов]'))
            self.assertNotIn('TASK [platform.core.resolve_application_libraries : '
                'Загрузка проверенных параметров приложения по умолчанию в изолированное пространство имен]', result.stdout)
            self.assertNotIn('TASK [platform.core.resolve_application_libraries : '
                'Определение параметров приложения после привязки идентификатора размещения]', result.stdout)
            self.assertEqual(2, result.stdout.count('TASK [platform.core.resolve_application_libraries : '
                'Добавление подключений приложений в рассчитанную топологию]'))
            rows = json.loads(output.read_text())
            self.assertEqual(8, len(rows))
            for row in rows:
                expected = row['libraryId'] + '-' + row['hostId']
                peers = row['settings']['environment']['QA_PEERS']
                peers = json.loads(peers) if isinstance(peers, str) else peers
                self.assertEqual(['node1', 'node2'], [peer['hostId'] for peer in peers])
                for peer in peers:
                    actual = next(item for item in rows if item['libraryId'] == row['libraryId']
                                  and item['slotId'] == row['slotId'] and item['hostId'] == peer['hostId'])
                    self.assertEqual(actual['settings'].get('ports', {}), peer['ports'])
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
                'TASK [platform.core.resolve_application_libraries : Сохранение строк размещений и библиотечных контекстов]'))
            self.assertNotIn('QA_UNDEFINED', result.stdout)

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
                    'TASK [platform.core.resolve_application_libraries : Сохранение строк размещений и библиотечных контекстов]'))
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
            instance = libraries['sdku']['instances']['gateway-sdku']
            self.assertEqual('https://gateway-cspa.apps.example.test', instance['connections']['identity']['url'])
            self.assertEqual({'tenant': 'override', 'origin': 'https://cspa.example.test',
                              'override_origin': 'cspa-override',
                              'nested': {'enabled': True, 'ports': [8443]}},
                             instance['connections']['identity']['parameters'])
            self.assertEqual({'apply_script': 'integrate'}, instance['connections']['identity']['connectionProvisioner'])
            self.assertIn('identity', instance['credentialRequirements'])
            self.assertTrue(instance['agentRequired'])
            self.assertEqual('https://gateway-cspa.apps.example.test', rows[-1]['settings']['environment']['API_ENDPOINT'])
            edit(vars_path, lambda data: data['platform_desired_state']['applicationLibraryDeployments']['sdku']['applications']['gateway']['overrides']['connections']['identity'].update(enabled=False))
            _, libraries = resolve()
            disabled = libraries['sdku']['instances']['gateway-sdku']
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

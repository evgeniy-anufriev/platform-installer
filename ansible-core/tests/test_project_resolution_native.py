"""Real standalone Ansible resolution across independently staged requests."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which('ansible-playbook'), 'native Ansible required')
class NativeProjectResolutionTests(unittest.TestCase):
    def test_project_snapshot_with_implicit_localhost_and_explicit_root(self):
        for applications, secret_reference in ((False, None), (True, None), (False, 'invalid-reference')):
            with self.subTest(applications=applications, reference=secret_reference), tempfile.TemporaryDirectory(prefix='snapshot-root-') as folder:
                directory = Path(folder)
                project = directory / 'project'
                shutil.copytree(ROOT / 'examples/valid/application-libraries', project)
                inventory_path = project / 'inventory/hosts.yml'
                inventory = yaml.safe_load(inventory_path.read_text())
                inventory['all']['hosts'].pop('localhost')
                inventory_path.write_text(yaml.safe_dump(inventory))
                variables_path = project / 'inventory/group_vars/all/platform-installer.yml'
                variables = yaml.safe_load(variables_path.read_text())
                if not applications:
                    variables['platform_desired_state'].pop('applicationLibraryDeployments', None)
                    variables['platform_desired_state']['serviceDeployments']['clickhouse-main']['configuration'].pop('defaultCredential', None)
                kafka = variables['platform_desired_state']['serviceDeployments']['kafka-main']['configuration']
                kafka.pop('adminCredential', None)
                if secret_reference is not None:
                    kafka['adminCredential'] = {'passwordSecretRef': secret_reference}
                variables_path.write_text(yaml.safe_dump(variables))
                output = directory / 'snapshot.json'
                collections = [str(ROOT / 'ansible-core/collections')] + [str(path)
                    for path in sorted((ROOT / 'services').glob('*/ansible_collections'))]
                environment = dict(os.environ, ANSIBLE_COLLECTIONS_PATH=os.pathsep.join(collections),
                    ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
                    ANSIBLE_CALLBACKS_ENABLED='platform.core.project_snapshot_json',
                    PLATFORM_PROJECT_SNAPSHOT_OUTPUT=str(output))
                completed = subprocess.run(['ansible-playbook', '-i', str(inventory_path),
                    str(ROOT / 'ansible-core/playbooks/project-snapshot.yml'),
                    '-e', 'platform_project_root=project',
                    '-e', 'platform_service_catalog_path=' + str(ROOT / 'examples/catalog/service-catalog.yml')],
                    cwd=directory, env=environment, capture_output=True, text=True, timeout=90)
                self.assertEqual(0, completed.returncode, completed.stdout[-4000:] + completed.stderr[-1500:])
                self.assertNotIn('UNREACHABLE', completed.stdout)
                snapshot = json.loads(output.read_text())
                self.assertTrue(snapshot['projectRevision'].startswith('sha256:'))
                self.assertNotIn('adapterError', snapshot)
                code = 'RUNTIME_SECRET_REFERENCE_REQUIRED' if secret_reference is None else 'RUNTIME_SECRET_REFERENCE_INVALID'
                findings = [item for item in snapshot['findings'] if item['code'] == code and
                            item.get('field') == 'serviceDeployments.kafka-main.configuration.adminCredential']
                self.assertEqual(1, len(findings), snapshot['findings'])
                self.assertEqual('serviceDeployments.kafka-main.configuration.adminCredential', findings[0]['field'])
                self.assertEqual('WARNING' if secret_reference is None else 'BLOCKED', findings[0]['status'])
                if secret_reference is None:
                    self.assertIn('before plan approval', findings[0]['safeMessage'])
                    self.assertEqual('PASS', snapshot['status'], snapshot['findings'])
                    self.assertFalse(snapshot['partial'])
                else:
                    self.assertEqual('PARTIAL', snapshot['status'])
                if not applications:
                    clickhouse = [item for item in snapshot['findings'] if
                        item.get('field') == 'serviceDeployments.clickhouse-main.configuration.defaultCredential']
                    self.assertEqual(1, len(clickhouse), snapshot['findings'])
                    self.assertEqual('WARNING', clickhouse[0]['status'])

    def test_root_expressions_are_lazy_and_keep_inventory_fallback(self):
        from ansible.parsing.dataloader import DataLoader
        from ansible.template import Templar
        paths = [
            'collections/ansible_collections/platform/core/roles/project_resolution/tasks/main.yml',
            'collections/ansible_collections/platform/core/roles/resolve_application_libraries/tasks/main.yml',
            'playbooks/validate.yml', 'playbooks/applications/stages/resolve-runtime.yml',
            'playbooks/applications/stages/providers-resolve.yml',
            'playbooks/applications/tasks/provider-batch.yml',
            'playbooks/applications/tasks/provider-script.yml',
        ]
        def expressions(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in ('project_root', 'workingDirectory') and isinstance(item, str) and 'platform_project_root' in item:
                        yield item
                    else:
                        yield from expressions(item)
            elif isinstance(value, list):
                for item in value:
                    yield from expressions(item)
        for path in paths:
            for expression in expressions(yaml.safe_load((ROOT / 'ansible-core' / path).read_text())):
                with self.subTest(path=path):
                    explicit = Templar(loader=DataLoader(), variables={'platform_project_root': '/explicit/project',
                        'application_provider_script': {'runOn': 'execution_node'}})
                    self.assertEqual('/explicit/project', explicit.template(expression).strip())
                    fallback = Templar(loader=DataLoader(), variables={'inventory_dir': '/ordinary/project/inventory',
                        'hostvars': {'localhost': {'inventory_dir': '/ordinary/project/inventory'}},
                        'application_provider_script': {'runOn': 'execution_node'}})
                    self.assertEqual('/ordinary/project', fallback.template(expression).strip())

    def test_real_resolver_runs_once_then_reuses_without_target_contact(self):
        with tempfile.TemporaryDirectory(prefix='project-resolution-') as folder:
            directory = Path(folder)
            project = directory / 'project'
            shutil.copytree(ROOT / 'examples/valid/application-libraries', project)
            (project / 'project.yml').write_text(yaml.safe_dump(dict(
                apiVersion='platform.installer/v2alpha1', kind='PlatformProject',
                metadata=dict(id='resolution-qa', name='Resolution QA'))))
            runtime = {'bundleDigest': 'sha256:test', 'coreVersion': 'qa'}
            collections = [str(ROOT / 'ansible-core/collections')] + [str(path)
                for path in sorted((ROOT / 'services').glob('*/ansible_collections'))]
            environment = dict(os.environ, ANSIBLE_COLLECTIONS_PATH=os.pathsep.join(collections),
                               ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'))
            def call(number, expected_hit, cache=True):
                output = directory / ('snapshot-%s.json' % number)
                variables = dict(platform_project_root=str(project),
                    platform_service_catalog_path=str(ROOT / 'examples/catalog/service-catalog.yml'))
                if cache:
                    variables.update(platform_project_resolution_directory=str(directory / 'cache'),
                        platform_project_resolution_local_path=str(directory / ('request-%s.json' % number)),
                        platform_project_resolution_runtime=runtime)
                play = directory / 'play.yml'
                play.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False,
                    vars=variables, tasks=[{'ansible.builtin.include_role': {'name': 'platform.core.project_resolution'}},
                        {'ansible.builtin.assert': {'that': [
                            '_project_resolution_cache.hit == ' + str(expected_hit).lower(),
                            '(_application_inputs is defined) == ' + str(not expected_hit).lower()]}}])]))
                completed = subprocess.run(['ansible-playbook', '-i', str(project / 'inventory/hosts.yml'), str(play)],
                    env=dict(environment, ANSIBLE_CALLBACKS_ENABLED='platform.core.project_snapshot_json',
                             PLATFORM_PROJECT_SNAPSHOT_OUTPUT=str(output)),
                    capture_output=True, text=True, timeout=180)
                self.assertEqual(0, completed.returncode, completed.stdout[-6000:] + completed.stderr[-1500:])
                self.assertNotIn('UNREACHABLE', completed.stdout)
                return json.loads(output.read_text())
            first = call(1, False)
            second = call(2, True)
            self.assertEqual(first, second)
            variables = project / 'inventory/group_vars/all/platform-installer.yml'
            variables.write_text(variables.read_text() + '\n# changed desired bytes\n')
            third = call(3, False)
            self.assertNotEqual(first['projectRevision'], third['projectRevision'])
            call(4, True)
            call(5, False, cache=False)
            # External inputs remain fresh on every independent request; no
            # result artifact is published from an environment-dependent resolve.
            external = yaml.safe_load(variables.read_text())
            external['resolution_external_probe'] = "{{ lookup('env', 'HOME') }}"
            variables.write_text(yaml.safe_dump(external))
            call(6, False)
            call(7, False)
            self.assertFalse((directory / 'request-6.json').exists())
            self.assertFalse((directory / 'request-7.json').exists())

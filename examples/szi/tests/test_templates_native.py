"""Render every declared SZI template with native Ansible and resolved fixtures.

No target connections, Docker operations or runtime credentials are required.
"""
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

import yaml

SZI = Path(__file__).resolve().parents[1]
ROOT = SZI.parents[1]
PREFLIGHT = ROOT / 'ansible-core/collections/ansible_collections/platform/core/roles/application_runtime/tasks/preflight.yml'


@unittest.skipUnless(shutil.which('ansible-playbook'), 'native Ansible required on Execution Node')
class SziTemplateTests(unittest.TestCase):
    def render(self, explicit_override=False, missing_endpoint=False):
        applications = sorted((SZI / 'application-packages').iterdir())
        endpoints = {p.name: {'endpoint': {'fqdn': p.name + '.resolved.example'}} for p in applications}
        if missing_endpoint:
            endpoints.pop('nginx')
        sso = {'url': 'https://keycloak.resolved.example',
               'parameters': {'realm': 'master', 'proxy_url': 'https://nginx.resolved.example'}}
        library = {'instances': {p.name: {'applicationName': p.name, 'connections': {'sso': sso}}
                                 for p in applications}, 'providedConnections': {'sso': sso}}
        tasks = [{'ansible.builtin.set_fact': {
            'platform_endpoint_sources': endpoints,
            'application_snapshot': {'snapshot': {'applicationLibraries': {'libraries': {'szi': library}}}},
        }}]
        deployment = {'bindings': {'endpoint': {'endpointGroupRef': 'inherited'}},
                      'applications': {p.name: {} for p in applications}}
        if explicit_override:
            deployment['applications']['nginx'] = {'overrides': {'endpoint': {'endpoint_group': 'explicit'}}}
        common = {
            'application_project_id': 'qa', 'application_config_digest': '0' * 64,
            'library_instance_id': 'szi',
            'application_connections': {'sso': sso},
            'platform_desired_state': {
                'applicationLibraryDeployments': {'szi': deployment},
                'endpointGroups': {key: {'address': {'domain': key + '.example'}}
                                   for key in ('inherited', 'explicit')},
            },
            'library_runtime': {'library_id': 'szi', 'host_id': 'app2',
                                'connections': {'postgres': {'targets': [{'address': '192.0.2.10', 'port': 5432}]}}},
        }
        nginx_defaults = yaml.safe_load((SZI / 'application-packages/nginx/1.0.0/roles/application_nginx/defaults/main.yml').read_text())['platform_application_definition']['defaults']
        library_defaults = yaml.safe_load((SZI / 'library-packages/szi/1.0.0/roles/library_szi/defaults/main.yml').read_text())['platform_library_definition']
        tasks.append({'ansible.builtin.set_fact': common})
        tasks.append({'name': 'Render endpoint defaults with inherited or explicit group',
                      'ansible.builtin.set_fact': {
                          'qa_nginx_host': nginx_defaults['environment']['NGINX_HOST'],
                          'qa_grant_host': nginx_defaults['environment']['GA_HOST'],
                          'qa_proxy_url': library_defaults['provided_connections']['sso']['parameters']['proxy_url'],
                      }})
        nginx_domain = 'explicit.example' if explicit_override else 'inherited.example'
        tasks.append({'ansible.builtin.assert': {'that': [
            "qa_nginx_host == 'nginx." + nginx_domain + "'",
            "qa_grant_host == 'https://grant-access.inherited.example'",
            "qa_proxy_url == 'https://nginx." + nginx_domain + "'",
        ]}})
        production = yaml.safe_load(PREFLIGHT.read_text())
        config_task = next(t for t in production if t.get('name') ==
                           'Формирование конфигурационных файлов по шаблонам в защищённой памяти')
        expected_templates = set()
        for package in applications:
            name = package.name
            version = package / '1.0.0'
            defaults = yaml.safe_load((version / f'roles/application_{name}/defaults/main.yml').read_text())[
                'platform_application_definition']['defaults']
            settings = {k: copy.deepcopy(defaults[k]) for k in
                        ('user', 'restart', 'ports', 'config_files', 'config_directories', 'config_archives') if k in defaults}
            settings['command'] = ['/bin/true']
            if explicit_override and name == 'nginx':
                settings['ports']['port-1']['container'] = 28443
            configs = [dict(c, path=str(version / c['template'])) for c in settings.get('config_files', [])
                       if 'template' in c]
            if missing_endpoint and name == 'nginx':
                configs = [c for c in configs if c['destination'] == 'scada-lawellet.conf']
            runtime = {
                'base_compose_path': '/qa/base.yml', 'base_service': 'base', 'image': 'fixture:1',
                'container_name': name, 'config_path': '/qa/config', 'pki_path': '/qa/pki', 'vault_path': '/qa/vault',
                'application_command': ['/bin/true'],
                'vault': {'endpoint_url': 'https://vault.example', 'ca_container_path': '/qa/ca.pem',
                          'auth_mount': 'auth/approle', 'role_id_container_path': '/qa/role-id', 'env_templates': []},
            }
            context = dict(common, application_instance_id=name, application_effective=settings,
                           application_environment={'KEYCLOAK_MEMORY_LIMIT': '2G'}, application_runtime=runtime,
                           application_runtime_job={'instanceId': name, 'slotId': name, 'libraryId': 'szi',
                                                    'projectId': 'qa', 'settings': settings, 'configs': configs,
                                                    'integrationConsumers': []}, application_config_contents=[])
            tasks.append({'ansible.builtin.set_fact': context})
            # Use the exact production task, including lookup options and no_log.
            tasks.append(copy.deepcopy(config_task))
            templates = set(version.rglob('*.j2')) | {Path(c['path']) for c in configs}
            for path in sorted(templates):
                expected_templates.add(path)
                tasks.append({'name': 'Render ' + str(path.relative_to(SZI)),
                              'ansible.builtin.set_fact': {
                                  'qa_rendered': "{{ lookup('ansible.builtin.template', " + repr(str(path)) +
                                                 ", convert_data=False) }}"}})
                if path.name == 'scada-lawellet.conf':
                    tasks.append({'ansible.builtin.assert': {'that': [
                        "'server_name nginx.resolved.example;' in qa_rendered",
                        "'listen ' ~ (application_effective.ports['port-1'].container | string) ~ ' ssl' in qa_rendered",
                    ]}})
                elif path.suffix == '.json' or path.name.endswith('.json.j2'):
                    tasks.append({'ansible.builtin.assert': {'that': '(qa_rendered | from_json) is mapping'}})
                elif path.name == 'data.env':
                    tasks.append({'ansible.builtin.assert': {'that': [
                        "'GA_HOST=\"https://grant-access.resolved.example\"' in qa_rendered",
                        "'COMMON_REDIRECT_URL=\"https://nginx.resolved.example/grant-access-front/\"' in qa_rendered",
                    ]}})
        for path in sorted((SZI / 'library-packages').rglob('*.j2')):
            expected_templates.add(path)
            tasks.append({'name': 'Render ' + str(path.relative_to(SZI)), 'ansible.builtin.set_fact': {
                'qa_rendered': "{{ lookup('ansible.builtin.template', " + repr(str(path)) + ", convert_data=False) }}"}})
        # Catch newly added Jinja files even if omitted from the package declarations.
        self.assertEqual(set(SZI.rglob('*.j2')), {p for p in expected_templates if p.suffix == '.j2'})
        with tempfile.TemporaryDirectory(prefix='szi-template-') as directory:
            play = Path(directory) / 'play.yml'
            play.write_text(yaml.safe_dump([{'hosts': 'localhost', 'gather_facts': False, 'tasks': tasks}]))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', '-c', 'local', str(play)],
                                    capture_output=True, text=True, timeout=120, env=dict(
                                        os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
                                        ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections'),
                                        ANSIBLE_STDOUT_CALLBACK='default'))
        return result

    def test_all_templates_without_application_endpoint_override(self):
        result = self.render()
        self.assertEqual(0, result.returncode, result.stdout[-5000:] + result.stderr[-1000:])

    def test_all_templates_with_override_use_resolved_endpoint_and_effective_port(self):
        result = self.render(explicit_override=True)
        self.assertEqual(0, result.returncode, result.stdout[-5000:] + result.stderr[-1000:])

    def test_missing_resolved_endpoint_fails_instead_of_inventing_address(self):
        result = self.render(missing_endpoint=True)
        self.assertNotEqual(0, result.returncode)
        tasks = re.findall(r'TASK \[([^\]\n]+)\]', result.stdout)
        self.assertEqual('Формирование конфигурационных файлов по шаблонам в защищённой памяти', tasks[-1])


if __name__ == '__main__':
    unittest.main()

"""Package role files use native Ansible templating and ordinary parameter overrides."""
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
class LibraryGroupRoleFilesTests(unittest.TestCase):
    def test_account_files_resolve_direct_realm_and_client_roles(self):
        for app in ('grant-access', 'grant-access-audit'):
            with self.subTest(application=app), tempfile.TemporaryDirectory() as directory:
                defaults = ROOT / f'examples/szi/application-packages/{app}/1.0.0/roles/application_{app}/defaults/main.yml'
                definition = yaml.safe_load(defaults.read_text())['platform_application_definition']
                account = definition['defaults']['accounts']['sso']
                self.assertEqual('admin-' + app, account['credentials']['username']['source']['value'])
                play = Path(directory) / 'account.yml'
                play.write_text(json.dumps([dict(hosts='localhost', connection='local', gather_facts=False,
                    vars=dict(application_job={'application': {'defaultsPath': str(defaults)}},
                              account_parameters=account['parameters']),
                    tasks=[{'ansible.builtin.assert': {'that': [
                        "'admin' in account_parameters.roles_file.realm_roles",
                        "'manage-users' in account_parameters.roles_file.client_roles['master-realm']",
                        "'view-profile' in account_parameters.roles_file.client_roles.account",
                        "account_parameters.groups == ['ТУЗ']"]}}])]), encoding='utf-8')
                result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(play)],
                    env=dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg')),
                    capture_output=True, text=True, timeout=60)
                self.assertEqual(0, result.returncode, result.stdout[-2500:] + result.stderr[-1000:])

    def test_package_files_resolve_and_library_override_replaces_the_group_list(self):
        for library, group in [('szi', 'ТУЗ'), ('sdku', 'Администратор СДКУ')]:
            with self.subTest(library=library), tempfile.TemporaryDirectory() as directory:
                defaults = ROOT / f'examples/{library}/library-packages/{library}/1.0.0/roles/library_{library}/defaults/main.yml'
                play = Path(directory) / 'roles.yml'
                play.write_text(json.dumps([dict(hosts='localhost', connection='local', gather_facts=False,
                    vars=dict(library_instance_id='sample', platform_project_root=str(ROOT / 'examples' / library),
                              parameters_definition=yaml.safe_load(defaults.read_text())['platform_library_definition']['defaults']['parameters']),
                    tasks=[
                        {'ansible.builtin.set_fact': {'parameters': '{{ parameters_definition }}'}},
                        {'ansible.builtin.assert': {'that': [
                            'parameters.IDENTITY_GROUPS[0].name == ' + json.dumps(group),
                            'parameters.IDENTITY_GROUPS[0].roles_file.realm_roles is sequence',
                            'parameters.IDENTITY_GROUPS[0].roles_file.client_roles is mapping']}},
                        {'ansible.builtin.set_fact': {'parameters': "{{ parameters | combine({'IDENTITY_GROUPS': []}, recursive=true, list_merge='replace') }}"}},
                        {'ansible.builtin.assert': {'that': ['parameters.IDENTITY_GROUPS == []']}}
                    ])]), encoding='utf-8')
                result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(play)],
                    env=dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg')),
                    capture_output=True, text=True, timeout=60)
                self.assertEqual(0, result.returncode, result.stdout[-2500:] + result.stderr[-1000:])

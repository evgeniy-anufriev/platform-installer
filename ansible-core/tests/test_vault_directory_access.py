import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROLE = Path(__file__).resolve().parents[2] / "services/vault/ansible_collections/platform/vault/roles/vault_tls"


class VaultDirectoryAccessTests(unittest.TestCase):
    def test_parent_traversal_does_not_grant_service_write_or_public_access(self):
        source = yaml.safe_load((ROLE / "tasks/provision.yml").read_text())
        task = next(task for task in source if task['name'] ==
                    'Ensure the deployment-level Vault directories remain root-owned')
        self.assertEqual({'path': '{{ item }}', 'state': 'directory', 'owner': 'root',
                          'group': '{{ platform_vault_group }}', 'mode': '0750'},
                         task['ansible.builtin.file'])
        self.assertEqual(3, len(task['loop']))

    @unittest.skipUnless(hasattr(os, 'geteuid') and os.geteuid() == 0 and
                         shutil.which('ansible-playbook') and shutil.which('runuser'),
                         'Local root Ansible permission proof required')
    def test_real_file_tasks_allow_service_access_and_repeat_without_changes(self):
        import grp
        import pwd
        account = pwd.getpwnam('nobody')
        group = grp.getgrgid(account.pw_gid).gr_name
        source = yaml.safe_load((ROLE / 'tasks/provision.yml').read_text())
        names = ['Ensure fixed Vault config, data and log roots remain root-owned',
                 'Ensure the deployment-level Vault directories remain root-owned',
                 'Create isolated member config directories',
                 'Create isolated member Raft data directories',
                 'Create isolated member audit backing directories',
                 'Create private per-member PKI directories']
        tasks = [copy.deepcopy(next(task for task in source if task['name'] == name))
                 for name in names]
        with tempfile.TemporaryDirectory(prefix='vault-directory-test-') as directory:
            root = Path(directory)
            root.chmod(0o755)
            roots = {kind: root / kind for kind in ('config', 'data', 'log')}
            member = {kind + '_directory': str(path / 'qa' / 'vault-1')
                      for kind, path in roots.items()}
            config = Path(member['config_directory']) / 'vault.hcl'
            private_key = config.parent / 'pki' / 'private-key.pem'
            for path in (config, private_key):
                tasks.append({'ansible.builtin.copy': {
                    'content': 'synthetic QA marker\n', 'dest': str(path),
                    'owner': account.pw_name, 'group': group, 'mode': '0600'}})
            variables = {'platform_vault_user': account.pw_name, 'platform_vault_group': group,
                         'platform_vault_deployment_id': 'qa', '_platform_vault_local_instances': [member]}
            variables.update({'platform_vault_' + kind + '_root': str(path)
                              for kind, path in roots.items()})
            play = [{'hosts': 'localhost', 'connection': 'local', 'gather_facts': False,
                     'vars': variables, 'tasks': tasks}]
            path = root / 'probe.json'
            path.write_text(json.dumps(play), encoding='utf-8')
            for repeat in (False, True):
                result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(path)],
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90,
                                        env=dict(os.environ, ANSIBLE_NOCOLOR='1'))
                self.assertEqual(0, result.returncode, 'Local Vault directory proof failed')
                if repeat:
                    self.assertIn(b'changed=0', result.stdout)
            for base in roots.values():
                metadata = (base / 'qa').stat()
                self.assertEqual((0, account.pw_gid, 0o750),
                                 (metadata.st_uid, metadata.st_gid, metadata.st_mode & 0o777))
                result = subprocess.run(['runuser', '-u', account.pw_name, '--', 'test', '-x', str(base / 'qa')])
                self.assertEqual(0, result.returncode)
                result = subprocess.run(['runuser', '-u', account.pw_name, '--', 'test', '-w', str(base / 'qa')])
                self.assertNotEqual(0, result.returncode)
            for path in (config, private_key):
                self.assertEqual(0o600, path.stat().st_mode & 0o777)
                result = subprocess.run(['runuser', '-u', account.pw_name, '--', 'test', '-r', str(path)])
                self.assertEqual(0, result.returncode)
            for field in ('config_directory', 'data_directory'):
                self.assertEqual(0o700, Path(member[field]).stat().st_mode & 0o777)

import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROLE = Path(__file__).resolve().parents[2] / 'services/vault/ansible_collections/platform/vault/roles/vault_tls'
TASKS = yaml.safe_load((ROLE / 'tasks/unseal_member.yml').read_text())


@unittest.skipUnless(shutil.which('ansible-playbook'), 'Ansible runtime required')
class VaultUnsealIdentityTests(unittest.TestCase):
    def probe(self, slot=0, sealed=True, identity='synthetic-cluster', expected=0):
        for native in (False, True):
            tasks = copy.deepcopy(TASKS)
            before = {'initialized': True, 'sealed': sealed}
            if not sealed:
                before['cluster_id'] = 'synthetic-cluster'
            after = {'initialized': True, 'sealed': False}
            if identity is not None:
                after['cluster_id'] = identity
            # Substitute only the external API boundary. Execute actual
            # ordering, material guards, set_fact and cluster equality asserts.
            for task in tasks:
                if 'ansible.builtin.uri' not in task:
                    continue
                register = task.pop('register')
                task.pop('ansible.builtin.uri')
                task.pop('delegate_to')
                for key in ('retries', 'delay', 'until'):
                    task.pop(key, None)
                value = before if register.endswith('_before') else after
                task['ansible.builtin.set_fact'] = {register: {'json': value}}
            variables = {'vault_member': {'slot': slot}, 'platform_vault_unseal_threshold': 2,
                         '_platform_vault_effective_unseal_keys': ['synthetic-share-a', 'synthetic-share-b']}
            if slot != 0:
                variables['_platform_vault_seed_cluster_id'] = 'synthetic-cluster'
            tasks.append({'ansible.builtin.assert': {'that':
                "_platform_vault_seed_cluster_id == 'synthetic-cluster'"}, 'no_log': True})
            play = [{'hosts': 'localhost', 'connection': 'local', 'gather_facts': False,
                     'vars': variables, 'tasks': tasks}]
            with tempfile.TemporaryDirectory(prefix='vault-unseal-identity-') as root:
                path = Path(root) / 'probe.json'
                path.write_text(json.dumps(play))
                result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(path)],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=45,
                    env=dict(os.environ, ANSIBLE_NOCOLOR='1', ANSIBLE_JINJA2_NATIVE=str(native)))
            self.assertEqual(expected, result.returncode, 'Synthetic unseal identity proof failed; output withheld')
            for secret in variables['_platform_vault_effective_unseal_keys']:
                self.assertNotIn(secret.encode(), result.stdout)

    def test_sealed_seed_without_pre_unseal_cluster_id(self):
        self.probe()

    def test_already_unsealed_seed(self):
        self.probe(sealed=False)

    def test_follower_must_match_without_replacing_seed_identity(self):
        self.probe(slot=1)
        self.probe(slot=1, identity='different-cluster', expected=2)

    def test_missing_or_empty_post_unseal_identity_fails_closed(self):
        self.probe(identity=None, expected=2)
        self.probe(identity='', expected=2)


if __name__ == '__main__':
    unittest.main()

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
BOOTSTRAP = yaml.safe_load((ROLE / 'tasks/bootstrap.yml').read_text())
TOKEN = 'synthetic-test-token-not-real'
SHARES = ['synthetic-share-a', 'synthetic-share-b', 'synthetic-share-c']
MATERIAL = {'root_token': TOKEN, 'keys': SHARES}


@unittest.skipUnless(shutil.which('ansible-playbook'), 'Ansible runtime required')
class VaultBootstrapRecoveryTests(unittest.TestCase):
    def tasks(self):
        start = next(i for i, task in enumerate(BOOTSTRAP)
                     if task['name'] == 'Отклонение ответа на восстановление инициализации, если исходный узел все еще не инициализирован')
        end = next(i for i, task in enumerate(BOOTSTRAP)
                   if task['name'] == 'Разблокировка начального узла с настроенным порогом')
        tasks = copy.deepcopy(BOOTSTRAP[start:end])
        init = next(task for task in tasks if task['name'] == 'Инициализация нового начального узла ровно один раз')
        # Replace only remote API boundary with a fixed synthetic response. All
        # production custody/validation/durability tasks execute unchanged.
        init.pop('ansible.builtin.uri')
        init.pop('delegate_to')
        init.pop('register')
        init['ansible.builtin.set_fact'] = {'_platform_vault_init_response':
                                         "{{ {'json': qa_response, 'skipped': false} }}"}
        init['when'] = "not (_platform_vault_seed_init.json.initialized | bool)"
        return tasks

    def run_probe(self, directory, native=False, initialized=False, response=None,
                  fail_after=None, fail_task=None, expected=0, stale_recovery_observation=False):
        tasks = self.tasks()
        if fail_after:
            index = next(i for i, task in enumerate(tasks) if task['name'] == fail_after)
            tasks.insert(index + 1, {'ansible.builtin.fail': {'msg': 'QA_INJECTED_FAILURE'}, 'no_log': True})
        if fail_task:
            index = next(i for i, task in enumerate(tasks) if task['name'] == fail_task)
            tasks[index] = {'name': fail_task, 'ansible.builtin.fail': {'msg': 'QA_INJECTED_FAILURE'}, 'no_log': True}
        before = []
        for name in ('admin-token', 'unseal-shares', 'init-response.json'):
            path = directory / name
            before.append({'stat': {'exists': path.exists(), 'size': path.stat().st_size if path.exists() else 0}})
        if stale_recovery_observation:
            before[2]['stat']['exists'] = False
        variables = {'_platform_vault_bootstrap_output_dir': str(directory),
                     '_platform_vault_controller_uid': {'stdout': str(os.getuid())},
                     '_platform_vault_output_files': {'results': before},
                     '_platform_vault_seed_init': {'json': {'initialized': initialized}},
                     '_platform_vault_init_response': {'skipped': True},
                     'platform_vault_unseal_shares': 3, 'platform_vault_admin_token': '',
                     'platform_vault_unseal_keys': [],
                     'qa_response': dict(MATERIAL, keys_base64=['ignored'], non_custody_field='ignored') if response is None else response}
        if expected == 0:
            tasks.append({'ansible.builtin.assert': {'that': [
                '_platform_vault_admin_token == qa_expected_token',
                '_platform_vault_effective_unseal_keys == qa_expected_shares']}, 'no_log': True})
            variables.update(qa_expected_token=TOKEN, qa_expected_shares=SHARES)
            if initialized:
                tasks.append({'ansible.builtin.assert': {'that': '_platform_vault_init_response is skipped'}, 'no_log': True})
        play = [{'hosts': 'localhost', 'connection': 'local', 'gather_facts': False,
                 'vars': variables, 'tasks': tasks}]
        with tempfile.TemporaryDirectory(prefix='vault-recovery-play-') as workspace:
            path = Path(workspace) / 'probe.json'
            path.write_text(json.dumps(play))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(path)],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90,
                                    env=dict(os.environ, ANSIBLE_NOCOLOR='1', ANSIBLE_JINJA2_NATIVE=str(native)))
        self.assertEqual(expected, result.returncode, 'Synthetic bootstrap proof failed; output withheld')
        if expected == 0:
            self.assertEqual((directory / 'admin-token').read_bytes(), TOKEN.encode(),
                             'Producer must emit exact token bytes without a line terminator')
        for value in (TOKEN, *SHARES):
            self.assertNotIn(value.encode(), result.stdout, 'Synthetic secret leaked')
        return result.stdout

    def write_material(self, directory, name, value):
        path = directory / name
        path.write_text(value)
        path.chmod(0o600)

    def assert_pair(self, directory):
        self.assertEqual(TOKEN, (directory / 'admin-token').read_text().strip())
        self.assertEqual({'keys': SHARES}, json.loads((directory / 'unseal-shares').read_text()))

    def test_first_init_and_unchanged_repeat_in_both_native_modes(self):
        for native in (False, True):
            with self.subTest(native=native), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.run_probe(root, native=native)
                self.assert_pair(root)
                self.assertFalse((root / 'init-response.json').exists())
                before = {name: (root / name).read_bytes() for name in ('admin-token', 'unseal-shares')}
                output = self.run_probe(root, native=native, initialized=True)
                self.assertIn(b'changed=0', output)
                self.assertEqual(before, {name: (root / name).read_bytes() for name in before})

    def test_durable_recovery_and_partial_pair_reopen_in_both_native_modes(self):
        for native in (False, True):
            for point in ('Синхронизация данных восстановления и каталога результатов перед проверкой',
                          'Сохранение автономного исходного корневого токена без перезаписи существующего файла'):
                with self.subTest(native=native, point=point), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    self.run_probe(root, native=native, fail_after=point, expected=2)
                    self.assertEqual(MATERIAL, json.loads((root / 'init-response.json').read_text()))
                    self.assertFalse((root / 'unseal-shares').exists())
                    self.run_probe(root, native=native, initialized=True)
                    self.assert_pair(root)
                    self.assertFalse((root / 'init-response.json').exists())

    def test_invalid_material_is_retained_without_publication(self):
        for response in ({'root_token': TOKEN, 'keys': 'wrong'},
                         {'root_token': TOKEN, 'keys': SHARES[:2]},
                         {'root_token': TOKEN, 'keys': [1, 2, 3]},
                         {'root_token': TOKEN, 'keys': {'a': 1, 'b': 2, 'c': 3}},
                         {'root_token': '', 'keys': SHARES}):
            with self.subTest(shape=type(response['keys']).__name__), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.run_probe(root, response=response, expected=2)
                self.assertEqual(response, json.loads((root / 'init-response.json').read_text()))
                self.assertFalse((root / 'admin-token').exists())
                self.assertFalse((root / 'unseal-shares').exists())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.run_probe(root, response={'root_token': TOKEN}, expected=2)
            self.assertFalse((root / 'init-response.json').exists())

    def test_conflicting_recovery_or_pair_is_never_overwritten(self):
        for name, value in (('init-response.json', json.dumps({'root_token': 'conflict', 'keys': SHARES})),
                            ('admin-token', 'conflict\n'),
                            ('unseal-shares', json.dumps({'keys': ['conflict']}))):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.write_material(root, 'init-response.json', json.dumps(MATERIAL))
                self.write_material(root, name, value)
                before = (root / name).read_bytes()
                # Simulate a substituted stale observation for first-init
                # readback; copy force=false must not overwrite it.
                if name == 'init-response.json':
                    self.run_probe(root, expected=2, stale_recovery_observation=True)
                else:
                    self.run_probe(root, initialized=True, expected=2)
                self.assertEqual(before, (root / name).read_bytes())
                self.assertTrue((root / 'init-response.json').exists())
                if name == 'admin-token':
                    self.assertFalse((root / 'unseal-shares').exists())
                if name == 'unseal-shares':
                    self.assertFalse((root / 'admin-token').exists())

    def test_readback_sync_and_cleanup_failure_preserve_recoverability(self):
        for point in ('Чтение минимальной записи восстановления, не раскрывая ее',
                      'Синхронизация данных восстановления и каталога результатов перед проверкой',
                      'Синхронизация обоих проверенных файлов перед удалением записи восстановления',
                      'Удаление защищённой записи восстановления только после сохранения обоих файлов',
                      'Синхронизация каталога хранения после удаления записи восстановления'):
            with self.subTest(point=point), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.run_probe(root, fail_task=point, expected=2)
                if point.startswith('Синхронизация обоих проверенных файлов перед удалением записи восстановления') or point.startswith('Удал') or point.startswith('Синхронизация каталога хранения после удаления записи восстановления'):
                    self.assert_pair(root)
                if not point.startswith('Синхронизация каталога хранения после удаления записи восстановления'):
                    self.assertTrue((root / 'init-response.json').exists())
                else:
                    self.assertFalse((root / 'init-response.json').exists())
                self.run_probe(root, initialized=True)
                self.assert_pair(root)

    def test_pre_init_sync_failure_produces_no_material(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.run_probe(root, fail_task='Синхронизация файловой системы каталога результатов перед инициализацией Vault', expected=2)
            self.assertEqual([], list(root.iterdir()))

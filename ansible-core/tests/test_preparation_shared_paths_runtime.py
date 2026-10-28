import copy
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]
TASKS = ROOT / 'ansible-core/collections/ansible_collections/platform/core/roles/application_runtime/tasks/preflight.yml'


@unittest.skipUnless(shutil.which('ansible-playbook'), 'Ansible required')
class SharedPathRuntimeTests(unittest.TestCase):
    def test_readonly_scope_reuses_parent_but_manual_call_is_fresh(self):
        source = yaml.safe_load(TASKS.read_text())
        names = ['Проверка всех родительских каталогов без перехода по символическим ссылкам',
                 'Привязка наблюдений родительских путей в текущей read-only подготовке',
                 'Отклонение небезопасных путей и неуправляемых каталогов приложений']
        tasks = [next(t for t in source if t.get('name') == name) for name in names]
        with tempfile.TemporaryDirectory(prefix='preflight-paths-') as folder:
            root = Path(folder)
            for name in ['common', 'one', 'two']:
                (root / name).mkdir()
            def paths(*names):
                return {'ansible.builtin.set_fact': {'application_preflight_parent_paths': [str(root / n) for n in names]}}
            checks = [paths('common', 'one')] + copy.deepcopy(tasks) + [
                {'ansible.builtin.assert': {'that': ['_application_new_ancestors.results | length == 2']}},
                paths('common', 'two')] + copy.deepcopy(tasks) + [
                {'ansible.builtin.assert': {'that': ['_application_new_ancestors.results | length == 1', 'application_ancestors.results | length == 2']}},
                {'ansible.builtin.set_fact': {'application_runtime_reuse_preflight_paths': False}},
                paths('common', 'two')] + copy.deepcopy(tasks) + [
                {'ansible.builtin.assert': {'that': ['_application_new_ancestors.results | length == 2', 'application_preflight_path_observations | length == 0']}}]
            play = root / 'play.yml'
            play.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False,
                vars=dict(application_preflight_path_observations={}, application_runtime_reuse_preflight_paths=True,
                          application_root=str(root), application_uid=str(os.getuid())), tasks=checks)]))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(play)], capture_output=True,
                                    text=True, timeout=90)
            self.assertEqual(0, result.returncode, result.stdout[-3000:] + result.stderr[-1000:])
            self.assertIn('changed=0', result.stdout)

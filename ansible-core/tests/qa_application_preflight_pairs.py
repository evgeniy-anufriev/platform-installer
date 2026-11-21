"""Exercise production preflight pair construction through native Ansible."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


class PreflightPairsTests(unittest.TestCase):
    def test_pairs_and_digest_preserve_order_and_archive_content(self):
        source = ROOT / 'ansible-core/collections/ansible_collections/platform/core/roles/application_runtime/tasks/preflight.yml'
        tasks = yaml.safe_load(source.read_text())
        tasks = next(task['block'] for task in tasks if task.get('name') == 'Расчёт и проверка конфигурации размещения')
        task = next(t for t in tasks
                    if t['name'] == 'Сбор упорядоченных пар путей назначения и контрольных сумм содержимого')
        bind = next(t for t in tasks if 'platform.core.bind_application_preflight_context' in t)
        cases = [([], [], []),
                 ([dict(destination='z', sha256='z1'), dict(destination='a', sha256='a1')],
                  [['m', 'archive']], [['a', 'a1'], ['m', 'archive'], ['z', 'z1']]),
                 ([dict(destination='Я', sha256='u'), dict(destination='A', sha256='a')],
                  [], [['A', 'a'], ['Я', 'u']])]
        with tempfile.TemporaryDirectory(prefix='qa-preflight-pairs-') as directory:
            steps = [{'ansible.builtin.set_fact': dict(
                application_preflight_index=0, application_library_path='/qa/library',
                application_instance_path='/qa/library/app',
                _application_preflight_job=dict(
                    settings=dict(image='qa-image', command=['start'], environment={'NAME': 'original'}),
                    placement={'containerName': 'qa-app'}, baseFilename='base.yml', baseService='base',
                    libraryId='qa-library'),
                _application_preflight_template_context=dict(
                    identity_environment={'NAME': 'resolved'}, connections={'database': 'db'},
                    topics={}, library_connections={'cache': 'redis'}))}]
            for configs, archives, expected in cases:
                digest = hashlib.sha256(json.dumps(expected, ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()
                steps.extend([
                    {'ansible.builtin.set_fact': dict(application_config_contents=configs,
                                                     application_archive_pairs=archives,
                                                     application_config_pairs=[['stale', 'discard']])},
                    task,
                    bind,
                    {'ansible.builtin.assert': {'that': [
                        'application_config_pairs == ' + repr(expected),
                        "application_config_digest == '" + digest + "'",
                        "application_environment == {'NAME': 'resolved'}",
                        "application_runtime.base_compose_path == '/qa/library/base.yml'",
                        "application_runtime.connections == {'database': 'db'}",
                        "library_runtime.connections == {'cache': 'redis'}",
                        "(application_config_pairs | to_json(separators=[',', ':']) | hash('sha256')) == '" + digest + "'"]}}])
            path = Path(directory) / 'probe.yml'
            path.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False, tasks=steps)], sort_keys=False))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(path)],
                                    env=dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg')),
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(0, result.returncode, (result.stdout + result.stderr)[-2500:])

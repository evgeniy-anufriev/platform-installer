"""Standalone application entrypoints resolve without Installer or path overrides."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
PLAYBOOKS = ROOT / 'ansible-core/playbooks/applications'


@unittest.skipUnless(shutil.which('ansible-playbook'), 'Execution Node Ansible required')
class ApplicationPlaybookEntrypointTests(unittest.TestCase):
    def resolve(self, imported):
        with tempfile.TemporaryDirectory(prefix='application-entrypoint-') as temporary:
            directory = Path(temporary)
            project = directory / 'project'
            shutil.copytree(ROOT / 'examples/valid/application-runtime', project)
            variables = directory / 'vars.json'
            variables.write_text(json.dumps({
                'platform_project_root': str(project),
                'platform_service_catalog_path': str(ROOT / 'examples/catalog/service-catalog.yml'),
            }), encoding='utf-8')
            # Deliberately omit platform_contracts_root. Both a direct CLI and
            # an external importing playbook must retain the native default.
            playbook = PLAYBOOKS / 'stages/resolve-runtime.yml'
            if imported:
                wrapper = directory / 'standalone.yml'
                wrapper.write_text(yaml.safe_dump([
                    {'import_playbook': str(playbook)},
                    {'hosts': 'localhost', 'gather_facts': False, 'tasks': [
                        {'ansible.builtin.assert': {'that': [
                            "application_runtime_inputs.status == 'PASS'",
                            'application_runtime_inputs.jobs | length > 0',
                        ]}},
                    ]},
                ]), encoding='utf-8')
                playbook = wrapper
            environment = dict(os.environ,
                ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
                ANSIBLE_COLLECTIONS_PATH=os.pathsep.join(
                    [str(ROOT / 'ansible-core/collections')] +
                    [str(path) for path in sorted((ROOT / 'services').glob('*/ansible_collections'))]))
            result = subprocess.run([
                'ansible-playbook', '-i', str(project / 'inventory/hosts.yml'),
                str(playbook), '-e', '@' + str(variables),
            ], cwd=directory, env=environment, capture_output=True, text=True, timeout=120)
            self.assertEqual(0, result.returncode, result.stdout[-5000:] + result.stderr[-2000:])
            self.assertNotIn('UNREACHABLE', result.stdout)

    def test_direct_standalone_resolution_uses_native_contracts_default(self):
        self.resolve(imported=False)

    def test_external_import_uses_native_contracts_default(self):
        self.resolve(imported=True)


if __name__ == '__main__':
    unittest.main()

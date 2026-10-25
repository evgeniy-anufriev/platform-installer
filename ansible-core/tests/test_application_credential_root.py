"""Real Ansible compatibility boundary; no targets or credential values."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which('ansible-playbook'), 'Execution Node Ansible required')
class ApplicationCredentialRootTests(unittest.TestCase):
    def boundary(self, variables, expected_root=None, expected_files=None):
        with tempfile.TemporaryDirectory(prefix='application-input-') as temporary:
            directory = Path(temporary)
            extra = directory / 'vars.yml'
            extra.write_text(yaml.safe_dump(variables))
            play = [{'import_playbook': str(ROOT / 'ansible-core/playbooks/applications/stages/credential-root.yml')}]
            if expected_root is not None:
                play.append({'hosts': 'localhost', 'gather_facts': False, 'tasks': [
                    {'ansible.builtin.assert': {'that': [
                        'platform_application_secret_root == expected_root',
                        'platform_application_secret_files == expected_files']},
                     'vars': {'expected_root': expected_root, 'expected_files': expected_files or {}}}]})
            path = directory / 'play.yml'
            path.write_text(yaml.safe_dump(play))
            return subprocess.run(['ansible-playbook', '-i', 'localhost,', str(path), '-e', '@' + str(extra)],
                                  capture_output=True, timeout=30).returncode

    def test_legacy_input_normalizes_to_shared_custody(self):
        self.assertEqual(0, self.boundary({'platform_postgresql_application_secret_root': '/runtime/private',
                                           'platform_postgresql_secret_files': {'password': '/runtime/private/password'}},
                                          '/runtime/private', {'password': '/runtime/private/password'}))

    def test_generic_input_and_explicit_file_override(self):
        self.assertEqual(0, self.boundary({'platform_application_secret_root': '/runtime/shared',
                                           'platform_postgresql_secret_files': {'password': '/runtime/shared/old'},
                                           'platform_application_secret_files': {'password': '/runtime/shared/new'}},
                                          '/runtime/shared', {'password': '/runtime/shared/new'}))

    def test_conflicting_roots_are_blocked_before_any_target(self):
        self.assertEqual(2, self.boundary({'platform_application_secret_root': '/runtime/shared',
                                           'platform_postgresql_application_secret_root': '/runtime/other'}))

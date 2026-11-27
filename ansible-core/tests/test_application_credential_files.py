"""Controller-local credential files remain private through batched Apply."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which('ansible-playbook'), 'native Ansible required')
class ApplicationCredentialFilesTests(unittest.TestCase):
    def test_private_bytes_check_mode_and_scoped_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            journal = root / 'journal'
            journal.mkdir(mode=0o700)
            outside = root / 'outside'
            outside.write_text('untouched', encoding='utf-8')
            (journal / 'other').write_text('untouched', encoding='utf-8')
            value = '  literal-Ж-123\nlast line\n'

            def apply(operation, check=False, **args):
                play = root / 'play.json'
                play.write_text(json.dumps([dict(hosts='localhost', connection='local', gather_facts=False,
                    vars=dict(platform_application_generated_values={'generated-1': value}),
                    tasks=[{'platform.core.application_credential_files': dict(operation=operation,
                            root=str(journal), **args), 'no_log': True}])]), encoding='utf-8')
                command = ['ansible-playbook', '-i', 'localhost,', str(play)]
                if check:
                    command.append('--check')
                result = subprocess.run(command, env=dict(os.environ,
                    ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
                    ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections')),
                    capture_output=True, text=True, timeout=30)
                self.assertNotIn('literal-Ж-123', result.stdout + result.stderr)
                return result.returncode

            secret = journal / 'generated-1'
            self.assertEqual(0, apply('write', check=True))
            self.assertFalse(secret.exists())
            secret.write_text('replace', encoding='utf-8')
            self.assertEqual(0, apply('write'))
            self.assertEqual(value.encode('utf-8'), secret.read_bytes())
            self.assertEqual(0o600, secret.stat().st_mode & 0o777)
            self.assertEqual(0, apply('remove', check=True, names=[secret.name]))
            self.assertTrue(secret.exists())
            (journal / 'link').symlink_to(outside)
            self.assertEqual(2, apply('remove', names=['../outside']))
            self.assertEqual(2, apply('remove', names=['link', secret.name, secret.name]))
            self.assertFalse(secret.exists())
            self.assertTrue((journal / 'link').is_symlink())
            self.assertEqual('untouched', outside.read_text(encoding='utf-8'))
            self.assertEqual('untouched', (journal / 'other').read_text(encoding='utf-8'))
            self.assertEqual(0, apply('remove', names=[secret.name]))
            secret.symlink_to(outside)
            self.assertEqual(2, apply('write'))
            self.assertEqual('untouched', outside.read_text(encoding='utf-8'))

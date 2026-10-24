"""Availability-only script input checks, as requested by the owner."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils'))
from application_credentials import protected_secret_files
from ansible.errors import AnsibleFilterError


class ScriptInputAvailabilityTests(unittest.TestCase):
    def test_large_public_mode_file_and_link_are_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input'
            path.write_bytes(b'x' * 1048577)
            path.chmod(0o644)
            link = Path(directory) / 'link'
            link.symlink_to(path)
            self.assertTrue(protected_secret_files({'value': str(link)}, ['value']))
            self.assertTrue(protected_secret_files(
                {'value': str(link)}, ['value'], '/unused-legacy-root', 1))

    def test_missing_empty_and_directory_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            empty = root / 'empty'
            empty.touch()
            for path in (root / 'missing', empty, root):
                with self.subTest(path=path.name), self.assertRaises(AnsibleFilterError):
                    protected_secret_files({'value': str(path)}, ['value'])

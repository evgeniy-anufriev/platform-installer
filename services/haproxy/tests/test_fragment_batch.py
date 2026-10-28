import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('fragment_batch', ROOT / 'ansible_collections/platform/haproxy/plugins/modules/fragment_batch.py')
batch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(batch)


@unittest.skipUnless(os.name == 'posix' and os.geteuid() == 0, 'root-owned isolated Linux fixtures')
class FragmentBatchTests(unittest.TestCase):
    def test_batch_inspect_write_repeat_and_mode(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            files = [{'name': '10-public.cfg', 'content': 'frontend public\n'}] + [
                {'name': f'30-backend-test-{n}.cfg',
                 'content': f'# platform-installer-managed-backend/v1 30-backend-test-{n}.cfg\nbackend test{n}\n'}
                for n in range(20)]
            Path(directory, 'unrelated.cfg').write_text('keep')
            self.assertFalse(batch.reconcile(directory, files)['matches'])
            self.assertEqual(1, len(list(Path(directory).iterdir())))
            self.assertEqual(21, len(batch.reconcile(directory, files, True)['changedFiles']))
            self.assertFalse(batch.reconcile(directory, files, True)['changed'])
            Path(directory, '10-public.cfg').chmod(0o600)
            self.assertTrue(batch.reconcile(directory, files, True)['changed'])
            self.assertEqual(0o640, Path(directory, '10-public.cfg').stat().st_mode & 0o777)
            self.assertEqual('keep', Path(directory, 'unrelated.cfg').read_text())

    def test_invalid_batch_never_partially_writes(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            good = {'name': '10-public.cfg', 'content': 'frontend public\n'}
            for bad in [{'name': '../outside', 'content': 'no'}, good,
                        {'name': 'other.cfg', 'content': 'no'},
                        {'name': '30-backend-bad.cfg', 'content': 'wrong owner'},
                        {'name': '30-backend-big.cfg', 'content': 'x' * (batch.MAX_FILE + 1)}]:
                with self.subTest(name=bad['name']), self.assertRaises(batch.ArchiveError):
                    batch.reconcile(directory, [good, bad], True)
                self.assertEqual([], list(Path(directory).iterdir()))

    def test_symlink_directory_hardlink_and_fifo_fail_closed(self):
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            root = Path(directory)
            target = root / '10-public.cfg'
            outside = root / 'outside'
            outside.write_text('untouched')
            files = [{'name': target.name, 'content': 'replacement'}]
            for kind in ['link', 'dir', 'hardlink', 'fifo']:
                if kind == 'link': target.symlink_to(outside)
                elif kind == 'dir': target.mkdir()
                elif kind == 'hardlink': os.link(outside, target)
                else: os.mkfifo(target)
                with self.subTest(kind=kind), self.assertRaises((batch.ArchiveError, OSError)):
                    batch.reconcile(directory, files, True)
                if kind == 'dir': target.rmdir()
                else: target.unlink()
                self.assertEqual('untouched', outside.read_text())

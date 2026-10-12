import importlib.util
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
COLLECTION = ROOT / 'services/vault/ansible_collections/platform/vault'
SPEC = importlib.util.spec_from_file_location('vault_clear', COLLECTION / 'plugins/modules/clear_member.py')
CLEAR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLEAR)


class VaultClearContractTests(unittest.TestCase):
    def test_entry_is_explicit_locked_and_does_not_call_core_or_read_secrets(self):
        entry = yaml.safe_load((COLLECTION / 'roles/vault_tls/tasks/clear_entry.yml').read_text())
        block = next(task for task in entry if 'block' in task)
        self.assertIn('always', block)
        text = str(entry)
        self.assertIn('acquire_lock.yml', text)
        self.assertIn('release_lock.yml', text)
        self.assertIn('platform_vault_confirm_destructive_reset', text)
        tasks = yaml.safe_load((COLLECTION / 'roles/vault_tls/tasks/clear.yml').read_text())
        self.assertTrue(tasks[0]['platform.vault.clear_member']['inspect_only'])
        self.assertIn('ansible.builtin.systemd', tasks[1])
        self.assertIn('platform.vault.clear_member', tasks[2])
        self.assertFalse(any('ansible.builtin.file' in task for task in tasks))
        main = (COLLECTION / 'roles/vault_tls/tasks/main.yml').read_text()
        self.assertNotIn('clear.yml', main)
        play = yaml.safe_load((ROOT / 'services/vault/playbooks/clear.yml').read_text())[0]
        self.assertTrue(play['any_errors_fatal'])
        self.assertEqual('linear', play['strategy'])
        self.assertNotIn('import_playbook', play)

    def test_bad_identity_and_confirmation_fail_before_any_filesystem_access(self):
        for member in ('../vault', '1bad', 'a' * 129, '', 'vault/other'):
            with self.subTest(member=member), self.assertRaisesRegex(CLEAR.ClearFailure, 'IDENTITY_INVALID'):
                CLEAR.clear_member('qa', member, '/var/lib/qa', 'qa')
        with self.assertRaisesRegex(CLEAR.ClearFailure, 'CONFIRMATION_REQUIRED'):
            CLEAR.clear_member('qa', 'vault-1', '/var/lib/qa', '')

    def test_ansible_invalid_request_fails_safely_without_raw_payload(self):
        if not shutil.which('ansible-playbook'):
            self.skipTest('Ansible required')
        with tempfile.TemporaryDirectory(prefix='vault-clear-admission-') as directory:
            play = Path(directory) / 'probe.json'
            play.write_text(json.dumps([{'hosts': 'localhost', 'connection': 'local',
                'gather_facts': False, 'tasks': [{'platform.vault.clear_member': {
                    'deployment_id': 'qa', 'member_id': 'vault-1',
                    'data_directory': '/var/lib/qa', 'confirmation': ''}}]}]))
            env = dict(os.environ, ANSIBLE_NOCOLOR='1',
                       ANSIBLE_COLLECTIONS_PATHS=str(ROOT / 'services/vault'))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(play)],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    env=env, timeout=60)
            self.assertNotEqual(0, result.returncode)
            self.assertIn(b'VAULT_CLEAR_CONFIRMATION_REQUIRED', result.stdout)
            self.assertNotIn(b'Traceback', result.stdout)

    def test_real_clear_entry_requires_ack_before_lock_or_stop(self):
        if not shutil.which('ansible-playbook'):
            self.skipTest('Ansible required')
        with tempfile.TemporaryDirectory(prefix='vault-clear-entry-') as directory:
            play = Path(directory) / 'probe.json'
            play.write_text(json.dumps([{'hosts': 'localhost', 'connection': 'local',
                'gather_facts': False, 'vars': {'platform_vault_instances': [
                    {'id': 'vault-1', 'host': 'localhost', 'address': '192.0.2.1', 'roles': ['vault']}]},
                'tasks': [{'ansible.builtin.include_role': {
                    'name': 'platform.vault.vault_tls', 'tasks_from': 'clear_entry'}}]}]))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(play)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60,
                env=dict(os.environ, ANSIBLE_NOCOLOR='1',
                         ANSIBLE_COLLECTIONS_PATHS=str(ROOT / 'services/vault')))
            self.assertNotEqual(0, result.returncode)
            self.assertIn(b'VAULT_CLEAR_CONFIRMATION_REQUIRED', result.stdout)
            self.assertNotIn(b'Acquire the existing Vault deployment lock', result.stdout)
            self.assertNotIn(b'Stop and disable', result.stdout)



@unittest.skipUnless(hasattr(os, 'geteuid') and os.geteuid() == 0,
                     'Root Linux synthetic filesystem proof required')
class VaultClearSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='vault-clear-test-', dir='/run')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.account = pwd.getpwnam('nobody')
        self.deployment, self.member = 'qa', 'vault-1'
        self.unit = 'vault@qa-1'
        self.data_root = self.root / 'data'
        self.config_root = self.root / 'config'
        self.units = self.root / 'units'
        self.data = self.data_root / 'qa/vault-1'
        self.configs = self.config_root / 'vault/qa/vault-1'
        self.config = self.configs / 'vault.hcl'
        for path in (self.data, self.configs, self.units):
            path.mkdir(parents=True)
        for path in (self.data, self.configs):
            path.chmod(0o700)
            os.chown(path, self.account.pw_uid, self.account.pw_gid)
        self.marker = self.data / '.vault-member.json'
        self.marker.write_text(json.dumps({'apiVersion': 'platform.installer/vault-member-marker/v1alpha1',
            'deploymentId': 'qa', 'memberId': 'vault-1', 'instanceName': self.unit}))
        self.config.write_text('storage "raft" {\n  path = "' + str(self.data) +
                               '"\n  node_id = "' + self.unit + '"\n}\n')
        for path in (self.marker, self.config):
            path.chmod(0o600)
            os.chown(path, self.account.pw_uid, self.account.pw_gid)
        self.unit_file = self.units / (self.unit + '.service')
        self.unit_file.write_text('# vault-managed: qa/vault-1\nUser=vault\n' +
                                 'ExecStart=/usr/bin/vault server -config=' + str(self.config) + '\n')
        self.payload = self.data / 'raft'
        self.payload.mkdir()
        (self.payload / 'raft.db').write_bytes(b'SYNTHETIC_PRIVATE_DATA')
        self.properties = {'ActiveState': 'inactive', 'MainPID': '0', 'User': 'vault',
            'FragmentPath': str(self.unit_file),
            'ExecStart': '{ path=/usr/bin/vault ; argv[]=/usr/bin/vault server -config=' + str(self.config) + ' ; }'}
        # Fixed production roots are replaced only inside this in-process test.
        for name, value in [('CONFIG_ROOT', str(self.config_root)),
                            ('UNIT_ROOT', str(self.units))]:
            mock = patch.object(CLEAR, name, value)
            mock.start()
            self.addCleanup(mock.stop)
        for target, value in [('pwd.getpwnam', self.account), ('unit_properties', self.properties),
                              ('require_no_process', None), ('private_mount_namespace', None)]:
            # module is deliberately imported without registering a global package.
            owner, attribute = (CLEAR.pwd, 'getpwnam') if target == 'pwd.getpwnam' else (CLEAR, target)
            mock = patch.object(owner, attribute, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)

    def clear(self, inspect_only=False):
        return CLEAR.clear_member('qa', 'vault-1', str(self.data), 'qa', inspect_only)

    def test_clear_repeat_preserves_root_marker_config_audit_and_siblings(self):
        other = self.data_root / 'other'
        other.mkdir()
        (other / 'data').write_text('foreign')
        audit = self.root / 'audit.log'
        audit.write_text('audit')
        retained = {path: path.read_bytes() for path in (self.marker, self.config, self.unit_file, audit, other / 'data')}
        original = self.data.stat().st_ino
        self.assertTrue(self.clear(inspect_only=True))
        self.assertTrue(self.payload.exists())
        self.assertTrue(self.clear())
        self.assertFalse(self.clear())
        self.assertEqual(original, self.data.stat().st_ino)
        for path, data in retained.items():
            self.assertEqual(data, path.read_bytes())

    def test_marker_unit_config_and_owner_mismatches_reject_without_deletion(self):
        for path in (self.marker, self.config, self.unit_file):
            original = path.read_bytes()
            path.write_text('{}')
            with self.assertRaises(CLEAR.ClearFailure):
                self.clear()
            self.assertTrue(self.payload.exists())
            path.write_bytes(original)
        self.data.chmod(0o755)
        with self.assertRaisesRegex(CLEAR.ClearFailure, 'PATH_UNSAFE'):
            self.clear()
        self.data.chmod(0o700)
        os.chown(self.marker, 0, 0)
        with self.assertRaisesRegex(CLEAR.ClearFailure, 'FILE_UNSAFE'):
            self.clear()

    def test_symlinked_ancestry_and_marker_reject_without_deletion(self):
        for path in (self.data_root / 'qa', self.marker):
            saved = path.with_name(path.name + '-saved')
            path.rename(saved)
            path.symlink_to(saved)
            with self.assertRaises((CLEAR.ClearFailure, OSError)):
                self.clear()
            path.unlink()
            saved.rename(path)
            self.assertTrue(self.payload.exists())

    def test_nested_symlink_never_deletes_external_target(self):
        foreign = self.root / 'foreign'
        foreign.mkdir()
        (foreign / 'data').write_text('foreign')
        (self.payload / 'link').symlink_to(foreign)
        (self.data / 'link').symlink_to(foreign)
        self.assertTrue(self.clear())
        self.assertEqual('foreign', (foreign / 'data').read_text())

    def test_replacement_between_inspection_and_clear_is_revalidated(self):
        self.clear(inspect_only=True)
        saved = self.data.with_name('saved')
        self.data.rename(saved)
        self.data.mkdir(mode=0o700)
        (self.data / 'foreign').write_text('foreign')
        with self.assertRaisesRegex(CLEAR.ClearFailure, 'PATH_UNSAFE'):
            self.clear()
        self.assertTrue((saved / 'raft/raft.db').exists())
        self.assertTrue((self.data / 'foreign').exists())

    def test_replacement_during_clear_never_deletes_foreign_root(self):
        original = CLEAR.same_source
        count = 0
        def replace(fd, path):
            nonlocal count
            count += 1
            if count == 2:
                self.data.rename(self.data.with_name('saved'))
                self.data.mkdir(mode=0o700)
                (self.data / 'foreign').write_text('foreign')
            original(fd, path)
        with patch.object(CLEAR, 'same_source', side_effect=replace):
            with self.assertRaisesRegex(CLEAR.ClearFailure, 'SOURCE_CHANGED'):
                self.clear()
        self.assertTrue((self.data / 'foreign').exists())

    def test_stopped_state_process_guard_and_partial_failure(self):
        self.properties['ActiveState'] = 'active'
        with self.assertRaisesRegex(CLEAR.ClearFailure, 'MEMBER_RUNNING'):
            self.clear()
        self.properties['ActiveState'] = 'inactive'
        with patch.object(CLEAR, 'require_no_process', side_effect=CLEAR.ClearFailure('VAULT_CLEAR_MEMBER_RUNNING')):
            with self.assertRaises(CLEAR.ClearFailure):
                self.clear()
        (self.data / 'a-file').write_text('synthetic')
        original = CLEAR.remove_raft_child
        def fail_on_directory(parent, name, mount, depth=0):
            if name == 'raft':
                raise OSError('synthetic failure')
            return original(parent, name, mount, depth)
        with patch.object(CLEAR, 'remove_raft_child', side_effect=fail_on_directory):
            with self.assertRaises(OSError):
                self.clear()
        self.assertFalse((self.data / 'a-file').exists())
        self.assertTrue(self.marker.exists())
        self.assertTrue(self.config.exists())
        self.assertTrue(self.payload.exists())

    def test_mount_isolation_and_safe_delete_unavailability_fail_closed(self):
        with patch.object(CLEAR, 'private_mount_namespace', side_effect=CLEAR.ClearFailure('VAULT_CLEAR_MOUNT_ISOLATION_UNAVAILABLE')):
            with self.assertRaises(CLEAR.ClearFailure):
                self.clear()
        with patch.object(CLEAR.os, 'supports_dir_fd', set()):
            with self.assertRaisesRegex(CLEAR.ClearFailure, 'SAFE_DELETE_UNAVAILABLE'):
                self.clear()
        self.assertTrue(self.payload.exists())

    def test_loaded_unit_mismatch_is_rejected_before_any_clear(self):
        for key, value in [('FragmentPath', '/foreign/unit'), ('User', 'root'),
                           ('ExecStart', 'argv[]=/usr/bin/vault server -config=/foreign ;')]:
            original = self.properties[key]
            self.properties[key] = value
            with self.assertRaisesRegex(CLEAR.ClearFailure, 'UNIT_INVALID'):
                self.clear(inspect_only=True)
            self.assertTrue(self.payload.exists())
            self.properties[key] = original

    def test_file_size_type_and_private_mode_limits(self):
        original = self.marker.read_bytes()
        self.marker.write_bytes(b'x' * 4097)
        with self.assertRaisesRegex(CLEAR.ClearFailure, 'FILE_UNSAFE'):
            self.clear()
        self.marker.write_bytes(original)
        self.marker.chmod(0o644)
        with self.assertRaisesRegex(CLEAR.ClearFailure, 'FILE_UNSAFE'):
            self.clear()
        self.marker.chmod(0o600)
        self.marker.unlink()
        os.mkfifo(self.marker, 0o600)
        os.chown(self.marker, self.account.pw_uid, self.account.pw_gid)
        with self.assertRaisesRegex(CLEAR.ClearFailure, 'FILE_UNSAFE'):
            self.clear()
        self.assertTrue(self.payload.exists())

    def test_real_nested_bind_mount_refuses_clear_and_preserves_contents(self):
        # Everything, including temporary mounts, is confined to a disposable
        # subprocess namespace. Production Vault paths/units are never contacted.
        code = r'''
import importlib.util, json, os, pathlib, pwd, subprocess, sys, unittest.mock as mock
spec = importlib.util.spec_from_file_location('clear_probe', sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.private_mount_namespace()
data = pathlib.Path(sys.argv[2]); foreign = pathlib.Path(sys.argv[3])
properties = json.loads(sys.argv[4])
m.DATA_ROOT = str(data.parent.parent)
m.CONFIG_ROOT = sys.argv[5]
m.UNIT_ROOT = str(pathlib.Path(properties['FragmentPath']).parent)
account = pwd.getpwnam('nobody')
for index, kind in enumerate(('bind', 'tmpfs')):
    target = data/'raft'/('nested-' + kind)
    target.mkdir(parents=True)
    command = ['mount', '--bind', str(foreign), str(target)] if kind == 'bind' else ['mount', '-t', 'tmpfs', 'tmpfs', str(target)]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (target/'mounted-data').write_text('mounted')
    with mock.patch.object(m.pwd, 'getpwnam', return_value=account), mock.patch.object(m, 'unit_properties', return_value=properties):
        try:
            m.clear_member('qa', 'vault-1', str(data), 'qa')
        except m.ClearFailure as error:
            assert str(error) == 'VAULT_CLEAR_MOUNT_IN_USE'
        else:
            raise AssertionError('mounted tree was admitted')
    assert (target/'mounted-data').read_text() == 'mounted'
    subprocess.run(['umount', str(target)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
assert (foreign/'data').read_text() == 'foreign'
'''
        foreign = self.root / 'mount-source'
        foreign.mkdir()
        (foreign / 'data').write_text('foreign')
        result = subprocess.run(['python3', '-c', code, str(SPEC.origin), str(self.data), str(foreign),
                                 json.dumps(self.properties), str(self.config_root)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        self.assertEqual(0, result.returncode, 'Linux nested/bind mount safety proof failed')
        self.assertTrue(self.payload.exists())
        self.assertEqual('foreign', (foreign / 'data').read_text())

    def test_real_config_process_scanner_ignores_caller_selected_argv_zero(self):
        # Use the real scanner, not the guard mock used by unrelated filesystem tests.
        scanner = type(self).scanner
        for argv_zero in ('vault', 'renamed-process'):
            for arguments in (['-config=' + str(self.config)], ['-config', str(self.config)]):
                with self.subTest(argv_zero=argv_zero, arguments=arguments):
                    process = subprocess.Popen([argv_zero, '-c',
                        'import sys,time; print("ready",flush=True); time.sleep(30)', *arguments],
                        executable='/usr/bin/python3', stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                    try:
                        self.assertEqual(b'ready\n', process.stdout.readline())
                        with open('/proc/' + str(process.pid) + '/cmdline', 'rb') as stream:
                            self.assertEqual(argv_zero.encode(), stream.read(65536).split(b'\0')[0])
                        with self.assertRaisesRegex(CLEAR.ClearFailure, 'MEMBER_RUNNING'):
                            scanner(str(self.config))
                    finally:
                        process.terminate()
                        process.wait(timeout=10)
                        process.stdout.close()
        process = subprocess.Popen(['renamed-process', '-c',
            'import sys,time; print("ready",flush=True); time.sleep(30)', '-config=/unrelated/config'],
            executable='/usr/bin/python3', stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            self.assertEqual(b'ready\n', process.stdout.readline())
            scanner(str(self.config))
        finally:
            process.terminate()
            process.wait(timeout=10)
            process.stdout.close()

    def test_mount_move_after_admission_blocks_fd_descent(self):
        code = r'''
import importlib.util, json, pathlib, pwd, subprocess, sys, threading, unittest.mock as mock
spec = importlib.util.spec_from_file_location('clear_probe', sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m.private_mount_namespace()
data = pathlib.Path(sys.argv[2]); root = data.parent.parent.parent
properties = json.loads(sys.argv[3]); account = pwd.getpwnam('nobody')
m.DATA_ROOT = str(data.parent.parent); m.CONFIG_ROOT = sys.argv[4]
m.UNIT_ROOT = str(pathlib.Path(properties['FragmentPath']).parent)
for kind in ('bind', 'tmpfs'):
    outside = root/('outside-' + kind); outside.mkdir()
    mountpoint = outside/'nested'; mountpoint.mkdir()
    source = root/('source-' + kind); source.mkdir()
    (source/'sentinel').write_text('foreign')
    command = ['mount','--bind',str(source),str(mountpoint)] if kind == 'bind' else ['mount','-t','tmpfs','tmpfs',str(mountpoint)]
    subprocess.run(command,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    (mountpoint/'sentinel').write_text('foreign')
    destination = data/'raft'
    original = data/('saved-' + kind)
    admitted = threading.Event(); moved = threading.Event()
    def move():
        assert admitted.wait(10)
        destination.rename(original)
        outside.rename(destination)
        moved.set()
    worker = threading.Thread(target=move); worker.start()
    admission = m.reject_submounts
    def pause(path):
        admission(path)
        admitted.set()
        assert moved.wait(10)
    with mock.patch.object(m.pwd,'getpwnam',return_value=account), mock.patch.object(m,'unit_properties',return_value=properties), mock.patch.object(m,'reject_submounts',side_effect=pause):
        try:
            m.clear_member('qa','vault-1',str(data),'qa')
        except m.ClearFailure as error:
            assert str(error) == 'VAULT_CLEAR_MOUNT_IN_USE', str(error)
        else:
            raise AssertionError('moved mount was traversed')
    worker.join(10); assert not worker.is_alive()
    assert (destination/'nested'/'sentinel').read_text() == 'foreign'
    assert (source/'sentinel').read_text() == 'foreign'
    subprocess.run(['umount',str(destination/'nested')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    destination.rename(outside)
    original.rename(destination)
'''
        result = subprocess.run(['python3', '-c', code, str(SPEC.origin), str(self.data),
                                 json.dumps(self.properties), str(self.config_root)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        self.assertEqual(0, result.returncode, 'Concurrent bind/tmpfs movement proof failed')
        self.assertTrue(self.payload.exists())
        self.assertTrue(self.marker.exists())


    def test_missing_or_malformed_fd_mount_identity_fails_closed(self):
        from io import BytesIO
        for evidence in (b'', b'mnt_id: not-an-id\n', b'mnt_id: 1\nmnt_id: 2\n', b'x' * 4097):
            with self.subTest(evidence_length=len(evidence)), patch('builtins.open', return_value=BytesIO(evidence)):
                with self.assertRaisesRegex(CLEAR.ClearFailure, 'MOUNT_EVIDENCE_INVALID'):
                    CLEAR.mount_identity(123)


# Capture the actual scanner before per-test mocks are installed.
VaultClearSafetyTests.scanner = staticmethod(CLEAR.require_no_process)


if __name__ == '__main__':
    unittest.main()

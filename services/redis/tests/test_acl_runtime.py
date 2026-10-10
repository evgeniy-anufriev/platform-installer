import copy
import getpass
import grp
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import yaml

ROLE = Path(__file__).resolve().parents[1] / 'ansible_collections/platform/redis/roles/redis_tls'


class RedisACLRuntimeTests(unittest.TestCase):
    def test_default_acl_save_repeat_and_read_only_verify_on_redis_and_sentinel(self):
        if not all(shutil.which(name) for name in ['redis-server', 'redis-cli', 'ansible-playbook']):
            self.skipTest('Redis and Ansible runtime required')
        with tempfile.TemporaryDirectory(prefix='platform-redis-acl-') as directory:
            root = Path(directory)
            secrets = {}
            for kind in ['redis', 'sentinel']:
                path = root / (kind + '.secret')
                path.write_text('fixture-' + kind + '-password', encoding='utf-8')
                path.chmod(0o600)
                secrets[kind] = str(path)
            variables = {'redis_member': {'config_directory': str(root), 'roles': ['redis', 'sentinel']},
                         'platform_redis_user': getpass.getuser(),
                         'platform_redis_group': grp.getgrgid(os.getgid()).gr_name,
                         'platform_redis_credential': {'passwordSecretRef': 'redis'},
                         'platform_redis_sentinel_credential': {'passwordSecretRef': 'sentinel'},
                         'platform_redis_secret_files': secrets,
                         '_platform_redis_has_persistent_state': False,
                         '_platform_redis_acl_overwrite_allowed': False,
                         'platform_redis_verify_only': False}

            def run(tasks, values=variables, expected=0):
                play = [{'hosts': 'localhost', 'connection': 'local', 'gather_facts': False,
                         'vars': values, 'tasks': tasks}]
                path = root / 'test.yml'
                path.write_text(yaml.safe_dump(play), encoding='utf-8')
                result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(path)],
                                        capture_output=True, text=True, timeout=90)
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                return result.stdout

            prepare = yaml.safe_load((ROLE / 'tasks/acl_files.yml').read_text(encoding='utf-8'))
            runtime = yaml.safe_load((ROLE / 'tasks/acl_runtime.yml').read_text(encoding='utf-8'))
            run(prepare)
            processes = []
            try:
                for kind in ['redis', 'sentinel']:
                    socket = root / (kind + '.sock')
                    config = root / (kind + '.conf')
                    config.write_text('port 0\nunixsocket ' + str(socket) + '\nunixsocketperm 700\n'
                                      'aclfile ' + str(root / (kind + '.users.acl')) + '\n'
                                      'dir ' + str(root) + '\n', encoding='utf-8')
                    process = subprocess.Popen(['redis-server', str(config)] + (['--sentinel'] if kind == 'sentinel' else []),
                                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, umask=0o077)
                    processes.append(process)
                    for _ in range(100):
                        if socket.exists():
                            break
                        if process.poll() is not None:
                            diagnostic = process.communicate()[0]
                            diagnostic = re.sub(r'#[0-9a-f]{64}|fixture-\S+', '[redacted]', diagnostic)
                            self.fail(kind + ' failed to load ACL: ' + diagnostic[-1500:])
                        time.sleep(0.05)
                    self.assertTrue(socket.exists())
                fixture_runtime = copy.deepcopy(runtime)
                for task in fixture_runtime:
                    if 'ansible.builtin.command' in task:
                        arguments = task['ansible.builtin.command']['argv']
                        operation = arguments[arguments.index('default') + 1:]
                        task['ansible.builtin.command']['argv'] = ['redis-cli', '--raw', '-s',
                            str(root) + '/{{ item }}.sock', '--user', 'default'] + operation
                run(fixture_runtime)
                for kind in ['redis', 'sentinel']:
                    acl = root / (kind + '.users.acl')
                    content = acl.read_text(encoding='utf-8')
                    self.assertIn('#' + hashlib.sha256(('fixture-' + kind + '-password').encode()).hexdigest(), content)
                    self.assertNotIn('fixture-', content)
                    self.assertEqual(acl.stat().st_mode & 0o777, 0o600)
                self.assertIn('changed=0', run(prepare))
                owned = dict(variables, _platform_redis_has_persistent_state=True,
                             _platform_redis_acl_overwrite_allowed=True)
                run(prepare, owned)
                self.assertIn('changed=0', run(prepare, owned))
                self.assertIn('changed=0', run(fixture_runtime))
                redis_acl = root / 'redis.users.acl'
                redis_password_hash = hashlib.sha256(b'fixture-redis-password').hexdigest()
                redis_acl.write_text(redis_acl.read_text(encoding='utf-8').replace(redis_password_hash, '0' * 64),
                                     encoding='utf-8')
                run(prepare, owned)
                self.assertIn('#' + redis_password_hash, redis_acl.read_text(encoding='utf-8'))

                redis_config = root / 'redis.conf'
                own_path = str(root / 'redis.users.acl')
                redis_config.write_text('user default on #old-hash ~* &* +@all\n'
                                        'aclfile ' + own_path + '\nport 0\n', encoding='utf-8')
                run(prepare, owned)
                retained_config = redis_config.read_text(encoding='utf-8')
                self.assertNotRegex(retained_config, r'(?m)^\s*user\s+')
                self.assertIn('aclfile ' + own_path, retained_config)
                foreign_config = 'user foreign on nopass ~* +@all\naclfile /legacy/redis.acl\nport 0\n'
                redis_config.write_text(foreign_config, encoding='utf-8')
                run(prepare, owned, expected=2)
                self.assertEqual(foreign_config, redis_config.read_text(encoding='utf-8'))
                redis_config.write_text('aclfile ' + own_path + '\nport 0\n', encoding='utf-8')

                readonly = dict(variables, platform_redis_verify_only=True)
                before = [(root / (kind + '.users.acl')).stat().st_mtime_ns for kind in ['redis', 'sentinel']]
                run(fixture_runtime, readonly)
                self.assertEqual(before, [(root / (kind + '.users.acl')).stat().st_mtime_ns for kind in ['redis', 'sentinel']])
            finally:
                for process in processes:
                    process.terminate()
                    process.wait(timeout=10)
                    if process.stdout:
                        process.stdout.close()
            acl = root / 'redis.users.acl'
            original = acl.read_text(encoding='utf-8')
            for content in [original + 'user foreign on nopass ~* +@all\n',
                            original.replace(' +@all', ' >fixture-plaintext +@all')]:
                acl.write_text(content, encoding='utf-8')
                run(prepare, expected=2)
                run(prepare, owned, expected=2)
                self.assertEqual(content, acl.read_text(encoding='utf-8'))
            old_hash_acl = original.replace('#' + hashlib.sha256(b'fixture-redis-password').hexdigest(), '#' + '0' * 64)
            acl.write_text(old_hash_acl, encoding='utf-8')
            run(prepare, expected=2)
            self.assertEqual(old_hash_acl, acl.read_text(encoding='utf-8'))
            run(prepare, owned)
            self.assertIn('#' + hashlib.sha256(b'fixture-redis-password').hexdigest(), acl.read_text(encoding='utf-8'))
            acl.unlink()
            target = root / 'foreign.acl'
            target.write_text(original, encoding='utf-8')
            acl.symlink_to(target)
            run(prepare, expected=2)
            self.assertEqual(original, target.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()

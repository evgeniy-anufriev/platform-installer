"""Real Redis ACL engine tests; Unix transport is test-owned and local only."""
import hashlib
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ansible_collections.platform.redis.plugins.module_utils.application_acl import Client, ACLFailure, ensure_account, read_witness


class ApplicationACLTests(unittest.TestCase):
    def test_native_create_repeat_verify_and_foreign_user_denial(self):
        if not shutil.which('redis-server'):
            self.skipTest('Redis runtime required')
        with tempfile.TemporaryDirectory(prefix='platform-redis-app-acl-') as directory:
            root = Path(directory)
            password, app_password = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
            acl = root / 'redis.users.acl'
            acl.write_text('user default on #' + hashlib.sha256(password.encode()).hexdigest() + ' ~* &* +@all\n')
            acl.chmod(0o600)
            config = root / 'redis.conf'
            config.write_text('port 0\nunixsocket ' + str(root / 'redis.sock') + '\nunixsocketperm 700\n'
                              'aclfile ' + str(acl) + '\ndir ' + directory + '\n')
            process = subprocess.Popen(['redis-server', str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, umask=0o077)
            clients = []
            try:
                for _ in range(100):
                    if (root / 'redis.sock').exists():
                        break
                    time.sleep(0.02)

                def connection():
                    client = Client.__new__(Client)
                    client.socket = socket.socket(socket.AF_UNIX)
                    client.socket.settimeout(10)
                    client.socket.connect(str(root / 'redis.sock'))
                    client.stream = client.socket.makefile('rb')
                    clients.append(client)
                    return client

                admin = connection()
                self.assertEqual('OK', admin.command('AUTH', 'default', password))
                grants = {'commands': ['ping', 'get', 'set', 'del'], 'keys': ['sdku:*'], 'channels': []}
                args = (admin, connection(), directory, 'api-sdku', app_password, 'scope-sdku', 'client', grants, 'managed')
                self.assertFalse(ensure_account(*args, preflight=True))
                self.assertEqual({}, read_witness(directory))
                self.assertTrue(ensure_account(*args))
                before = acl.read_bytes()
                self.assertFalse(ensure_account(*args))
                self.assertFalse(ensure_account(*args, verify=True))
                self.assertEqual(before, acl.read_bytes())
                self.assertEqual('OK', args[1].command('SET', 'sdku:probe', 'healthy'))
                self.assertEqual('healthy', args[1].command('GET', 'sdku:probe'))
                self.assertEqual(1, args[1].command('DEL', 'sdku:probe'))
                with self.assertRaises(ACLFailure):
                    args[1].command('GET', 'foreign:probe')
                with self.assertRaises(ACLFailure):
                    ensure_account(admin, connection(), directory, 'api-sdku', 'wrong', 'scope-sdku', 'client', grants, 'managed')
                self.assertEqual({'client/api-sdku': 'scope-sdku'}, read_witness(directory))
                admin.command('ACL', 'SETUSER', 'foreign', 'on', '#' + hashlib.sha256(app_password.encode()).hexdigest(), '+ping')
                with self.assertRaises(ACLFailure):
                    ensure_account(admin, connection(), directory, 'foreign', app_password, 'ours', 'client', {'commands': ['ping']}, 'managed')
                self.assertFalse(ensure_account(admin, connection(), directory, 'foreign', app_password, 'ours', 'client', {'commands': ['ping']}, 'existing'))
                self.assertNotIn('client/foreign', read_witness(directory))
                admin.command('ACL', 'SETUSER', 'foreign-broad', 'on', '#' + hashlib.sha256(app_password.encode()).hexdigest(), '~*', '+@all')
                with self.assertRaisesRegex(ACLFailure, 'REDIS_APPLICATION_GRANTS_DRIFT'):
                    ensure_account(admin, connection(), directory, 'foreign-broad', app_password, 'ours-broad', 'client', grants, 'existing')
                self.assertNotIn('client/foreign-broad', read_witness(directory))
                self.assertIn('user api-sdku ', acl.read_text())
                self.assertIn('user default ', acl.read_text())
                self.assertNotIn(app_password, acl.read_text())
                concurrent_args = []
                for _ in range(2):
                    another_admin = connection()
                    self.assertEqual('OK', another_admin.command('AUTH', 'default', password))
                    concurrent_args.append((another_admin, connection(), directory, 'api-concurrent',
                                            app_password, 'scope-concurrent', 'client', grants, 'managed'))
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(lambda values: ensure_account(*values), concurrent_args))
                self.assertEqual([False, True], sorted(results))
                lock = root / '.application-accounts.lock'
                lock.unlink()
                lock.symlink_to(root / 'redis.users.acl')
                with self.assertRaises((ACLFailure, OSError)):
                    ensure_account(*args)
            finally:
                for client in clients:
                    client.close()
                process.terminate()
                process.wait(timeout=10)

    def test_native_partial_member_failure_retry_and_publish_barrier(self):
        """A later member failure must not lose the first member's custody or pass the barrier."""
        if not shutil.which('redis-server'):
            self.skipTest('Redis runtime required')
        with tempfile.TemporaryDirectory(prefix='platform-redis-app-partial-') as directory:
            root = Path(directory)
            password, app_password = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
            members, processes, clients = [], [], []
            for index in range(2):
                member = root / ('member-' + str(index + 1))
                member.mkdir(mode=0o700)
                acl = member / 'redis.users.acl'
                acl.write_text('user default on #' + hashlib.sha256(password.encode()).hexdigest() + ' ~* &* +@all\n')
                acl.chmod(0o600)
                config = member / 'redis.conf'
                config.write_text('port 0\nunixsocket ' + str(member / 'redis.sock') + '\nunixsocketperm 700\n'
                                  'aclfile ' + str(acl) + '\ndir ' + str(member) + '\npidfile ' + str(member / 'redis.pid') + '\n'
                                  'logfile ' + str(member / 'redis.log') + '\n')
                members.append((member, config))
                processes.append(subprocess.Popen(['redis-server', str(config)], stdout=subprocess.DEVNULL,
                                                  stderr=subprocess.DEVNULL, umask=0o077))
            try:
                for member, _ in members:
                    for _ in range(200):
                        if (member / 'redis.sock').exists():
                            break
                        time.sleep(0.02)

                def connection(member):
                    client = Client.__new__(Client)
                    client.socket = socket.socket(socket.AF_UNIX)
                    client.socket.settimeout(5)
                    try:
                        client.socket.connect(str(member / 'redis.sock'))
                    except OSError:
                        client.socket.close()
                        raise
                    client.stream = client.socket.makefile('rb')
                    clients.append(client)
                    self.assertEqual('OK', client.command('AUTH', 'default', password))
                    return client

                grants = {'commands': ['ping', 'get'], 'keys': ['sdku:*'], 'channels': []}
                first, _ = members[0]
                first_args = (connection(first), connection(first), str(first), 'api-sdku', app_password,
                              'scope-sdku', 'client', grants, 'managed')
                publish = root / 'vault-published'
                self.assertTrue(ensure_account(*first_args))
                second, _ = members[1]
                failed_admin = Client.__new__(Client)
                failed_admin.socket = socket.socket(socket.AF_UNIX)
                failed_admin.socket.settimeout(5)
                failed_admin.socket.connect(str(second / 'redis.sock'))
                failed_admin.stream = failed_admin.socket.makefile('rb')
                clients.append(failed_admin)
                with self.assertRaises(ACLFailure):
                    failed_admin.command('AUTH', 'default', secrets.token_urlsafe(24))
                self.assertFalse(publish.exists(), 'Vault publication barrier passed while a member was unavailable')
                self.assertEqual({'client/api-sdku': 'scope-sdku'}, read_witness(str(first)))
                cspa_args = (first_args[0], connection(first), str(first), 'api-cspa', app_password,
                             'scope-cspa', 'client', {'commands': ['ping'], 'keys': ['cspa:*'], 'channels': []}, 'managed')
                self.assertTrue(ensure_account(*cspa_args))
                self.assertFalse(ensure_account(*first_args), 'Installing a second library changed the first library account')
                self.assertEqual({'client/api-sdku': 'scope-sdku', 'client/api-cspa': 'scope-cspa'}, read_witness(str(first)))

                second_args = (connection(second), connection(second), str(second), 'api-sdku', app_password,
                               'scope-sdku', 'client', grants, 'managed')
                self.assertTrue(ensure_account(*second_args))
                self.assertFalse(ensure_account(*first_args), 'The successful member was mutated again during retry')
                self.assertFalse(ensure_account(*second_args), 'The recovered member was mutated again on repeat')
                self.assertEqual({'client/api-sdku': 'scope-sdku', 'client/api-cspa': 'scope-cspa'}, read_witness(str(first)))
                self.assertEqual({'client/api-sdku': 'scope-sdku'}, read_witness(str(second)))
                publish.write_text('published only after every member passed')
                self.assertTrue(publish.exists())
            finally:
                for client in clients:
                    client.close()
                for process in processes:
                    process.terminate()
                for process in processes:
                    process.wait(timeout=10)


if __name__ == '__main__':
    unittest.main()

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
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ansible_collections.platform.redis.plugins.module_utils.application_acl import Client, ACLFailure, ensure_account, read_witness, account_state, command_permissions


class ApplicationACLTests(unittest.TestCase):
    def test_ordered_rules_and_future_command_meaning(self):
        commands = {'get': ['@read'], 'config|get': ['@admin'], 'config|set': ['@admin'], 'modulecmd': []}
        categories = ['read', 'admin']
        self.assertEqual({'get', 'modulecmd', '@all'}, command_permissions(['+@all', '-@admin'], commands, categories))
        self.assertEqual(set(commands) | {'@all'}, command_permissions(['-@admin', '+@all'], commands, categories))
        self.assertEqual({'config|get'}, command_permissions(['+config', '-config|set'], commands, categories))
        self.assertEqual({'get'}, command_permissions(['+@all', '-@all', '+@read'], commands, categories))
        self.assertNotEqual(command_permissions(['+@all'], commands, categories),
                            command_permissions(list(commands), commands, categories))
        for rules in [['+@unknown'], ['+missingcommand'], ['+@all', 'reset'], ['+@all', '+@read extra']]:
            with self.subTest(rules=rules), self.assertRaises(ACLFailure):
                command_permissions(rules, commands, categories)

    def test_native_sentinel_operator_commands_and_repeat(self):
        if not shutil.which('redis-server'):
            self.skipTest('Redis runtime required')
        with tempfile.TemporaryDirectory(prefix='platform-sentinel-app-acl-') as directory, socket.socket() as reserved:
            reserved.bind(('127.0.0.1', 0))
            root = Path(directory)
            password, app_password = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
            acl = root / 'sentinel.users.acl'
            acl.write_text('user default on #' + hashlib.sha256(password.encode()).hexdigest() + ' ~* &* +@all\n')
            acl.chmod(0o600)
            config = root / 'sentinel.conf'
            config.write_text('port 0\nunixsocket ' + str(root / 'sentinel.sock') + '\nunixsocketperm 700\n'
                              'aclfile ' + str(acl) + '\ndir ' + directory + '\n'
                              'sentinel monitor qa-master 127.0.0.1 ' + str(reserved.getsockname()[1]) + ' 1\n')
            process = subprocess.Popen(['redis-server', str(config), '--sentinel'], stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, umask=0o077)
            clients = []
            try:
                for _ in range(100):
                    if (root / 'sentinel.sock').exists():
                        break
                    time.sleep(0.02)

                def connection():
                    client = Client.__new__(Client)
                    client.socket = socket.socket(socket.AF_UNIX)
                    client.socket.settimeout(10)
                    client.socket.connect(str(root / 'sentinel.sock'))
                    client.stream = client.socket.makefile('rb')
                    clients.append(client)
                    return client

                admin, app = connection(), connection()
                self.assertEqual('OK', admin.command('AUTH', 'default', password))
                grants = {'commands': ['ping', 'sentinel|get-master-addr-by-name', 'sentinel|master']}
                args = (admin, app, directory, 'sdku_dm', app_password, 'scope-sdku', 'sentinel', grants, 'managed')
                self.assertTrue(ensure_account(*args))
                self.assertIn('qa-master', app.command('SENTINEL', 'MASTER', 'qa-master'))
                self.assertEqual(['127.0.0.1', str(reserved.getsockname()[1])],
                                 app.command('SENTINEL', 'GET-MASTER-ADDR-BY-NAME', 'qa-master'))
                before = acl.read_bytes()
                for command in [('SENTINEL', 'RESET', 'qa-master'),
                                ('SENTINEL', 'SET', 'qa-master', 'down-after-milliseconds', '20000')]:
                    with self.subTest(command=command), self.assertRaises(ACLFailure):
                        app.command(*command)
                self.assertFalse(ensure_account(*args))
                self.assertFalse(ensure_account(*args, verify=True))
                self.assertEqual(before, acl.read_bytes())
                expanded = dict(grants, commands=grants['commands'] + ['sentinel|set', 'sentinel|reset'],
                                channels=['+switch-master'])
                expanded_args = (*args[:7], expanded, args[8])
                self.assertTrue(ensure_account(*expanded_args))
                self.assertEqual('OK', app.command('SENTINEL', 'SET', 'qa-master', 'down-after-milliseconds', '20000'))
                self.assertEqual(1, app.command('SENTINEL', 'RESET', 'qa-master'))
                before = acl.read_bytes()
                self.assertFalse(ensure_account(*expanded_args))
                self.assertFalse(ensure_account(*expanded_args, verify=True))
                self.assertEqual(before, acl.read_bytes())
                all_grants = dict(expanded, commands=['@all', 'ping'])
                all_args = (*args[:7], all_grants, args[8])
                with self.assertRaisesRegex(ACLFailure, 'REDIS_APPLICATION_GRANTS_MISSING'):
                    ensure_account(*all_args, verify=True)
                self.assertTrue(ensure_account(*all_args))
                self.assertIn('+@all', account_state(admin, 'sdku_dm')['commands'].split())
                before = acl.read_bytes()
                self.assertFalse(ensure_account(*all_args))
                self.assertFalse(ensure_account(*all_args, verify=True))
                self.assertEqual(before, acl.read_bytes())
                with self.assertRaisesRegex(ACLFailure, 'REDIS_APPLICATION_GRANTS_DRIFT'):
                    ensure_account(*expanded_args, verify=True)
                restricted = (*args[:7], dict(expanded, commands=['+@all', '-@admin']), args[8])
                self.assertTrue(ensure_account(*restricted))
                with self.assertRaises(ACLFailure):
                    app.command('SENTINEL', 'MASTER', 'qa-master')
                self.assertFalse(ensure_account(*restricted))
                self.assertFalse(ensure_account(*restricted, verify=True))
                self.assertTrue(ensure_account(*expanded_args))
                self.assertIn('qa-master', app.command('SENTINEL', 'MASTER', 'qa-master'))
            finally:
                for client in clients:
                    client.close()
                process.terminate()
                process.wait(timeout=10)

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
                grants = {'commands': ['ping', 'get', 'set', 'del', 'acl|whoami', 'config|get'],
                          'keys': ['sdku:*'], 'channels': []}
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
                self.assertEqual('api-sdku', args[1].command('ACL', 'WHOAMI'))
                self.assertEqual(['port', '0'], args[1].command('CONFIG', 'GET', 'port'))
                with self.assertRaises(ACLFailure):
                    args[1].command('GET', 'foreign:probe')
                replacement = secrets.token_urlsafe(24)
                rotate_args = (admin, connection(), directory, 'api-sdku', replacement, 'scope-sdku', 'client', grants, 'managed')
                self.assertFalse(ensure_account(*rotate_args, preflight=True))
                self.assertTrue(ensure_account(*rotate_args))
                self.assertFalse(ensure_account(*rotate_args))
                self.assertTrue(ensure_account(*args))
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
                all_args = (admin, connection(), directory, 'api-all', app_password, 'scope-all', 'client',
                            {'commands': ['@all'], 'keys': ['sdku:*'], 'channels': []}, 'managed')
                default_before = account_state(admin, 'default')
                self.assertTrue(ensure_account(*all_args))
                self.assertEqual('+@all', account_state(admin, 'api-all')['commands'])
                self.assertEqual('OK', all_args[1].command('HMSET', 'sdku:hash', 'field', 'value'))
                self.assertFalse(ensure_account(*all_args))
                self.assertFalse(ensure_account(*all_args, verify=True))
                with self.assertRaises(ACLFailure):
                    all_args[1].command('GET', 'foreign:probe')
                self.assertEqual(default_before, account_state(admin, 'default'))
                restricted = (*all_args[:7], dict(all_args[7], commands=['+@all', '-@admin']), all_args[8])
                before = acl.read_bytes()
                with self.assertRaises(ACLFailure):
                    ensure_account(*restricted, verify=True)
                with self.assertRaises(ACLFailure):
                    ensure_account(*restricted[:8], 'existing')
                self.assertEqual(before, acl.read_bytes())
                self.assertFalse(ensure_account(*restricted, preflight=True))
                self.assertEqual(before, acl.read_bytes())
                self.assertTrue(ensure_account(*restricted))
                self.assertEqual('OK', all_args[1].command('HMSET', 'sdku:hash', 'field', 'value'))
                with self.assertRaises(ACLFailure):
                    all_args[1].command('CONFIG', 'GET', 'port')
                before, witness_before = acl.read_bytes(), read_witness(directory)
                self.assertFalse(ensure_account(*restricted))
                self.assertFalse(ensure_account(*restricted, verify=True))
                for invalid in ['+@unknown', 'nocommands', '+missingcommand']:
                    with self.subTest(invalid=invalid), self.assertRaises(ACLFailure):
                        ensure_account(*all_args[:7], dict(all_args[7], commands=[invalid]), all_args[8])
                original_command = admin.command
                with patch.object(admin, 'command', side_effect=lambda *a: [[]] if a == ('COMMAND',) else original_command(*a)):
                    with self.assertRaisesRegex(ACLFailure, 'REDIS_APPLICATION_METADATA_INVALID'):
                        ensure_account(*restricted)
                self.assertEqual(before, acl.read_bytes())
                self.assertEqual(witness_before, read_witness(directory))
                self.assertEqual(default_before, account_state(admin, 'default'))
                exception = (*all_args[:7], dict(all_args[7], commands=['+@all', '-@admin', '+config|get']), all_args[8])
                self.assertTrue(ensure_account(*exception))
                self.assertEqual(['port', '0'], all_args[1].command('CONFIG', 'GET', 'port'))
                with self.assertRaises(ACLFailure):
                    all_args[1].command('CONFIG', 'SET', 'timeout', '0')
                self.assertFalse(ensure_account(*exception, verify=True))
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

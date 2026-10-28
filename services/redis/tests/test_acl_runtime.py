import copy
import getpass
import grp
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import yaml

ROLE = Path(__file__).resolve().parents[1] / 'ansible_collections/platform/redis/roles/redis_tls'


class RedisACLRuntimeTests(unittest.TestCase):
    def test_default_acl_save_repeat_and_read_only_verify_on_redis_and_sentinel(self):
        if not all(shutil.which(name) for name in ['redis-server', 'redis-cli', 'ansible-playbook', 'openssl']):
            self.skipTest('Redis and Ansible runtime required')
        with tempfile.TemporaryDirectory(prefix='platform-redis-acl-') as directory:
            root = Path(directory)
            pki = root / 'pki'
            pki.mkdir(mode=0o700)
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                            '-subj', '/CN=localhost', '-addext', 'subjectAltName=IP:127.0.0.1',
                            '-keyout', str(pki / 'private-key.pem'), '-out', str(pki / 'certificate.pem')],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            shutil.copyfile(pki / 'certificate.pem', pki / 'ca-chain.pem')
            ports = []
            reservations = []
            for _ in range(2):
                reservation = socket.socket()
                reservation.bind(('127.0.0.1', 0))
                ports.append(reservation.getsockname()[1])
                reservations.append(reservation)
            for reservation in reservations:
                reservation.close()
            secrets = {}
            for kind in ['redis', 'sentinel']:
                path = root / (kind + '.secret')
                path.write_text('fixture-' + kind + '-password', encoding='utf-8')
                path.chmod(0o600)
                secrets[kind] = str(path)
            variables = {'redis_member': {'config_directory': str(root), 'roles': ['redis', 'sentinel'],
                         'address': '127.0.0.1', 'redis_port': ports[0], 'sentinel_port': ports[1]},
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
                for index, kind in enumerate(['redis', 'sentinel']):
                    unix_socket = root / (kind + '.sock')
                    config = root / (kind + '.conf')
                    config.write_text('port 0\nbind 127.0.0.1\ntls-port ' + str(ports[index]) + '\n'
                                      'tls-cert-file ' + str(pki / 'certificate.pem') + '\n'
                                      'tls-key-file ' + str(pki / 'private-key.pem') + '\n'
                                      'tls-ca-cert-file ' + str(pki / 'ca-chain.pem') + '\n'
                                      'tls-auth-clients yes\nunixsocket ' + str(unix_socket) + '\nunixsocketperm 700\n'
                                      'aclfile ' + str(root / (kind + '.users.acl')) + '\n'
                                      'dir ' + str(root) + '\n' +
                                      ('sentinel sentinel-user default\nsentinel sentinel-pass ' +
                                       json.dumps('fixture-sentinel-password') + '\n' if kind == 'sentinel' else ''),
                                      encoding='utf-8')
                    process = subprocess.Popen(['redis-server', str(config)] + (['--sentinel'] if kind == 'sentinel' else []),
                                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, umask=0o077)
                    processes.append(process)
                    for _ in range(100):
                        if unix_socket.exists():
                            break
                        if process.poll() is not None:
                            diagnostic = process.communicate()[0]
                            diagnostic = re.sub(r'#[0-9a-f]{64}|fixture-\S+', '[redacted]', diagnostic)
                            self.fail(kind + ' failed to load ACL: ' + diagnostic[-1500:])
                        time.sleep(0.05)
                    self.assertTrue(unix_socket.exists())
                fixture_runtime = copy.deepcopy(runtime)
                for task in fixture_runtime:
                    if 'ansible.builtin.command' in task:
                        arguments = task['ansible.builtin.command']['argv']
                        operation = arguments[arguments.index('default') + 1:]
                        task['ansible.builtin.command']['argv'] = ['redis-cli', '--raw', '-s',
                            str(root) + '/{{ item }}.sock', '--user', 'default'] + operation
                run(fixture_runtime)
                app_secret = root / 'app.secret'
                app_secret.write_text(__import__('secrets').token_urlsafe(24), encoding='utf-8')
                app_secret.chmod(0o600)
                provider_job = {'serviceType': 'redis', 'providerId': 'redis-qa', 'mode': 'sentinel-ha', 'accounts': []}
                for index, alias in enumerate(['redis', 'sentinel']):
                    provider_job['accounts'].append({
                        'name': 'app-qa', 'mode': 'managed', 'listener': 'client' if alias == 'redis' else 'sentinel',
                        'passwordRef': 'app-password', 'adminPasswordRef': alias,
                        'marker': 'platform.application/v1:qa:redis-qa:lib:account:app-qa/' + alias,
                        'grants': {'commands': ['ping']} if alias == 'sentinel' else {'commands': ['ping', 'get'], 'keys': ['qa:*'], 'channels': []},
                        'candidates': [{'hostId': 'localhost', 'memberId': root.name, 'address': '127.0.0.1', 'port': ports[index]}]})
                provider_vars = dict(variables, platform_redis_application_job=provider_job,
                                     platform_redis_config_root=str(root.parent), platform_application_secret_root=str(root),
                                     platform_redis_application_credential_files=dict(secrets, **{'app-password': str(app_secret)}))
                def provider_tasks(stage):
                    return [{'ansible.builtin.include_role': {'name': 'platform.redis.application_provider', 'tasks_from': stage}}]
                self.assertIn('changed=0', run(provider_tasks('preflight'), provider_vars))
                run(provider_tasks('accounts'), provider_vars)
                self.assertIn('changed=0', run(provider_tasks('accounts'), provider_vars))
                self.assertIn('changed=0', run(provider_tasks('verify'), provider_vars))
                run(prepare)
                run(fixture_runtime)
                for alias in ['redis', 'sentinel']:
                    self.assertIn('user app-qa ', (root / (alias + '.users.acl')).read_text())
                for kind in ['redis', 'sentinel']:
                    acl = root / (kind + '.users.acl')
                    content = acl.read_text(encoding='utf-8')
                    self.assertIn('user default on sanitize-payload ', content)
                    self.assertIn('#' + hashlib.sha256(('fixture-' + kind + '-password').encode()).hexdigest(), content)
                    self.assertNotIn('fixture-', content)
                    self.assertEqual(acl.stat().st_mode & 0o777, 0o600)
                self.assertIn('changed=0', run(prepare))
                owned = dict(variables, _platform_redis_has_persistent_state=True,
                             _platform_redis_acl_overwrite_allowed=True)
                self.assertIn('changed=0', run(prepare, owned))
                self.assertIn('changed=0', run(prepare, owned))
                self.assertIn('changed=0', run(fixture_runtime))

                member = yaml.safe_load((ROLE / 'tasks/member.yml').read_text(encoding='utf-8'))
                config_tasks = [task for task in member if task['name'] in (
                    'Подключение файла Redis ACL без перезаписи сохраненного состояния репликации',
                    'Подключение ACL-файла Sentinel, сохранив сведения о выбранном мастере',
                    'Настройка пароля узла Sentinel из секрета времени выполнения')]
                self.assertEqual(3, len(config_tasks))
                tracked = [root / (kind + suffix) for kind in ['redis', 'sentinel']
                           for suffix in ['.users.acl', '.conf']]
                for _ in range(2):
                    for index, kind in enumerate(['redis', 'sentinel']):
                        cli = ['redis-cli', '--raw', '--tls', '--cacert', str(pki / 'ca-chain.pem'),
                               '--cert', str(pki / 'certificate.pem'), '--key', str(pki / 'private-key.pem'),
                               '-h', '127.0.0.1', '-p', str(ports[index])]
                        cli_env = dict(os.environ, REDISCLI_AUTH='fixture-' + kind + '-password')
                        for command in [['ACL', 'SAVE'],
                                        ['CONFIG', 'REWRITE'] if kind == 'redis' else ['SENTINEL', 'FLUSHCONFIG']]:
                            saved = subprocess.run(cli + command, env=cli_env, capture_output=True,
                                                   text=True, timeout=15)
                            self.assertEqual(saved.returncode, 0, 'Native save/rewrite failed')
                            self.assertEqual(saved.stdout.strip(), 'OK')
                    before = [path.read_bytes() for path in tracked]
                    self.assertIn('changed=0', run(prepare + config_tasks, owned))
                    self.assertEqual(before, [path.read_bytes() for path in tracked])
                    self.assertIn('changed=0', run(prepare + config_tasks, owned))

                sentinel_config = root / 'sentinel.conf'
                original_sentinel_config = sentinel_config.read_text(encoding='utf-8')
                try:
                    for value in ['fixture!plain', 'fixture with spaces', 'fixture\\slash', 'fixture"quote']:
                        Path(secrets['sentinel']).write_text(value, encoding='utf-8')
                        encoded_values = [json.dumps(value)]
                        if ' ' not in value and '"' not in value:
                            encoded_values.append(value)
                        for encoded in encoded_values:
                            sentinel_config.write_text(re.sub(r'(?m)^sentinel sentinel-pass .+$',
                                lambda _: 'sentinel sentinel-pass ' + encoded, original_sentinel_config), encoding='utf-8')
                            before = sentinel_config.read_bytes()
                            self.assertIn('changed=0', run([prepare[0]] + config_tasks, owned))
                            self.assertEqual(before, sentinel_config.read_bytes())
                    Path(secrets['sentinel']).write_text('fixture-sentinel-password', encoding='utf-8')
                    sentinel_config.write_text(re.sub(r'(?m)^sentinel sentinel-pass .+$',
                        'sentinel sentinel-pass wrong-fixture-value', original_sentinel_config), encoding='utf-8')
                    self.assertIn('changed=1', run([prepare[0]] + config_tasks, owned))
                    self.assertIn('changed=0', run([prepare[0]] + config_tasks, owned))
                finally:
                    Path(secrets['sentinel']).write_text('fixture-sentinel-password', encoding='utf-8')
                    sentinel_config.write_text(original_sentinel_config, encoding='utf-8')

                redis_config = root / 'redis.conf'
                redis_config.write_text(re.sub(r'(?m)^aclfile .+\n', '', redis_config.read_text()), encoding='utf-8')
                self.assertIn('changed=1', run(prepare + config_tasks, owned))
                self.assertIn('changed=0', run(prepare + config_tasks, owned))

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
            retained = original + 'user foreign off -@all\n'
            acl.write_text(retained, encoding='utf-8')
            self.assertIn('changed=0', run(prepare))
            self.assertIn('user foreign off', acl.read_text(encoding='utf-8'))
            for content in [original + 'user default on nopass ~* +@all\n',
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

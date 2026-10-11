"""Explicit isolated A5 full entrypoint QA, reusing the A4 Vault/PKCS12 fixture."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('application_a4_fixture', ROOT / 'services/vault/tests/qa_application_provider.py')
a4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a4)


class ApplicationA5QA(a4.ApplicationVaultQA):
    @classmethod
    def setUpClass(cls):
        if os.environ.get('A4_FULL_SERVICES') == '1':
            raise RuntimeError('A5_REQUIRES_ISOLATED_INFRASTRUCTURE')
        image_id = os.environ.get('A5_PROBE_IMAGE_ID', '')
        if not __import__('re').fullmatch(r'sha256:[a-f0-9]{64}', image_id):
            raise RuntimeError('A5_BUILT_PROBE_IMAGE_REQUIRED')
        a4.IMAGE, a4.IMAGE_ID = 'platform-application-connection-probe:a5-qa', image_id
        cls.processes = []
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        for process in reversed(cls.processes):
            process.terminate()
        for process in reversed(cls.processes):
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        super().tearDownClass()

    def test_a5_full_apply_verify_repeat(self):
        self.configured = False
        self.table_ready = False
        super().test_a4_full_apply_verify_repeat()
        print('A5_NATIVE_ENTRYPOINT_REPEAT_VERIFY_PASS redis=ok sentinel=ok clickhouse=ok pg_pkcs12_agent=ok')

    def free_base(self, count=1):
        while True:
            reservations = []
            try:
                for index in range(count):
                    sock = socket.socket()
                    reservations.append(sock)
                    sock.bind((a4.ADDRESS, 0 if index == 0 else base + index))
                    if index == 0:
                        base = sock.getsockname()[1]
                return base
            except OSError:
                pass
            finally:
                for sock in reservations:
                    sock.close()

    def private_password(self, reference):
        path = self.secret_root / reference.replace(':', '-')
        value = secrets.token_urlsafe(24)
        path.write_text(value)
        path.chmod(0o600)
        self.passwords[reference] = str(path)
        return value

    def member_pki(self, directory):
        directory.mkdir(parents=True, mode=0o700)
        pki = directory / 'pki'
        pki.mkdir(mode=0o700)
        for source, destination in [('pg-cert.pem', 'certificate.pem'), ('pg-key.pem', 'private-key.pem'), ('pg-cert.pem', 'ca-chain.pem')]:
            shutil.copyfile(self.tls / source, pki / destination)
            (pki / destination).chmod(0o600)

    def launch(self, binary, config):
        self.processes.append(subprocess.Popen([binary, str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                               env=dict(os.environ, CLICKHOUSE_WATCHDOG_ENABLE='0')))

    def configure_providers(self):
        kafka_host, kafka_port, kafka_ca = (os.environ.get(name) for name in ['A5_KAFKA_HOST', 'A5_KAFKA_PORT', 'A5_KAFKA_CA_PATH'])
        if any([kafka_host, kafka_port, kafka_ca]) and not all([kafka_host, kafka_port, kafka_ca]):
            raise RuntimeError('A5_KAFKA_TLS_INPUTS_INCOMPLETE')
        if kafka_ca:
            ca = subprocess.run(['sudo', '-n', 'cat', kafka_ca], capture_output=True, check=True).stdout
            if b'-----BEGIN CERTIFICATE-----' not in ca or b'PRIVATE KEY' in ca:
                raise RuntimeError('A5_KAFKA_PUBLIC_CA_REQUIRED')
            for filename in ['pg-ca.pem', 'ca-chain.pem']:
                path = self.tls / filename
                path.write_bytes(path.read_bytes() + ca)
        self.kafka_enabled = bool(kafka_host)
        self.redis_root = self.secret_root / 'redis'
        self.clickhouse_root = self.secret_root / 'clickhouse'
        redis_port, sentinel_port = self.free_base(3), self.free_base(3)
        native_port, https_port = self.free_base(), self.free_base()
        redis_admin = self.private_password('runtime:redis-admin')
        sentinel_admin = self.private_password('runtime:sentinel-admin')
        ch_admin = self.private_password('runtime:clickhouse-admin')
        for alias in ['redis', 'sentinel', 'clickhouse']:
            self.private_password(alias + '-app-password')
        for index in range(3):
            member = self.redis_root / ('redis-' + str(index + 1))
            self.member_pki(member)
            certs = ('tls-cert-file %s\ntls-key-file %s\ntls-ca-cert-file %s\n' % tuple(member / 'pki' / name
                     for name in ['certificate.pem', 'private-key.pem', 'ca-chain.pem']))
            for listener, password in [('redis', redis_admin), ('sentinel', sentinel_admin)]:
                acl = member / (listener + '.users.acl')
                acl.write_text('user default on #' + hashlib.sha256(password.encode()).hexdigest() + ' ~* &* +@all\n')
                acl.chmod(0o600)
            redis = member / 'redis.conf'
            redis.write_text('port 0\nbind ' + a4.ADDRESS + '\ntls-port ' + str(redis_port + index) + '\n' + certs
                             + 'aclfile ' + str(member / 'redis.users.acl') + '\ndir ' + str(member) + '\n'
                             + ('tls-replication yes\nreplicaof %s %d\nmasterauth %s\n' % (a4.ADDRESS, redis_port, redis_admin) if index else ''))
            redis.chmod(0o600)
            self.launch('redis-server', redis)
            sentinel = member / 'sentinel.conf'
            sentinel.write_text('port 0\nbind ' + a4.ADDRESS + '\ntls-port ' + str(sentinel_port + index) + '\n' + certs
                                + 'tls-replication yes\naclfile ' + str(member / 'sentinel.users.acl') + '\ndir ' + str(member) + '\n'
                                + 'sentinel monitor redis-1 %s %d 2\nsentinel auth-pass redis-1 %s\n' % (a4.ADDRESS, redis_port, redis_admin))
            sentinel.chmod(0o600)
            self.launch('redis-sentinel', sentinel)
        ch = self.clickhouse_root / 'clickhouse-main' / 'ch-1'
        self.member_pki(ch)
        users = ch / 'users.xml'
        users.write_text('<clickhouse><users><default><password_sha256_hex>' + hashlib.sha256(ch_admin.encode()).hexdigest()
                         + '</password_sha256_hex><networks><ip>::/0</ip></networks><profile>default</profile><quota>default</quota>'
                         + '<access_management>1</access_management></default></users><profiles><default/></profiles><quotas><default/></quotas></clickhouse>')
        users.chmod(0o600)
        config = ch / 'server.xml'
        config.write_text('<clickhouse><listen_host>' + a4.ADDRESS + '</listen_host><tcp_port_secure>' + str(native_port)
                          + '</tcp_port_secure><https_port>' + str(https_port) + '</https_port><path>' + str(ch / 'data')
                          + '/</path><access_control_path>' + str(ch / 'access') + '/</access_control_path><users_config>' + str(users)
                          + '</users_config><openSSL><server><certificateFile>' + str(ch / 'pki/certificate.pem')
                          + '</certificateFile><privateKeyFile>' + str(ch / 'pki/private-key.pem') + '</privateKeyFile><caConfig>'
                          + str(ch / 'pki/ca-chain.pem') + '</caConfig><verificationMode>none</verificationMode></server></openSSL>'
                          + '<background_schedule_pool_size>16</background_schedule_pool_size><background_buffer_flush_schedule_pool_size>4</background_buffer_flush_schedule_pool_size>'
                          + '<background_message_broker_schedule_pool_size>4</background_message_broker_schedule_pool_size><background_distributed_schedule_pool_size>4</background_distributed_schedule_pool_size>'
                          + '<max_thread_pool_size>256</max_thread_pool_size><max_server_memory_usage>1073741824</max_server_memory_usage></clickhouse>')
        self.processes.append(subprocess.Popen(['clickhouse-server', '--config-file', str(config)], stdout=subprocess.DEVNULL,
                                               stderr=subprocess.DEVNULL, env=dict(os.environ, CLICKHOUSE_WATCHDOG_ENABLE='0')))
        group_path = self.project / 'inventory/group_vars/all/platform-installer.yml'
        group = json.loads(group_path.read_text())
        desired = group['platform_desired_state']
        desired['serviceDeployments']['redis-main'] = {'serviceType': 'redis', 'mode': 'sentinel-ha', 'configuration': {
            'tlsProfile': 'apps-tls', 'redisPort': redis_port, 'sentinelPort': sentinel_port,
            'redisCredential': {'passwordSecretRef': 'runtime:redis-admin'}, 'sentinelCredential': {'passwordSecretRef': 'runtime:sentinel-admin'}}}
        desired['serviceDeployments']['clickhouse-main'] = {'serviceType': 'clickhouse', 'mode': 'standalone', 'configuration': {
            'tlsProfile': 'apps-tls', 'port': https_port, 'nativePort': native_port, 'defaultCredential': {'passwordSecretRef': 'runtime:clickhouse-admin'}}}
        if self.kafka_enabled:
            desired['serviceDeployments']['kafka-main'] = {'serviceType': 'kafka', 'mode': 'kraft-standalone', 'configuration': {
                'tlsProfile': 'apps-tls', 'listeners': {
                    'CLIENT_SSL': {'purpose': 'client', 'securityProtocol': 'SSL', 'port': int(kafka_port), 'advertisedAddress': kafka_host},
                    'SSL': {'purpose': 'interBroker', 'securityProtocol': 'SSL', 'port': 19096},
                    'CONTROLLER': {'purpose': 'controller', 'securityProtocol': 'SSL', 'port': 19093}}}}
        library = desired['applicationLibraryDeployments']['sdku']
        library['bindings'].update(redis={'deploymentRef': 'redis-main'}, sentinel={'deploymentRef': 'redis-main'},
                                   clickhouse={'deploymentRef': 'clickhouse-main'})
        if self.kafka_enabled:
            library['bindings']['kafka'] = {'deploymentRef': 'kafka-main'}
        library['resources']['analytics'] = {'kind': 'clickhouse.database', 'mode': 'managed', 'binding': 'clickhouse', 'parameters': {'name': 'analytics'}}
        group_path.write_text(json.dumps(group))
        host_path = self.project / 'inventory/host_vars/node1/platform-installer.yml'
        host = json.loads(host_path.read_text())
        host['platform_deployments'].update({'redis-main': {'members': {'redis-' + str(index): {'roles': ['redis', 'sentinel']} for index in range(1, 4)}},
                                            'clickhouse-main': {'members': {'ch-1': {'roles': ['server']}}}})
        if self.kafka_enabled:
            host['platform_deployments']['kafka-main'] = {'members': {'broker-1': {'roles': ['broker', 'controller']}}}
        host_path.write_text(json.dumps(host))
        defaults_path = self.project / 'application-packages/apigateway/1.0.0/roles/application_apigateway/defaults/main.yml'
        defaults = json.loads(defaults_path.read_text())
        definition, base = defaults['platform_application_definition'], defaults['platform_application_definition']['defaults']
        if self.kafka_enabled:
            definition['connections']['kafka'] = {'library_binding': 'kafka', 'purpose': 'client'}
            library_path = self.project / 'library-packages/sdku/1.0.0/roles/library_sdku/defaults/main.yml'
            library_defaults = json.loads(library_path.read_text())
            library_defaults['platform_library_definition']['connection_defaults']['kafka'] = {'connectionRef': 'CLIENT_SSL'}
            library_path.write_text(json.dumps(library_defaults))
            base['environment']['KAFKA_TARGETS'] = kafka_host + ':' + kafka_port
        for alias in ['redis', 'sentinel', 'clickhouse']:
            definition['connections'][alias] = {'library_binding': alias, 'purpose': 'sentinel' if alias == 'sentinel' else 'client'}
            base['accounts'][alias] = {'mode': 'managed', 'credentials': {
                'username': {'source': {'kind': 'literal', 'value': 'apigateway-sdku'}},
                'password': {'source': {'kind': 'runtime_secret_ref', 'ref': alias + '-app-password'}}}}
            for field in ['username', 'password']:
                base['provisioner']['secret_bindings'][alias.upper() + ('_USER' if field == 'username' else '_PASSWORD')] = {
                    'source': {'account': alias, 'field': field}}
        base['accounts']['redis']['grants'] = {'commands': ['ping', 'get', 'set', 'del'], 'keys': ['a5qa:*']}
        base['accounts']['sentinel']['grants'] = {'commands': ['ping', 'sentinel|get-master-addr-by-name']}
        base['accounts']['clickhouse'].update(databaseRef='analytics', grants=[{'databaseRef': 'analytics', 'tables': ['*'], 'privileges': ['SELECT', 'INSERT']}])
        base['environment'].update(REDIS_HOST=a4.ADDRESS, REDIS_PORT=str(redis_port), SENTINEL_HOST=a4.ADDRESS,
            SENTINEL_PORT=str(sentinel_port), SENTINEL_MASTER_NAME='redis-1',
            REDIS_TARGETS=','.join(a4.ADDRESS + ':' + str(redis_port + index) for index in range(3)),
            PROBE_REDIS_KEY_PREFIX='a5qa:', CLICKHOUSE_URL='https://' + a4.ADDRESS + ':' + str(https_port),
            PROBE_CLICKHOUSE_DATABASE='analytics', PROBE_CLICKHOUSE_TABLE='events',
            PROBE_CLICKHOUSE_DENIED_DATABASE='analytics_forbidden', PROBE_CLICKHOUSE_DENIED_TABLE='events')
        defaults_path.write_text(json.dumps(defaults))
        self.a5_definition = json.loads(json.dumps(definition))
        extra = json.loads(self.extra.read_text())
        extra.update(platform_application_secret_root=str(self.secret_root), platform_application_secret_files=self.passwords,
                     platform_redis_config_root=str(self.redis_root), platform_redis_user=os.environ['USER'],
                     platform_clickhouse_config_root=str(self.clickhouse_root), platform_clickhouse_user=os.environ['USER'])
        self.extra.write_text(json.dumps(extra))
        self.env['ANSIBLE_COLLECTIONS_PATH'] = ':'.join(str(ROOT / path) for path in ['ansible-core/collections', 'services/postgresql', 'services/vault', 'services/redis', 'services/clickhouse'])
        self.ch_target = {'address': a4.ADDRESS, 'port': native_port}
        self.ch_directory = ch
        self.ch_admin = ch_admin
        time.sleep(1)

    def play_core(self, playbook, success=True):
        if not self.configured:
            self.configured = True
            self.configure_providers()
        else:
            # A4's negative scenarios rewrite their original PG-only defaults.
            # Retain those PG edits while keeping A5's declared provider scopes.
            path = self.project / 'application-packages/apigateway/1.0.0/roles/application_apigateway/defaults/main.yml'
            defaults = json.loads(path.read_text())
            definition = defaults['platform_application_definition']
            if 'redis' not in definition['defaults']['accounts']:
                definition['connections'].update(self.a5_definition['connections'])
                for alias in ['redis', 'sentinel', 'clickhouse']:
                    definition['connections'][alias] = self.a5_definition['connections'][alias]
                    definition['defaults']['accounts'][alias] = self.a5_definition['defaults']['accounts'][alias]
                    for field in ['_USER', '_PASSWORD']:
                        name = alias.upper() + field
                        definition['defaults']['provisioner']['secret_bindings'][name] = self.a5_definition['defaults']['provisioner']['secret_bindings'][name]
                definition['defaults']['environment'].update(self.a5_definition['defaults']['environment'])
                path.write_text(json.dumps(defaults))
        return super().play_core(playbook, success)

    def probe_status(self, host='node1'):
        if not self.table_ready:
            sys.path.insert(0, str(ROOT / 'services/clickhouse'))
            from ansible_collections.platform.clickhouse.plugins.module_utils.application_sql import NativeClient
            client = NativeClient(self.ch_target, str(self.ch_directory), self.ch_admin)
            try:
                client.query('CREATE TABLE analytics.events (id UInt64) ENGINE = Memory;\nCREATE DATABASE analytics_forbidden;\nCREATE TABLE analytics_forbidden.events (id UInt64) ENGINE = Memory;')
            finally:
                client.close()
            self.table_ready = True
        report = super().probe_status(host)
        for name in ['redis', 'sentinel', 'clickhouse']:
            self.assertEqual('ok', report['checks'][name]['state'], 'A5_' + name.upper() + '_STATUS_FAILED')
        if self.kafka_enabled:
            self.assertEqual('ok', report['checks']['kafka']['state'], 'A5_KAFKA_SSL_STATUS_FAILED')
            self.assertEqual('ok', report['overall'], 'A5_ALL_CONNECTIONS_REQUIRED')
        return report


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([ApplicationA5QA('test_a5_full_apply_verify_repeat')]))
    sys.exit(not result.wasSuccessful())

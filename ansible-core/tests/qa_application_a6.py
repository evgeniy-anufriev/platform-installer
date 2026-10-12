"""Explicit A6 QA using the existing isolated A5 Vault/PKCS provider fixture."""
import importlib.util
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('application_a5_fixture', ROOT / 'ansible-core/tests/qa_application_a5.py')
a5 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a5)


class ApplicationA6QA(a5.ApplicationA5QA):
    @classmethod
    def setUpClass(cls):
        a5.a4.ADDRESS = '192.168.56.101'
        cls.ssh_root = Path(os.environ['A6_SSH_ROOT'])
        cls.full_project = Path(os.environ['A6_FULL_PROJECT'])
        cls.application_cleanup_hosts = (('node1', '192.168.56.101'), ('node2', '192.168.56.102'))
        os.environ['A4_PROTECTED_LOG'] = str(cls.ssh_root / 'last-core-protected.log')
        super().setUpClass()

    def play_core(self, playbook, success=True):
        if not self.configured:
            inventory_path = self.project / 'inventory/hosts.yml'
            inventory = json.loads(inventory_path.read_text())
            for host, address in [('node2', '192.168.56.102'), ('node3', '192.168.56.103')]:
                inventory['all']['children']['platform_targets']['hosts'][host] = {
                    'ansible_host': address, 'ansible_user': 'platform-automation',
                    'ansible_private_key_file': str(self.ssh_root / 'node2-key'),
                    'ansible_ssh_common_args': '-o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=' + str(self.ssh_root / 'node2-known-hosts')}
                directory = self.project / 'inventory/host_vars' / host
                directory.mkdir(parents=True, exist_ok=True)
                variables = {'platform_deployments': {}, 'platform_application_libraries': {}}
                if host == 'node2':
                    variables.update(platform_deployments={'docker': {}}, platform_application_libraries={'sdku': {}})
                (directory / 'platform-installer.yml').write_text(json.dumps(variables))
            inventory_path.write_text(json.dumps(inventory))
        return super().play_core(playbook, success)

    def test_a6_endpoint_apply_verify_repeat(self):
        self.exercise_endpoint_case(full_haproxy=True)

    def test_a6_full_dns_reconcile(self):
        self.exercise_endpoint_case(full_haproxy=False)

    def exercise_endpoint_case(self, full_haproxy):
        self.configured = False
        self.table_ready = False
        self.prepare_application_fixture()
        node3_path = self.project / 'inventory/host_vars/node3/platform-installer.yml'
        node3 = json.loads(node3_path.read_text())
        node3['platform_application_libraries'] = {}
        node3_path.write_text(json.dumps(node3))
        # Core creates the managed database and ownership witness first; the
        # fixture migration adds tables before /status is used as readiness.
        self.play_core('application-libraries-providers-apply.yml')
        sys.path.insert(0, str(ROOT / 'services/clickhouse'))
        from ansible_collections.platform.clickhouse.plugins.module_utils.application_sql import NativeClient
        client = NativeClient(self.ch_target, str(self.ch_directory), self.ch_admin)
        try:
            client.query('CREATE TABLE analytics.events (id UInt64) ENGINE = Memory; CREATE DATABASE analytics_forbidden; CREATE TABLE analytics_forbidden.events (id UInt64) ENGINE = Memory;')
        finally:
            client.close()
        self.table_ready = True
        path = self.project / 'inventory/group_vars/all/platform-installer.yml'
        group = json.loads(path.read_text())
        desired = group['platform_desired_state']
        full = yaml.safe_load((self.full_project / 'inventory/group_vars/all/platform-installer.yml').read_text())['platform_desired_state']
        for key in ['endpointGroups', 'certificateAuthorities', 'certificateProfiles', 'tlsProfiles']:
            desired.setdefault(key, {}).update(copy.deepcopy(full.get(key, {})))
        group['platform_data_root_directory'] = '/data'
        infrastructure_sources = ['qa-haproxy', 'qa-bind', 'qa-keepalived', 'qa-vault-consumer', 'qa-clickhouse']
        for name in infrastructure_sources:
            desired['serviceDeployments'][name] = copy.deepcopy(full['serviceDeployments'][name])
        # Shared ClickHouse contributes only its existing endpoint. Its admin
        # credential is not consumed by this test's isolated account provider.
        desired['serviceDeployments']['qa-clickhouse']['configuration'].pop('defaultCredential', None)
        host_vars = self.project / 'inventory/host_vars'
        for host in ['node1', 'node2', 'node3']:
            hp = host_vars / host / 'platform-installer.yml'
            data = json.loads(hp.read_text())
            original = yaml.safe_load((self.full_project / 'inventory/host_vars' / host / 'platform-installer.yml').read_text())
            for name in infrastructure_sources:
                if name in original.get('platform_deployments', {}):
                    data['platform_deployments'][name] = original['platform_deployments'][name]
            hp.write_text(json.dumps(data))
        overrides = desired['applicationLibraryDeployments']['sdku']['applications']['gateway']['overrides']
        overrides['endpoint'] = {'enabled': True, 'endpoint_group': 'qa-shared-endpoint', 'listener': 'http',
                                 'protocol': 'http', 'probe': {'path': '/status', 'expected_status': 200, 'timeout': 10}}
        path.write_text(json.dumps(group))
        self.env['ANSIBLE_COLLECTIONS_PATH'] += ':' + ':'.join(str(ROOT / 'services' / name) for name in ['haproxy', 'bind', 'keepalived'])
        self.play_core('application-libraries-apply.yml')
        statuses = {host: self.probe_status(host) for host in ['node1', 'node2']}
        for host, report in statuses.items():
            for name in ['pkcs12', 'pkcs12Client', 'postgresql', 'redis', 'sentinel', 'clickhouse', 'kafka', 'vaultAgent']:
                self.assertEqual('ok', report['checks'][name]['state'], 'A6_' + host.upper() + '_' + name.upper() + '_STATUS_FAILED')
            self.assertEqual('ok', report['overall'], 'A6_' + host.upper() + '_ALL_CONNECTIONS_REQUIRED')
        self.play_core('application-libraries-verify.yml')
        extra = json.loads(self.extra.read_text())
        if full_haproxy:
            repeated = self.play_core('application-libraries-apply.yml')
            self.assertFalse(re.search(rb'changed=[1-9]', repeated), 'A6_REPEAT_NOT_IDEMPOTENT')
            print('A6_TWO_HOST_ENDPOINT_APPLY_VERIFY_REPEAT_PASS status=node1,node2 all-services=ok')
            extra['platform_haproxy_full_reconcile'] = True
            self.extra.write_text(json.dumps(extra))
            self.play_core('application-libraries-apply.yml')
            self.play_core('application-libraries-verify.yml')
            repeated = self.play_core('application-libraries-apply.yml')
            self.assertFalse(re.search(rb'changed=[1-9]', repeated), 'A6_FULL_RECONCILE_REPEAT_NOT_IDEMPOTENT')
            for host in ['node1', 'node2']:
                self.assertEqual('ok', self.probe_status(host)['overall'])
            print('A6_FULL_HAPROXY_RECONCILE_APPLY_VERIFY_REPEAT_PASS')
        else:
            print('A6_TWO_HOST_ENDPOINT_APPLY_VERIFY_PASS status=node1,node2 all-services=ok')
        extra['platform_contracts_root'] = str(ROOT / 'contracts')
        extra['platform_bind_full_reconcile'] = True
        self.extra.write_text(json.dumps(extra))
        self.play_core('../../services/bind/playbooks/apply.yml')
        self.play_core('application-libraries-verify.yml')
        print('A6_FULL_DNS_RECONCILE_APPLICATION_ENDPOINT_PRESERVED_PASS')
    def launch(self, binary, config):
        # Match the service's private-file umask when Sentinel rewrites its config.
        self.processes.append(subprocess.Popen([binary, str(config)], stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, env=dict(os.environ), umask=0o077))

    def configure_providers(self):
        super().configure_providers()
        sys.path.insert(0, str(ROOT / 'services/redis'))
        from ansible_collections.platform.redis.plugins.module_utils.application_acl import Client, ensure_account
        environment = self.a5_definition['defaults']['environment']
        for alias, port_name in [('redis', 'REDIS_PORT'), ('sentinel', 'SENTINEL_PORT')]:
            for index in range(3):
                directory = self.redis_root / ('redis-' + str(index + 1))
                clients = []
                try:
                    for _ in range(2):
                        clients.append(Client(a5.a4.ADDRESS, int(environment[port_name]) + index,
                            str(directory / 'pki/ca-chain.pem'), str(directory / 'pki/certificate.pem'),
                            str(directory / 'pki/private-key.pem'), timeout=5))
                    password = Path(self.passwords['runtime:' + alias + '-admin']).read_text()
                    if clients[0].command('AUTH', 'default', password) != 'OK':
                        raise RuntimeError('A6_PROVIDER_AUTH_FAILED')
                    account = self.a5_definition['defaults']['accounts'][alias]
                    ensure_account(clients[0], clients[1], str(directory), 'apigateway-sdku',
                        Path(self.passwords[alias + '-app-password']).read_text(), 'a6-fixture-prerequisite',
                        'client' if alias == 'redis' else 'sentinel', account['grants'], 'managed', preflight=True)
                except Exception as error:
                    code = str(error)
                    if not re.fullmatch(r'(?:REDIS_APPLICATION|A6_PROVIDER)_[A-Z_]+', code):
                        code = type(error).__name__
                    raise RuntimeError('A6_' + alias.upper() + '_PREREQUISITE_' + code) from None
                finally:
                    for client in clients:
                        client.close()
        print('A6_ISOLATED_PROVIDER_PREREQUISITES_PASS')


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([
        ApplicationA6QA('test_a6_endpoint_apply_verify_repeat')]))
    sys.exit(not result.wasSuccessful())

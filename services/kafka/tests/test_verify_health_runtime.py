"""Isolated real Ansible/TLS/API Verify with bounded synthetic Kafka CLI replies."""
import copy
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest

import yaml
import qa_pem_tls as pem_fixture

ROOT = Path(__file__).resolve().parents[3]
ROLE = ROOT / 'services/kafka/ansible_collections/platform/kafka/roles/kafka_kraft'


@unittest.skipUnless(shutil.which('ansible-playbook') and shutil.which('openssl'), 'Ansible/OpenSSL required')
class VerifyHealthRuntimeTests(unittest.TestCase):
    def setUp(self):
        fixture = pem_fixture.PemTlsQA(methodName='runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root, self.source = fixture.root, fixture.source
        class Handler(BaseHTTPRequestHandler):
            status = 200
            def do_GET(handler):
                handler.send_response(handler.status)
                handler.end_headers()
                handler.wfile.write(b'[]')
            def log_message(*args):
                pass
        self.handler = Handler
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(self.source / 'certificate.pem'), str(self.source / 'private-key.pem'))
        server.socket = context.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        port = server.server_port
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.script('systemctl', 'printf "ActiveState=active\\nMainPID=42\\n"')
        self.script('kafka-metadata-quorum.sh', 'printf \'LeaderId: 1\\nCurrentVoters: [{"id":1,}]\\n\'')
        self.script('kafka-broker-api-versions.sh',
                    "printf 'localhost:%s (id: 1 rack: null isFenced: false) -> (\\n'" % port)
        member = copy.deepcopy(fixture.member)
        member.update(host='localhost', advertised_host='localhost', node_id=1, roles=['broker', 'controller'],
            data_directory=str(self.root / 'data'), log_directory=str(self.root / 'logs'),
            schema_registry={'http_port': port + 1, 'https_port': port},
            listeners={name: dict(port=port, purpose=purpose, securityProtocol='SSL')
                       for name, purpose in [('CLIENT', 'client'), ('INTERNAL', 'interBroker'), ('CTRL', 'controller')]})
        # Registry health uses its existing consumer CA; no materialization runs.
        registry = self.root / 'registry'
        self.values = dict(fixture.values, platform_kafka_instances=[member],
            platform_kafka_install_directory=str(self.root),
            platform_kafka_schema_registry_config_directory=str(registry),
            platform_kafka_schema_registry_log_directory=str(self.root / 'logs'),
            platform_kafka_schema_registry_enabled=True, platform_kafka_schema_registry_kafka_listener='CLIENT',
            platform_kafka_schema_registry_http_port=port + 1, platform_kafka_schema_registry_https_port=port,
            platform_kafka_verify_only=True, platform_kafka_startup_readiness_retries=0,
            platform_kafka_startup_readiness_delay=0, platform_kafka_schema_registry_readiness_retries=0,
            platform_kafka_schema_registry_readiness_delay=0,
            # Apply-only constraints must not run in health-only Verify.
            platform_kafka_schema_registry_install_directory='/not-an-apply-path',
            platform_kafka_advanced_config={'node.id': 'ignored-by-health'})
        self.member = member

    def script(self, name, body):
        path = self.bin / name
        path.write_text('#!/bin/sh\n' + body + '\n')
        path.chmod(0o700)

    def run_verify(self, values=None):
        play = self.root / 'health.yml'
        # Discover the exact Registry path using the production filter, then
        # seed only synthetic CA bytes before the tested read-only operation.
        prepare = [dict(**{'ansible.builtin.set_fact': {'projection':
            "{{ platform_kafka_instances | platform.core.platform_kafka_schema_registry_projection(true, platform_kafka_schema_registry_kafka_listener, platform_kafka_schema_registry_http_port, platform_kafka_schema_registry_https_port, platform_kafka_schema_registry_name, platform_kafka_schema_registry_config_directory, platform_kafka_schema_registry_log_directory) }}"}}),
            {'ansible.builtin.file': {'path': "{{ projection.instances[0].config_directory }}/pki", 'state': 'directory'}},
            {'ansible.builtin.copy': {'src': str(self.source / 'ca-chain.pem'), 'dest': "{{ projection.instances[0].config_directory }}/pki/ca-chain.pem"}}]
        prepare_path = self.root / 'prepare.yml'
        base = dict(hosts='localhost', connection='local', gather_facts=False,
                    vars=values or self.values)
        environment = dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
            ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections') + ':' + str(ROOT / 'services/kafka'),
            PATH=str(self.bin) + os.pathsep + os.environ['PATH'])
        # Load role defaults for the preparation filter without entering main.
        defaults = yaml.safe_load((ROLE / 'defaults/main.yml').read_text())
        base['vars'] = dict(defaults, **(values or self.values))
        prepare_path.write_text(yaml.safe_dump([dict(base, tasks=prepare)]))
        prepared = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(prepare_path)],
                                  env=environment, capture_output=True, text=True, timeout=90)
        self.assertEqual(0, prepared.returncode, prepared.stdout[-1800:] + prepared.stderr[-1000:])
        play.write_text(yaml.safe_dump([dict(base, tasks=[
            {'ansible.builtin.include_role': {'name': 'platform.kafka.kafka_kraft'}}])]))
        return subprocess.run(['ansible-playbook', '-i', 'localhost,', str(play)],
                              env=environment, capture_output=True, text=True, timeout=120)

    def test_health_repeat_and_single_tls_resolution(self):
        for _ in range(2):
            result = self.run_verify()
            output = result.stdout + result.stderr
            self.assertEqual(0, result.returncode, output[-4000:])
            self.assertIn('changed=0', output)
            self.assertEqual(1, output.count('TASK [platform.kafka.kafka_kraft : Выбор действующих запросов и наборов планов PKI-01]'))
            self.assertNotIn('Проверка ресурсов Schema Registry перед модификацией Kafka', output)

    def test_inactive_node_fails(self):
        self.script('systemctl', 'printf "ActiveState=inactive\\nMainPID=0\\n"')
        result = self.run_verify()
        self.assertNotEqual(0, result.returncode)
        self.assertIn('Kafka member systemd instance is not active', result.stdout)

    def test_wrong_quorum_fails(self):
        self.script('kafka-metadata-quorum.sh', 'printf \'LeaderId: 99\\nCurrentVoters: [{"id":99,}]\\n\'')
        result = self.run_verify()
        self.assertNotEqual(0, result.returncode)
        self.assertIn('Получение состояния кворума контроллеров Kafka', result.stdout)

    def test_missing_broker_fails(self):
        self.script('kafka-broker-api-versions.sh', "printf 'no registered brokers\\n'")
        result = self.run_verify()
        self.assertNotEqual(0, result.returncode)
        self.assertIn('Запрос регистрации брокера Kafka', result.stdout)

    def test_schema_registry_unready_fails(self):
        self.handler.status = 503
        result = self.run_verify()
        self.assertNotEqual(0, result.returncode)
        self.assertIn('Выполнение реального TLS-соединения', result.stdout)
        self.assertIn('503', result.stdout)

    def test_scram_cli_uses_runtime_credentials_and_same_tls_projection(self):
        values = copy.deepcopy(self.values)
        values['platform_kafka_instances'][0]['listeners']['CLIENT']['securityProtocol'] = 'SASL_SSL'
        values['platform_kafka_schema_registry_kafka_listener'] = 'INTERNAL'
        secret = self.root / 'synthetic-password'
        secret.write_text('synthetic-test-password')
        secret.chmod(0o600)
        values['platform_kafka_admin_credential'] = {'passwordSecretRef': 'runtime:qa-admin'}
        values['platform_kafka_secret_files'] = {'runtime:qa-admin': str(secret)}
        self.script('kafka-metadata-quorum.sh',
            'while [ "$1" != --command-config ]; do shift; done\n'
            'grep -q "security.protocol=SASL_SSL" "$2" || exit 9\n'
            'grep -q "synthetic-test-password" "$2" || exit 10\n'
            'printf \'LeaderId: 1\\nCurrentVoters: [{"id":1,}]\\n\'')
        result = self.run_verify(values)
        self.assertEqual(0, result.returncode, result.stdout[-3500:] + result.stderr[-800:])
        self.assertIn('changed=0', result.stdout)
        self.assertNotIn('synthetic-test-password', result.stdout + result.stderr)
        self.assertEqual(1, result.stdout.count(' : Создание временной конфигурации Kafka CLI]'))
        self.assertEqual(1, result.stdout.count(' : Удаление общей временной конфигурации Kafka CLI]'))

    def test_local_member_and_listener_includes_align_across_hosts(self):
        values = copy.deepcopy(self.values)
        members, requests, plans = [], [], []
        for number, host in enumerate(('node1', 'node2', 'node3', 'node2'), 1):
            member = dict(self.member, id='kafka-' + str(number), node_id=number, host=host)
            members.append(member)
            requests.append(dict(id='cert-' + str(number), usages=['serverAuth', 'clientAuth'], consumers=[dict(
                deploymentId=member['deployment_id'], memberId=member['id'], hostId=host, tlsProfileRef='infra')]))
            plans.append(dict(requestId='cert-' + str(number), tlsProfileId='infra', hostId=host,
                              targetDirectory=str(self.source), formats=['PEM']))
        values.update(_platform_kafka_input_instances=members, platform_pki_requests=requests,
                      platform_pki_materialization_plans=plans,
                      _platform_kafka_local_instances="{{ _platform_kafka_instances | selectattr('host', 'equalto', inventory_hostname) | list }}")
        call = copy.deepcopy(yaml.safe_load((ROLE / 'tasks/verify.yml').read_text())[0])
        call['ansible.builtin.include_tasks'] = str(ROLE / 'tasks/verify_member.yml')
        play = self.root / 'parallel.yml'
        play.write_text(yaml.safe_dump([dict(hosts='all', connection='local', gather_facts=False,
            vars=values, tasks=[{'ansible.builtin.include_role': dict(name='platform.kafka.kafka_kraft',
                tasks_from='normalize_members', public=True)}, call])]))
        result = subprocess.run(['ansible-playbook', '-i', 'node1,node2,node3,', str(play)],
            env=dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections') + ':' + str(ROOT / 'services/kafka'),
                     PATH=str(self.bin) + os.pathsep + os.environ['PATH']), capture_output=True, text=True, timeout=120)
        self.assertEqual(0, result.returncode, result.stdout[-4000:] + result.stderr[-1000:])
        self.assertEqual(2, result.stdout.count('TASK [Проверка состояния экземпляра службы Kafka systemd и основного процесса]'))
        self.assertEqual(6, result.stdout.count('TASK [Выполнение реального TLS-соединения с listener Kafka]'))
        for host in ('node1', 'node2', 'node3'):
            self.assertRegex(result.stdout, host + r'\s+: ok=.*changed=0.*failed=0')

    def test_shared_cli_configuration_reused_and_removed_after_failure(self):
        values = copy.deepcopy(self.values)
        values['platform_kafka_instances'][0]['listeners']['CLIENT']['securityProtocol'] = 'SASL_SSL'
        values['platform_kafka_schema_registry_kafka_listener'] = 'INTERNAL'
        secret = self.root / 'synthetic-password'
        secret.write_text('synthetic-test-password')
        values['platform_kafka_admin_credential'] = {'passwordSecretRef': 'runtime:qa-admin'}
        values['platform_kafka_secret_files'] = {'runtime:qa-admin': str(secret)}
        paths = self.root / 'config-paths'
        record = ('while [ "$1" != --command-config ]; do shift; done\n'
                  'test "$(stat -c %a "$2")" = 600 || exit 9\n'
                  'printf "%s\\n" "$2" >> ' + str(paths) + '\n')
        self.script('kafka-metadata-quorum.sh', record + 'printf \'LeaderId: 1\\nCurrentVoters: [{"id":1,}]\\n\'')
        self.script('kafka-broker-api-versions.sh', record + 'exit 7')
        result = self.run_verify(values)
        self.assertNotEqual(0, result.returncode)
        observed = paths.read_text().splitlines()
        self.assertEqual(2, len(observed))
        self.assertEqual(observed[0], observed[1])
        self.assertFalse(Path(observed[0]).exists())
        self.assertNotIn('synthetic-test-password', result.stdout + result.stderr)

    def test_untrusted_tls_fails(self):
        other = self.root / 'wrong-ca.pem'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
            '-subj', '/CN=untrusted', '-keyout', str(self.root / 'wrong.key'), '-out', str(other)],
            check=True, capture_output=True)
        shutil.copyfile(other, self.source / 'ca-chain.pem')
        result = self.run_verify()
        self.assertNotEqual(0, result.returncode)
        self.assertIn('Выполнение реального TLS-соединения', result.stdout)

    def test_wrong_tls_identity_fails(self):
        values = copy.deepcopy(self.values)
        values['platform_kafka_instances'][0]['advertised_host'] = 'wrong.invalid'
        result = self.run_verify(values)
        self.assertNotEqual(0, result.returncode)
        self.assertIn('Выполнение реального TLS-соединения', result.stdout)

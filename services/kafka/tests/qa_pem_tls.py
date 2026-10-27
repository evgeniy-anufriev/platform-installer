"""Real Ansible materialization + shipped JVM TLS engines, isolated synthetic PKI.

No installed service state, real credentials, Kafka storage or external traffic.
Run on RED OS with existing Kafka/JDK/Confluent dependencies; never downloads.
"""
import copy
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[3]
ROLE = ROOT / 'services/kafka/ansible_collections/platform/kafka/roles/kafka_kraft'


class PemTlsQA(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='qa-kafka-pem-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'source'
        self.source.mkdir(mode=0o700)
        self.user = pwd.getpwuid(os.getuid()).pw_name
        self.group = grp.getgrgid(os.getgid()).gr_name
        self.run_command(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                          '-subj', '/CN=synthetic-ca', '-days', '1', '-keyout', str(self.root / 'ca.key'),
                          '-out', str(self.source / 'ca-chain.pem')])
        self.run_command(['openssl', 'req', '-new', '-newkey', 'rsa:2048', '-nodes',
                          '-subj', '/CN=localhost', '-keyout', str(self.source / 'private-key.pem'),
                          '-out', str(self.root / 'leaf.csr')])
        extensions = self.root / 'extensions.cnf'
        extensions.write_text('subjectAltName=DNS:localhost,IP:127.0.0.1\nextendedKeyUsage=serverAuth,clientAuth\n')
        self.run_command(['openssl', 'x509', '-req', '-in', str(self.root / 'leaf.csr'),
                          '-CA', str(self.source / 'ca-chain.pem'), '-CAkey', str(self.root / 'ca.key'),
                          '-CAcreateserial', '-days', '1', '-extfile', str(extensions),
                          '-out', str(self.source / 'certificate.pem')])
        (self.source / 'private-key.pem').chmod(0o600)
        (self.source / 'materialization-fingerprint').write_text('synthetic-fingerprint\n')
        self.member = dict(id='kafka-1', deployment_id='qa-kafka', host='localhost',
                           config_directory=str(self.root / 'broker'), tls_profile='infra')
        self.plan = dict(requestId='qa-cert', tlsProfileId='infra', hostId='localhost',
                         targetDirectory=str(self.source), formats=['PEM'])
        self.values = dict(platform_kafka_user=self.user, platform_kafka_group=self.group,
            platform_kafka_verify_only=False, platform_pki_secret_files={},
            platform_pki_requests=[dict(id='qa-cert', usages=['serverAuth', 'clientAuth'],
                consumers=[dict(deploymentId='qa-kafka', memberId='kafka-1', hostId='localhost', tlsProfileRef='infra')])],
            platform_pki_materialization_plans=[self.plan], kafka_member=self.member,
            kafka_tls_member=self.member, kafka_effective_config={},
            kafka_ssl_listener=dict(name='INTERNAL', securityProtocol='SSL'),
            platform_kafka_schema_registry_user=self.user, platform_kafka_schema_registry_group=self.group,
            _platform_kafka_instances=[self.member],
            registry_instance=dict(id='kafka-1', deployment_id='qa-kafka', tls_profile='infra',
                config_directory=str(self.root / 'registry'), advertised_host='localhost',
                bootstrap_servers='SSL://localhost:19095', security_protocol='SSL', replication_factor=1, http_port=18081, https_port=18082),
            ansible_search_path=[str(ROLE)])
        self.values = dict(yaml.safe_load((ROLE / 'defaults/main.yml').read_text()), **self.values)
        self.assertEqual('PEM', self.values['platform_kafka_store_type'])
        (self.root / 'registry/pki').mkdir(parents=True, mode=0o700)
        (self.root / 'broker').mkdir(mode=0o700)
        self.classpath = ':'.join(['/opt/confluent-8.3.2/share/java/schema-registry/*',
                                  '/opt/confluent-8.3.2/share/java/rest-utils/*', '/opt/kafka/libs/*'])
        self.probe = str(Path(__file__).with_name('PemTlsProbe.java'))

    def run_command(self, argv):
        result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
        self.assertEqual(0, result.returncode, 'Synthetic command failed: ' + argv[0] + '\n' + result.stderr[-1500:].decode(errors='replace'))
        return result

    def include(self, name, **variables):
        return dict(name='Run production ' + name,
                    **{'ansible.builtin.include_role': dict(name='platform.kafka.kafka_kraft', tasks_from=name)},
                    vars=variables)

    def play(self, tasks, values=None, expected=None, unchanged=False):
        if expected:
            tasks = [dict(block=tasks + [dict(**{'ansible.builtin.fail': dict(msg='EXPECTED_FAILURE_NOT_RAISED')})],
                          rescue=[dict(**{'ansible.builtin.assert': dict(
                              that=[json.dumps(expected) + ' in ansible_failed_result.msg'],
                              fail_msg='EXPECTED_FAILURE_CODE_MISMATCH')}, no_log=True)])]
        path = self.root / 'play.yml'
        path.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False,
                                             vars=values or self.values, tasks=tasks)]))
        env = dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
                   ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections') + ':' + str(ROOT / 'services/kafka'))
        runner = subprocess.Popen(['ansible-playbook', '-i', 'localhost,', str(path)], env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            output = runner.communicate(timeout=240)[0].decode(errors='replace')
        except subprocess.TimeoutExpired:
            import signal
            os.killpg(runner.pid, signal.SIGKILL)
            runner.communicate()
            self.fail('ISOLATED_ANSIBLE_TIMEOUT')
        if expected:
            self.assertEqual(0, runner.returncode, output[-1600:])
        else:
            self.assertEqual(0, runner.returncode, output[-3000:])
            if unchanged:
                self.assertRegex(output, r'changed=0\s+')
        return output

    def registry_prefix(self):
        source = yaml.safe_load((ROLE / 'tasks/schema_registry_member.yml').read_text())
        begin = next(i for i, t in enumerate(source) if t['name'] == 'Копирование хранилищ PKI в принадлежащие им каталоги времени выполнения реестра')
        end = next(i for i, t in enumerate(source) if t.get('ansible.builtin.include_tasks') == 'schema_registry_topic.yml')
        tasks = [source[0]] + source[begin:end]
        for task in tasks:
            if 'ansible.builtin.include_tasks' in task:
                task['ansible.builtin.include_tasks'] = str(ROLE / 'tasks' / task['ansible.builtin.include_tasks'])
            if 'ansible.builtin.template' in task:
                # Keep the production template and inputs; only make its lookup root explicit.
                for entry in task['loop']:
                    entry['source'] = str(ROLE / 'templates' / entry['source'])
            if 'ansible.builtin.assert' in task:
                task['ansible.builtin.assert']['that'] = [value.replace("'schema-registry.properties.j2'",
                    repr(str(ROLE / 'templates/schema-registry.properties.j2')))
                    for value in task['ansible.builtin.assert']['that']]
        return tasks

    def apply_tasks(self):
        return [self.include('validate_ssl_listener.yml'),
                dict(name='Render actual broker configuration', **{'ansible.builtin.template':
                     dict(src=str(ROLE / 'templates/server.properties.j2'), dest=str(self.root / 'broker/server.properties'), mode='0600')})] + self.registry_prefix()

    def verify_prefix(self):
        # Direct material-custody helper checks; the service's real health-only
        # Verify is exercised by test_verify_health_runtime with live TLS/API.
        verify = self.include('pem_identity.yml', kafka_pem_source_directory='{{ _platform_kafka_tls_runtime.targetDirectory }}',
            kafka_pem_identity_path='{{ _platform_kafka_tls_runtime.keystorePath }}',
            kafka_pem_ca_path='{{ _platform_kafka_tls_runtime.truststorePath }}',
            kafka_pem_owner=self.user, kafka_pem_group=self.group, kafka_pem_verify_only=True)
        verify['when'] = "platform_kafka_store_type == 'PEM'"
        return [self.include('resolve_tls_runtime.yml'), verify]

    def native(self, mode, path):
        result = self.run_command(['java', '-cp', self.classpath, self.probe, mode, str(path)])
        self.assertIn(b'PEM_TLS_NATIVE_PASS', result.stdout)

    def source_hashes(self):
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.source.iterdir() if p.is_file()}

    def test_pem_apply_repeat_verify_and_native_kafka_registry_tls(self):
        before = self.source_hashes()
        tasks = self.apply_tasks()
        self.play(tasks)
        for path in (self.root / 'broker/server.properties', self.root / 'registry/schema-registry.properties', self.root / 'registry/kafka-client.properties'):
            text = path.read_text()
            self.assertNotIn('.password=', text)
            self.assertNotIn('BEGIN PRIVATE KEY', text)
            self.assertNotIn('PKCS12', text)
        self.native('broker', self.root / 'broker/server.properties')
        self.native('registry', self.root / 'registry/schema-registry.properties')
        self.native('--command-config', self.root / 'registry/kafka-client.properties')
        self.play(tasks, unchanged=True)
        verify = copy.deepcopy(self.values)
        verify['platform_kafka_verify_only'] = True
        pem_vars = dict(kafka_pem_source_directory=str(self.source),
                        kafka_pem_identity_path=str(self.root / 'broker/pki/identity.pem'),
                        kafka_pem_ca_path=str(self.root / 'broker/pki/ca-chain.pem'),
                        kafka_pem_owner=self.user, kafka_pem_group=self.group, kafka_pem_verify_only=True)
        self.play(self.verify_prefix() + self.registry_prefix(), verify, unchanged=True)
        self.assertEqual(before, self.source_hashes())
        config = self.root / 'broker/server.properties'
        previous = config.read_text()
        config.write_text(previous + 'listener.name.internal.ssl.keystore.password=synthetic-invalid\n')
        self.play(self.verify_prefix(), verify, unchanged=True)
        self.assertTrue(config.read_text().endswith('password=synthetic-invalid\n'))
        config.write_text(previous)
        (self.root / 'broker/pki/identity.pem').chmod(0o644)
        self.play([self.include('pem_identity.yml', **pem_vars)], verify, expected='KAFKA_PEM_CONSUMER_DRIFT')
        self.assertEqual(0o644, (self.root / 'broker/pki/identity.pem').stat().st_mode & 0o777)

        # Real generic CLI task loads its ephemeral rendered config with the shipped engine.
        (self.root / 'broker/pki/identity.pem').chmod(0o600)
        cli = copy.deepcopy(self.values)
        cli.update(kafka_cli_connection=dict(securityProtocol='SSL', tls=dict(
            truststoreType='PEM', truststorePath=str(self.root / 'broker/pki/ca-chain.pem'),
            keystorePath=str(self.root / 'broker/pki/identity.pem'), storePasswordSecretRef=None)),
            kafka_cli_command_prefix=['java', '-cp', self.classpath, self.probe], kafka_cli_command_suffix=[])
        cleanup = [dict(**{'ansible.builtin.stat': dict(path='{{ _platform_kafka_cli_command_config.path }}')}, register='cli_after'),
                   dict(**{'ansible.builtin.assert': dict(that=['not cli_after.stat.exists'])})]
        self.play([self.include('run_cli_command.yml')] + cleanup, cli, unchanged=True)

    def test_store_selection_requires_explicit_valid_inputs_and_verify_never_repairs(self):
        for store, code in [('INVALID', 'exact PKI-01'), ('PKCS12', 'explicit PKCS12')]:
            values = copy.deepcopy(self.values)
            values['platform_kafka_store_type'] = store
            self.play([self.include('resolve_tls_runtime.yml')], values, expected=code)
        values = copy.deepcopy(self.values)
        values['platform_pki_requests'][0]['consumers'][0]['deploymentId'] = 'wrong-deployment'
        self.play([self.include('resolve_tls_runtime.yml')], values, expected='exact PKI-01')
        missing = self.root / 'broker/pki/identity.pem'
        self.play([self.include('pem_identity.yml', kafka_pem_source_directory=str(self.source),
                    kafka_pem_identity_path=str(missing), kafka_pem_owner=self.user,
                    kafka_pem_group=self.group, kafka_pem_verify_only=True)], expected='KAFKA_PEM_CONSUMER_DRIFT')
        self.assertFalse(missing.exists())

        self.run_command(['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048',
                          '-out', str(self.source / 'private-key.pem')])
        self.play([self.include('pem_identity.yml', kafka_pem_source_directory=str(self.source),
                    kafka_pem_identity_path=str(missing), kafka_pem_owner=self.user,
                    kafka_pem_group=self.group)], expected='KAFKA_PEM_KEY_CERT_MISMATCH')
        self.assertFalse(missing.exists())

    def test_explicit_pkcs12_apply_repeat_verify_uses_runtime_input(self):
        self.assertTrue(shutil.which('keytool'), 'Existing PKCS12 runtime dependency required')
        password = 'synthetic-store-123'
        self.run_command(['openssl', 'pkcs12', '-export', '-in', str(self.source / 'certificate.pem'),
            '-inkey', str(self.source / 'private-key.pem'), '-certfile', str(self.source / 'ca-chain.pem'),
            '-out', str(self.source / 'keystore.p12'), '-passout', 'pass:' + password])
        self.run_command(['keytool', '-importcert', '-noprompt', '-storetype', 'PKCS12', '-alias', 'synthetic-ca',
            '-file', str(self.source / 'ca-chain.pem'), '-keystore', str(self.source / 'truststore.p12'),
            '-storepass', password])
        secret = self.root / 'store-password'
        secret.write_text(password)
        secret.chmod(0o600)
        values = copy.deepcopy(self.values)
        values['platform_kafka_store_type'] = 'PKCS12'
        values['platform_pki_materialization_plans'][0].update(
            formats=['PEM', 'PKCS12_KEYSTORE', 'PKCS12_TRUSTSTORE'], storePasswordSecretRef='runtime:synthetic-store')
        values['platform_pki_secret_files'] = {'runtime:synthetic-store': str(secret)}
        self.play(self.apply_tasks(), values)
        self.native('broker', self.root / 'broker/server.properties')
        self.native('registry', self.root / 'registry/schema-registry.properties')
        self.play(self.apply_tasks(), values, unchanged=True)
        values['platform_kafka_verify_only'] = True
        self.play(self.registry_prefix(), values, unchanged=True)
        # The new default must not silently accept the old material or repair it.
        self.assertFalse((self.root / 'broker/pki/identity.pem').exists())
        self.play([self.include('pem_identity.yml', kafka_pem_source_directory=str(self.source),
            kafka_pem_identity_path=str(self.root / 'broker/pki/identity.pem'), kafka_pem_owner=self.user,
            kafka_pem_group=self.group, kafka_pem_verify_only=True)], expected='KAFKA_PEM_CONSUMER_DRIFT')
        self.assertFalse((self.root / 'broker/pki/identity.pem').exists())
        # Material helper checks do not migrate existing PKCS12 properties.
        self.play([self.include('pem_identity.yml', kafka_pem_source_directory=str(self.source),
            kafka_pem_identity_path=str(self.root / 'broker/pki/identity.pem'), kafka_pem_owner=self.user,
            kafka_pem_group=self.group)])
        previous = (self.root / 'broker/server.properties').read_bytes()
        self.play(self.verify_prefix(), unchanged=True)
        self.assertEqual(previous, (self.root / 'broker/server.properties').read_bytes())

    def test_library_only_pem_custody_and_cleanup_on_success_and_error(self):
        secret = self.root / 'synthetic-admin'
        secret.write_text('synthetic-admin-password')
        secret.chmod(0o600)
        values = copy.deepcopy(self.values)
        values.update(platform_kafka_application_job=dict(topics=[], accounts=[], adminPasswordRef='runtime:synthetic-admin'),
            application_topic_candidate=dict(address='127.0.0.1', port=19093, tls=True, securityProtocol='SSL', pkiPlans=[self.plan]),
            application_kafka_credentials={'runtime:synthetic-admin': str(secret)},
            platform_application_secret_files={'runtime:synthetic-admin': str(secret)}, platform_kafka_application_phase='verify')
        # This fixture exercises custody/cleanup, not a live Kafka account API.
        cli = self.root / 'cli/bin'
        cli.mkdir(parents=True)
        (cli / 'kafka-configs.sh').write_text('#!/bin/sh\nexit 0\n')
        (cli / 'kafka-configs.sh').chmod(0o700)
        values['application_topic_cli_directory'] = str(cli.parent)
        before = self.source_hashes()
        cleanup = [dict(**{'ansible.builtin.stat': dict(path='{{ application_kafka_private.path }}')}, register='private_after'),
                   dict(**{'ansible.builtin.assert': dict(that=['not private_after.stat.exists'])})]
        for protocol, scope in [('SSL', 'application_topics_scope.yml'), ('SASL_SSL', 'application_accounts_scope.yml')]:
            values['application_topic_candidate']['securityProtocol'] = protocol
            self.play([dict(block=[self.include(scope)] + cleanup, become=True)], values, unchanged=True)
        self.assertEqual(before, self.source_hashes())
        self.run_command(['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048',
                          '-out', str(self.source / 'private-key.pem')])
        failed_source = self.source_hashes()
        for scope in ('application_topics_scope.yml', 'application_accounts_scope.yml'):
            tasks = [dict(block=[self.include(scope)], always=cleanup, become=True)]
            self.play(tasks, values, expected='KAFKA_PEM_KEY_CERT_MISMATCH')
        self.assertEqual(failed_source, self.source_hashes())


if __name__ == '__main__':
    unittest.main()

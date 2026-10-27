"""Production member TLS task sequence: one materialization, multiple listeners."""
import copy
from pathlib import Path
import shutil
import unittest
import yaml

import qa_pem_tls as pem_fixture

ROLE = Path(__file__).resolve().parents[1] / 'ansible_collections/platform/kafka/roles/kafka_kraft'


@unittest.skipUnless(shutil.which('ansible-playbook') and shutil.which('openssl'), 'Ansible/OpenSSL required')
class ApplyTlsOnceRuntimeTests(unittest.TestCase):
    def test_materialization_once_for_three_listeners_repeat_and_explicit_pkcs12(self):
        fixture = pem_fixture.PemTlsQA(methodName='runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        source = yaml.safe_load((ROLE / 'tasks/member.yml').read_text())
        names = {'Подготовка PKI-01 один раз для TLS listeners экземпляра Kafka',
                 'Настройка TLS каждого listener по готовым материалам экземпляра Kafka'}
        tasks = [copy.deepcopy(t) for t in source if t.get('name') in names]
        self.assertEqual(2, len(tasks))
        for task in tasks:
            task['ansible.builtin.include_tasks'] = str(ROLE / 'tasks' / task['ansible.builtin.include_tasks'])
        values = copy.deepcopy(fixture.values)
        values['_platform_kafka_member_named_listeners'] = [
            dict(name='INTERNAL', securityProtocol='SSL'), dict(name='CLIENT', securityProtocol='SASL_SSL'),
            dict(name='CONTROLLER', securityProtocol='SSL')]
        values['kafka_member']['listeners'] = {row['name']: dict(securityProtocol=row['securityProtocol'])
            for row in values['_platform_kafka_member_named_listeners']}
        values['_platform_kafka_scram_enabled'] = True
        assertions = {'ansible.builtin.assert': {'that': [
            "kafka_effective_config['listener.name.internal.ssl.keystore.location'] == kafka_effective_config['listener.name.client.ssl.keystore.location']",
            "kafka_effective_config['listener.name.controller.ssl.truststore.location'] == kafka_effective_config['listener.name.client.ssl.truststore.location']",
            "kafka_effective_config['listener.name.client.ssl.client.auth'] == 'none'",
            "kafka_effective_config['listener.name.internal.ssl.client.auth'] == 'requested'",
        ]}, 'no_log': True}
        for store in ['PEM', 'PKCS12']:
            values['platform_kafka_store_type'] = store
            if store == 'PKCS12':
                for name in ['keystore.p12', 'truststore.p12']:
                    (fixture.source / name).write_bytes(b'synthetic-store-bytes')
                password = fixture.root / 'store-password'
                password.write_text('synthetic-store-password')
                password.chmod(0o600)
                values['platform_pki_materialization_plans'][0].update(
                    formats=['PEM', 'PKCS12_KEYSTORE', 'PKCS12_TRUSTSTORE'], storePasswordSecretRef='runtime:qa-store')
                values['platform_pki_secret_files'] = {'runtime:qa-store': str(password)}
            sequence = [{'ansible.builtin.set_fact': {'kafka_effective_config': {}, 'platform_kafka_member_pki_changed': False}}] + tasks + [assertions]
            output = fixture.play(sequence, values)
            self.assertEqual(1, output.count('Выбор действующих запросов и наборов планов PKI-01'))
            self.assertEqual(1 if store == 'PEM' else 0,
                output.count('Чтение идентификатора PKCS8 и цепочки сертификатов без ведения журнала'))
            self.assertNotIn('synthetic-store-password', output)
            fixture.play(sequence, values, unchanged=True)
            if store == 'PEM':
                # KAS-N01: changed bytes at the same authoritative PKI paths
                # must retain the restart signal, then become idempotent again.
                fixture.run_command(['openssl', 'req', '-new', '-newkey', 'rsa:2048', '-nodes',
                    '-subj', '/CN=localhost', '-keyout', str(fixture.source / 'private-key.pem'),
                    '-out', str(fixture.root / 'rotated.csr')])
                fixture.run_command(['openssl', 'x509', '-req', '-in', str(fixture.root / 'rotated.csr'),
                    '-CA', str(fixture.source / 'ca-chain.pem'), '-CAkey', str(fixture.root / 'ca.key'),
                    '-CAcreateserial', '-days', '1', '-extfile', str(fixture.root / 'extensions.cnf'),
                    '-out', str(fixture.source / 'certificate.pem')])
                changed = {'ansible.builtin.assert': {'that': ['platform_kafka_member_pki_changed | bool']}}
                stable = {'ansible.builtin.assert': {'that': ['not (platform_kafka_member_pki_changed | bool)']}}
                fixture.play(sequence + [changed], values)
                fixture.play(sequence + [stable], values, unchanged=True)

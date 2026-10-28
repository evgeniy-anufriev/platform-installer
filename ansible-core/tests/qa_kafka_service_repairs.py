"""Native task probes in temporary directories; never contact deployed services."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml
from qa_kafka_application_accounts import CLI

ROOT = Path(__file__).resolve().parents[2]
ROLE = ROOT / 'services/kafka/ansible_collections/platform/kafka/roles/kafka_kraft'


class KafkaServiceRepairTests(unittest.TestCase):
    def run_play(self, root, tasks, variables=None, hosts='localhost', success=True):
        play = root / 'play.yml'
        inventory = root / 'hosts.yml'
        inventory.write_text(yaml.safe_dump(dict(all=dict(hosts={h: dict(ansible_connection='local')
            for h in (['h1', 'h2', 'h3'] if hosts == 'all' else ['localhost', 'h1', 'h2'])}))))
        play.write_text(yaml.safe_dump([dict(hosts=hosts, gather_facts=False,
            vars={'platform_kafka_script_extension': '.sh', **(variables or {})}, tasks=tasks)], sort_keys=False))
        result = subprocess.run(['ansible-playbook', '-i', str(inventory), str(play)],
            env=dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg')),
            capture_output=True, text=True, timeout=180)
        self.assertEqual(success, result.returncode == 0, (result.stdout + result.stderr)[-2500:])
        return result.stdout + result.stderr

    def test_preseeded_admin_reads_inventory_before_login(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            role = root / 'roles/qa'
            shutil.copytree(ROLE, role)
            (role / 'tasks/resolve_cli_connection.yml').write_text(yaml.safe_dump([
                {'ansible.builtin.set_fact': dict(_platform_kafka_cli_connection=dict(bootstrapHost='127.0.0.1', bootstrapPort=9094),
                    _platform_kafka_tls_runtime_plans=[dict(targetDirectory='/qa', storePasswordSecretRef='runtime:admin')])}]))
            (role / 'tasks/authorization_principal.yml').write_text(yaml.safe_dump([
                {'ansible.builtin.assert': dict(that=[
                    'application_kafka_login.rc | default(application_kafka_password_probe.rc | default(1)) == 0'])}]))
            (root / 'bin').mkdir()
            for name in ['kafka-configs.sh', 'kafka-acls.sh', 'kafka-broker-api-versions.sh']:
                file = root / 'bin' / name
                file.write_text(CLI)
                file.chmod(0o700)
            secret = root / 'password'
            secret.write_text('qa-good')
            secret.chmod(0o600)
            member = dict(host='localhost', listener_endpoints=[dict(purpose='client', security_protocol='SASL_SSL',
                bootstrap_host='127.0.0.1', bootstrap_port=9096)])
            variables = dict(_platform_kafka_broker_instances=[member], _platform_kafka_internal_principals=[],
                platform_kafka_install_directory=str(root),
                platform_kafka_verify_only=False, platform_kafka_store_type='PKCS12',
                platform_kafka_application_timeout_ms=1000, platform_kafka_admin_credential=dict(passwordSecretRef='runtime:admin'),
                platform_kafka_secret_files={'runtime:admin': str(secret)}, platform_pki_secret_files={'runtime:admin': str(secret)})
            for metadata_fail in [False, True]:
                users = {'admin': ['SCRAM-SHA-512', 'qa-good']}
                (root / 'state.json').write_text(json.dumps(dict(users=users, metadata_fail=metadata_fail)))
                (root / 'calls.jsonl').write_text('')
                self.run_play(root, [{'ansible.builtin.include_role': dict(name='qa', tasks_from='authorization_setup')}],
                              variables, success=not metadata_fail)
                calls = [json.loads(line) for line in (root / 'calls.jsonl').read_text().splitlines()]
                self.assertEqual('kafka-configs.sh', calls[0][0])
                self.assertIn('--describe', calls[0][1])
                self.assertEqual(1, sum('--describe' in args for _, args in calls))
                self.assertEqual(0, sum('--alter' in args for _, args in calls))
                self.assertEqual(0 if metadata_fail else 1, sum(name == 'kafka-broker-api-versions.sh' for name, _ in calls))
                self.assertEqual(0 if metadata_fail else 1, sum(name == 'kafka-acls.sh' and '--list' in args for name, args in calls))

    def test_cluster_guard_ignores_data_all_but_rejects_cluster_alter(self):
        tasks = yaml.safe_load((ROLE / 'tasks/authorization_security_guard.yml').read_text())[1:]
        data = 'Current ACLs for resource `ResourcePattern(resourceType=TOPIC, name=*, patternType=LITERAL)`:\n  (principal=User:ANONYMOUS, host=*, operation=ALL, permissionType=ALLOW)\n'
        cluster = 'Current ACLs for resource `ResourcePattern(resourceType=CLUSTER, name=kafka-cluster, patternType=LITERAL)`:\n  (principal=User:ANONYMOUS, host=*, operation=%s, permissionType=ALLOW)\n'
        with tempfile.TemporaryDirectory() as directory:
            for operation in ['DESCRIBE', 'ALTER', 'ALL']:
                self.run_play(Path(directory), tasks, dict(kafka_authorization_cluster_acls=dict(
                    rc=0, stdout=data + cluster % operation)), success=operation == 'DESCRIBE')

    def test_listener_key_reaches_real_include_without_embedded_name(self):
        task = yaml.safe_load((ROLE / 'tasks/verify_member.yml').read_text())[-1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'verify_ssl_listener.yml').write_text(yaml.safe_dump([{'ansible.builtin.assert': dict(
                that=['kafka_ssl_listener.name == "SASL"', 'kafka_ssl_listener.port == 9096'])}]))
            task['ansible.builtin.include_tasks'] = str(root / 'verify_ssl_listener.yml')
            self.run_play(root, [task], dict(kafka_member=dict(id='m1', roles=['broker'],
                listeners=dict(SASL=dict(port=9096, purpose='client', securityProtocol='SASL_SSL')))))

    def test_verify_selects_one_controller_even_when_local_member_differs(self):
        task = yaml.safe_load((ROLE / 'tasks/verify.yml').read_text())[1]
        with tempfile.TemporaryDirectory() as directory:
            self.run_play(Path(directory), [task, {'ansible.builtin.assert': dict(
                that=['kafka_quorum_diagnostic_member.id == "c1"'])}], dict(
                _platform_kafka_scram_enabled=False,
                _platform_kafka_controller_instances=[dict(id='c1', host='node1'), dict(id='c2', host='node2')],
                _platform_kafka_local_controller_instances=[dict(id='c2', host='node2')]))

    def test_broker_headers_use_the_selected_sasl_listener(self):
        task = yaml.safe_load((ROLE / 'tasks/verify.yml').read_text())[-1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            variables = dict(_platform_kafka_verify_broker=dict(host='localhost'),
                _platform_kafka_cli_connection=dict(listenerName='SASL', securityProtocol='SASL_SSL'),
                _platform_kafka_broker_instances=[dict(id='m1', node_id=1, client_endpoint=dict(
                    bootstrap_host='127.0.0.1', bootstrap_port=9094), listener_endpoints=[
                        dict(name='SASL', security_protocol='SASL_SSL', bootstrap_host='127.0.0.1', bootstrap_port=9096)])])
            for port in [9096, 9094]:
                variables['_platform_kafka_unfenced_broker_headers'] = [
                    '127.0.0.1:%s (id: 1 rack: null isFenced: false) -> (' % port]
                self.run_play(root, [task], variables, success=port == 9096)

    def test_quorum_uses_admin_server_with_scram_and_controller_without_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copy(ROLE / 'tasks/verify_quorum.yml', root)
            (root / 'resolve_cli_connection.yml').write_text(yaml.safe_dump([
                {'ansible.builtin.assert': dict(that=[
                    'kafka_cli_purpose == ("admin" if _platform_kafka_scram_enabled else "controller")'])},
                {'ansible.builtin.set_fact': dict(_platform_kafka_cli_connection=dict(
                    securityProtocol='PLAINTEXT', bootstrapHost='127.0.0.1', bootstrapPort=9096))}]))
            shutil.copy(ROLE / 'tasks/run_cli_command.yml', root)
            (root / 'bin').mkdir()
            probe = root / 'bin/kafka-metadata-quorum.sh'
            probe.write_text('''#!/usr/bin/python3
import os, sys
expected='--bootstrap-server' if os.environ['QA_SCRAM']=='True' else '--bootstrap-controller'
assert expected in sys.argv
print('LeaderId: 1')
print('CurrentVoters: [{"id": 1,}, {"id": 2,}, {"id": 3,}]')
''')
            probe.chmod(0o700)
            for scram in [True, False]:
                self.run_play(root, [{'ansible.builtin.include_tasks': dict(file=str(root / 'verify_quorum.yml'),
                    apply=dict(environment=dict(QA_SCRAM=str(scram))))}], dict(_platform_kafka_scram_enabled=scram,
                    kafka_quorum_diagnostic_member={}, platform_kafka_install_directory=str(root),
                    platform_kafka_name='qa', platform_kafka_startup_readiness_retries=1,
                    platform_kafka_startup_readiness_delay=0,
                    _platform_kafka_controller_instances=[dict(id='m'+str(i), node_id=i) for i in [1, 2, 3]]))

    def test_sasl_cli_uses_private_runtime_file_and_always_cleans_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            secret = root / 'runtime-password'
            secret.write_text('qa-only-scram')
            secret.chmod(0o600)
            probe = root / 'probe.py'
            probe.write_text('''#!/usr/bin/python3
import pathlib, sys
p=pathlib.Path(sys.argv[sys.argv.index('--command-config')+1])
s=p.read_text()
assert p.stat().st_mode & 0o777 == 0o600
assert 'security.protocol=SASL_SSL' in s and 'sasl.mechanism=SCRAM-SHA-512' in s
assert '"admin"' in s and 'qa-only-scram' in s
assert 'ssl.keystore.' not in s and 'ssl.truststore.password' not in s
pathlib.Path(sys.argv[1]).write_text(str(p))
sys.exit(int(sys.argv[2]))
''')
            probe.chmod(0o700)
            for rc in [0, 1]:
                variables = dict(platform_kafka_name='qa', platform_kafka_startup_readiness_retries=1,
                    platform_kafka_startup_readiness_delay=0, platform_kafka_secret_files={'runtime:admin': str(secret)},
                    kafka_cli_connection=dict(securityProtocol='SASL_SSL', adminPasswordRef='runtime:admin',
                        tls=dict(truststorePath='/qa/ca.pem', truststoreType='PEM')),
                    kafka_cli_command_prefix=[str(probe), str(root / 'config-path'), str(rc)], kafka_cli_command_suffix=[])
                output = self.run_play(root, [
                    {'ansible.builtin.include_tasks': str(ROLE / 'tasks/run_cli_command.yml')},
                    {'ansible.builtin.assert': dict(that=['platform_kafka_cli_command_result.rc == ' + str(rc)])}], variables)
                self.assertNotIn('qa-only-scram', output)
                self.assertFalse(Path((root / 'config-path').read_text()).exists())


if __name__ == '__main__':
    unittest.main()

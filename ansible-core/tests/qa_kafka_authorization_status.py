"""Native encrypted JAAS role proof; no deployed Kafka process is changed."""
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]
ROLE = ROOT / 'services/kafka/ansible_collections/platform/kafka/roles/kafka_kraft'

@unittest.skipUnless(os.geteuid() == 0 and shutil.which('ansible-playbook') and shutil.which('systemd-creds'), 'root native Ansible/systemd-creds required')
class KafkaEncryptedCredentialsTests(unittest.TestCase):
    def test_encrypt_repeat_change_and_corrupt_recovery(self):
        private = Path.home() / '.runtime/secrets'
        private.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.TemporaryDirectory(prefix='kafka-credentials-qa-', dir=private) as directory:
            root = Path(directory)
            secret = root / 'admin-input'
            secret.write_text(secrets.token_hex(24))
            secret.chmod(0o600)
            config = root / 'member'
            config.mkdir(mode=0o700)
            values = dict(kafka_member=dict(config_directory=str(config)),
                platform_kafka_admin_credential=dict(passwordSecretRef='runtime:admin'),
                platform_kafka_secret_files={'runtime:admin': str(secret)},
                _platform_kafka_member_named_listeners=[dict(name='QUORUM',purpose='controller',securityProtocol='SASL_SSL')])
            play = root / 'play.yml'
            task = {'ansible.builtin.include_role': dict(name='platform.kafka.kafka_kraft', tasks_from='controller_credentials')}
            def run(changed):
                tasks = [task, {'ansible.builtin.assert': dict(that=['platform_kafka_member_credentials_changed | bool == ' + str(changed).lower()])}]
                play.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False, vars=values, tasks=tasks)]))
                result = subprocess.run(['ansible-playbook','-i','localhost,',str(play)], capture_output=True,text=True,
                    env=dict(os.environ, ANSIBLE_CONFIG=str(ROOT/'ansible-core/ansible.cfg'),
                        ANSIBLE_COLLECTIONS_PATH=str(ROOT/'services/kafka/ansible_collections')+':'+str(ROOT/'ansible-core/collections')),timeout=150)
                self.assertEqual(0,result.returncode,(result.stdout+result.stderr)[-2400:])
            run(True)
            encrypted = config / 'controller-jaas.cred'
            before = encrypted.read_bytes()
            self.assertNotIn(secret.read_bytes(), before)
            self.assertEqual(0o400,encrypted.stat().st_mode & 0o777)
            run(False)
            self.assertEqual(before,encrypted.read_bytes())
            secret.write_text(secrets.token_hex(24) + ',"\\Ж')
            run(True)
            self.assertNotEqual(before,encrypted.read_bytes())
            decoded = subprocess.run(['systemd-creds','decrypt','--name=kafka-jaas',str(encrypted),'-'],capture_output=True,check=True).stdout
            self.assertIn(b'quorum.KafkaServer',decoded)
            self.assertIn(json.dumps(secret.read_text(),ensure_ascii=False).encode(),decoded)
            encrypted.write_bytes(b'corrupt encrypted content')
            run(True)
            run(False)
            self.assertEqual(['controller-jaas.cred'],[p.name for p in config.iterdir()])

if __name__ == '__main__':
    unittest.main()
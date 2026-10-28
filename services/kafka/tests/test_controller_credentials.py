"""Native formatter input and controller configuration contract."""
import base64
import hashlib
import importlib.util
from pathlib import Path
import re
import secrets
import unittest
import yaml

SERVICE = Path(__file__).resolve().parents[1]
ROLE = SERVICE / 'ansible_collections/platform/kafka/roles/kafka_kraft'
spec = importlib.util.spec_from_file_location('storage_credentials', SERVICE / 'ansible_collections/platform/kafka/plugins/filter/storage_credentials.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ControllerCredentialsTests(unittest.TestCase):
    def test_initial_scram_supports_arbitrary_password_without_exposing_it(self):
        password = secrets.token_hex(20) + ',"\\Ж\n'
        salt = bytes(range(16))
        entry = module.storage_scram(password, salt)
        self.assertNotIn(password, entry)
        self.assertNotIn('password=', entry.replace('saltedpassword=', ''))
        encoded = re.search(r'saltedpassword=([^\]]+)',entry).group(1)
        self.assertEqual(hashlib.pbkdf2_hmac('sha512',password.encode(),salt,8192),base64.b64decode(encoded))

    def test_empty_runtime_password_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'KAFKA_ADMIN_RUNTIME_SECRET_INVALID'):
            module.storage_scram('')

    def test_controller_baseline_uses_plain_over_tls_and_only_admin_superuser(self):
        defaults = yaml.safe_load((ROLE/'defaults/main.yml').read_text())
        self.assertEqual('SASL_SSL',defaults['platform_kafka_listeners']['CONTROLLER']['securityProtocol'])
        member = (ROLE/'tasks/member.yml').read_text()
        self.assertIn("'sasl.mechanism.controller.protocol': 'PLAIN'",member)
        self.assertIn("'super.users': 'User:admin'",member)
        self.assertNotIn('_platform_kafka_authorization_bootstrap', member)
        unit = (ROLE/'templates/kafka.service.j2').read_text()
        self.assertIn('LoadCredentialEncrypted=kafka-jaas:',unit)
        self.assertIn('java.security.auth.login.config=%d/kafka-jaas',unit)
        self.assertNotIn('password',unit.lower())

"""Native shared SCRAM/ACL discovery; no live Kafka or container access."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
CLI = r'''#!/usr/bin/python3
import json, pathlib, re, sys
root = pathlib.Path(__file__).resolve().parents[1]
state = json.loads((root / 'state.json').read_text())
args, kind = sys.argv[1:], pathlib.Path(__file__).name
with (root / 'calls.jsonl').open('a') as stream:
    stream.write(json.dumps([kind, args]) + '\n')
if kind == 'kafka-configs.sh':
    if '--alter' in args:
        name = args[args.index('--entity-name') + 1]
        state['users'][name] = ['SCRAM-SHA-512', 'qa-good']
        (root / 'state.json').write_text(json.dumps(state))
    else:
        if state.get('metadata_fail'):
            sys.exit(1)
        for name, (mechanism, password) in state['users'].items():
            print("SCRAM credential configs for user-principal '%s' are %s=iterations=8192" % (name, mechanism))
        if state.get('metadata_error'):
            print("Error retrieving SCRAM credential configs for user-principal 'other': ExecutionException")
elif kind == 'kafka-broker-api-versions.sh':
    if state.get('login_transport_fail'):
        sys.exit(1)
    content = pathlib.Path(args[args.index('--command-config') + 1]).read_text()
    # Dummy identities/passwords contain no properties escapes. Avoid interpreting
    # escaped key separators or mistaking the administrative JAAS line for the
    # application's later SASL override.
    name = next((name for name in state['users'] if '"' + name + '"' in content), None)
    if name is None or '"' + state['users'][name][1] + '"' not in content:
        print('SaslAuthenticationException: Authentication failed due to invalid credentials', file=sys.stderr)
        sys.exit(1)
elif '--list' in args:
    if state.get('acl_fail'):
        sys.exit(1)
    print(state.get('acl', ''))
'''


class KafkaApplicationAccountsTests(unittest.TestCase):
    def probe(self, users, names, *, mode='existing', phase='apply', acl_names=None,
              success=True, client_passwords=None, **errors):
        with tempfile.TemporaryDirectory(prefix='qa-kafka-accounts-') as directory:
            root = Path(directory)
            (root / 'bin').mkdir()
            for name in ['kafka-configs.sh', 'kafka-acls.sh', 'kafka-broker-api-versions.sh']:
                path = root / 'bin' / name
                path.write_text(CLI)
                path.chmod(0o700)
            secret = root / 'password'
            secret.write_text('qa-good')
            credential_files = {}
            for index, name in enumerate(names):
                password_file = root / ('password-' + str(index))
                password_file.write_text((client_passwords or {}).get(name, 'qa-good'))
                credential_files[name] = str(password_file)
            acl = 'Current ACLs for resource `ResourcePattern(resourceType=TOPIC, name=qa.topic, patternType=LITERAL)`:\n'
            acl += '\n'.join('  (principal=User:%s, host=*, operation=READ, permissionType=ALLOW)' % name
                             for name in (names if acl_names is None else acl_names))
            (root / 'state.json').write_text(json.dumps(dict(users=users, acl=acl, **errors)))
            candidate = dict(address='127.0.0.1', port='9096', tls=False, securityProtocol='SASL_SSL')
            variables = dict(platform_kafka_application_phase=phase, platform_kafka_store_type='PKCS12',
                platform_kafka_application_timeout_ms=1000, application_topic_cli_directory=str(root),
                application_topic_candidate=candidate, application_kafka_credentials=credential_files,
                platform_application_secret_files=dict(admin=str(secret)),
                platform_kafka_application_job=dict(providerId='qa', adminPasswordRef='admin', accounts=[dict(
                    accountId=name, name=name, mode=mode, passwordRef=name, candidates=[candidate],
                    grants=[dict(resourceType='topic', name='qa.topic', patternType='literal', operations=['Read'])])
                    for name in names]))
            play = root / 'probe.yml'
            play.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False,
                vars=variables, tasks=[{'ansible.builtin.include_role': dict(name='platform.kafka.kafka_kraft',
                    tasks_from='application_accounts_scope')}])], sort_keys=False))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(play)],
                env=dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg')),
                capture_output=True, text=True, timeout=60)
            self.assertEqual(success, result.returncode == 0, (result.stdout + result.stderr)[-2200:])
            return [json.loads(line) for line in (root / 'calls.jsonl').read_text().splitlines()]

    def test_two_users_share_both_inventory_commands_and_authenticate_separately(self):
        calls = self.probe({'qa.one': ['SCRAM-SHA-512', 'qa-good'], 'qa-two': ['SCRAM-SHA-512', 'qa-good']},
                           ['qa.one', 'qa-two'])
        self.assertEqual(4, len(calls))
        metadata = next(args for kind, args in calls if kind == 'kafka-configs.sh')
        acl = next(args for kind, args in calls if kind == 'kafka-acls.sh')
        self.assertNotIn('--entity-name', metadata)
        self.assertNotIn('--principal', acl)
        self.assertEqual(2, sum(kind == 'kafka-broker-api-versions.sh' for kind, _ in calls))

    def test_similar_principal_cannot_supply_missing_scram_metadata(self):
        calls = self.probe({'qaXone': ['SCRAM-SHA-512', 'qa-good']}, ['qa.one'], success=False)
        self.assertEqual(2, len(calls))

    def test_two_users_keep_distinct_password_files_inside_one_batch(self):
        passwords = {'qa.one': 'qa-alpha', 'qa-two': 'qa-beta'}
        calls = self.probe({name: ['SCRAM-SHA-512', password] for name, password in passwords.items()},
                           list(passwords), client_passwords=passwords)
        self.assertEqual(4, len(calls))

    def test_other_principal_acl_cannot_supply_missing_existing_grant(self):
        calls = self.probe({'qa.one': ['SCRAM-SHA-512', 'qa-good']}, ['qa.one'],
                           acl_names=['qaXone'], success=False)
        self.assertFalse(any('--add' in args for _, args in calls))

    def test_new_managed_user_is_created_authenticated_and_granted(self):
        calls = self.probe({}, ['qa.one'], mode='managed', acl_names=[])
        self.assertEqual(5, len(calls))
        self.assertEqual(1, sum('--alter' in args for _, args in calls))
        self.assertEqual(1, sum('--add' in args for _, args in calls))

    def test_managed_application_password_is_reconciled_before_grants(self):
        calls = self.probe({'qa.one': ['SCRAM-SHA-512', 'qa-wrong']}, ['qa.one'],
                           mode='managed', acl_names=[])
        self.assertEqual(1, sum('--alter' in args for _, args in calls))
        self.assertEqual(1, sum('--add' in args for _, args in calls))

    def test_transport_error_stops_before_any_password_or_acl_mutation(self):
        calls = self.probe({'qa.one': ['SCRAM-SHA-512', 'qa-wrong']}, ['qa.one'],
                           mode='managed', acl_names=[], success=False, login_transport_fail=True)
        self.assertEqual(3, len(calls))
        self.assertFalse(any('--add' in args or '--alter' in args for _, args in calls))

    def test_existing_application_password_and_infrastructure_admin_are_not_reset(self):
        for name, mode in [('qa.one', 'existing'), ('admin', 'managed')]:
            with self.subTest(name=name):
                calls = self.probe({name: ['SCRAM-SHA-512', 'qa-wrong']}, [name],
                                   mode=mode, acl_names=[], success=False)
                self.assertFalse(any('--alter' in args or '--add' in args for _, args in calls))

    def test_partial_or_failed_metadata_batch_never_creates_credentials(self):
        for error in ['metadata_fail', 'metadata_error']:
            with self.subTest(error=error):
                calls = self.probe({}, ['qa.one'], mode='managed', success=False, **{error: True})
                self.assertEqual(1, len(calls))

    def test_failed_acl_inventory_prevents_account_mutations(self):
        calls = self.probe({}, ['qa.one'], mode='managed', success=False, acl_fail=True)
        self.assertEqual(2, len(calls))

    def test_verify_reads_fresh_and_never_creates_a_missing_user(self):
        calls = self.probe({}, ['qa.one'], mode='managed', phase='verify', success=False)
        self.assertEqual(2, len(calls))


if __name__ == '__main__':
    unittest.main()

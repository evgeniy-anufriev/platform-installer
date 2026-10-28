"""Real Ansible ACL invocation with a stateful, isolated CLI substitute."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
TASKS = ROOT / 'services/kafka/ansible_collections/platform/kafka/roles/kafka_kraft/tasks'
CLI = r'''#!/usr/bin/python3
import json, pathlib, re, sys
root = pathlib.Path(__file__).resolve().parents[1]
state = json.loads((root / 'state.json').read_text())
args = sys.argv[1:]
with (root / 'calls.jsonl').open('a') as stream:
    stream.write(json.dumps(args) + '\n')
if '--add' in args:
    if state.get('fail_add'):
        sys.exit(1)
    principal = args[args.index('--allow-principal') + 1]
    host = args[args.index('--allow-host') + 1]
    pattern = args[args.index('--resource-pattern-type') + 1].upper()
    operations = [re.sub(r'([a-z])([A-Z])', r'\1_\2', args[i+1]).upper()
                  for i, value in enumerate(args) if value == '--operation']
    for i, value in enumerate(args):
        if value in ['--topic', '--group', '--transactional-id', '--cluster']:
            kind = value[2:].replace('-', '_').upper()
            name = 'kafka-cluster' if value == '--cluster' else args[i+1]
            for operation in operations:
                binding = [kind, name, pattern, principal, host, operation, 'ALLOW']
                if binding not in state['bindings']:
                    state['bindings'].append(binding)
            if state.get('fail_partial'):
                state['fail_partial'] = False
                (root / 'state.json').write_text(json.dumps(state))
                sys.exit(1)
    (root / 'state.json').write_text(json.dumps(state))
else:
    resources = {}
    for kind, name, pattern, principal, host, operation, permission in state['bindings']:
        resources.setdefault((kind, name, pattern), []).append(
            '  (principal=%s, host=%s, operation=%s, permissionType=%s)' %
            (principal, host, operation, permission))
    for (kind, name, pattern), bindings in resources.items():
        print('Current ACLs for resource `ResourcePattern(resourceType=%s, name=%s, patternType=%s)`:' %
              (kind, name, pattern))
        print('\n'.join(bindings))
'''


def grant(name, operations=('Read',), kind='topic', pattern='literal'):
    return dict(name=name, operations=list(operations), resourceType=kind, patternType=pattern)


class KafkaAclWritesTests(unittest.TestCase):
    def probe(self, accounts, bindings=(), *, phase='apply', repeat=False, fail=False, direct=False,
              success=True, direct_after=None, recover=False, compatibility=False):
        with tempfile.TemporaryDirectory(prefix='qa-kafka-acl-writes-') as directory:
            root = Path(directory)
            (root / 'bin').mkdir()
            cli = root / 'bin/kafka-acls.sh'
            cli.write_text(CLI)
            cli.chmod(0o700)
            (root / 'state.json').write_text(json.dumps(dict(bindings=list(bindings), fail_add=fail, fail_partial=recover)))
            steps = [{'ansible.builtin.include_tasks': str(TASKS / 'application_acls_read_all.yml')}]
            if compatibility:
                steps.append({'ansible.builtin.include_tasks': str(TASKS / 'authorization_principal.yml'),
                              'loop': ['ANONYMOUS', 'CN=broker'],
                              'loop_control': dict(loop_var='kafka_authorization_principal'),
                              'vars': dict(kafka_authorization_cluster_operations=['Describe', 'IdempotentWrite'])})
            elif direct:
                steps.append({'ansible.builtin.include_tasks': str(TASKS / 'application_acl.yml'),
                              'vars': dict(application_kafka_account=accounts[0],
                                           application_kafka_grant=accounts[0]['grants'][0])})
            else:
                steps.append({'ansible.builtin.include_tasks': str(TASKS / 'application_acls.yml'),
                              'loop': accounts, 'loop_control': dict(loop_var='application_kafka_account')})
            if direct_after:
                steps.append({'ansible.builtin.include_tasks': str(TASKS / 'application_acl.yml'),
                              'vars': dict(application_kafka_account=direct_after,
                                           application_kafka_grant=direct_after['grants'][0])})
            variables = dict(application_topic_cli_directory=str(root),
                             application_topic_candidate=dict(address='127.0.0.1', port='1'),
                             application_kafka_private=dict(path=str(root)),
                             platform_kafka_application_phase=phase)
            play = root / 'probe.yml'
            play.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False,
                                                 vars=variables, tasks=steps)], sort_keys=False))
            for iteration in range(2 if repeat or recover else 1):
                result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(play)],
                                        env=dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg')),
                                        capture_output=True, text=True, timeout=60)
                expected_success = iteration > 0 if recover else success
                self.assertEqual(expected_success, result.returncode == 0, (result.stdout + result.stderr)[-2000:])
                if repeat and iteration:
                    self.assertIn('changed=0', result.stdout)
                if not expected_success:
                    self.assertIn('APPLICATION_KAFKA_ACL_', result.stdout)
            return ([json.loads(line) for line in (root / 'calls.jsonl').read_text().splitlines()],
                    json.loads((root / 'state.json').read_text())['bindings'])

    def test_compatible_topics_share_one_write_and_repeat_changes_nothing(self):
        accounts = [dict(name='qa', mode='managed', grants=[grant('one', ['Read', 'Describe']),
                                                          grant('two', ['Read', 'Describe'])])]
        calls, bindings = self.probe(accounts, repeat=True)
        writes = [a for a in calls if '--add' in a]
        self.assertEqual(1, len(writes))
        self.assertEqual(2, writes[0].count('--topic'))
        self.assertEqual({('TOPIC', name, 'LITERAL', 'User:qa', '*', operation, 'ALLOW')
                          for name in ['one', 'two'] for operation in ['READ', 'DESCRIBE']},
                         {tuple(b) for b in bindings})

    def test_compatible_types_share_a_write_but_patterns_and_deltas_do_not_cross(self):
        grants = [grant('one'), grant('two', ['Write']), grant('one', pattern='prefixed'),
                  grant('group', kind='group'), grant('kafka-cluster', ['IdempotentWrite'], kind='cluster')]
        calls, bindings = self.probe([dict(name='qa', mode='managed', grants=grants)])
        self.assertEqual(4, sum('--add' in a for a in calls))
        self.assertEqual({('TOPIC', 'one', 'LITERAL', 'READ'), ('TOPIC', 'two', 'LITERAL', 'WRITE'),
                          ('TOPIC', 'one', 'PREFIXED', 'READ'), ('GROUP', 'group', 'LITERAL', 'READ'),
                          ('CLUSTER', 'kafka-cluster', 'LITERAL', 'IDEMPOTENT_WRITE')},
                         {(b[0], b[1], b[2], b[5]) for b in bindings})

    def test_only_missing_operations_are_grouped(self):
        existing = [['TOPIC', 'one', 'LITERAL', 'User:qa', '*', 'READ', 'ALLOW']]
        calls, bindings = self.probe([dict(name='qa', mode='managed', grants=[
            grant('one', ['Read', 'Describe']), grant('two', ['Read', 'Describe'])])], existing)
        self.assertEqual(2, sum('--add' in a for a in calls))
        self.assertEqual(4, len(bindings))
        write_one = next(a for a in calls if '--add' in a and 'one' in a)
        self.assertNotIn('Read', write_one)

    def test_group_queue_is_reset_between_principals(self):
        calls, bindings = self.probe([dict(name=name, mode='managed', grants=[grant(name)])
                                      for name in ['first', 'second']],
                                     direct_after=dict(name='third', mode='managed', grants=[grant('third')]))
        self.assertEqual(3, sum('--add' in a for a in calls))
        self.assertEqual({(name, 'User:' + name) for name in ['first', 'second', 'third']},
                         {(b[1], b[3]) for b in bindings})

    def test_operation_order_and_duplicate_resources_share_a_group(self):
        calls, bindings = self.probe([dict(name='qa', mode='managed', grants=[
            grant('one', ['Read', 'Describe']), grant('one', ['Describe', 'Read']),
            grant('One', ['Describe', 'Read'])])])
        writes = [a for a in calls if '--add' in a]
        self.assertEqual(1, len(writes))
        self.assertEqual(2, writes[0].count('--topic'))
        self.assertEqual(4, len(bindings))

    def test_partial_write_stops_following_groups_and_retry_uses_fresh_inventory(self):
        calls, bindings = self.probe([dict(name='qa', mode='managed', grants=[
            grant('one'), grant('two'), grant('group', kind='group')])], recover=True)
        writes = [a for a in calls if '--add' in a]
        self.assertEqual(2, len(writes))
        self.assertEqual(2, writes[0].count('--topic'))
        second_read = [index for index, args in enumerate(calls) if '--list' in args][1]
        self.assertEqual(1, sum('--add' in args for args in calls[:second_read]))
        self.assertNotIn('one', writes[1])
        self.assertIn('two', writes[1])
        self.assertEqual({('TOPIC', 'one'), ('TOPIC', 'two'), ('GROUP', 'group')},
                         {(b[0], b[1]) for b in bindings})

    def test_existing_and_verify_never_write(self):
        existing = [['TOPIC', 'one', 'LITERAL', 'User:qa', '*', 'READ', 'ALLOW']]
        for mode, phase in [('existing', 'apply'), ('managed', 'verify')]:
            for bindings in [existing, []]:
                with self.subTest(mode=mode, phase=phase, present=bool(bindings)):
                    calls, _ = self.probe([dict(name='qa', mode=mode, grants=[grant('one')])], bindings,
                                          phase=phase, success=bool(bindings))
                    self.assertFalse(any('--add' in a for a in calls))

    def test_write_failure_is_reported(self):
        calls, bindings = self.probe([dict(name='qa', mode='managed', grants=[grant('one')])], fail=True, success=False)
        self.assertEqual(1, sum('--add' in a for a in calls))
        self.assertEqual([], bindings)

    def test_direct_caller_keeps_immediate_write(self):
        calls, bindings = self.probe([dict(name='qa', mode='managed', grants=[grant('one')])], direct=True)
        self.assertEqual(1, sum('--add' in a for a in calls))
        self.assertEqual(1, len(bindings))

    def test_service_principals_use_two_writes_each_and_repeat_is_read_only(self):
        calls, bindings = self.probe([], compatibility=True, repeat=True)
        writes = [a for a in calls if '--add' in a]
        self.assertEqual(4, len(writes))
        expected = set()
        for principal in ['User:ANONYMOUS', 'User:CN=broker']:
            for kind in ['TOPIC', 'GROUP', 'TRANSACTIONAL_ID']:
                expected.add((kind, '*', 'LITERAL', principal, '*', 'ALL', 'ALLOW'))
            for operation in ['DESCRIBE', 'IDEMPOTENT_WRITE']:
                expected.add(('CLUSTER', 'kafka-cluster', 'LITERAL', principal, '*', operation, 'ALLOW'))
        self.assertEqual(expected, {tuple(b) for b in bindings})
        for args in writes:
            if '--cluster' in args:
                self.assertNotIn('All', args)
                self.assertNotIn('--topic', args)

    def test_same_name_on_different_types_is_not_deduplicated(self):
        grants = [grant('*', ['All'], kind=kind) for kind in ['topic', 'group', 'transactional-id']]
        calls, bindings = self.probe([dict(name='qa', mode='managed', grants=grants)])
        self.assertEqual(1, sum('--add' in a for a in calls))
        self.assertEqual({'TOPIC', 'GROUP', 'TRANSACTIONAL_ID'}, {b[0] for b in bindings})

    def test_cross_type_partial_deltas_do_not_widen_permissions(self):
        existing = [['TOPIC', '*', 'LITERAL', 'User:qa', '*', 'READ', 'ALLOW']]
        grants = [grant('*', ['Read', 'Describe'], kind=kind) for kind in ['topic', 'group']]
        calls, bindings = self.probe([dict(name='qa', mode='managed', grants=grants)], existing)
        self.assertEqual(2, sum('--add' in a for a in calls))
        self.assertEqual({(kind, '*', 'LITERAL', 'User:qa', '*', op, 'ALLOW')
                          for kind in ['TOPIC', 'GROUP'] for op in ['READ', 'DESCRIBE']},
                         {tuple(b) for b in bindings})

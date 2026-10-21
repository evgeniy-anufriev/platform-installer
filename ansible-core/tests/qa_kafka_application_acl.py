"""Read-only native Ansible ACL predicate checks; no Kafka or target mutations."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


class KafkaApplicationAclTests(unittest.TestCase):
    def test_batch_selection_never_borrows_acl_from_another_resource_or_pattern(self):
        path = ROOT / 'services/kafka/ansible_collections/platform/kafka/roles/kafka_kraft/tasks/application_acl.yml'
        tasks = yaml.safe_load(path.read_text())
        select = next(t for t in tasks if t['name'] == 'Select only this exact resource from the principal ACL inventory')
        predicate = next(t for t in tasks if t['name'] == 'Select missing exact ALLOW operations with wildcard host')
        actual = '\n'.join([
            'ACLs for principal `User:qa_probe`',
            'Current ACLs for resource `ResourcePattern(resourceType=TOPIC, name=qa.events, patternType=PREFIXED)`: ',
            '  (principal=User:qa_probe, host=*, operation=READ, permissionType=ALLOW)',
            'Current ACLs for resource `ResourcePattern(resourceType=TOPIC, name=qaXevents, patternType=LITERAL)`: ',
            '  (principal=User:qa_probe, host=*, operation=READ, permissionType=ALLOW)',
            'Current ACLs for resource `ResourcePattern(resourceType=TOPIC, name=qa.events, patternType=LITERAL)`: ',
            '  (principal=User:qa_probe, host=*, operation=DESCRIBE, permissionType=ALLOW)',
            'Current ACLs for resource `ResourcePattern(resourceType=GROUP, name=qa.events, patternType=LITERAL)`: ',
            '  (principal=User:qa_probe, host=*, operation=READ, permissionType=ALLOW)',
        ])
        play = [dict(hosts='localhost', connection='local', gather_facts=False,
                     vars=dict(application_kafka_account=dict(name='qa_probe'),
                               application_kafka_grant=dict(resourceType='topic', name='qa.events',
                                                           patternType='literal', operations=['Read', 'Describe']),
                               application_kafka_acl_inventory=dict(stdout=actual),
                               application_kafka_acl_operations=[]),
                     tasks=[select, predicate, {'ansible.builtin.assert': dict(
                         that=["application_kafka_acl_operations == ['--operation', 'Read']"])}])]
        with tempfile.TemporaryDirectory(prefix='qa-kafka-acl-batch-') as directory:
            probe = Path(directory, 'probe.yml')
            probe.write_text(yaml.safe_dump(play, sort_keys=False))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(probe)],
                                    env=dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg')),
                                    capture_output=True, text=True, timeout=45)
            self.assertEqual(0, result.returncode, (result.stdout + result.stderr)[-1800:])

    def check_operations(self, actual, requested, missing):
        path = ROOT / 'services/kafka/ansible_collections/platform/kafka/roles/kafka_kraft/tasks/application_acl.yml'
        subject = next(task for task in yaml.safe_load(path.read_text())
                       if task['name'] == 'Select missing exact ALLOW operations with wildcard host')
        expected = [value for operation in missing for value in ('--operation', operation)]
        play = [dict(hosts='localhost', connection='local', gather_facts=False,
                     vars=dict(application_kafka_account=dict(name='qa_probe'),
                               application_kafka_grant=dict(operations=requested),
                               application_kafka_acl_actual=dict(stdout=actual),
                               application_kafka_acl_operations=[], expected=expected),
                     tasks=[subject, {'ansible.builtin.assert': dict(
                         that=['application_kafka_acl_operations == expected'])}])]
        with tempfile.TemporaryDirectory(prefix='qa-kafka-acl-') as directory:
            probe = Path(directory, 'probe.yml')
            probe.write_text(yaml.safe_dump(play, sort_keys=False))
            environment = dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(probe)],
                                    env=environment, capture_output=True, text=True, timeout=45)
            self.assertEqual(0, result.returncode, (result.stdout + result.stderr)[-1800:])

    def test_existing_camel_case_operations_are_recognized(self):
        operations = dict(Read='READ', Write='WRITE', Describe='DESCRIBE',
                          IdempotentWrite='IDEMPOTENT_WRITE', DescribeConfigs='DESCRIBE_CONFIGS',
                          ClusterAction='CLUSTER_ACTION')
        actual = '\n'.join('principal=User:qa_probe, host=*, operation=' + value + ', permissionType=ALLOW'
                           for value in operations.values())
        self.check_operations(actual, list(operations), [])

    def test_cluster_idempotent_write_is_selected_from_full_inventory(self):
        tasks = yaml.safe_load((ROOT / 'services/kafka/ansible_collections/platform/kafka/roles/kafka_kraft/tasks/application_acl.yml').read_text())
        select = next(t for t in tasks if t['name'] == 'Select only this exact resource from the principal ACL inventory')
        predicate = next(t for t in tasks if t['name'] == 'Select missing exact ALLOW operations with wildcard host')
        actual = '\n'.join([
            'Current ACLs for resource `ResourcePattern(resourceType=TOPIC, name=*, patternType=LITERAL)`:',
            '  (principal=User:qa_probe, host=*, operation=ALL, permissionType=ALLOW)',
            'Current ACLs for resource `ResourcePattern(resourceType=CLUSTER, name=kafka-cluster, patternType=LITERAL)`:',
            '  (principal=User:other, host=*, operation=ALL, permissionType=ALLOW)',
            '  (principal=User:qa_probe, host=*, operation=IDEMPOTENT_WRITE, permissionType=ALLOW)',
            '  (principal=User:qa_probe, host=*, operation=CLUSTER_ACTION, permissionType=ALLOW)',
        ])
        with tempfile.TemporaryDirectory() as directory:
            probe = Path(directory, 'probe.yml')
            probe.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False,
                vars=dict(application_kafka_account=dict(name='qa_probe'), application_kafka_acl_inventory=dict(stdout=actual),
                    application_kafka_acl_operations=[], application_kafka_grant=dict(resourceType='cluster',
                        name='kafka-cluster', patternType='literal', operations=['IdempotentWrite', 'ClusterAction'])),
                tasks=[select, predicate, {'ansible.builtin.assert': dict(that=['application_kafka_acl_operations | length == 0'])}])], sort_keys=False))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(probe)],
                env=dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg')),
                capture_output=True, text=True, timeout=45)
            self.assertEqual(0, result.returncode, (result.stdout + result.stderr)[-1800:])

    def test_only_missing_operations_are_added_in_original_cli_spelling(self):
        actual = 'principal=User:qa_probe, host=*, operation=DESCRIBE, permissionType=ALLOW'
        self.check_operations(actual, ['Describe', 'IdempotentWrite'], ['IdempotentWrite'])

    def test_other_principals_hosts_and_deny_bindings_do_not_grant_access(self):
        actual = '\n'.join([
            'principal=User:qa_probe_other, host=*, operation=READ, permissionType=ALLOW',
            'principal=User:qa_probe, host=127.0.0.1, operation=READ, permissionType=ALLOW',
            'principal=User:qa_probe, host=*, operation=READ, permissionType=DENY',
        ])
        self.check_operations(actual, ['Read'], ['Read'])


if __name__ == '__main__':
    unittest.main()

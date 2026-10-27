"""Native Ansible batch/read-back checks using isolated fake Kafka CLI executables."""
import json
import os
import pwd
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
TASKS = ROOT / 'services/kafka/ansible_collections/platform/kafka/roles/kafka_kraft/tasks'
CLI = r'''#!/usr/bin/python3
import json, pathlib, sys
root = pathlib.Path(__file__).resolve().parents[1]
state = json.loads((root / 'state.json').read_text())
args = sys.argv[1:]
kind = pathlib.Path(__file__).name
with (root / 'calls.jsonl').open('a') as stream:
    stream.write(json.dumps([kind, args]) + '\n')
if state.get('fail'):
    sys.exit(1)
if '--create' in args and state.get('fail_create'):
    sys.exit(1)
if '--create' in args:
    state['topics'][args[args.index('--topic')+1]] = 'delete'
    (root / 'state.json').write_text(json.dumps(state))
elif kind == 'kafka-acls.sh':
    print(state.get('acl', ''))
elif kind == 'kafka-topics.sh':
    import re
    for name in state['topics']:
        if re.fullmatch(args[args.index('--topic')+1], name):
            print('Topic: %s\tPartitionCount: 1\tReplicationFactor: 1' % name)
            print('Topic: %s\tPartition: 0\tLeader: 1\tReplicas: 1\tIsr: 1' % name)
else:
    selected = [args[args.index('--entity-name')+1]] if '--entity-name' in args else state['topics']
    for name in selected:
        print('All configs for topic %s are:' % name)
        print('  cleanup.policy=%s sensitive=false synonyms={}' % state['topics'][name])
'''


class KafkaApplicationBatchTests(unittest.TestCase):
    def probe(self, state, topics, expected_success=True, repeat=False, acl=False, skip_infra_verify=False):
        with tempfile.TemporaryDirectory(prefix='qa-kafka-batch-') as directory:
            root = Path(directory)
            (root / 'bin').mkdir()
            for name in ['kafka-topics.sh', 'kafka-configs.sh', 'kafka-acls.sh']:
                path = root / 'bin' / name
                path.write_text(CLI)
                path.chmod(0o700)
            (root / 'state.json').write_text(json.dumps(state))
            variables = dict(platform_execution_skip_infrastructure_verify=skip_infra_verify,
                             application_topic_cli_directory=str(root),
                             application_topic_candidate=dict(address='127.0.0.1', port='9092'),
                             application_topic_client=dict(path=str(root / 'client.properties')),
                             platform_kafka_application_job=dict(providerId='qa', topics=topics),
                             platform_kafka_application_phase='apply',
                             platform_kafka_application_timeout_ms=1000,
                             platform_kafka_startup_readiness_retries=1,
                             platform_kafka_startup_readiness_delay=0)
            steps = [{'ansible.builtin.include_tasks': str(TASKS / 'application_topics_read.yml')},
                     {'ansible.builtin.include_tasks': str(TASKS / 'application_topic.yml'),
                      'loop': '{{ platform_kafka_application_job.topics }}',
                      'loop_control': dict(loop_var='application_topic'),
                      'vars': dict(application_topic_must_exist=False)}]
            if acl:
                variables.update(application_kafka_private=dict(path=str(root)),
                                 application_kafka_account=dict(name='qa_probe', mode='existing'))
                steps = [{'ansible.builtin.include_tasks': str(TASKS / 'application_acls_read.yml')},
                         {'ansible.builtin.include_tasks': str(TASKS / 'application_acl.yml'),
                          'loop': [dict(resourceType=kind, name=name, patternType='literal', operations=['Read'])
                                   for kind, name in [('topic', 'qa.a'), ('group', 'qa-group')]],
                          'loop_control': dict(loop_var='application_kafka_grant')}]
            play = [dict(hosts='localhost', connection='local', gather_facts=False,
                         vars=variables, tasks=steps)]
            probe = root / 'probe.yml'
            probe.write_text(yaml.safe_dump(play, sort_keys=False))
            def run():
                result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(probe)],
                                        env=dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
                                                 ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'services/kafka') + ':' + str(ROOT / 'ansible-core/collections')),
                                        capture_output=True, text=True, timeout=90)
                self.assertEqual(expected_success, result.returncode == 0,
                                 (result.stdout + result.stderr)[-2400:])
            run()
            if repeat:
                run()
            return [json.loads(line) for line in (root / 'calls.jsonl').read_text().splitlines()]

    def topic(self, name, mode='managed', policy='delete'):
        return dict(name=name, mode=mode, partitions=1, replicationFactor=1,
                    config={'cleanup.policy': policy})

    def test_existing_topics_use_only_two_read_commands(self):
        calls = self.probe({'topics': {'qa.a': 'delete', 'qa-b': 'compact', 'qaXa': 'compact'}},
                           [self.topic('qa.a'), self.topic('qa-b', policy='compact')])
        self.assertEqual(2, len(calls))
        self.assertEqual('^(qa\\.a|qa\\-b)$', calls[0][1][-1])

    def test_skip_infra_verify_still_prepares_only_selected_library_topics(self):
        from test_application_providers import KafkaAdminSelectionTest, project_providers
        inputs = KafkaAdminSelectionTest().fixture(accounts=False)
        inputs[1]['applicationExecutionScope'] = {'installLibraries': ['a']}
        projected = project_providers(*inputs)
        self.assertEqual('PASS', projected['status'], projected['findings'])
        stage = yaml.safe_load((ROOT / 'ansible-core/playbooks/applications/stages/provider-stage.yml').read_text())
        def walk(value):
            if isinstance(value, dict):
                yield value
                for child in value.values():
                    yield from walk(child)
            elif isinstance(value, list):
                for child in value:
                    yield from walk(child)
        task = next(t for t in walk(stage) if t.get('ansible.builtin.include_role', {}).get('tasks_from') == 'application_topics')
        from ansible.template import Templar
        from ansible.parsing.dataloader import DataLoader
        jobs = Templar(loader=DataLoader(), variables={'application_provider_inputs': projected}).template(task['loop'])
        self.assertEqual(1, len(jobs))
        self.assertEqual(['a-events'], [t['name'] for t in jobs[0]['topics']])
        for skip in (False, True):
            with self.subTest(skipInfraVerify=skip):
                calls = self.probe({'topics': {}}, jobs[0]['topics'], repeat=True, skip_infra_verify=skip)
                created = [args[args.index('--topic') + 1] for _, args in calls if '--create' in args]
                self.assertEqual(['a-events'], created)

    def test_configuration_from_neighbour_topic_cannot_hide_drift(self):
        calls = self.probe({'topics': {'qa.a': 'compact', 'qaXa': 'delete'}},
                           [self.topic('qa.a')], expected_success=False)
        self.assertEqual(2, len(calls))

    def test_missing_managed_topic_is_created_without_readback_then_repeat_is_read_only(self):
        calls = self.probe({'topics': {}}, [self.topic('qa.a')], repeat=True)
        self.assertEqual(5, len(calls), calls)
        self.assertEqual(1, sum('--create' in args for _, args in calls))
        self.assertEqual(0, sum('--entity-name' in args for _, args in calls))

    def test_failed_creation_stops_without_post_creation_reads(self):
        calls = self.probe({'topics': {}, 'fail_create': True},
                           [self.topic('qa.a')], expected_success=False)
        self.assertEqual(3, len(calls))
        self.assertIn('--create', calls[-1][1])

    def test_missing_existing_topic_never_creates(self):
        calls = self.probe({'topics': {}}, [self.topic('qa.a', mode='existing')], expected_success=False)
        self.assertFalse(any('--create' in args for _, args in calls))

    def test_failed_metadata_read_never_creates(self):
        calls = self.probe({'topics': {}, 'fail': True}, [self.topic('qa.a')], expected_success=False)
        self.assertEqual(1, len(calls))

    def test_acl_inventory_is_read_once_for_multiple_resources(self):
        actual = '\n'.join(
            'Current ACLs for resource `ResourcePattern(resourceType=%s, name=%s, patternType=LITERAL)`:\n'
            '  (principal=User:qa_probe, host=*, operation=READ, permissionType=ALLOW)'
            % (kind, name) for kind, name in [('TOPIC', 'qa.a'), ('GROUP', 'qa-group')])
        calls = self.probe({'topics': {}, 'acl': actual}, [], acl=True)
        self.assertEqual(1, len(calls))
        self.assertIn('--principal', calls[0][1])
        self.assertIn('any', calls[0][1])
        self.assertNotIn('--add', calls[0][1])

    def test_library_verify_has_only_container_and_endpoint_checks(self):
        plays = yaml.safe_load((ROOT / 'ansible-core/playbooks/applications/verify.yml').read_text())
        self.assertFalse(any(p.get('import_playbook') == 'stages/provider-verify-stage.yml' for p in plays))
        container = next(t for p in plays for t in p.get('tasks', []) if t['name'] == 'Проверка выбранного размещения каждого приложения')
        self.assertIs(False, container['vars']['application_runtime_verify_vault'])
        self.assertTrue(any(p.get('import_playbook') == 'stages/endpoint.yml' for p in plays))

    def test_container_verify_with_agent_does_not_need_vault_or_provider_credentials(self):
        self.container_probe()

    def test_activation_with_agent_does_not_repeat_vault_login_or_secret_reads(self):
        self.container_probe(activate=True)

    def test_activation_still_rejects_an_unhealthy_container_without_vault_probe(self):
        self.container_probe(activate=True, healthy=False)

    def container_probe(self, activate=False, healthy=True):
        with tempfile.TemporaryDirectory(prefix='qa-container-verify-') as directory:
            root = Path(directory)
            inspected = [dict(Id='qa-container', Image='sha256:qa', Config=dict(Labels={
                'platform.installer.project': 'qa-project', 'platform.installer.library': 'qa-library',
                'platform.installer.instance': 'qa-instance', 'platform.installer.host': 'qa-host'}),
                State=dict(Running=True, Health=dict(Status='healthy' if healthy else 'unhealthy')))]
            docker = root / 'docker'
            image = [dict(Id='sha256:qa', Os='linux', Architecture='amd64')]
            docker.write_text('#!/usr/bin/python3\nimport sys\n'
                              'if sys.argv[1:3] == ["container", "inspect"]: print(' + repr(json.dumps(inspected)) + ')\n'
                              'elif sys.argv[1:3] == ["image", "inspect"]: print(' + repr(json.dumps(image)) + ')\n'
                              'elif sys.argv[1] not in ["tag", "compose"]: sys.exit(1)\n')
            docker.chmod(0o700)
            role = ROOT / 'ansible-core/collections/ansible_collections/platform/core/roles/application_runtime/tasks' / ('activate_instance.yml' if activate else 'verify.yml')
            variables = dict(application_runtime_verify_vault=False, application_runtime_job=dict(
                instancePath=str(root), agentTemplate=True,
                account=pwd.getpwuid(os.getuid()).pw_name,
                dockerEnvironment=dict(PATH=str(root) + ':' + os.environ['PATH']),
                placement=dict(containerName='qa-instance'),
                composeArgv=['docker', 'compose'], source=dict(source='OFFLINE_BUNDLE'),
                authority=dict(requirement=dict(imageId='sha256:qa', localReference='qa:locked',
                                               platform=dict(os='linux', architecture='amd64'))),
                projectId='qa-project', libraryId='qa-library', instanceId='qa-instance', hostId='qa-host',
                settings=dict(image='qa:original', readiness=dict(mode='healthcheck', retries=1, delay=0))))
            if activate:
                # Default direct Verify still requests Vault verification; activation must override it.
                variables['application_runtime_verify_vault'] = True
            probe = root / 'verify.yml'
            probe.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False,
                vars=variables, tasks=[{'ansible.builtin.include_tasks': str(role)}])], sort_keys=False))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(probe)],
                env=dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg')),
                capture_output=True, text=True, timeout=45)
            self.assertEqual(healthy, result.returncode == 0, (result.stdout + result.stderr)[-1800:])


if __name__ == '__main__':
    unittest.main()

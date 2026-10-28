"""Run production orchestration/CLI tasks in native Ansible, with isolated IO.

No installed service is contacted. Preparation, systemd and API IO use a local
event recorder; topic policy checks and orchestration are the production YAML.
"""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[3]
TASKS = Path(__file__).resolve().parents[1] / 'ansible_collections/platform/kafka/roles/kafka_kraft/tasks'
RECORDER = r'''#!/usr/bin/python3
import json, pathlib, sys
root = pathlib.Path(__file__).resolve().parent
args = sys.argv[1:]
settings = json.loads((root/'settings.json').read_text())
if args[0] in ['prepare', 'start', 'ready']:
    kind, identity, config, host, dep = args
    with (root/'events.jsonl').open('a') as f: f.write(json.dumps([kind, identity])+'\n')
    if kind == 'prepare':
        path = pathlib.Path(config)/'kafka-client.properties'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(id=identity, host=host, deployment_id=dep)))
    sys.exit(1 if identity == settings.get('fail_'+kind) else 0)
client = pathlib.Path(args[args.index('--command-config')+1])
if not client.is_file(): sys.exit(51)
context = json.loads(client.read_text())
if settings['expected_clients'].get(str(client)) != context: sys.exit(52)
if pathlib.Path(sys.argv[0]).parents[2].name != context['host']: sys.exit(53)
dep = context['deployment_id']
kind = 'create' if '--create' in args else 'describe'
with (root/'events.jsonl').open('a') as f: f.write(json.dumps([kind, dep])+'\n')
if settings.get('fail_topic') == kind: sys.exit(1)
topic = root/('topic-'+dep)
if kind == 'create':
    topic.write_text('Topic: _schemas PartitionCount: '+('2' if settings.get('bad_create') else '1')+
        ' ReplicationFactor: 2 Configs: cleanup.policy=compact,min.insync.replicas=2')
elif topic.exists(): print(topic.read_text())
'''


class RegistryOptimizationRuntimeTests(unittest.TestCase):
    def run_fixture(self, *, existing=(), settings=None, present=True, partial=False,
                    two_deployments=False, serial=None, repeat=False, colocated=False, controller=False,
                    invalid_prepared=None, stale_dict=False):
        with tempfile.TemporaryDirectory(prefix='qa-registry-order-') as directory:
            root = Path(directory)
            recorder = root/'record'
            recorder.write_text(RECORDER)
            recorder.chmod(0o700)
            instances = [dict(id='m'+str(i), host='h'+str(i), deployment_id='other' if two_deployments and i == 3 else 'qa',
                              bootstrap_servers='SSL://unused:9093', config_directory=str(root/('other' if two_deployments and i == 3 else 'qa')/('m'+str(i))),
                              replication_factor=2, min_insync_replicas=2, unit_name='unused') for i in [1, 2, 3]]
            if colocated:
                for instance in instances:
                    instance['host'] = 'h1'
            if present:
                for dep in {i['deployment_id'] for i in instances}:
                    (root/('topic-'+dep)).write_text('Topic: _schemas PartitionCount: 1 ReplicationFactor: 2 Configs: cleanup.policy=compact,min.insync.replicas=2')
            fixture_tasks = root/'tasks'
            shutil.copytree(TASKS, fixture_tasks)
            def command(kind):
                return {'ansible.builtin.command': {'argv': [str(recorder), kind, '{{ registry_instance.id }}',
                    '{{ registry_instance.config_directory }}', '{{ registry_instance.host }}', '{{ registry_instance.deployment_id }}']}, 'changed_when': False}
            prepare = [command('prepare'), {'ansible.builtin.set_fact': {'_platform_kafka_registry_activation':
                "{{ _platform_kafka_registry_activation + [{'key': [registry_instance.deployment_id, registry_instance.id] | to_json, 'new': registry_instance.id not in existing, 'restart': true, 'reload': false}] }}"}}]
            if invalid_prepared == 'missing':
                prepare = prepare[:1]
            elif invalid_prepared == 'duplicate':
                prepare.append(copy.deepcopy(prepare[-1]))
            (fixture_tasks/'schema_registry_member.yml').write_text(yaml.safe_dump(prepare, sort_keys=False))
            activation = yaml.safe_load((TASKS/'schema_registry_activate.yml').read_text())
            activation[0].pop('ansible.builtin.systemd')
            activation[0].update(command('start'))
            (fixture_tasks/'schema_registry_activate.yml').write_text(yaml.safe_dump(activation, sort_keys=False))
            (fixture_tasks/'schema_registry_ready.yml').write_text(yaml.safe_dump([command('ready')]))
            topic = yaml.safe_load((TASKS/'schema_registry_topic_for_host.yml').read_text())
            topic[1]['ansible.builtin.include_tasks']['apply']['become'] = False
            (fixture_tasks/'schema_registry_topic_for_host.yml').write_text(yaml.safe_dump(topic, sort_keys=False))
            hosts = ['h1'] if colocated else (['h2'] if partial else ['h1', 'h2', 'h3'])
            if controller:
                hosts.append('h4')
            inventory = root/'inventory.yml'
            hostvars, clients = {}, {}
            for host in hosts:
                cli = root/host/'cli'
                (cli/'bin').mkdir(parents=True)
                (cli/'bin/kafka-topics.sh').symlink_to(recorder)
                projected = copy.deepcopy(instances)
                for instance in projected:
                    instance['config_directory'] = str(root/host/'config'/instance['deployment_id']/('registry-'+host+'-'+instance['id']))
                    instance['unit_name'] = 'registry-'+host+'-'+instance['id']
                    if instance['host'] == host:
                        clients[str(Path(instance['config_directory'])/'kafka-client.properties')] = {
                            key: instance[key] for key in ['id', 'host', 'deployment_id']}
                hostvars[host] = dict(ansible_connection='local', ansible_python_interpreter='/usr/bin/python3',
                    platform_kafka_install_directory=str(cli), _platform_kafka_registry_projection=dict(instances=projected))
            (root/'settings.json').write_text(json.dumps(dict(settings or {}, expected_clients=clients)))
            inventory.write_text(yaml.safe_dump({'all': {'hosts': hostvars}}))
            steps = [{'ansible.builtin.include_tasks': str(fixture_tasks/'schema_registry_instances.yml'),
                      'when': '_platform_kafka_registry_local | length > 0'}]
            if repeat:
                steps = steps * 2
            # Production schema_registry_validate stores this as a host fact.
            # A play-only variable is intentionally not visible via hostvars.
            steps.insert(0, {'ansible.builtin.set_fact': {'_platform_kafka_registry_local':
                "{{ _platform_kafka_registry_projection.instances | selectattr('host', 'equalto', inventory_hostname) | list }}"}})
            steps += [{'ansible.builtin.assert': {'that': [
                "_platform_kafka_registry_activation is not mapping",
                "_platform_kafka_registry_activation | selectattr('key', 'equalto', 'stale') | list | length == 0",
                '_platform_kafka_registry_activation | length == _platform_kafka_registry_local | length']},
                'when': '_platform_kafka_registry_local | length > 0'}]
            play = dict(hosts='all', order='reverse_inventory', strategy='linear', gather_facts=False,
                vars=dict(_platform_kafka_registry_local="{{ _platform_kafka_registry_projection.instances | selectattr('host', 'equalto', inventory_hostname) | list }}",
                    platform_kafka_verify_only=False, existing=list(existing),
                    _platform_kafka_registry_activation=({'stale': {'new': True}} if stale_dict else [{'key': 'stale', 'new': True}])), tasks=steps)
            if serial:
                play['serial'] = serial
            play_file = root/'play.yml'
            play_file.write_text(yaml.safe_dump([play], sort_keys=False))
            result = subprocess.run(['ansible-playbook', '-i', str(inventory), str(play_file)],
                env=dict(os.environ, ANSIBLE_CONFIG=str(ROOT/'ansible-core/ansible.cfg')),
                capture_output=True, text=True, timeout=100)
            events = [json.loads(line) for line in (root/'events.jsonl').read_text().splitlines()]
            return result.returncode, events, (result.stdout+result.stderr)[-2200:]

    def test_cold_starts_precede_readiness_and_topic_is_read_once(self):
        rc, events, output = self.run_fixture()
        self.assertEqual(0, rc, output)
        self.assertEqual(1, sum(k == 'describe' for k, _ in events))
        self.assertEqual(3, sum(k == 'start' for k, _ in events))
        self.assertLess(max(i for i, e in enumerate(events) if e[0] == 'start'),
                        min(i for i, e in enumerate(events) if e[0] == 'ready'))
        self.assertLess(max(i for i, e in enumerate(events) if e[0] == 'prepare'),
                        min(i for i, e in enumerate(events) if e[0] == 'describe'))

    def test_existing_instances_wait_before_next_restart(self):
        rc, events, output = self.run_fixture(existing=['m1', 'm2', 'm3'])
        self.assertEqual(0, rc, output)
        lifecycle = [e for e in events if e[0] in ['start', 'ready']]
        self.assertEqual(['start', 'ready']*3, [e[0] for e in lifecycle])
        for a, b in zip(lifecycle[::2], lifecycle[1::2]):
            self.assertEqual(a[1], b[1])

    def test_preparation_failure_blocks_all_activation(self):
        rc, events, _ = self.run_fixture(settings={'fail_prepare': 'm2'})
        self.assertNotEqual(0, rc)
        self.assertFalse(any(k in ['start', 'describe'] for k, _ in events))

    def test_existing_readiness_failure_stops_remaining_restarts(self):
        rc, events, _ = self.run_fixture(existing=['m1', 'm2', 'm3'], settings={'fail_ready': 'm3'})
        self.assertNotEqual(0, rc)
        # Reverse inventory makes m3 the first activation group.
        self.assertEqual([['start', 'm3']], [e for e in events if e[0] == 'start'])

    def test_create_is_confirmed_before_activation(self):
        rc, events, output = self.run_fixture(present=False)
        self.assertEqual(0, rc, output)
        self.assertEqual(['describe', 'create', 'describe'], [k for k, _ in events if k in ['describe', 'create']])

    def test_create_failure_or_wrong_policy_blocks_every_activation(self):
        for settings in [{'fail_topic': 'create'}, {'bad_create': True}, {'fail_topic': 'describe'}]:
            with self.subTest(settings=settings):
                rc, events, _ = self.run_fixture(present=False, settings=settings)
                self.assertNotEqual(0, rc)
                self.assertFalse(any(k == 'start' for k, _ in events))

    def test_partial_inventory_reads_through_available_member_but_cannot_create(self):
        for present in [True, False]:
            rc, events, output = self.run_fixture(partial=True, present=present)
            self.assertEqual(present, rc == 0, output)
            self.assertEqual(1, sum(k == 'describe' for k, _ in events))
            self.assertFalse(any(k == 'create' for k, _ in events))

    def test_deployments_have_separate_topic_checks(self):
        rc, events, output = self.run_fixture(two_deployments=True)
        self.assertEqual(0, rc, output)
        self.assertEqual({'qa', 'other'}, {v for k, v in events if k == 'describe'})
        self.assertEqual(2, sum(k == 'describe' for k, _ in events))

    def test_missing_or_ambiguous_prepared_record_stops_before_topic_or_activation(self):
        for invalid in ['missing', 'duplicate']:
            with self.subTest(invalid=invalid):
                rc, events, output = self.run_fixture(invalid_prepared=invalid)
                self.assertNotEqual(0, rc)
                self.assertIn('SCHEMA_REGISTRY_PREPARED_INSTANCE_REQUIRED', output)
                self.assertFalse(any(k in ['describe', 'create', 'start'] for k, _ in events))

    def test_legacy_dictionary_is_replaced_even_with_merge_precedence(self):
        rc, _, output = self.run_fixture(stale_dict=True, repeat=True)
        self.assertEqual(0, rc, output)

    def test_serial_batch_never_uses_future_host_and_repeat_has_no_stale_cache(self):
        rc, events, output = self.run_fixture(serial=1, repeat=True)
        self.assertEqual(0, rc, output)
        self.assertEqual(6, sum(k == 'describe' for k, _ in events))

    def test_colocated_members_keep_individual_flags_and_controller_host_is_skipped(self):
        for colocated, controller in [(True, False), (False, True)]:
            with self.subTest(colocated=colocated, controller=controller):
                rc, events, output = self.run_fixture(colocated=colocated, controller=controller, existing=['m2'])
                self.assertEqual(0, rc, output)
                self.assertEqual(1, sum(k == 'describe' for k, _ in events))
                self.assertEqual({'m1', 'm2', 'm3'}, {v for k, v in events if k == 'ready'})
                start = events.index(['start', 'm2'])
                ready = events.index(['ready', 'm2'])
                self.assertFalse(any(k == 'start' for k, _ in events[start+1:ready]))

    def test_loaded_unit_without_file_is_not_classified_as_cold(self):
        source = yaml.safe_load((TASKS/'schema_registry_member.yml').read_text())
        save = next(t for t in source if t['name'] == 'Сохранение индивидуальных признаков запуска Schema Registry')
        with tempfile.TemporaryDirectory(prefix='qa-registry-state-') as directory:
            root = Path(directory)
            tasks = []
            for exists, lines, cold in [(False, ['LoadState=not-found', 'ActiveState=inactive'], True),
                                       (False, ['LoadState=loaded', 'ActiveState=active'], False),
                                       (True, ['LoadState=not-found', 'ActiveState=inactive'], False),
                                       (False, [], False)]:
                tasks += [{'ansible.builtin.set_fact': {'_platform_kafka_registry_unit_before': {'stat': {'exists': exists}},
                           '_platform_kafka_registry_service_before': {'stdout_lines': lines}}}, copy.deepcopy(save),
                          {'ansible.builtin.assert': {'that': ["(_platform_kafka_registry_activation | first).new == " + str(cold).lower(),
                             '_platform_kafka_registry_activation | length == 1']}}]
            play = dict(hosts='localhost', connection='local', gather_facts=False, tasks=tasks,
                        vars=dict(registry_instance=dict(deployment_id='qa', id='m1'), _platform_kafka_registry_activation=[],
                                  _platform_kafka_registry_unit={}, _platform_kafka_registry_properties={},
                                  _platform_kafka_registry_pki_copy={}, _platform_kafka_registry_pem_changed=False))
            path = root/'play.yml'
            path.write_text(yaml.safe_dump([play]))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(path)], capture_output=True, text=True, timeout=60)
            self.assertEqual(0, result.returncode, (result.stdout+result.stderr)[-2200:])


if __name__ == '__main__':
    unittest.main()

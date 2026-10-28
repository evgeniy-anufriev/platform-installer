"""Native, target-free resource context checks on the Execution Node."""
import copy
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
TASKS = ROOT / 'ansible-core/collections/ansible_collections/platform/core/roles/resolve_application_libraries/tasks'


class ResourceContextBatchQA(unittest.TestCase):
    def test_native_batch_binding_isolation_empty_and_repeat(self):
        bindings = {'pg': {'deploymentRef': 'pg-one'}, 'pgAlias': {'deploymentRef': 'pg-one'},
                    'otherPg': {'deploymentRef': 'pg-two'}, 'ch': {'deploymentRef': 'ch-one'},
                    'kafka': {'deploymentRef': 'kafka-one'},
                    'provided': {'providedConnectionRef': {'libraryId': 'lib', 'name': 'db'}},
                    'providedAlias': {'providedConnectionRef': {'libraryId': 'other', 'name': 'db'}}}
        connections = {key: {'library_binding': binding} for key, binding in
                       [('db', 'pg'), ('dbAlias', 'pgAlias'), ('other', 'otherPg'),
                        ('history', 'ch'), ('events', 'kafka'), ('missing', 'absent'),
                        ('provided', 'provided')]}
        connections['unbound'] = {}
        resources = {key: {'kind': kind, 'binding': binding, 'parameters': {'name': name}}
                     for key, kind, binding, name in [
                         ('main', 'postgresql.database', 'pgAlias', 'Main'),
                         ('foreign', 'postgresql.database', 'otherPg', 'Other'),
                         ('history', 'clickhouse.database', 'ch', 'История'),
                         ('events', 'kafka.topic', 'kafka', 'Events'),
                         ('ignored', 'redis.key', 'pg', 'Ignore'),
                         ('unbound', 'kafka.topic', 'absent', 'Ignore'),
                         ('providedDb', 'postgresql.database', 'providedAlias', 'Provided')]}
        def entry(key):
            return {key: {'resourceId': key, 'name': resources[key]['parameters']['name']}}
        expected_topics = {'events': entry('events')}
        expected_databases = {'db': entry('main'), 'dbAlias': entry('main'),
                              'other': entry('foreign'), 'history': entry('history'),
                              'provided': entry('providedDb')}
        cases = [(connections, resources, {}, {}, expected_topics, expected_databases),
                 (connections, resources, expected_topics, expected_databases,
                  expected_topics, expected_databases),
                 ({}, resources, {}, {}, {}, {}),
                 (connections, {}, {}, {}, {}, {}),
                 (connections, resources, {'kept': entry('events')},
                  {'db': {'kept': {'resourceId': 'kept', 'name': 'kept'}}},
                  dict(expected_topics, kept=entry('events')),
                  dict(expected_databases, db=dict(entry('main'), kept={'resourceId': 'kept', 'name': 'kept'})))]
        include = next(task for task in yaml.safe_load((TASKS / 'instance.yml').read_text())
                       if task.get('ansible.builtin.include_tasks') == 'resource_context.yml')
        include = copy.deepcopy(include)
        include['ansible.builtin.include_tasks'] = str(TASKS / 'resource_context.yml')
        steps = []
        for conns, res, topics, databases, want_topics, want_databases in cases:
            steps.extend([
                {'ansible.builtin.set_fact': {
                    '_application_connections': conns, '_application_resources': res,
                    'application_job': {'deployment': {'bindings': bindings}},
                    'application_topics': topics, 'application_databases': databases,
                    'expected_topics': want_topics, 'expected_databases': want_databases}},
                include,
                {'ansible.builtin.assert': {'that': [
                    'application_topics == expected_topics',
                    'application_databases == expected_databases']}}])
        with tempfile.TemporaryDirectory(prefix='qa-resource-context-') as directory:
            play = Path(directory) / 'test.yml'
            play.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local',
                                               gather_facts=False, tasks=steps)], sort_keys=False))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(play)],
                                    env=dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
                                             ANSIBLE_STDOUT_CALLBACK='default', ANSIBLE_NOCOLOR='1'),
                                    capture_output=True, text=True, timeout=90)
            self.assertEqual(0, result.returncode, (result.stdout + result.stderr)[-4000:])
            self.assertRegex(result.stdout, r'changed=0\s+unreachable=0\s+failed=0\s+skipped=0')
            self.assertEqual(len(cases), result.stdout.count('TASK [Передача выбранных ресурсов провайдерам соединений приложения]'))

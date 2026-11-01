"""Core defaults must reach the real Kafka inventory-to-instance tasks."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ansible-core/collections'))
from ansible_collections.platform.core.plugins.module_utils.deployment_plan import _execution_role_variables
from ansible_collections.platform.core.plugins.module_utils.service_configuration_resolution import resolve_service_configuration


@unittest.skipUnless(shutil.which('ansible-playbook'), 'Ansible runtime required')
class KafkaNodeIdExecutionTests(unittest.TestCase):
    def probe(self, overrides=None, colocated=False, native=False):
        overrides = overrides or {}
        definition = yaml.safe_load((ROOT / 'services/kafka/service.yml').read_text())
        # Exercise the production nodeId declaration and resolver; unrelated
        # service settings are evaluated normally by the actual role defaults.
        definition['configuration']['settings'] = {
            'nodeId': definition['configuration']['settings']['nodeId']}
        members = {f'kafka-{i}': {
            'host': 'node1' if colocated else f'node{i}',
            'roles': ['broker', 'controller'],
            'configuration': {'nodeId': overrides[i]} if i in overrides else {},
        } for i in range(1, 4)}
        desired = {'serviceDeployments': {'kafka': {
            'serviceType': 'kafka', 'mode': 'kraft-ha', 'configuration': {},
            'members': members}}}
        before = copy.deepcopy(desired)
        topology = {'status': 'PASS', 'resolvedTopology': desired}
        configuration = resolve_service_configuration(
            topology, desired, {'definitions': {'kafka': definition}}, {'kafka': {}})
        targets = sorted({member['host'] for member in members.values()})
        variables = _execution_role_variables(
            'kafka', definition, 'platform_kafka_', configuration, targets)
        self.assertEqual(before, desired)
        expected = [overrides.get(i, i) for i in range(1, 4)]
        for values in variables.values():
            self.assertNotIn('platform_kafka_node_id', values)
            self.assertEqual(expected, [values['platform_kafka_member_inputs'][f'kafka-{i}']['nodeId']
                                        for i in range(1, 4)])
        hosts = {host: {'ansible_connection': 'local', 'ansible_host': '127.0.0.1',
                        'platform_deployments': {}}
                 for host in ['app1', 'app2', 'node1', 'node2', 'node3']}
        for member_id, member in members.items():
            placement = hosts[member['host']]['platform_deployments'].setdefault('kafka', {'members': {}})
            placement['members'][member_id] = {key: copy.deepcopy(member[key])
                                               for key in ['roles', 'configuration']}
        play = [{'hosts': 'platform_targets', 'gather_facts': False, 'vars': {
            'platform_desired_state': {'serviceDeployments': {'kafka': {
                'serviceType': 'kafka', 'mode': 'kraft-ha', 'configuration': {}}}},
            'platform_execution_service_deployment': 'kafka',
            'platform_execution_role_variables_by_host': variables,
        }, 'tasks': [
            {'include_role': {'name': 'platform.core.runtime_role_variables'}},
            {'include_role': {'name': 'platform.kafka.kafka_kraft', 'tasks_from': 'project_runtime.yml'}},
            {'assert': {'that': [
                '(platform_kafka_instances | map(attribute="node_id") | list) == ' + json.dumps(expected),
                'platform_kafka_instances | length == 3',
                'platform_kafka_instances | map(attribute="node_id") | select("integer") | list | length == 3',
            ]}},
        ]}]
        with tempfile.TemporaryDirectory(prefix='kafka-node-id-') as folder:
            folder = Path(folder)
            (folder / 'hosts.json').write_text(json.dumps({'all': {'children': {
                'platform_targets': {'hosts': hosts}}}}))
            (folder / 'play.json').write_text(json.dumps(play))
            env = dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
                       ANSIBLE_COLLECTIONS_PATH=os.pathsep.join([
                           str(ROOT / 'ansible-core/collections'),
                           str(ROOT / 'services/kafka/ansible_collections')]),
                       ANSIBLE_JINJA2_NATIVE=str(native), ANSIBLE_NOCOLOR='1')
            result = subprocess.run([
                'ansible-playbook', '-i', str(folder / 'hosts.json'), str(folder / 'play.json'),
                '--limit', 'localhost:' + ':'.join(targets)],
                env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(0, result.returncode, result.stdout[-5000:] + result.stderr[-1000:])
        self.assertIn('changed=0', result.stdout)

    def test_defaults_reach_three_of_five_hosts(self):
        for native in (False, True):
            with self.subTest(native=native):
                self.probe(native=native)

    def test_explicit_zero_and_other_override_are_preserved(self):
        self.probe(overrides={1: 0, 2: 42})

    def test_colocated_members_keep_distinct_ids(self):
        self.probe(colocated=True)


if __name__ == '__main__':
    unittest.main()

"""Ordinary Kafka inventory retains Registry port types in both Jinja modes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


@unittest.skipUnless(shutil.which('ansible-playbook'), 'Ansible runtime required')
class RegistryProjectionTypesTests(unittest.TestCase):
    def probe(self, configuration, expected, valid, native):
        variables = {
            'platform_desired_state': {'serviceDeployments': {'qa-kafka': {
                'serviceType': 'kafka', 'mode': 'kraft-ha', 'configuration': configuration}}},
            'platform_deployments': {'qa-kafka': {'members': {'kafka-1': {
                'roles': ['broker', 'controller'], 'configuration': {'nodeId': 1}}}}},
        }
        member = dict(id='kafka-1', deployment_id='qa-kafka', host='localhost',
                      advertised_host='127.0.0.1', roles=['broker'], listeners={},
                      schema_registry='{{ platform_kafka_instances[0].schema_registry }}')
        assertions = [
            'platform_kafka_instances[0].schema_registry.http_port == ' + json.dumps(expected),
            '(_registry.findings | length == 0) == ' + str(valid).lower(),
        ]
        if valid:
            assertions.append('platform_kafka_instances[0].schema_registry.http_port is integer')
        play = [dict(hosts='localhost', connection='local', gather_facts=False,
                     vars=variables, tasks=[
                         {'include_role': {'name': 'platform.kafka.kafka_kraft',
                                           'tasks_from': 'project_runtime.yml'}},
                         {'set_fact': {'_member': member}},
                         {'set_fact': {'_registry': '{{ [_member] | platform.core.platform_kafka_schema_registry_projection(false) }}'}},
                         {'assert': {'that': assertions}},
                     ])]
        with tempfile.TemporaryDirectory(prefix='kafka-port-types-') as folder:
            path = Path(folder)
            (path / 'inventory.json').write_text(json.dumps({'all': {'hosts': {
                'localhost': dict(variables, ansible_connection='local', ansible_host='127.0.0.1')},
                'children': {'platform_targets': {'hosts': {'localhost': {}}}}}}))
            (path / 'play.json').write_text(json.dumps(play))
            env = dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
                       ANSIBLE_COLLECTIONS_PATH=os.pathsep.join([
                           str(ROOT / 'ansible-core/collections'),
                           str(ROOT / 'services/kafka/ansible_collections')]),
                       ANSIBLE_JINJA2_NATIVE=str(native), ANSIBLE_NOCOLOR='1')
            result = subprocess.run(['ansible-playbook', '-i', str(path / 'inventory.json'),
                                     str(path / 'play.json')], env=env, capture_output=True, timeout=60)
        self.assertEqual(0, result.returncode, result.stdout.decode(errors='replace')[-3000:])
        self.assertIn(b'changed=0', result.stdout)

    def test_defaults_and_overrides_keep_integers_and_invalid_values_rejected(self):
        for native in (False, True):
            for configuration, expected, valid in [({}, 8081, True),
                    ({'schemaRegistryHttpPort': 8181, 'schemaRegistryHttpsPort': 8182}, 8181, True),
                    ({'schemaRegistryHttpPort': True}, True, False),
                    ({'schemaRegistryHttpPort': 8081.5}, 8081.5, False)]:
                with self.subTest(native=native, configuration=configuration):
                    self.probe(configuration, expected, valid, native)

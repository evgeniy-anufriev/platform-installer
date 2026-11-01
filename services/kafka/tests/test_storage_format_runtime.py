"""Run production format/config tasks against legacy and modern CLI fixtures."""
import getpass
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[3]
ROLE = ROOT / 'services/kafka/ansible_collections/platform/kafka/roles/kafka_kraft'


@unittest.skipUnless(shutil.which('ansible-playbook'), 'Ansible runtime required')
class StorageFormatRuntimeTests(unittest.TestCase):
    def probe(self, mode, modern=False, roles=None, directory_id=True, controller_count=3, native=False):
        member_tasks = yaml.safe_load((ROLE / 'tasks/member.yml').read_text())
        preparation = yaml.safe_load((ROLE / 'tasks/prepare_host.yml').read_text())
        strategy = next(task for task in member_tasks if task['name'] == 'Определение стратегии формата хранения Kafka')
        formatting = next(task['block'] for task in member_tasks
                          if task['name'] == 'Форматирование чистого хранилища с готовым SCRAM admin до первого запуска')
        with tempfile.TemporaryDirectory(prefix='kafka-storage-format-') as folder:
            base = Path(folder)
            (base / 'bin').mkdir()
            record = base / 'format-args.json'
            cli = base / 'bin/kafka-storage'
            cli.write_text('#!/usr/bin/python3\n' + '''
import argparse, json, pathlib, sys
parser = argparse.ArgumentParser()
parser.add_argument('command', choices=['format'])
parser.add_argument('--config', required=True)
parser.add_argument('--cluster-id', required=True)
''' + ('''
parser.add_argument('--initial-controllers')
parser.add_argument('--no-initial-controllers', action='store_true')
parser.add_argument('--standalone', action='store_true')
''' if modern else '') + '''
args = parser.parse_args()
config = pathlib.Path(args.config).read_text()
values = dict(line.split('=', 1) for line in config.splitlines() if '=' in line)
advertised = values.get('advertised.listeners', '')
if 'CONTROLLER://' in advertised:
    parser.error('controller listener must not be advertised to broker clients')
if 'broker' not in values.get('process.roles', '') and 'advertised.listeners' in values:
    parser.error('controller-only member must omit advertised.listeners')
''' + ('' if modern else '''
if 'controller.quorum.voters=' not in config or 'controller.quorum.bootstrap.servers=' in config:
    parser.error('legacy static quorum configuration required')
''') + 'pathlib.Path(' + repr(str(record)) + ').write_text(json.dumps(sys.argv[1:]))\n')
            cli.chmod(0o755)
            member = {'roles': roles or ['broker', 'controller'], 'config_directory': str(base),
                      'node_id': 1, 'data_directory': str(base / 'data'), 'advertised_host': 'localhost',
                      'listeners': {'CONTROLLER': {'purpose': 'controller', 'securityProtocol': 'PLAINTEXT', 'port': 19193},
                                    'REPLICATION': {'purpose': 'interBroker', 'securityProtocol': 'PLAINTEXT', 'port': 19192},
                                    'CLIENT': {'purpose': 'client', 'securityProtocol': 'PLAINTEXT', 'port': 19194}}}
            if directory_id:
                member['directory_id'] = 'qa-directory-id'
            variables = dict(platform_kafka_install_directory=os.environ['KAFKA_STORAGE_NATIVE_HOME'] if native else str(base), platform_kafka_script_extension='',
                platform_kafka_user=getpass.getuser(), platform_kafka_quorum_mode=mode,
                platform_kafka_cluster_id='MkU3OEVBNTcwNTJENDM2Qk', platform_kafka_verify_only=False,
                platform_kafka_member_metadata={'stat': {'exists': False}}, kafka_member=member,
                _platform_kafka_scram_enabled=False,
                _platform_kafka_controller_instances=[{}] * controller_count,
                _platform_kafka_initial_controllers='1@node1:9093:qa-directory-id',
                _platform_kafka_static_quorum_voters='1@127.0.0.1:19193,2@127.0.0.1:19293,3@127.0.0.1:19393',
                _platform_kafka_controller_bootstrap_servers='node1:9093,node2:9093,node3:9093',
                platform_kafka_advanced_config={}, platform_kafka_log_retention_hours=168, kafka_effective_config={})
            tasks = [task for task in preparation if task.get('register') == '_platform_kafka_storage_format_help'
                     or task['name'] == 'Проверка поддержки динамического кворума до форматирования Kafka']
            tasks += [task for task in member_tasks if task['name'] in (
                'Создание проекции Kafka listeners экземпляра с учётом ролей',
                'Преобразование проекции именованных Kafka listeners в список Ansible',
                'Выбор listeners экземпляра Kafka',
                'Формирование строк действующих именованных Kafka listeners',
                'Создание действующей конфигурации экземпляра службы',
                'Добавление действующей конфигурации брокера',
                'Добавление запрошенной проекции динамического кворума',
                'Добавление статической проекции кворума при явном выборе')]
            tasks += [{'ansible.builtin.template': {
                'src': str(ROLE / 'templates/server.properties.j2'), 'dest': str(base / 'server.properties')}},
                strategy]
            tasks += [task for task in formatting if task.get('register') == 'kafka_storage_format_result'
                      or task['name'] == 'Проверка успешности форматирования с безопасной классификацией ошибки']
            play = base / 'play.yml'
            play.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local',
                gather_facts=False, vars=variables, tasks=tasks)], sort_keys=False))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(play)],
                env=dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg')),
                capture_output=True, text=True, timeout=60)
            output = result.stdout + result.stderr
            if mode == 'dynamic' and not modern:
                self.assertNotEqual(0, result.returncode, output[-3000:])
                self.assertIn('KAFKA_DYNAMIC_QUORUM_UNSUPPORTED', output)
                self.assertFalse(record.exists())
                self.assertFalse((base / 'server.properties').exists())
                return
            self.assertEqual(0, result.returncode, output[-3000:])
            if native:
                self.assertTrue((base / 'data/meta.properties').is_file())
                return
            arguments = json.loads(record.read_text())
            flags = [item for item in arguments if item in (
                '--initial-controllers', '--no-initial-controllers', '--standalone')]
            if mode == 'static':
                self.assertEqual([], flags)
                self.assertIn('controller.quorum.voters=', (base / 'server.properties').read_text())
            else:
                expected = ('--initial-controllers' if directory_id and 'controller' in member['roles'] else
                            '--standalone' if 'controller' in member['roles'] and controller_count == 1 else
                            '--no-initial-controllers')
                self.assertEqual([expected], flags)

    def test_legacy_static_format_uses_supported_arguments_and_voters(self):
        self.probe('static')

    def test_modern_static_format_also_omits_dynamic_arguments(self):
        self.probe('static', modern=True)

    def test_legacy_dynamic_is_blocked_before_formatting(self):
        self.probe('dynamic')

    def test_modern_dynamic_controller_format_keeps_initial_controllers(self):
        self.probe('dynamic', modern=True)

    def test_modern_single_controller_keeps_standalone_compatibility(self):
        self.probe('dynamic', modern=True, directory_id=False, controller_count=1)

    def test_modern_broker_format_keeps_no_initial_controllers(self):
        self.probe('dynamic', modern=True, roles=['broker'], directory_id=False)

    def test_static_controller_only_omits_advertised_listeners(self):
        self.probe('static', roles=['controller'])

    @unittest.skipUnless(os.environ.get('KAFKA_STORAGE_NATIVE_HOME'), 'explicit installed Kafka required')
    def test_native_static_format_accepts_production_listener_projection(self):
        self.probe('static', native=True)


if __name__ == '__main__':
    unittest.main()

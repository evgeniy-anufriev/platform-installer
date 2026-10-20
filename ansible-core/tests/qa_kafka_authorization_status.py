"""Native Ansible process/file proof using synthetic processes and a fake systemctl.

Does not start Kafka, change installed units or connect to Kafka/Vault.
"""
import os
import base64
import signal
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar
from ansible.plugins.loader import init_plugin_loader
init_plugin_loader()

TASKS = (Path(__file__).resolve().parents[2] / 'services/kafka/ansible_collections/'
         'platform/kafka/roles/kafka_kraft/tasks')


class KafkaAuthorizationProcessProof(unittest.TestCase):
    def test_native_expression_requires_final_process_and_exact_arguments(self):
        expression = yaml.safe_load((TASKS / 'authorization_status.yml').read_text())[-1]['ansible.builtin.set_fact']['kafka_authorization_running_final']
        state = dict(kafka_authorization_config_line=dict(rc=0, stdout='super.users=User:admin'),
                     kafka_authorization_config_stat=dict(stat=dict(isreg=True, islnk=False, mtime=100)),
                     kafka_authorization_process=dict(rc=0, stdout='stable', stdout_lines=['ActiveState=active']),
                     kafka_authorization_process_after=dict(rc=0, stdout='stable'),
                     kafka_authorization_pid='123', kafka_authorization_start_epoch=dict(rc=0, stdout='110.0'),
                     kafka_authorization_member=dict(config_directory='/tmp/member'),
                     kafka_authorization_command=dict(content=base64.b64encode(b'java\0kafka.Kafka\0/tmp/member/server.properties\0').decode()))
        def render():
            return Templar(loader=DataLoader(), variables=state).template(expression)
        self.assertTrue(render())
        state['kafka_authorization_start_epoch']['stdout'] = '90.0'
        self.assertFalse(render())
        state['kafka_authorization_config_stat']['stat']['mtime'] = 100.75
        state['kafka_authorization_start_epoch']['stdout'] = '100'
        self.assertFalse(render())  # Same-second observation cannot prove startup.
        state['kafka_authorization_start_epoch']['stdout'] = '101'
        self.assertTrue(render())   # The write-second barrier preserves strict proof.
        state['kafka_authorization_start_epoch']['stdout'] = '110.0'
        state['kafka_authorization_command']['content'] = base64.b64encode(b'java\0kafka.Kafka\0/tmp/member/server.properties\0--override\0super.users=other\0').decode()
        self.assertFalse(render())

    def test_interrupted_final_file_and_partial_restart_fail_closed(self):
        children = []
        with tempfile.TemporaryDirectory(prefix='qa-kafka-authorization-') as directory:
            root = Path(directory)
            binary = root / 'bin'
            binary.mkdir()
            fake = binary / 'systemctl'
            fake.write_text('#!/bin/sh\ncat "$QA_SYSTEMCTL_STATE/$2.state"\n')
            fake.chmod(0o700)
            members = []
            for index in range(3):
                config = root / ('member-' + str(index))
                config.mkdir()
                properties = config / 'server.properties'
                properties.write_text('super.users=User:admin\n')
                members.append(dict(config_directory=str(config), systemd_unit_name='member-' + str(index)))

            def process(member, final_loaded):
                child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(900)',
                                          'kafka.Kafka', member['config_directory'] + '/server.properties'])
                children.append(child)
                started = time.time()
                # Both cases use the same final line. Only actual process/file
                # ordering differs, including the crash-before-restart case.
                stamp = started - 5 if final_loaded else started + 5
                os.utime(member['config_directory'] + '/server.properties', (stamp, stamp))
                timestamp = subprocess.check_output(['date', '--date=@' + str(started), '+%a %Y-%m-%d %H:%M:%S %Z'], text=True,
                                                    env=dict(os.environ, LC_ALL='C')).strip()
                (root / (member['systemd_unit_name'] + '.state')).write_text(
                    'MainPID=%s\nExecMainStartTimestamp=%s\nActiveState=active\n' % (child.pid, timestamp))

            def observe(expected, confirm=False):
                tasks = [dict(name='Begin observation', **{'ansible.builtin.set_fact': {'kafka_authorization_local_final': True}}),
                         dict(name='Observe all members', **{'ansible.builtin.include_tasks': str(TASKS / 'authorization_observe.yml')},
                              loop=members, loop_control=dict(loop_var='kafka_authorization_member')),
                         dict(name='Check observed result', **{'ansible.builtin.assert': {'that': [
                             'kafka_authorization_local_final | bool == ' + ('true' if expected else 'false')]}})]
                tasks.insert(2, dict(name='Synthetic fixture process diagnostics', **{'ansible.builtin.debug': {'msg': {
                    'systemd': '{{ kafka_authorization_process.stdout }}',
                    'timestamp': '{{ kafka_authorization_start_epoch }}',
                    'mtime': '{{ kafka_authorization_config_stat.stat.mtime }}',
                    'command': '{{ kafka_authorization_command.content | default("missing") }}',
                    'final': '{{ kafka_authorization_running_final }}'}}}))
                if confirm:
                    tasks.append(dict(name='Require runtime finalization', **{'ansible.builtin.include_tasks': str(TASKS / 'authorization_confirm.yml')},
                                      loop=members, loop_control=dict(loop_var='kafka_authorization_member')))
                play = [dict(hosts='localhost', gather_facts=False, connection='local',
                             environment=dict(PATH=str(binary) + ':' + os.environ['PATH'], QA_SYSTEMCTL_STATE=directory), tasks=tasks)]
                path = root / 'check.yml'
                path.write_text(yaml.safe_dump(play))
                runner = subprocess.Popen(['ansible-playbook', '-i', 'localhost,', str(path)], stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE, text=True, start_new_session=True)
                try:
                    stdout, stderr = runner.communicate(timeout=240)
                except subprocess.TimeoutExpired:
                    os.killpg(runner.pid, signal.SIGKILL)
                    stdout, stderr = runner.communicate(timeout=5)
                    self.fail('ISOLATED_ANSIBLE_TIMEOUT: ' + stdout[-1600:] + stderr[-500:])
                result = subprocess.CompletedProcess(runner.args, runner.returncode, stdout, stderr)
                if not expected and confirm:
                    self.assertNotEqual(0, result.returncode)
                    self.assertIn('KAFKA_AUTHORIZATION_RUNTIME_FINALIZATION_REQUIRED', result.stdout)
                else:
                    self.assertEqual(0, result.returncode, result.stdout[-3500:] + result.stderr[-500:])

            try:
                for member in members:
                    process(member, False)
                observe(False)
                observe(False, confirm=True)  # Verify must not repair or pass.
                process(members[0], True)
                observe(False)  # Interrupted after restarting only one member.
                for member in members[1:]:
                    process(member, True)
                observe(True, confirm=True)
            finally:
                for child in children:
                    child.terminate()
                    child.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()

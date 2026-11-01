"""Real delivery/stat/unarchive with distinct controller/target filesystems."""
import copy
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import time
import unittest
import uuid

import yaml

ROOT = Path(__file__).resolve().parents[3]
ROLE = ROOT / 'services/kafka/ansible_collections/platform/kafka/roles/kafka_kraft'
STAGE = Path('/var/tmp/platform-installer/artifacts')

# Test-only local transport enters a private target mount namespace. Module
# upload paths remain shared, but /opt and the approved artifact stage do not.
CONNECTION = '''
import os
import shlex
from ansible.plugins.connection.local import Connection as Local, DOCUMENTATION
DOCUMENTATION = DOCUMENTATION.replace('name: local', 'name: qa_mount')
class Connection(Local):
    transport = 'qa_mount'
    def exec_command(self, cmd, in_data=None, sudoable=True):
        pid = os.environ['KAFKA_QA_NAMESPACE_PID']
        assert pid.isdecimal()
        command = 'sudo -n nsenter --mount --target ' + pid + ' -- /bin/sh -c ' + shlex.quote(cmd)
        return super().exec_command(command, in_data=in_data, sudoable=sudoable)
    def put_file(self, in_path, out_path):
        rc, out, err = self.exec_command('cp -- ' + shlex.quote(in_path) + ' ' + shlex.quote(out_path))
        if rc:
            raise RuntimeError('QA namespace upload failed: ' + err.decode(errors='replace'))
'''


@unittest.skipUnless(shutil.which('ansible-playbook'), 'Ansible runtime required')
class ArtifactLocationRuntimeTests(unittest.TestCase):
    def probe(self, offline=True, failure=None):
        available = subprocess.run(['sudo', '-n', 'unshare', '--mount',
                                    '--propagation', 'private', 'true'], capture_output=True)
        if available.returncode or not STAGE.is_dir():
            self.skipTest('Existing stage and sudo mount namespaces required; no host path changes allowed')
        with tempfile.TemporaryDirectory(prefix='kafka-artifact-location-') as folder:
            base = Path(folder)
            opt, stage = base / 'opt', base / 'stage'
            opt.mkdir()
            stage.mkdir()
            source = base / 'bundle/runtime/artifacts/kafka'
            source.mkdir(parents=True)
            distribution = base / 'distribution/kafka-qa/bin'
            distribution.mkdir(parents=True)
            (distribution / 'kafka-storage.sh').write_text('#!/bin/sh\nexit 0\n')
            (distribution / 'kafka-storage.sh').chmod(0o755)
            archive = source / ('fixture-' + uuid.uuid4().hex + '.tar.gz')
            with tarfile.open(archive, 'w:gz') as stream:
                stream.add(distribution.parent, arcname='kafka-qa')
            checksum = 'sha256:' + hashlib.sha256(archive.read_bytes()).hexdigest()
            controller_stage_path = STAGE / 'kafka-binary' / (checksum[7:] + '-' + archive.name)
            self.assertEqual(1, subprocess.run(
                ['sudo', '-n', 'test', '-e', str(controller_stage_path)], capture_output=True).returncode)
            pidfile = base / 'namespace.pid'
            process = subprocess.Popen([
                'sudo', '-n', 'unshare', '--mount', '--propagation', 'private',
                'sh', '-c', 'mount --bind "$1" /opt && mount --bind "$2" "$3" '
                '&& echo $$ > "$4" && exec sleep 240',
                'kafka-artifact-qa', str(opt), str(stage), str(STAGE), str(pidfile)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            namespace_pid = None
            try:
                deadline = time.monotonic() + 5
                while not pidfile.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertTrue(pidfile.exists(), 'Could not create isolated target mount namespace')
                namespace_pid = pidfile.read_text().strip()
                self.assertTrue(namespace_pid.isdecimal())
                plugins = base / 'connection_plugins'
                plugins.mkdir()
                (plugins / 'qa_mount.py').write_text(CONNECTION)
                apply = yaml.safe_load((ROLE / 'tasks/apply.yml').read_text())
                select = next(task for task in apply if
                              'platform_kafka_artifact_path' in task.get('ansible.builtin.set_fact', {}))
                check = next(task for task in apply if task.get('register') == 'platform_kafka_artifact_stat')
                reject = next(task for task in apply if task['name'] ==
                              'Отклонение отсутствующего или несоответствующего артефакта Kafka')
                unpack = next(task for task in yaml.safe_load((ROLE / 'tasks/prepare_host.yml').read_text())
                              if 'ansible.builtin.unarchive' in task)
                tasks = []
                variables = dict(platform_kafka_verify_only=False, platform_kafka_phase='full',
                    platform_kafka_archive_directory='kafka-qa', platform_kafka_script_extension='.sh',
                    ansible_remote_tmp=str(base / 'remote-tmp'),
                    platform_kafka_artifact_path=str(archive), platform_kafka_artifact_checksum=checksum)
                if offline:
                    variables.update(platform_execution_runtime_root=str(base / 'bundle'),
                        platform_artifact_delivery_requirements=[{'id': 'kafka-binary', 'name': 'kafka'}],
                        platform_resolved_artifact_sources={'kafka-binary': {
                            'source': 'OFFLINE_BUNDLE', 'artifacts': [{
                                'ref': str(archive.relative_to(base / 'bundle')),
                                'sha256': checksum, 'type': 'archive'}]}})
                    tasks += [{'ansible.builtin.include_role': {'name': 'platform.core.artifact_delivery'}},
                              copy.deepcopy(select)]
                if failure == 'missing':
                    tasks.append({'ansible.builtin.file': {
                        'path': '{{ platform_kafka_artifact_path }}', 'state': 'absent'}})
                if failure == 'checksum':
                    tasks.append({'ansible.builtin.copy': {
                        'content': 'corrupted after delivery', 'dest': '{{ platform_kafka_artifact_path }}'}})
                tasks += [copy.deepcopy(check), copy.deepcopy(reject), copy.deepcopy(unpack)]
                play = base / 'play.yml'
                play.write_text(yaml.safe_dump([dict(hosts='kafka_target', gather_facts=False,
                    vars=variables, tasks=tasks)], sort_keys=False))
                inventory = base / 'hosts.yml'
                inventory.write_text(yaml.safe_dump({'all': {'hosts': {
                    'kafka_target': {'ansible_connection': 'qa_mount'},
                    'localhost': {'ansible_connection': 'local'}}}}))
                env = dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
                    ANSIBLE_CONNECTION_PLUGINS=str(plugins), KAFKA_QA_NAMESPACE_PID=namespace_pid,
                    ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections'), ANSIBLE_NOCOLOR='1')
                for attempt in range(1 if failure else 2):
                    result = subprocess.run(['ansible-playbook', '-i', str(inventory), str(play)],
                                            env=env, capture_output=True, text=True, timeout=60)
                    output = result.stdout + result.stderr
                    if failure:
                        self.assertNotEqual(0, result.returncode, output[-3000:])
                        self.assertIn('Kafka artifact is missing or its SHA-256', output)
                        self.assertFalse((opt / 'kafka-qa').exists())
                    else:
                        self.assertEqual(0, result.returncode, output[-4000:])
                        self.assertTrue((opt / 'kafka-qa/bin/kafka-storage.sh').exists())
                        if attempt:
                            self.assertRegex(output, r'kafka_target\s+:.*changed=0\s+.*failed=0')
                    self.assertEqual(1, subprocess.run(
                        ['sudo', '-n', 'test', '-e', str(controller_stage_path)], capture_output=True).returncode)
            finally:
                if namespace_pid:
                    subprocess.run(['sudo', '-n', 'kill', '--', namespace_pid], capture_output=True)
                process.wait(timeout=10)
                subprocess.run(['sudo', '-n', 'chown', '-hR',
                    str(os.getuid()) + ':' + str(os.getgid()), str(base)],
                    check=True, capture_output=True)

    def test_delivered_archive_exists_only_on_target_and_repeat_is_unchanged(self):
        self.probe()

    def test_manual_controller_archive_and_repeat_remain_supported(self):
        self.probe(offline=False)

    def test_missing_target_archive_is_rejected_before_unpack(self):
        self.probe(failure='missing')

    def test_corrupt_target_archive_is_rejected_before_unpack(self):
        self.probe(failure='checksum')


if __name__ == '__main__':
    unittest.main()

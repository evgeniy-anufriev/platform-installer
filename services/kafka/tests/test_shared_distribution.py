"""Target-free Ansible checks of shared-distribution safety assertions."""
import copy
import hashlib
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[3]
ROLE = ROOT / 'services/kafka/ansible_collections/platform/kafka/roles/kafka_kraft'


class SharedDistributionTests(unittest.TestCase):
    def probe(self, overrides=None, expected=True):
        shared = yaml.safe_load((ROLE / 'tasks/schema_registry_shared_distribution.yml').read_text())
        registry = yaml.safe_load((ROLE / 'tasks/schema_registry.yml').read_text())[0]['block']
        tasks = [copy.deepcopy(task) for task in shared
                 if 'ansible.builtin.assert' in task or
                 task['name'] == 'Выбор контрольной суммы общего дистрибутива']
        tasks += [copy.deepcopy(task) for task in registry if task['name'] in (
            'Отклонение небезопасного корня установки реестра',
            'Проверка зафиксированного дистрибутива Schema Registry',
            'Определение выбранной программы запуска реестра')]
        tasks.append({'ansible.builtin.assert': {'that': [
            "_platform_kafka_registry_launcher == '/opt/confluent-qa/bin/schema-registry-start'"]}})
        variables = dict(
            platform_kafka_schema_registry_use_kafka_distribution=True,
            platform_kafka_verify_only=True,
            platform_kafka_archive_directory='confluent-qa',
            platform_kafka_schema_registry_install_directory='/opt/confluent-qa',
            platform_kafka_artifact_checksum='sha256:' + 'a' * 64,
            _platform_kafka_shared_marker_stat={'stat': {'isreg': True, 'islnk': False}},
            _platform_kafka_shared_marker={'stdout': 'sha256:' + 'a' * 64},
            _platform_kafka_shared_launcher={'stat': {'isreg': True, 'islnk': False, 'executable': True}},
            _platform_kafka_registry_install_stat={'stat': {'exists': True, 'isdir': True, 'islnk': False}},
            _platform_kafka_registry_jar={'stat': {'isreg': True, 'islnk': False}})
        variables.update(overrides or {})
        with tempfile.TemporaryDirectory(prefix='qa-kafka-shared-') as directory:
            play = Path(directory) / 'probe.yml'
            play.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local',
                gather_facts=False, vars=variables, tasks=tasks)], sort_keys=False))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(play)],
                env=dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg')),
                capture_output=True, text=True, timeout=60)
        self.assertEqual(expected, result.returncode == 0, (result.stdout + result.stderr)[-2500:])

    def test_shared_verify_needs_no_archive_or_separate_registry_source(self):
        self.probe()

    def test_shared_verify_uses_pinned_kafka_digest(self):
        self.probe({'platform_resolved_artifact_sources': {
            'kafka-binary': {'source': 'OFFLINE_BUNDLE', 'artifacts': [{'sha256': 'sha256:' + 'a' * 64}]}}})

    def test_foreign_installation_is_rejected(self):
        self.probe({'platform_kafka_schema_registry_install_directory': '/opt/foreign'}, expected=False)

    def test_missing_symlink_or_wrong_marker_is_rejected(self):
        for overrides in (
            {'_platform_kafka_shared_marker_stat': {'stat': {'exists': False}}},
            {'_platform_kafka_shared_marker_stat': {'stat': {'isreg': True, 'islnk': True}}},
            {'_platform_kafka_shared_marker': {'stdout': 'sha256:' + 'b' * 64}},
        ):
            with self.subTest(overrides=overrides):
                self.probe(overrides, expected=False)

    def test_missing_launcher_or_jar_is_rejected(self):
        for key in ('_platform_kafka_shared_launcher', '_platform_kafka_registry_jar'):
            with self.subTest(key=key):
                self.probe({key: {'stat': {'exists': False}}}, expected=False)

    def test_symlink_installation_is_rejected(self):
        self.probe({'_platform_kafka_registry_install_stat': {
            'stat': {'exists': True, 'isdir': True, 'islnk': True}}}, expected=False)


class SharedDistributionNativeTests(unittest.TestCase):
    def test_fresh_repeat_registry_only_verify_and_interrupted_marker(self):
        """Real production preparation tasks inside an isolated /opt mount."""
        available = subprocess.run(['sudo', '-n', 'unshare', '--mount',
                                    '--propagation', 'private', 'true'], capture_output=True)
        if available.returncode:
            self.skipTest('sudo mount namespace unavailable; no host /opt writes allowed')
        with tempfile.TemporaryDirectory(prefix='qa-kafka-shared-native-') as directory:
            base = Path(directory)
            opt = base / 'opt'
            opt.mkdir()
            distribution = base / 'source/confluent-qa'
            for relative, content in (
                ('bin/kafka-storage', '#!/bin/sh\nexit 0\n'),
                ('bin/schema-registry-start', '#!/bin/sh\nexit 0\n'),
                ('share/java/schema-registry/kafka-schema-registry-qa.jar', 'isolated fixture\n'),
            ):
                path = distribution / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
                path.chmod(0o755 if relative.startswith('bin/') else 0o644)
            archive = base / 'combined.tar.gz'
            with tarfile.open(archive, 'w:gz') as stream:
                stream.add(distribution, arcname=distribution.name)
            digest = 'sha256:' + hashlib.sha256(archive.read_bytes()).hexdigest()
            preparation = yaml.safe_load((ROLE / 'tasks/prepare_host.yml').read_text())
            preparation = [task for task in preparation if task['name'] in (
                'Однократная распаковка разрешённого дистрибутива Kafka',
                'Маркировка распакованного общего дистрибутива Kafka',
                'Указание стабильного пути установки Kafka в утвержденной версии')]
            registry = yaml.safe_load((ROLE / 'tasks/schema_registry.yml').read_text())[0]['block']
            boundary = next(i for i, task in enumerate(registry)
                            if task['name'] == 'Создание группы служб реестра')
            registry = copy.deepcopy(registry[:boundary])
            for task in registry:
                if 'ansible.builtin.include_tasks' in task:
                    task['ansible.builtin.include_tasks'] = str(
                        ROLE / 'tasks' / task['ansible.builtin.include_tasks'])
            defaults = yaml.safe_load((ROLE / 'defaults/main.yml').read_text())
            variables = dict(defaults, platform_kafka_schema_registry_use_kafka_distribution=True,
                platform_kafka_archive_directory='confluent-qa',
                platform_kafka_schema_registry_install_directory='/opt/confluent-qa',
                platform_kafka_schema_registry_version='qa', platform_kafka_script_extension='',
                platform_kafka_artifact_path=str(archive), platform_kafka_artifact_checksum=digest)
            config = str(ROOT / 'ansible-core/ansible.cfg')
            command = ['sudo', '-n', 'unshare', '--mount', '--propagation', 'private',
                'sh', '-c', 'mount --bind "$1" /opt && exec env ANSIBLE_CONFIG="$2" '
                'ansible-playbook -i localhost, "$3"', 'qa-kafka-shared', str(opt), config]
            try:
                for phase in ('fresh', 'repeat', 'schema_registry', 'verify', 'interrupted'):
                    with self.subTest(phase=phase):
                        phase_vars = dict(variables, platform_kafka_verify_only=phase == 'verify')
                        if phase == 'verify':
                            phase_vars['platform_kafka_artifact_path'] = '/missing-verify-archive'
                        if phase == 'interrupted':
                            (opt / 'confluent-qa/.platform-kafka-approved-sha256').unlink()
                        tasks = (preparation if phase in ('fresh', 'repeat', 'interrupted') else []) + registry
                        play = base / (phase + '.yml')
                        play.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local',
                            gather_facts=False, vars=phase_vars, tasks=tasks)], sort_keys=False))
                        result = subprocess.run(command + [str(play)], capture_output=True,
                                                text=True, timeout=120)
                        output = result.stdout + result.stderr
                        if phase == 'interrupted':
                            self.assertNotEqual(0, result.returncode, output[-3000:])
                            self.assertIn('SCHEMA_REGISTRY_SHARED_INSTALL_OWNERSHIP_UNKNOWN', output)
                        else:
                            self.assertEqual(0, result.returncode, output[-3000:])
                            if phase != 'fresh':
                                self.assertRegex(output, r'localhost\s+:.*changed=0\s+.*failed=0')
                            self.assertEqual(digest,
                                (opt / 'confluent-qa/.platform-kafka-approved-sha256').read_text())
            finally:
                # Root-owned files stay inside the temporary mount backing directory.
                subprocess.run(['sudo', '-n', 'chown', '-hR', str(os.getuid()) + ':' + str(os.getgid()),
                                str(opt)], check=True, capture_output=True)


if __name__ == '__main__':
    unittest.main()

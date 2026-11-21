"""Exercise shared and fresh path checks with the production Ansible tasks."""
import importlib.util
import json
import os
from pathlib import Path
import pwd
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
COLLECTIONS = ROOT / 'ansible-core/collections'
TASKS = COLLECTIONS / 'ansible_collections/platform/core/roles/application_runtime/tasks'
MODULE = COLLECTIONS / 'ansible_collections/platform/core/plugins/modules/application_path_observations.py'


class SharedPathRuntimeTests(unittest.TestCase):
    def test_container_list_skips_missing_inspect_and_keeps_ownership_check(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            calls = root / 'calls'
            docker = root / 'docker'
            docker.write_text(
                '#!/bin/sh\n'
                f'printf "%s\\n" "$*" >> "{calls}"\n'
                'case "$1 $2" in\n'
                '  "info --format") echo "{}";;\n'
                '  "compose version") echo "2.0";;\n'
                '  "container ls") test "$5" = "{{.Names}}" && echo "foreign";;\n'
                '  "container inspect") echo \'[{"Config":{"Labels":{"platform.installer.project":"foreign"}}}]\';;\n'
                '  *) exit 2;;\n'
                'esac\n')
            docker.chmod(0o700)
            source = yaml.safe_load((TASKS / 'preflight.yml').read_text())
            checks = [task for task in source[4]['block'] if task.get('name') in (
                'Проверка точного контейнера, не раскрывая среду',
                'Проверка меток владения существующим контейнером')]
            account = pwd.getpwuid(os.getuid()).pw_name
            job = dict(account=account, projectId='expected', libraryId='library', instanceId='instance')
            tasks = [{'ansible.builtin.include_role': dict(
                name='platform.core.application_runtime', tasks_from='discover_runtime'),
                'vars': {'application_runtime_job': job}}]
            for name in ('absent', 'foreign'):
                tasks.append({'ansible.builtin.set_fact': dict(application_runtime_job=dict(
                    job, placement={'containerName': name}))})
                tasks.extend(checks)
            play = root / 'containers.yml'
            play.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False,
                environment={'PATH': str(root) + ':' + os.environ['PATH']},
                vars=dict(application_discovery_key='account', application_runtime_discoveries={},
                          application_runtime_inventory_containers=True,
                          platform_application_registry_config_directory='', application_docker_environment={}),
                tasks=tasks)]))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(play)],
                env=dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(COLLECTIONS)),
                capture_output=True, text=True, timeout=60)
            self.assertEqual(['info --format json', 'compose version --short',
                              'container ls --all --format {{.Names}}', 'container inspect foreign'],
                             calls.read_text().splitlines(), result.stdout + result.stderr)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('fatal: [localhost]', result.stdout)

    def test_marker_swapped_after_stat_and_request_limit(self):
        spec = importlib.util.spec_from_file_location('path_observations', MODULE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / '.owner.json'
            marker.write_text('{"project":"old"}')
            original = module.read_marker

            def swap(parent, name, observed):
                marker.rename(marker.with_suffix('.old'))
                marker.write_text('{"project":"new"}')
                return original(parent, name, observed)

            with patch.object(module, 'read_marker', side_effect=swap), self.assertRaises(ValueError):
                module.observations([], [str(marker)])
            with patch.object(module, 'MAX_PATHS', 1), self.assertRaises(ValueError):
                module.observations(['/one', '/two'], [])

    def run_case(self, root, *, problem=None, batched=True):
        library = root / 'library'
        library.mkdir()
        identity = dict(project='p', library='l', host='localhost')
        (library / '.owner.json').write_text(json.dumps(identity))
        jobs = []
        for index, name in enumerate(('one', 'two')):
            instance = library / name
            instance.mkdir()
            (instance / '.owner.json').write_text(json.dumps(dict(identity, instance=name)))
            jobs.append(dict(index=index, account='qa', projectId='p', libraryId='l', instanceId=name,
                             placement=dict(runtimeDirectory=str(library), runtimePath=name, containerName=name),
                             agentTemplate=None, settings={},
                             configs=[], directoryConfigs=[], archiveConfigs=[], baseFilename='base.yml'))
        if problem == 'output-link':
            (library / 'two' / 'compose.yml').symlink_to('/etc/passwd')
        elif problem == 'marker-link':
            marker = library / 'two' / '.owner.json'
            marker.unlink()
            marker.symlink_to(library / '.owner.json')
        elif problem == 'marker-identity':
            (library / 'two' / '.owner.json').write_text(json.dumps(dict(identity, instance='one')))
        elif problem == 'marker-size':
            (library / 'two' / '.owner.json').write_text(' ' * 16385)
        elif problem == 'ancestor-link':
            (library / 'two' / 'config').symlink_to('/tmp')
        elif problem == 'traversal':
            jobs[1]['placement']['runtimePath'] = '../two'
        source = yaml.safe_load((TASKS / 'preflight.yml').read_text())
        direct_checks = source[4]['block']
        check = next(task for task in direct_checks if task.get('name') == 'Проверка наблюдений путей текущего размещения')
        tasks = [{'ansible.builtin.set_fact': dict(application_runtime_inputs=dict(jobs=jobs))}]
        if batched:
            tasks.append({'ansible.builtin.include_role': dict(
                name='platform.core.application_runtime', tasks_from='observe_paths')})
        for job in jobs:
            tasks.append({'ansible.builtin.set_fact': dict(application_runtime_job=job)})
            if not batched:
                tasks.append({'ansible.builtin.include_role': dict(
                    name='platform.core.application_runtime', tasks_from='observe_paths'),
                    'vars': {'application_host_jobs': ['{{ application_runtime_job }}'],
                             'application_observe_paths_only': True}})
            tasks.append(check)
        play = root / 'play.yml'
        play.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local',
            gather_facts=False, vars=dict(application_host_jobs=jobs,
                application_runtime_use_path_batch=batched, application_home=str(root),
                application_library_path=str(library), application_root=str(library),
                application_uid=str(os.getuid()),
                application_discovery_key='["qa", ""]',
                application_runtime_discoveries={
                    '["qa", ""]': dict(account='qa', uid=str(os.getuid()), home=str(root))}),
            tasks=tasks)]))
        return subprocess.run(['ansible-playbook', '-i', 'localhost,', str(play)],
            env=dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(COLLECTIONS)),
            capture_output=True, text=True, timeout=90)

    def test_batch_and_direct_preflight_have_one_and_two_remote_observations(self):
        for batched, expected in [(True, 1), (False, 2)]:
            with self.subTest(batched=batched), tempfile.TemporaryDirectory() as folder:
                result = self.run_case(Path(folder), batched=batched)
                self.assertEqual(result.returncode, 0, result.stdout[-3000:] + result.stderr)
                self.assertIn('changed=0', result.stdout)
                label = 'Чтение уникальных путей размещений'
                self.assertEqual(result.stdout.count(label), expected)

    def test_batch_rejects_unsafe_paths_and_invalid_markers(self):
        for problem in ('output-link', 'marker-link', 'marker-identity', 'marker-size',
                        'ancestor-link', 'traversal'):
            with self.subTest(problem=problem), tempfile.TemporaryDirectory() as folder:
                result = self.run_case(Path(folder), problem=problem)
                self.assertNotEqual(result.returncode, 0, result.stdout[-3000:])


if __name__ == '__main__':
    unittest.main()

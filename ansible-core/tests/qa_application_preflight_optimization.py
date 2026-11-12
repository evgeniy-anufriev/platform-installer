"""Read-only source and path regressions; execute on the Linux Core QA node."""
import base64
import copy
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import pwd
import subprocess
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / 'ansible-core/collections/ansible_collections/platform/core'
TASKS = CORE / 'roles/application_runtime/tasks'
spec = importlib.util.spec_from_file_location('source_file', CORE / 'plugins/modules/application_source_file.py')
SOURCE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(SOURCE)


class SourceFileTests(unittest.TestCase):
    def test_exact_bytes_empty_utf8_binary_and_large(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source'
            for raw in (b'', 'Настройки\n'.encode(), bytes(range(256)), b'PK\x00\xff' * (3 * 1024 * 1024)):
                with self.subTest(size=len(raw)):
                    path.write_bytes(raw)
                    before = path.stat()
                    result = SOURCE.read_source(str(path))
                    self.assertEqual(raw, base64.b64decode(result['content'], validate=True))
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), result['sha256'])
                    self.assertEqual('base64', result['encoding'])
                    self.assertEqual(before.st_mtime_ns, path.stat().st_mtime_ns)

    def test_missing_symlink_directory_fifo_are_rejected_without_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'file').write_bytes(b'ordinary config')
            (root / 'link').symlink_to(root / 'file')
            os.mkfifo(root / 'fifo')
            for path in (root / 'missing', root / 'link', root, root / 'fifo'):
                with self.subTest(kind=path.name), self.assertRaises((ValueError, OSError)):
                    SOURCE.read_source(str(path))

    def test_unreadable_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'unreadable'
            path.write_bytes(b'ordinary config')
            path.chmod(0)
            try:
                if os.geteuid() == 0:
                    with patch.object(SOURCE.os, 'open', side_effect=PermissionError), self.assertRaises(PermissionError):
                        SOURCE.read_source(str(path))
                else:
                    with self.assertRaises(PermissionError):
                        SOURCE.read_source(str(path))
            finally:
                path.chmod(0o600)

    def test_metadata_change_or_short_read_is_rejected_and_descriptor_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source'
            path.write_bytes(b'ordinary config')
            info = path.stat()
            for field in ('st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_ino', 'st_dev'):
                changed = SimpleNamespace(**{name: getattr(info, name) for name in
                    ('st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_ino', 'st_dev', 'st_mode')})
                setattr(changed, field, getattr(changed, field) + 1)
                with self.subTest(field=field), patch.object(SOURCE.os, 'fstat', side_effect=[info, changed]), \
                        patch.object(SOURCE.os, 'close', wraps=os.close) as close:
                    with self.assertRaises(ValueError):
                        SOURCE.read_source(str(path))
                    close.assert_called_once()
            with patch.object(SOURCE.os, 'fdopen', return_value=io.BytesIO(b'short')), \
                    patch.object(SOURCE.os, 'close', wraps=os.close) as close:
                with self.assertRaises(ValueError):
                    SOURCE.read_source(str(path))
                close.assert_called_once()

    def test_read_failure_closes_descriptor(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source'
            path.write_bytes(b'ordinary config')
            with patch.object(SOURCE.os, 'fdopen', side_effect=OSError), \
                    patch.object(SOURCE.os, 'close', wraps=os.close) as close:
                with self.assertRaises(OSError):
                    SOURCE.read_source(str(path))
                close.assert_called_once()


class NativePreflightOptimizationTests(unittest.TestCase):
    def run_play(self, directory, tasks, variables=None, check=False, inventory='localhost,', environment=None):
        play = Path(directory) / 'play.yml'
        play.write_text(yaml.safe_dump([dict(hosts='all', connection='local', gather_facts=False,
            vars=variables or {}, environment=environment or {}, tasks=tasks)], sort_keys=False), encoding='utf-8')
        command = ['ansible-playbook', '-i', str(inventory), str(play)] + (['--check'] if check else [])
        return subprocess.run(command, env=dict(os.environ,
            ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
            ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections')),
            capture_output=True, text=True, timeout=90)

    def test_host_preflight_assembles_checked_jobs_once_in_placement_order(self):
        for mode in ('shared', 'application', 'different-contexts', 'foreign-marker', 'assets-registry', 'dynamic-hostvars'):
            with self.subTest(mode=mode):
                self.check_host_preflight(mode)

    def check_host_preflight(self, mode):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docker = root / 'docker'
            docker.write_text(
                '#!/bin/sh\n'
                'case "$1 $2" in\n'
                '  "info --format") echo \'{"OSType":"linux","Architecture":"x86_64",'
                '"SecurityOptions":["rootless"],"Swarm":{"LocalNodeState":"inactive"}}\';;\n'
                '  "compose version") echo 2.0;;\n'
                '  "container ls") exit 0;;\n'
                '  "manifest inspect") echo \'{"config":{"digest":"sha256:approved"}}\';;\n'
                '  *) exit 2;;\n'
                'esac\n')
            docker.chmod(0o700)
            template = root / 'compose.j2'
            template.write_text('{{ application_parameters.label }} '
                                '{{ application_environment.IDENTITY }} '
                                '{{ application_runtime.connections.database }} '
                                '{{ library_runtime.connections.database }}')
            if mode == 'dynamic-hostvars':
                template.write_text('{{ hostvars[inventory_hostname].application_instance_id }} '
                                    '{{ hostvars[inventory_hostname].application_config_digest }}\n')
            base = root / 'base.j2'
            base.write_text(
                '{% set peer = hostvars[inventory_hostname] %}'
                '{{ library_runtime.defaults.label }} {{ peer.ansible_host | default(inventory_hostname) }}'
                if mode != 'application' else template.read_text())
            static = root / 'static.conf'
            static.write_bytes(b'ordinary\x00content')
            archive = root / 'files.tar.gz'
            with tarfile.open(archive, 'w:gz') as output:
                output.add(static, arcname='static.conf')
            config_template = root / 'dynamic.j2'
            config_template.write_text('{% set ns = namespace(values={}) %}'
                                       '{% for value in [application_instance_id] %}'
                                       '{% if value %}{% set _ = ns.values.update({"instance": value}) %}{% endif %}'
                                       '{% endfor %}instance={{ ns.values.instance }}\n')
            account = pwd.getpwuid(os.getuid()).pw_name
            jobs, instances = [], {}
            for name in ('second', 'first'):
                jobs.append(dict(
                    hostId='localhost', account=account, projectId='p', libraryId='l',
                    applicationName=name, instanceId=name, inherited=dict(label=name),
                    commonDefaults=dict(label=name if mode == 'different-contexts' else 'shared'),
                    placement=dict(runtimeDirectory=str(root / 'library'), runtimePath=name,
                                   containerName=name, composeProject=name),
                    settings=dict(image='test', command=[], parameters=dict(label=name),
                                  environment=dict(IDENTITY='overridden')),
                    authority=dict(apiVersion='platform.installer/artifact-source-authority/v1alpha2',
                                   kind='ArtifactSourceAuthority', sourcePolicy='REPOSITORY_THEN_OFFLINE',
                                   requirement=dict(artifactType='container-image',
                                                    platform=dict(os='linux', architecture='amd64')),
                                   repository={}, offlineBundle=dict(ref='runtime/artifacts/test.tar')),
                    configs=[], directoryConfigs=[], archiveConfigs=[], agentTemplate=None,
                    appTemplate=str(template), baseTemplate=str(base), baseFilename='base.yml',
                    baseService='base', envSource=None))
                instances[name] = dict(identityEnvironment=dict(IDENTITY=name),
                                       connections=dict(database='instance'))
                if mode == 'assets-registry':
                    job = jobs[-1]
                    job['authority']['requirement'].update(id=name + ':image', imageId='sha256:approved')
                    job['authority']['repository'] = dict(reference='registry.example/test:1', manifestDigest='sha256:' + 'a' * 64)
                    job['configs'] = [dict(source='static.conf', path=str(static), destination='static.conf'),
                                      dict(template='dynamic.j2', path=str(config_template), destination='dynamic.conf')]
                    job['archiveConfigs'] = [dict(path=str(archive), destination='files')]
            stage = yaml.safe_load((ROOT / 'ansible-core/playbooks/applications/stages/preflight.yml').read_text())
            inputs = {'ansible.builtin.set_fact': dict(
                application_runtime_inputs=dict(jobs=jobs + [dict(jobs[0], hostId='unselected')]),
                application_snapshot=dict(snapshot=dict(applicationLibraries=dict(
                    libraries=dict(l=dict(instances=instances, connections=dict(database='shared')))))),
            )}
            expected_base = {
                'shared': ['shared localhost', 'shared localhost'],
                'application': ['second second instance shared', 'first first instance shared'],
                'different-contexts': ['second localhost', 'first localhost'],
                'foreign-marker': [],
                'assets-registry': ['shared localhost', 'shared localhost'],
                'dynamic-hostvars': ['shared localhost', 'shared localhost'],
            }
            if mode == 'foreign-marker':
                library = root / 'library'
                library.mkdir()
                (library / '.owner.json').write_text('{"project":"other","library":"l","host":"localhost"}')
            stage_tasks = stage[2]['tasks']
            if mode in ('application', 'different-contexts'):
                stage_tasks[-1]['no_log'] = False  # This fixture contains only synthetic values.
            expected_compose = ['second second instance shared', 'first first instance shared']
            if mode == 'dynamic-hostvars':
                digest = hashlib.sha256(b'[]').hexdigest()
                expected_compose = [f'{name} {digest}\n' for name in ('second', 'first')]
            tasks = [inputs, stage[1]['tasks'][-1]] + stage_tasks + [{'ansible.builtin.assert': {'that': [
                'platform_application_preflight_jobs | map(attribute="instanceId") | list == ["second", "first"]',
                'application_host_jobs | map(attribute="index") | list == [0, 1]',
                'application_host_jobs | selectattr("settings", "defined") | list | length == 0',
                'platform_application_preflight_jobs | map(attribute="composeContent") | list == ' +
                repr(expected_compose),
                'platform_application_preflight_jobs | map(attribute="source.source") | unique | list == ' +
                repr(['REPOSITORY' if mode == 'assets-registry' else 'OFFLINE_BUNDLE']),
                'platform_application_preflight_jobs | map(attribute="baseContent") | list == ' +
                repr(expected_base[mode]),
                '_application_shared_base | length == ' + str(
                    {'application': 0, 'shared': 1, 'different-contexts': 2, 'foreign-marker': 0,
                     'assets-registry': 1, 'dynamic-hostvars': 1}[mode]),
                '_application_shared_env | length == 1',
                'hostvars["localhost"]._application_preflight_native == ' + ('true' if mode == 'dynamic-hostvars' else 'false'),
                'platform_application_preflight_jobs[0].dockerEnvironment.DOCKER_CONFIG == ' +
                ('registry_config' if mode == 'application' else 'platform_application_preflight_jobs[0].home ~ "/.docker"'),
            ]}, 'no_log': True}]
            variables = dict(ansible_connection='local', ansible_become=False)
            if mode == 'application':
                variables['registry_config'] = str(root / 'registry')
                variables['platform_application_registry_config_directory'] = variables['registry_config']
            if mode == 'assets-registry':
                variables['platform_application_approved_registries'] = ['registry.example']
                tasks[-1]['ansible.builtin.assert']['that'].extend([
                    'platform_application_preflight_jobs | map(attribute="source.requirement.id") | list == ["second:image", "first:image"]',
                    'platform_application_preflight_jobs[0].configContents[0].content == "instance=second\n"',
                    'platform_application_preflight_jobs[1].configContents[0].content == "instance=first\n"',
                    'platform_application_preflight_jobs[0].configContents[1].content == ' + repr(base64.b64encode(static.read_bytes()).decode()),
                    'platform_application_preflight_jobs[1].archiveChecksums.files == ' + repr(hashlib.sha256(archive.read_bytes()).hexdigest()),
                ])
            result = self.run_play(directory, tasks, variables,
                                   environment={'PATH': str(root) + ':' + os.environ['PATH']})
            if mode == 'foreign-marker':
                self.assertNotEqual(0, result.returncode)
                self.assertIn('Проверка путей и маркеров всех размещений узла', result.stdout)
                self.assertNotIn('Запись неизменяемого контекста', result.stdout)
                return
            if mode in ('application', 'different-contexts'):
                self.assertNotEqual(0, result.returncode)
                self.assertIn('APPLICATION_LIBRARY_HOST_PROJECTION_CONFLICT', result.stdout)
                return
            self.assertEqual(0, result.returncode, (result.stdout + result.stderr)[-3500:])
            self.assertIn('changed=0', result.stdout)
            self.assertEqual(1, result.stdout.count('Чтение уникальных путей размещений'))
            self.assertEqual(1, result.stdout.count('Проверка путей и маркеров всех размещений узла'))
            self.assertEqual(1, result.stdout.count('Подготовка корней библиотек для выбранного узла'))
            self.assertEqual(1, result.stdout.count('Подготовка окружения Docker один раз'))
            self.assertEqual(1, result.stdout.count('Чтение уникальных исходных файлов'))
            self.assertEqual(1, result.stdout.count(
                'Запись неизменяемого контекста предварительной проверки размещений узла'))
            self.assertEqual(2 if mode == 'dynamic-hostvars' else int(mode == 'assets-registry'),
                             result.stdout.count(
                                 'Запись неизменяемого контекста предварительной проверки размещения приложения'))
            if mode not in ('dynamic-hostvars', 'assets-registry'):
                self.assertNotIn('Предварительная проверка выбранного реестра', result.stdout)
                self.assertNotIn('Чтение объявленных исходных файлов', result.stdout)
            if mode != 'dynamic-hostvars':
                self.assertEqual(int(mode == 'assets-registry'),
                                 result.stdout.count('Проверка только утвержденного неизменяемого манифеста'))
            if mode not in ('dynamic-hostvars', 'assets-registry'):
                self.assertNotIn('Проверка точного контейнера, не раскрывая среду', result.stdout)
                self.assertNotIn('Проверка доступности публикуемых портов до записи файлов', result.stdout)
            self.assertNotIn('Проверка отсутствия пересечений каталогов библиотек перед записью файлов',
                             result.stdout)
            self.assertEqual(1, result.stdout.count('Сбор результатов предварительной проверки размещений узла'))

    def test_shared_template_subset_accepts_stock_bases_and_rejects_dynamic_inputs(self):
        paths = [ROOT / 'examples' / name / 'library-packages' / name / '1.0.0' /
                 'roles' / ('library_' + name) / 'templates/.base_compose.yml.j2'
                 for name in ('szi', 'sdku')]
        with tempfile.TemporaryDirectory() as directory:
            for index, source in enumerate((
                    "{{ lookup('env', 'HOME') }}",
                    "{% include 'other.j2' %}",
                    "{{ hostvars[inventory_hostname].application_environment }}",
                    "{{ application_instance_id | default('shared') }}",
                    "{% if false %}{% set name = 'shared' %}{% endif %}{{ name }}",
            )):
                path = Path(directory) / f'base-{index}.j2'
                path.write_text(source)
                paths.append(path)
            result = self.run_play(directory, [
                {'ansible.builtin.set_fact': {'shared_templates':
                    '{{ jobs | platform.core.application_preflight_shared_templates(hostvars) }}'}},
                {'ansible.builtin.assert': {'that': [
                    'shared_templates.base[item] == (index < 2)'],
                }, 'loop': [str(path) for path in paths], 'loop_control': {'index_var': 'index'}},
            ], dict(jobs=[dict(baseTemplate=str(path)) for path in paths]))
            self.assertEqual(0, result.returncode, (result.stdout + result.stderr)[-3500:])

    def test_production_source_tasks_binary_parity_repeat_check_mode_and_redaction(self):
        with tempfile.TemporaryDirectory() as directory:
            configs, expected = [], []
            marker = 'PREFLIGHT_CONTENT_MUST_NOT_BE_LOGGED'
            for index, raw in enumerate((marker.encode(), b'', bytes(range(256)) * 4096)):
                path = Path(directory) / str(index)
                path.write_bytes(raw)
                configs.append(dict(path=str(path), destination=str(index), mode='0640'))
                expected.append(hashlib.sha256(raw).hexdigest())
            tasks = [dict(name='Read production source tasks', **{'ansible.builtin.include_tasks': str(TASKS / 'source_config.yml')},
                loop=configs, loop_control=dict(loop_var='application_config'), no_log=True),
                {'ansible.builtin.assert': {'that': [
                    'application_config_contents | platform.core.application_validate_configs',
                    'application_config_contents | map(attribute="sha256") | list == expected',
                    'application_config_contents | map(attribute="mode") | unique | list == ["0640"]']}, 'no_log': True}]
            for check in (False, False, True):
                result = self.run_play(directory, tasks, dict(application_config_contents=[], expected=expected), check=check)
                self.assertEqual(0, result.returncode, (result.stdout + result.stderr)[-2500:])
                self.assertIn('changed=0', result.stdout)
                self.assertNotIn(marker, result.stdout + result.stderr)
                self.assertNotIn(base64.b64encode(marker.encode()).decode(), result.stdout + result.stderr)

    def test_source_failure_and_secret_detection_do_not_expose_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source'
            marker = 'PREFLIGHT_PRIVATE_CONTENT_MUST_NOT_BE_LOGGED'
            path.write_text('-----BEGIN PRIVATE KEY-----\n' + marker)
            link = Path(directory) / 'link'
            link.symlink_to(path)
            for source in (path, link):
                result = self.run_play(directory, [
                    {'ansible.builtin.include_tasks': str(TASKS / 'source_config.yml')},
                    {'ansible.builtin.assert': {'that': 'application_config_contents | platform.core.application_validate_configs'}, 'no_log': True}],
                    dict(application_config_contents=[], application_config=dict(path=str(source), destination='config')))
                self.assertNotEqual(0, result.returncode)
                self.assertNotIn(marker, result.stdout + result.stderr)
                self.assertNotIn(base64.b64encode(path.read_bytes()).decode(), result.stdout + result.stderr)

    def test_read_records_feed_production_copy_and_repeat_without_changes(self):
        copy_task = next(task for task in yaml.safe_load((TASKS / 'apply_instance.yml').read_text())
                         if task.get('name') == 'Запись файлов конфигурации экземпляра')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'instance'
            (target / 'config/lib').mkdir(parents=True)
            raw = bytes(range(256)) * 4096
            source = root / 'source.bin'
            source.write_bytes(raw)
            tasks = [{'ansible.builtin.include_tasks': str(TASKS / 'source_config.yml')},
                     {'ansible.builtin.assert': {'that': 'application_config_contents | platform.core.application_validate_configs'}, 'no_log': True},
                     copy_task]
            variables = dict(application_config_contents=[],
                application_config=dict(path=str(source), destination='lib/source.bin', mode='0640'),
                application_runtime_job=dict(instancePath=str(target), account=pwd.getpwuid(os.getuid()).pw_name,
                    configContents='{{ application_config_contents }}'))
            for repeat in (False, True):
                result = self.run_play(directory, tasks, variables)
                self.assertEqual(0, result.returncode, (result.stdout + result.stderr)[-2000:])
                self.assertEqual(raw, (target / 'config/lib/source.bin').read_bytes())
                self.assertEqual(0o640, (target / 'config/lib/source.bin').stat().st_mode & 0o777)
                if repeat:
                    self.assertIn('changed=0', result.stdout)

    def test_overlap_filter_keeps_equal_ancestor_descendant_case_and_sibling_semantics(self):
        original = next(task for task in yaml.safe_load((TASKS / 'resolve_paths.yml').read_text())
                        if task.get('ansible.builtin.assert', {}).get('fail_msg') == 'APPLICATION_LIBRARY_PATH_OVERLAP')
        cases = [([], '/srv/apps/a', True, 0),
                 ([dict(libraryId='current', libraryPath='/srv/apps/a')]*5, '/srv/apps/a', True, 0),
                 ([dict(libraryId='other', libraryPath='/srv/apps/b')]*5, '/srv/apps/a', True, 1),
                 ([dict(libraryId='other', libraryPath='/srv/apps/a')], '/srv/apps/a', False, 1),
                 ([dict(libraryId='other', libraryPath='/srv/apps')], '/srv/apps/a', False, 1),
                 ([dict(libraryId='other', libraryPath='/srv/apps/a/child')], '/srv/apps/a', False, 1),
                 ([dict(libraryId='other', libraryPath='/srv/apps/ab')], '/srv/apps/a', True, 1),
                 ([dict(libraryId='other', libraryPath=p) for p in ['/srv/apps/a', '/srv/apps/A']], '/srv/apps/A', False, 2)]
        with tempfile.TemporaryDirectory() as directory:
            tasks = []
            for jobs, root, passed, count in cases:
                overlap = copy.deepcopy(original)
                overlap['register'] = 'overlap_result'
                tasks += [{'ansible.builtin.set_fact': dict(platform_application_preflight_jobs=jobs,
                            application_root=root, overlap_failed=False)},
                          {'block': [overlap], 'rescue': [{'ansible.builtin.set_fact': dict(overlap_failed=True)}]},
                          {'ansible.builtin.assert': {'that': [
                              'overlap_failed == ' + str(not passed),
                              '(overlap_result.results | default([]) | length) == ' + str(count)]}}]
            result = self.run_play(directory, tasks, dict(application_runtime_job=dict(libraryId='current')))
            self.assertEqual(0, result.returncode, (result.stdout + result.stderr)[-3000:])

    def test_overlap_observations_stay_host_local(self):
        overlap = next(task for task in yaml.safe_load((TASKS / 'resolve_paths.yml').read_text())
                       if task.get('ansible.builtin.assert', {}).get('fail_msg') == 'APPLICATION_LIBRARY_PATH_OVERLAP')
        with tempfile.TemporaryDirectory() as directory:
            inventory = Path(directory) / 'inventory.yml'
            inventory.write_text(yaml.safe_dump(dict(all=dict(hosts=dict(
                first=dict(application_root='/srv/apps/a', platform_application_preflight_jobs=[dict(libraryId='other', libraryPath='/srv/apps/b')]),
                second=dict(application_root='/srv/apps/b', platform_application_preflight_jobs=[dict(libraryId='other', libraryPath='/srv/apps/a')]))))))
            result = self.run_play(directory, [overlap], dict(application_runtime_job=dict(libraryId='current')), inventory=inventory)
            self.assertEqual(0, result.returncode, (result.stdout + result.stderr)[-2000:])

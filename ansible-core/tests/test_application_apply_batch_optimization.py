"""Batch Apply preserves bytes, ownership, CAS and bounded image observations."""
import base64
import copy
import hashlib
import os
from pathlib import Path
import pwd
import sys
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'ansible-core/collections'), str(ROOT / 'services/vault')]
from ansible_collections.platform.core.plugins.filter.application_runtime import image_delivery_jobs
from ansible_collections.platform.core.plugins.modules.application_identity_files import write_configs
from ansible_collections.platform.vault.plugins.action.application_document import ActionModule as VaultAction, reconcile_documents, reconcile_identity


class BatchImageTests(unittest.TestCase):
    def test_native_cold_delivery_and_warm_tag_keep_conditional_valid(self):
        image = dict(Id='sha256:a', Os='linux', Architecture='amd64', RepoTags=[])
        import json
        for observation, present in ((None, False), (image, True), ('unobserved', False)):
            with self.subTest(observation=observation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                state, calls = root / 'loaded', root / 'calls'
                if present:
                    state.touch()
                docker = root / 'docker'
                docker.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "' + str(calls) + '"\n'
                    'case "$1 $2" in\n'
                    '"load --input") touch "' + str(state) + '";;\n'
                    '"image inspect") test -f "' + str(state) + '" || exit 1; '
                    "printf '%s\\n' '" + json.dumps([image]) + "';;\n"
                    'tag*) ;;\n*) exit 2;;\nesac\n')
                docker.chmod(0o700)
                archive = root / 'archive'
                archive.write_bytes(b'bounded offline fixture')
                job = dict(self.job(pwd.getpwuid(os.geteuid()).pw_name),
                    dockerEnvironment=dict(PATH=str(root) + ':' + os.environ['PATH']),
                    source=dict(source='OFFLINE_BUNDLE'), libraryPath=str(root), archivePath=str(archive))
                job['authority']['offlineBundle'] = dict(
                    sha256='sha256:' + hashlib.sha256(archive.read_bytes()).hexdigest(), size=archive.stat().st_size)
                if observation != 'unobserved':
                    job['observedLocalImage'] = observation
                play = root / 'play.yml'
                play.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False,
                    vars=dict(application_runtime_job=job), tasks=[dict(
                        name='Deliver the selected image through actual tasks',
                        **{'ansible.builtin.include_tasks': str(ROOT / 'ansible-core/collections/ansible_collections/platform/core/roles/application_runtime/tasks/image_delivery.yml')})])], sort_keys=False))
                result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(play)],
                    capture_output=True, text=True, timeout=90)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertEqual(0 if present else 1,
                    sum(line.startswith('load --input') for line in calls.read_text().splitlines()))
                self.assertFalse(list(root.glob('.application-image-*')))

    def job(self, account='first'):
        return dict(account=account, settings=dict(image='qa:one'),
                    authority=dict(requirement=dict(imageId='sha256:a', platform=dict(os='linux', architecture='amd64'))))

    def test_existing_image_and_tag_need_no_delivery_for_100_placements(self):
        observation = dict(item=['first', []], rc=0,
            stdout='[{"Id":"sha256:a","Os":"linux","Architecture":"amd64","RepoTags":["qa:one"]}]')
        self.assertEqual([], image_delivery_jobs([self.job() for _ in range(100)], [observation]))

    def test_native_library_path_inspects_100_placements_in_one_docker_call(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docker = root / 'docker'
            docker.write_text('#!/bin/sh\nprintf "inspect\\n" >> "' + str(root / 'calls') + '"\n'
                'printf \'[{"Id":"sha256:a","Os":"linux","Architecture":"amd64","RepoTags":["qa:one"]}]\\n\'\n')
            docker.chmod(0o700)
            account = pwd.getpwuid(os.geteuid()).pw_name
            jobs = [dict(self.job(account), dockerEnvironment=dict(PATH=str(root) + ':' + os.environ['PATH']))
                    for _ in range(100)]
            source = yaml.safe_load((ROOT / 'ansible-core/playbooks/applications/tasks/ordered-library.yml').read_text())
            tasks = [task for task in source if task['name'] in (
                'Пакетная проверка образов библиотеки для каждой учётной записи узла',
                'Доставка выбранных образов библиотеки перед выполнением сценариев pre_start')]
            play = root / 'play.yml'
            play.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False,
                vars=dict(application_library_runtime_jobs=jobs), tasks=tasks)], sort_keys=False))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(play)], capture_output=True,
                text=True, timeout=60, env=dict(os.environ,
                ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections')))
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual(['inspect'], (root / 'calls').read_text().splitlines())

    def test_missing_tag_retains_local_image_and_accounts_are_isolated(self):
        observed = dict(item=['first', []], rc=0,
            stdout='[{"Id":"sha256:a","Os":"linux","Architecture":"amd64","RepoTags":[]}]')
        missing = dict(item=['second', []], rc=1, stdout='[]')
        jobs = image_delivery_jobs([self.job(), self.job('second')], [observed, missing])
        self.assertEqual('sha256:a', jobs[0]['observedLocalImage']['Id'])
        self.assertIsNone(jobs[1]['observedLocalImage'])

    def test_cold_image_is_delivered_once_for_repeated_placements_and_aliases(self):
        jobs = [self.job() for _ in range(100)]
        jobs.append(dict(self.job(), settings=dict(image='qa:alias')))
        pending = image_delivery_jobs(jobs, [dict(item=['first', []], rc=1, stdout='[]')])
        self.assertEqual(2, len(pending))
        self.assertIsNone(pending[0]['observedLocalImage'])
        self.assertEqual('sha256:a', pending[1]['observedLocalImage']['Id'])

    def test_platform_mismatch_and_docker_failure_are_rejected(self):
        for response in [dict(rc=2, stdout='[]'), dict(rc=0,
            stdout='[{"Id":"sha256:a","Os":"linux","Architecture":"arm64","RepoTags":["qa:one"]}]')]:
            with self.subTest(response=response), self.assertRaises(Exception):
                image_delivery_jobs([self.job()], [dict(response, item=['first', []])])


class ConfigurationBatchTests(unittest.TestCase):
    def test_exact_binary_bytes_modes_noop_and_repair(self):
        account = pwd.getpwuid(os.geteuid())
        with tempfile.TemporaryDirectory(dir=account.pw_dir) as directory:
            root = Path(directory)
            (root / 'config').mkdir(mode=0o700)
            raw = b'\x00\xff\x01\n'
            rows = [dict(destination='binary', content=base64.b64encode(raw).decode(), encoding='base64',
                         sha256=hashlib.sha256(raw).hexdigest(), mode='0640')]
            self.assertEqual([str(root / 'config/binary')], write_configs(account.pw_name, directory, rows))
            target = root / 'config/binary'
            self.assertEqual(raw, target.read_bytes())
            self.assertEqual(0o640, target.stat().st_mode & 0o777)
            identity = target.stat().st_ino
            self.assertEqual([], write_configs(account.pw_name, directory, rows))
            self.assertEqual(identity, target.stat().st_ino)
            target.chmod(0o600)
            self.assertTrue(write_configs(account.pw_name, directory, rows))
            target.unlink()
            target.symlink_to(root / 'outside')
            with self.assertRaises(OSError):
                write_configs(account.pw_name, directory, rows)
            self.assertFalse((root / 'outside').exists())

    def test_traversal_wrong_digest_and_duplicate_destinations_are_rejected(self):
        account = pwd.getpwuid(os.geteuid())
        with tempfile.TemporaryDirectory(dir=account.pw_dir) as directory:
            (Path(directory) / 'config').mkdir()
            row = dict(destination='probe', content='fixture', sha256=hashlib.sha256(b'fixture').hexdigest(), mode='0644')
            for rows in [[dict(row, destination='../outside')], [dict(row, sha256='0' * 64)], [row, row]]:
                with self.subTest(rows=rows), self.assertRaises(ValueError):
                    write_configs(account.pw_name, directory, rows)
            self.assertEqual([], list((Path(directory) / 'config').iterdir()))

    def test_check_mode_reports_missing_files_without_creating_directories(self):
        account = pwd.getpwuid(os.geteuid())
        with tempfile.TemporaryDirectory(dir=account.pw_dir) as directory:
            root = str(Path(directory) / 'missing')
            rows = [dict(destination='config', content='fixture', mode='0644',
                         sha256=hashlib.sha256(b'fixture').hexdigest())]
            self.assertEqual([root + '/config/config'], write_configs(account.pw_name, root, rows, True))
            self.assertFalse(Path(root).exists())

    def test_owned_absolute_runtime_directory_outside_home_remains_supported(self):
        account = pwd.getpwuid(os.geteuid())
        with tempfile.TemporaryDirectory(dir='/var/tmp') as directory:
            (Path(directory) / 'config').mkdir(mode=0o700)
            rows = [dict(destination='config', content='fixture', mode='0644',
                         sha256=hashlib.sha256(b'fixture').hexdigest())]
            self.assertTrue(write_configs(account.pw_name, directory, rows))
            self.assertEqual('fixture', (Path(directory) / 'config/config').read_text())


class VaultBatchTests(unittest.TestCase):
    def test_check_mode_skips_mutating_operations_before_reading_credentials(self):
        for operation in ('documents', 'identity'):
            action = VaultAction.__new__(VaultAction)
            action._task = SimpleNamespace(args=dict(operation=operation), check_mode=True)
            self.assertEqual(dict(changed=False, skipped=True), action.run())

    def state(self, value='before', reused=False, owner='qa-owner'):
        return dict(status=200, reused=reused, json=dict(data=dict(
            data=dict(password=value, _platform_owner=owner, unrelated='preserve'), metadata=dict(version=4))))

    def test_unchanged_reused_document_has_one_fresh_read_and_no_write(self):
        requests = []
        document = dict(mount='secret', document='qa/account', owner='qa-owner')
        def request(method, path, body=None):
            requests.append((method, path))
            return self.state()
        changed = reconcile_documents([document], 'vault', {'vault:secret/qa/account': self.state(reused=True)},
            {'vault:secret/qa/account': dict(password='before')}, request)
        self.assertFalse(changed)
        self.assertEqual([('GET', 'secret/data/qa/account')], requests)

    def test_cas_conflict_retries_once_preserving_unrelated_fields(self):
        document = dict(mount='secret', document='qa/account', owner='qa-owner')
        calls = []
        def request(method, path, body=None):
            calls.append((method, copy.deepcopy(body)))
            if len(calls) == 1:
                return dict(status=400, json=dict(errors=['check-and-set parameter did not match']))
            if method == 'GET':
                state = self.state()
                state['json']['data']['metadata']['version'] = 5
                return state
            return dict(status=200)
        self.assertTrue(reconcile_documents([document], 'vault', {'vault:secret/qa/account': self.state()},
            {'vault:secret/qa/account': dict(password='after')}, request))
        self.assertEqual(['PATCH', 'GET', 'PATCH'], [call[0] for call in calls])
        self.assertEqual(dict(options=dict(cas=5), data=dict(password='after')), calls[-1][1])

    def test_fresh_foreign_owner_is_rejected_before_write(self):
        document = dict(mount='secret', document='qa/account', owner='qa-owner')
        calls = []
        def request(method, path, body=None):
            calls.append(method)
            return self.state(owner='another-owner')
        with self.assertRaises(Exception):
            reconcile_documents([document], 'vault', {'vault:secret/qa/account': self.state(reused=True)},
                {'vault:secret/qa/account': dict(password='before')}, request)
        self.assertEqual(['GET'], calls)

    def test_second_cas_conflict_stops_after_one_retry(self):
        document = dict(mount='secret', document='qa/account', owner='qa-owner')
        calls = []
        def request(method, path, body=None):
            calls.append(method)
            return self.state() if method == 'GET' else dict(status=400, json=dict(errors=['check-and-set conflict']))
        with self.assertRaisesRegex(ValueError, 'APPLICATION_VAULT_DOCUMENT_CAS_CONFLICT'):
            reconcile_documents([document], 'vault', {'vault:secret/qa/account': self.state()},
                {'vault:secret/qa/account': dict(password='after')}, request)
        self.assertEqual(['PATCH', 'GET', 'PATCH'], calls)

    def test_unchanged_identity_reads_role_id_without_writes(self):
        role = dict(token_policies=['qa-role'], token_type='service')
        current = [dict(status=200, json=dict(data=dict(policy='# qa-owner\npolicy'))),
                   dict(status=200, json=dict(data=role))]
        calls = []
        def request(method, path, body=None):
            calls.append(method)
            return dict(status=200, json=dict(data=dict(role_id='qa-role-id')))
        result = reconcile_identity('qa-role', 'qa-owner', '# qa-owner\npolicy', role, current, request)
        self.assertFalse(result['changed'])
        self.assertEqual(['GET'], calls)


if __name__ == '__main__':
    unittest.main()

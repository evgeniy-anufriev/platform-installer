"""Run generic batch jobs and standard source delivery through actual Ansible tasks."""
import json
import os
from pathlib import Path
import pwd
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
ROLE = ROOT / 'ansible-core/collections/ansible_collections/platform/core/roles/package_script/tasks/main.yml'


class PackageBatchRuntimeTests(unittest.TestCase):
    @unittest.skipUnless(os.geteuid() == 0, 'isolated ownership fixture requires sudo -n')
    def test_neighbor_substitution_across_accounts_is_repaired_by_copy(self):
        with tempfile.TemporaryDirectory(prefix='qa-script-neighbor-owner-') as directory:
            root = Path(directory)
            root.chmod(0o755)
            first, second = root / 'first.sh', root / 'second.sh'
            first.write_text('#!/bin/sh\nprintf "A\\n" >> "$PWD/seen"\n'
                             'printf \'{"status":"ok","changed":false}\\n\'\n')
            second.write_text('''#!/bin/sh
set -eu
[ "$(id -un)" = nobody ]
rm "$PWD/.scripts/first"
cat > "$PWD/.scripts/first" <<'SUBSTITUTED'
#!/bin/sh
printf 'TAMPER\n' >> "$PWD/seen"
printf '{"status":"ok","changed":false}\n'
SUBSTITUTED
chmod 0700 "$PWD/.scripts/first"
printf '{"status":"ok","changed":false}\n'
''')
            jobs = [dict(self.job(root, first), id='first'),
                    dict(self.job(root, second), id='second', account='nobody'),
                    dict(self.job(root, first), id='first')]
            tasks = [self.call(job) for job in jobs]
            for task in tasks:
                task['ansible.builtin.include_role']['apply'] = {'become': True}
            self.run_play(root, tasks)
            self.assertEqual(['A', 'A'], (root / 'seen').read_text().splitlines())
            copied = root / '.scripts/first'
            self.assertEqual(first.read_bytes(), copied.read_bytes())
            self.assertEqual(0, copied.stat().st_uid)
            self.assertEqual(0o700, copied.stat().st_mode & 0o777)

    def test_timeout_is_the_sum_of_original_invocation_limits(self):
        source = yaml.safe_load(ROLE.read_text())
        command = next(t for task in source for t in task.get('block', [])
                       if t.get('name') == 'Выполнение точного сценария пакета без оболочки или неограниченной среды выполнения')
        with tempfile.TemporaryDirectory(prefix='qa-script-timeout-') as directory:
            root = Path(directory)
            tasks = []
            for count, expected in [(0, '300s'), (1, '300s'), (3, '900s')]:
                tasks.extend([
                    {'ansible.builtin.set_fact': {'rendered_argv': command['ansible.builtin.command']['argv']},
                     'vars': dict(platform_script_directory='/unused', platform_script_job=dict(
                         id='probe', argv=[], invocations=[['input']] * count))},
                    {'ansible.builtin.assert': {'that': "rendered_argv[2] == '" + expected + "'"}}])
            self.run_play(root, tasks)

    def run_play(self, directory, tasks, success=True):
        play = directory / 'probe.yml'
        play.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False,
                                             tasks=tasks)], sort_keys=False))
        result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(play)],
                                env=dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections')),
                                capture_output=True, text=True, timeout=90)
        self.assertEqual(success, result.returncode == 0, (result.stdout + result.stderr)[-2500:])
        self.assertNotIn('private-probe-value', result.stdout + result.stderr)
        return result

    def job(self, work, script, **fields):
        return dict(id='probe', path=str(script), workingDirectory=str(work),
                    account=pwd.getpwuid(os.getuid()).pw_name, argv=[], secretInputs={},
                    **fields)

    def call(self, job, **variables):
        return {'ansible.builtin.include_role': {'name': 'platform.core.package_script'},
                'vars': dict(platform_script_job=job, platform_script_secret_files={}, **variables)}

    def test_batch_without_secrets_preserves_literal_arguments_and_cleans_up(self):
        with tempfile.TemporaryDirectory(prefix='qa-script-batch-') as directory:
            root = Path(directory)
            script = root / 'probe.sh'
            script.write_text('#!/bin/sh\nset -eu\n[ "$#" -eq 0 ]\n'
                              '[ "$(stat -c %a "$PLATFORM_SCRIPT_BATCH_FILE")" = 600 ]\n'
                              'cp "$PLATFORM_SCRIPT_BATCH_FILE" "$PWD/observed.json"\n'
                              'printf \'{"status":"ok","changed":false}\\n\'\n')
            invocations = [['first', 'line\nbreak'], ['second', '; touch must-not-exist']]
            job = self.job(root, script, invocations=invocations)
            self.run_play(root, [self.call(job)])
            self.assertEqual(invocations, json.loads((root / 'observed.json').read_text()))
            self.assertFalse((root / '.scripts/.secrets/probe').exists())
            self.assertFalse((root / 'must-not-exist').exists())

    def test_standard_copy_preserves_a_b_a_and_working_directory(self):
        with tempfile.TemporaryDirectory(prefix='qa-script-reuse-') as directory:
            root = Path(directory)
            scripts = []
            for name in ['A', 'B']:
                script = root / (name + '.sh')
                script.write_text('#!/bin/sh\nprintf "' + name + '\\n" >> "$PWD/seen"\n'
                                  'printf \'{"status":"ok","changed":false}\\n\'\n')
                scripts.append(script)
            jobs = [self.job(root, scripts[index]) for index in [0, 1, 0, 0]]
            tasks = [self.call(job) for job in jobs]
            other = root / 'other'
            other.mkdir()
            tasks.append(self.call(self.job(other, scripts[0])))
            self.run_play(root, tasks)
            self.assertEqual(['A', 'B', 'A', 'A'], (root / 'seen').read_text().splitlines())
            self.assertEqual(['A'], (other / 'seen').read_text().splitlines())

    def test_missing_source_fails_before_script_execution(self):
        with tempfile.TemporaryDirectory(prefix='qa-script-copy-fail-') as directory:
            root = Path(directory)
            script = root / 'ok.sh'
            script.write_text('#!/bin/sh\nprintf \'{"status":"ok","changed":false}\\n\'\n')
            job = self.job(root, script)
            bad = dict(job, path=str(root / 'absent.sh'))
            tasks = [self.call(job), {'block': [self.call(bad),
                {'ansible.builtin.fail': {'msg': 'COPY_FAILURE_EXPECTED'}}], 'rescue': [
                {'ansible.builtin.assert': {'that': [
                    "'COPY_FAILURE_EXPECTED' not in (ansible_failed_result.msg | default(''))"]}}]}]
            self.run_play(root, tasks)

    def test_failed_batch_hides_secret_and_removes_inputs(self):
        with tempfile.TemporaryDirectory(prefix='qa-script-batch-fail-') as directory:
            root = Path(directory)
            script = root / 'fail.sh'
            script.write_text('#!/bin/sh\ncat "$PLATFORM_SCRIPT_SECRET_TOKEN_FILE" >&2\n'
                              'printf \'{"status":"error","step":3,"http_status":409}\\n\'\nexit 1\n')
            token = root / 'token'
            token.write_text('private-probe-value')
            job = self.job(root, script, invocations=[['first'], ['second']])
            job['secretInputs'] = {'token': 'ref'}
            call = self.call(job)
            call['vars']['platform_script_secret_files'] = {'ref': str(token)}
            result = self.run_play(root, [call], success=False)
            self.assertIn('APPLICATION_SCRIPT_EXECUTION_FAILED', result.stdout)
            self.assertFalse((root / '.scripts/.secrets/probe').exists())

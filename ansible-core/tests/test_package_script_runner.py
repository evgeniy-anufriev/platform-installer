"""Native proof that the package script runner needs no container context."""
import os
import json
from pathlib import Path
import pwd
import shutil
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which('ansible-playbook'), 'native Ansible required')
class PackageScriptRunnerTests(unittest.TestCase):
    def test_execution_node_callback_never_contacts_provider_host(self):
        with tempfile.TemporaryDirectory(prefix='script-controller-') as directory:
            root = Path(directory)
            script = root / 'callback.sh'
            script.write_text('#!/bin/sh\n'
                              '[ "$(cat "$PLATFORM_SCRIPT_SECRET_TOKEN_FILE")" = private-probe-value ] || exit 1\n'
                              'printf \'{"status":"ok","changed":false}\\n\'\n')
            token = root / 'token'
            token.write_text('private-probe-value')
            inventory = root / 'inventory.yml'
            inventory.write_text(yaml.safe_dump({'all': {'hosts': {
                'localhost': {'ansible_connection': 'local',
                              'application_runtime_inputs': {'scriptContexts': [{'libraryId': 'provider', 'instanceId': 'server', 'hostId': 'node2'}]},
                              'platform_application_secret_files': {'token': str(token)},
                              'platform_application_secret_root': str(root)},
                'node2': {'ansible_host': 'unreachable.invalid', 'platform_application_preflight_jobs': [{
                    'libraryId': 'provider', 'instanceId': 'server',
                    'account': 'must-not-be-used', 'instancePath': '/must-not-be-used'}]}}}}))
            playbook = root / 'play.yml'
            playbook.write_text(yaml.safe_dump([{
                'hosts': 'localhost', 'gather_facts': False,
                'vars': {'platform_project_root': str(root),
                         'platform_application_secret_files': {'token': str(token)},
                         'platform_application_secret_root': str(root),
                         'application_provider_batch': {'providerLibraryId': 'provider', 'providerInstanceId': 'server'},
                         'application_provider_script_host': 'node2',
                         'application_provider_script': {'id': 'controller-probe', 'path': str(script),
                             'runOn': 'execution_node', 'argv': [], 'secretInputs': {'token': 'token'}}},
                'tasks': [{'ansible.builtin.include_tasks': str(ROOT / 'ansible-core/playbooks/tasks/application-provider-script.yml')}]}
            ], sort_keys=False))
            env = dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections'))
            result = subprocess.run(['ansible-playbook', '-i', str(inventory), str(playbook)],
                                    capture_output=True, text=True, timeout=90, env=env)
            self.assertEqual(0, result.returncode, result.stdout[-3000:] + result.stderr[-1000:])
            self.assertNotIn('private-probe-value', result.stdout + result.stderr)
            self.assertFalse((root / '.scripts/.secrets/controller-probe').exists())

    def test_plain_shell_script_receives_argv_and_private_secret_file(self):
        with tempfile.TemporaryDirectory(prefix='package-script-runner-') as directory:
            root = Path(directory)
            work = root / 'work'
            secrets = root / 'secrets'
            work.mkdir(mode=0o700)
            secrets.mkdir(mode=0o700)
            token = secrets / 'token'
            token.write_text('private-probe-value', encoding='utf-8')
            token.chmod(0o600)
            script = root / 'probe.sh'
            script.write_text(
                '#!/bin/sh\nset -eu\n'
                '[ "$#" -eq 2 ] && [ "$1" = "--name" ] && [ "$2" = "probe" ]\n'
                '[ -z "${PLATFORM_SCRIPT_COMPOSE_ARGV:-}" ]\n'
                '[ -z "${PLATFORM_SCRIPT_CONTAINER_NAME:-}" ]\n'
                '[ -z "${PLATFORM_SCRIPT_LIBRARY_ID:-}" ]\n'
                '[ "$(cat "$PLATFORM_SCRIPT_SECRET_TOKEN_FILE")" = "private-probe-value" ]\n'
                'printf \'{"status":"ok","changed":false}\\n\'\n',
                encoding='utf-8')
            playbook = root / 'playbook.yml'
            playbook.write_text(yaml.safe_dump([{
                'hosts': 'localhost', 'connection': 'local', 'gather_facts': False,
                'tasks': [{'ansible.builtin.include_role': {'name': 'platform.core.package_script'},
                           'vars': {
                               'platform_script_job': {
                                   'id': 'probe', 'path': str(script), 'workingDirectory': str(work),
                                   'account': pwd.getpwuid(os.getuid()).pw_name, 'argv': ['--name', 'probe'],
                                   'secretInputs': {'token': 'probe-token'}},
                               'platform_script_secret_files': {'probe-token': str(token)}}}]
            }], sort_keys=False), encoding='utf-8')
            env = dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections'))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(playbook)],
                                    capture_output=True, text=True, timeout=90, env=env)
            self.assertEqual(0, result.returncode, result.stdout[-3000:] + result.stderr[-1000:])
            self.assertNotIn('private-probe-value', result.stdout + result.stderr)
            self.assertFalse((work / '.scripts/.secrets/probe').exists())
            script.write_text(
                '#!/bin/sh\n'
                'printf private-probe-value >&2\n'
                'printf \'{"status":"error","step":12,"http_status":409,"curl_exit":0,"raw":"private-probe-value"}\\n\'\n'
                'exit 1\n', encoding='utf-8')
            failed = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(playbook)],
                                    capture_output=True, text=True, timeout=90, env=env)
            self.assertNotEqual(0, failed.returncode)
            self.assertIn('APPLICATION_SCRIPT_EXECUTION_FAILED', failed.stdout)
            self.assertIn('409', failed.stdout)
            failure_line = next(line for line in failed.stdout.splitlines()
                                if 'FAILED! =>' in line and 'APPLICATION_SCRIPT_EXECUTION_FAILED' in line)
            diagnostic = json.loads(failure_line.split('FAILED! =>', 1)[1])['msg']
            self.assertIsInstance(diagnostic, dict)
            self.assertEqual(409, diagnostic['http_status'])
            self.assertNotIn('private-probe-value', failed.stdout + failed.stderr)
            self.assertFalse((work / '.scripts/.secrets/probe').exists())


if __name__ == '__main__':
    unittest.main()

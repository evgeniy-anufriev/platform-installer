"""Native proof that the package script runner needs no container context."""
import os
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
                               'platform_script_secret_files': {'probe-token': str(token)},
                               'platform_script_secret_root': str(secrets)}}]
            }], sort_keys=False), encoding='utf-8')
            env = dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections'))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(playbook)],
                                    capture_output=True, text=True, timeout=90, env=env)
            self.assertEqual(0, result.returncode, result.stdout[-3000:] + result.stderr[-1000:])
            self.assertNotIn('private-probe-value', result.stdout + result.stderr)
            self.assertFalse((work / '.scripts/.secrets/probe').exists())


if __name__ == '__main__':
    unittest.main()

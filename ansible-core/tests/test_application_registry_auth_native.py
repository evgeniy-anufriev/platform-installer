"""Exercise production auth/pull cleanup with a private local command fixture."""
import getpass
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which('ansible-playbook'), 'native Ansible required')
class ApplicationRegistryAuthNativeTests(unittest.TestCase):
    def test_target_auth_is_removed_after_success_and_failed_pull(self):
        for exit_code in (0, 23):
            with self.subTest(exit_code=exit_code), tempfile.TemporaryDirectory(prefix='platform-registry-auth-') as tmp:
                root = Path(tmp)
                secret_root = root / 'secrets'; secret_root.mkdir(mode=0o700)
                files, pair = {}, {}
                for name in ('username', 'password'):
                    path = secret_root / name
                    path.write_text('fixture-' + name); path.chmod(0o600)
                    files['registry-' + name] = str(path)
                    pair[name] = dict(source=dict(kind='runtime_secret_ref', ref='registry-' + name))
                permanent = root / 'docker'; permanent.mkdir()
                original = '{"auths":{"node-owned.example":{}}}'
                (permanent / 'config.json').write_text(original)
                instance = root / 'instance'; instance.mkdir()
                marker = root / 'auth-observed'
                command = root / 'pull-fixture'
                command.write_text('#!/bin/sh\ntest -f "$DOCKER_CONFIG/config.json" || exit 22\n'
                                   + "touch '" + str(marker) + "'\nexit " + str(exit_code) + '\n')
                command.chmod(0o700)
                environment = dict(XDG_RUNTIME_DIR=str(root), DOCKER_CONFIG=str(permanent))
                job = dict(projectId='fixture', libraryId='fixture-library', account=getpass.getuser(),
                           instanceId='fixture-app', instancePath=str(instance), composeArgv=[str(command)],
                           dockerEnvironment=environment, registryCredentials=pair,
                           authority=dict(repository=dict(reference='registry.example/app:qa', manifestDigest='sha256:' + 'a' * 64)))
                play = [dict(hosts='all', gather_facts=False, vars=dict(
                    application_runtime_job=job, application_docker_environment=environment,
                    platform_application_secret_files=files, platform_application_secret_root=str(secret_root)),
                    tasks=[{'ansible.builtin.include_role': dict(name='platform.core.application_runtime', tasks_from='pull_registry')}])]
                play_path = root / 'play.yml'; play_path.write_text(yaml.safe_dump(play))
                result = subprocess.run(['ansible-playbook', '-i', 'localhost,', '-c', 'local', str(play_path)],
                    env=dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
                             ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections')),
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=90)
                self.assertEqual(result.returncode == 0, exit_code == 0, result.stdout[-2400:])
                self.assertTrue(marker.exists(), result.stdout[-2400:])
                self.assertEqual(list(root.glob('.platform-registry-*')), [])
                self.assertFalse((instance / '.image-delivery.yml').exists())
                self.assertEqual((permanent / 'config.json').read_text(), original)

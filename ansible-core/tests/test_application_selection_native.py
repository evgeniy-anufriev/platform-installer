"""Real ordered Ansible tasks with a skipped, non-preflighted provider."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which('ansible-playbook'), 'native Ansible required')
class SelectedProviderNativeTests(unittest.TestCase):
    def test_skipped_provider_runs_only_selected_callbacks_without_target_contact(self):
        with tempfile.TemporaryDirectory(prefix='selected-provider-') as folder:
            root = Path(folder)
            marker = root / 'callback-result.json'
            script = root / 'callback.sh'
            script.write_text('#!/bin/sh\nset -eu\n'
                              'printf \'{"consumer":"%s"}\\n\' "$1" > "$2"\n'
                              'printf \'{"status":"ok","changed":false}\\n\'\n')
            hook = dict(id='prepare', phase='provider_prepare', scope='instance', path=str(script),
                        argv=['selected-consumer', str(marker)], secretInputs={}, runOn='execution_node',
                        target=dict(libraryId='provider', instanceId='api', hostId='unreachable'))
            batch = dict(id='provider-batch', providerLibraryId='provider', providerInstanceId='api',
                         hooks=[hook], accounts=[])
            variables = dict(platform_project_root=str(root), platform_application_preflight_jobs=[],
                platform_application_secret_files={}, platform_application_secret_root=str(root),
                platform_application_completed_batches=[], platform_application_delivered_instances=[],
                application_library_id='provider', platform_endpoint_sources={},
                application_selection={'scope': {'skippedLibraries': ['provider'], 'providerLibraries': ['provider']}},
                application_runtime_inputs=dict(jobs=[], integrationScripts=[],
                    scriptContexts=[dict(libraryId='provider', instanceId='api', hostId='unreachable')],
                    integrations=dict(batches=[batch], dependencies={}, sharedDependencies={})),
                application_vault_inputs=dict(libraryJobs=[], instanceJobs=[]))
            inventory = root / 'inventory.yml'
            inventory.write_text(yaml.safe_dump({'all': {'hosts': {
                'localhost': dict(variables, ansible_connection='local'),
                'unreachable': {'ansible_host': 'unreachable.invalid'}}}}))
            playbook = root / 'play.yml'
            playbook.write_text(yaml.safe_dump([dict(hosts='localhost', gather_facts=False,
                tasks=[{'ansible.builtin.include_tasks': str(ROOT/'ansible-core/playbooks/application-libraries-ordered-library.yml')},
                       {'ansible.builtin.assert': {'that': ["platform_application_completed_batches == ['provider-batch']"]}}])], sort_keys=False))
            env = dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(ROOT/'ansible-core/collections') + os.pathsep + str(ROOT/'services/vault/ansible_collections'))
            for repeat in range(2):
                result = subprocess.run(['ansible-playbook', '-i', str(inventory), str(playbook)],
                                        capture_output=True, text=True, timeout=90, env=env)
                self.assertEqual(0, result.returncode, result.stdout[-4000:] + result.stderr[-1000:])
                self.assertEqual({'consumer': 'selected-consumer'}, json.loads(marker.read_text()))
                self.assertNotIn('UNREACHABLE', result.stdout)
                self.assertNotIn('APPLICATION_DOCKER', result.stdout)

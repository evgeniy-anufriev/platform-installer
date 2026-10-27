"""Real standalone Ansible resolution across independently staged requests."""
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
class NativeProjectResolutionTests(unittest.TestCase):
    def test_real_resolver_runs_once_then_reuses_without_target_contact(self):
        with tempfile.TemporaryDirectory(prefix='project-resolution-') as folder:
            directory = Path(folder)
            project = directory / 'project'
            shutil.copytree(ROOT / 'examples/valid/application-libraries', project)
            (project / 'project.yml').write_text(yaml.safe_dump(dict(
                apiVersion='platform.installer/v2alpha1', kind='PlatformProject',
                metadata=dict(id='resolution-qa', name='Resolution QA'))))
            runtime = {'bundleDigest': 'sha256:test', 'coreVersion': 'qa'}
            collections = [str(ROOT / 'ansible-core/collections')] + [str(path)
                for path in sorted((ROOT / 'services').glob('*/ansible_collections'))]
            environment = dict(os.environ, ANSIBLE_COLLECTIONS_PATH=os.pathsep.join(collections),
                               ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'))
            def call(number, expected_hit, cache=True):
                output = directory / ('snapshot-%s.json' % number)
                variables = dict(platform_project_root=str(project),
                    platform_service_catalog_path=str(ROOT / 'examples/catalog/service-catalog.yml'))
                if cache:
                    variables.update(platform_project_resolution_directory=str(directory / 'cache'),
                        platform_project_resolution_local_path=str(directory / ('request-%s.json' % number)),
                        platform_project_resolution_runtime=runtime)
                play = directory / 'play.yml'
                play.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False,
                    vars=variables, tasks=[{'ansible.builtin.include_role': {'name': 'platform.core.project_resolution'}},
                        {'ansible.builtin.assert': {'that': [
                            '_project_resolution_cache.hit == ' + str(expected_hit).lower(),
                            '(_application_inputs is defined) == ' + str(not expected_hit).lower()]}}])]))
                completed = subprocess.run(['ansible-playbook', '-i', str(project / 'inventory/hosts.yml'), str(play)],
                    env=dict(environment, ANSIBLE_CALLBACKS_ENABLED='platform.core.project_snapshot_json',
                             PLATFORM_PROJECT_SNAPSHOT_OUTPUT=str(output)),
                    capture_output=True, text=True, timeout=180)
                self.assertEqual(0, completed.returncode, completed.stdout[-6000:] + completed.stderr[-1500:])
                self.assertNotIn('UNREACHABLE', completed.stdout)
                return json.loads(output.read_text())
            first = call(1, False)
            second = call(2, True)
            self.assertEqual(first, second)
            variables = project / 'inventory/group_vars/all/platform-installer.yml'
            variables.write_text(variables.read_text() + '\n# changed desired bytes\n')
            third = call(3, False)
            self.assertNotEqual(first['projectRevision'], third['projectRevision'])
            call(4, True)
            call(5, False, cache=False)
            # External inputs remain fresh on every independent request; no
            # result artifact is published from an environment-dependent resolve.
            external = yaml.safe_load(variables.read_text())
            external['resolution_external_probe'] = "{{ lookup('env', 'HOME') }}"
            variables.write_text(yaml.safe_dump(external))
            call(6, False)
            call(7, False)
            self.assertFalse((directory / 'request-6.json').exists())
            self.assertFalse((directory / 'request-7.json').exists())

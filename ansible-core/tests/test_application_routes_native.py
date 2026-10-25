"""Route JSON reconciliation directly and through the production Ansible runner."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import uuid

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT/'examples/szi/application-packages/nginx/1.0.0/assets/prepare-routes.sh'
ACCOUNT = os.environ.get('PLATFORM_QA_NGINX_ROUTES_ACCOUNT')


@unittest.skipUnless(shutil.which('jq'), 'jq required')
class ApplicationRoutesJqTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='routes-jq-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'config').mkdir()
        (self.root/'bin').mkdir()
        docker = self.root/'bin/docker'
        docker.write_text('#!/bin/sh\necho UNEXPECTED_DOCKER_CALL >&2\nexit 97\n')
        docker.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.root/'bin')+os.pathsep+os.environ['PATH'])
        self.owner = 'platform.application.routes/v1:project:provider:nginx'
        self.retained = dict(endpoint='https://retained.example.test', subpath='/retained', parameters={'keep': True})
        self.requested = dict(owner=self.owner, routes={'retained': self.retained})
        (self.root/'config/routes.requested.json').write_text(json.dumps(self.requested))

    def invoke(self, consumers=None, success=True):
        argv = ['sh', str(SCRIPT), 'project', 'provider', 'nginx', 'node']
        if consumers is not None:
            argv.append(json.dumps(consumers))
        result = subprocess.run(argv, cwd=self.root, env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(success, result.returncode == 0, result.stderr[-3000:])
        self.assertNotIn('UNEXPECTED_DOCKER_CALL', result.stderr)
        return json.loads(result.stdout) if success else result

    def test_startup_integration_update_repeat_and_empty_selection(self):
        self.assertTrue(self.invoke()['changed'])
        self.assertFalse(self.invoke()['changed'])
        consumers = [dict(applicationId='selected', placements={
            'node-b': dict(endpointUrl='https://selected.example.test', parameters={'IDENTITY_ROUTE': {'site': 'b'}}),
            'node-a': dict(endpointUrl='https://selected.example.test', parameters={'IDENTITY_ROUTE': {'site': 'a'}})}),
            dict(applicationId='no-endpoint', placements={'node-a': {}})]
        self.assertTrue(self.invoke(consumers)['changed'])
        effective = self.root/'routes/routes.effective.json'
        content, timestamp = effective.read_bytes(), effective.stat().st_mtime_ns
        self.assertFalse(self.invoke(consumers)['changed'])
        self.assertEqual((content, timestamp), (effective.read_bytes(), effective.stat().st_mtime_ns))
        doc = json.loads(content)
        self.assertEqual({'retained', 'selected'}, set(doc['routes']))
        self.assertEqual(self.retained, doc['routes']['retained'])
        self.assertEqual({'site': 'a'}, doc['routes']['selected']['parameters'])
        self.assertFalse(self.invoke([])['changed'])
        consumers[0]['placements']['node-a']['endpointUrl'] = 'https://updated.example.test'
        self.assertTrue(self.invoke(consumers)['changed'])
        self.assertEqual('https://updated.example.test', json.loads(effective.read_text())['routes']['selected']['endpoint'])
        self.assertEqual(0o644, effective.stat().st_mode & 0o777)

    def test_foreign_owner_fails_without_modifying_routes(self):
        self.invoke()
        effective = self.root/'routes/routes.effective.json'
        doc = json.loads(effective.read_text()); doc['owner'] = 'foreign'
        effective.write_text(json.dumps(doc)); content = effective.read_bytes()
        result = self.invoke(success=False)
        self.assertIn('APPLICATION_ROUTES_OWNER_INVALID', result.stderr)
        self.assertEqual(content, effective.read_bytes())

    def test_invalid_endpoint_fails_without_modifying_routes(self):
        self.invoke()
        effective = self.root/'routes/routes.effective.json'; content = effective.read_bytes()
        self.requested['routes']['retained']['endpoint'] = 'https://host/path'
        (self.root/'config/routes.requested.json').write_text(json.dumps(self.requested))
        result = self.invoke(success=False)
        self.assertIn('APPLICATION_ROUTES_INPUT_INVALID', result.stderr)
        self.assertEqual(content, effective.read_bytes())

    def test_malformed_input_is_diagnosed_and_transient_files_are_removed(self):
        (self.root/'config/routes.requested.json').write_text('{')
        self.invoke(success=False)
        self.assertFalse(list((self.root/'.scripts').glob('routes-input-*')))
        self.assertTrue(list((self.root/'.scripts/diagnostics').glob('*.log')))
        self.assertFalse((self.root/'routes/routes.effective.json').exists())


@unittest.skipUnless(ACCOUNT and shutil.which('jq') and shutil.which('ansible-playbook'), 'explicit target account, jq and Ansible required')
class ApplicationRoutesNativeTests(unittest.TestCase):
    def test_startup_integration_and_repeat_keep_unselected_routes(self):
        project = 'qa-routes-' + uuid.uuid4().hex[:12]
        owner = 'platform.application.routes/v1:' + project + ':provider:nginx'
        retained = dict(endpoint='https://retained.example.test', subpath='/retained', parameters={'keep': True})
        requested = dict(owner=owner, routes={'retained': retained})
        consumers = [dict(applicationId='selected', placements={
            'node-b': dict(endpointUrl='https://selected.example.test', parameters={'IDENTITY_ROUTE': {'site': 'b'}}),
            'node-a': dict(endpointUrl='https://selected.example.test', parameters={'IDENTITY_ROUTE': {'site': 'a'}})})]
        tasks = [
            {'ansible.builtin.tempfile': {'state': 'directory', 'path': '/var/tmp', 'prefix': 'platform-szi-stage3-routes-'}, 'register': 'qa_root'},
            {'block': [
                {'ansible.builtin.file': {'path': '{{ qa_root.path }}/nginx/config', 'state': 'directory', 'mode': '0700'}},
                {'ansible.builtin.copy': {'content': json.dumps(requested), 'dest': '{{ qa_root.path }}/nginx/config/routes.requested.json', 'mode': '0644'}},
            ], 'always': [{'ansible.builtin.file': {'path': '{{ qa_root.path }}', 'state': 'absent'}}]}]
        body = tasks[-1]['block']
        for phase, changed in (('startup', True), ('integration', True), ('repeat', False)):
            argv = [project, 'provider', 'nginx', 'local']
            if phase != 'startup':
                argv.append(json.dumps(consumers))
            body.extend([
                {'name': 'Run isolated routes ' + phase, 'ansible.builtin.include_role': {'name': 'platform.core.package_script'},
                 'vars': {'platform_script_job': dict(id='routes-' + phase, path=str(SCRIPT),
                     workingDirectory='{{ qa_root.path }}/nginx', account=ACCOUNT, secretInputs={}, argv=argv),
                     'platform_script_secret_files': {}}},
                {'ansible.builtin.assert': {'that': ['(platform_script_result.stdout | from_json).changed == ' + str(changed).lower()]}},
            ])
        body.extend([
            {'ansible.builtin.slurp': {'src': '{{ qa_root.path }}/nginx/routes/routes.effective.json'}, 'register': 'qa_routes'},
            {'ansible.builtin.assert': {'that': [
                '(qa_routes.content | b64decode | from_json).routes | list | sort == ["retained", "selected"]',
                '(qa_routes.content | b64decode | from_json).routes.retained.parameters.keep',
                '(qa_routes.content | b64decode | from_json).routes.selected.parameters.site == "a"']}},
        ])
        with tempfile.TemporaryDirectory(prefix='routes-controller-') as directory:
            playbook = Path(directory)/'play.yml'
            playbook.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False,
                                                   become=True, become_user=ACCOUNT, tasks=tasks)], sort_keys=False))
            env = dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(ROOT/'ansible-core/collections'))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(playbook)], capture_output=True, text=True, timeout=180, env=env)
            self.assertEqual(0, result.returncode, result.stdout[-4500:] + result.stderr[-1500:])

"""PKI delivery is independent of Agent and preserves private byte custody."""
import copy
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import yaml
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ansible-core/collections'))


class ApplicationPkiProjectionTests(unittest.TestCase):
    def resolve(self, agent=False, plans=None, profile=True):
        module = importlib.import_module('ansible_collections.platform.core.plugins.action.prepare_application_runtime')
        job = dict(libraryId='library', instanceId='web', hostId='node2', agentTemplate='agent' if agent else None)
        row = dict(libraryId='library', instanceId='web', hostId='node2',
                   bindings={'tls': {'profileRef': 'application-tls'}} if profile else {})
        if plans is None:
            plans = [dict(hostId='node1', tlsProfileId='application-tls'),
                     dict(hostId='node2', tlsProfileId='application-tls'),
                     dict(hostId='node2', tlsProfileId='unrelated')]
        with tempfile.TemporaryDirectory() as folder:
            action = module.ActionModule.__new__(module.ActionModule)
            action._task = SimpleNamespace(args=dict(project_root=folder, contracts_root=str(ROOT / 'contracts'),
                                                    snapshot={'project': {'id': 'project'},
                                                              'applicationLibraries': {'libraries': {'library': {'instances': {}}}}}))
            action._loader = SimpleNamespace(load_from_file=lambda _: {})
            values = dict(platform_application_rows=[row], platform_desired_state={},
                          application_snapshot={'pki_materialization': {'materializationPlans': plans}})
            if agent:
                values['application_vault_inputs'] = dict(instanceJobs=[dict(libraryId='library', instanceId='web',
                    providerId='vault', envTemplates=[], readFields={})], providers=[dict(providerId='vault', url='https://vault')])
            with patch.object(module, 'prepare_runtime', return_value=[job]), \
                 patch.object(module, 'resolve_image_lock'), patch.object(module, 'prepare_integrations', return_value={}):
                return action.run(task_vars=values)

    def test_non_agent_selects_its_host_and_profile_without_vault_or_password_binding(self):
        result = self.resolve()
        self.assertEqual('PASS', result['status'])
        self.assertEqual([dict(hostId='node2', tlsProfileId='application-tls')], result['jobs'][0]['pkiPlans'])
        self.assertNotIn('vault', result['jobs'][0])

    def test_agent_uses_the_same_pki_projection(self):
        result = self.resolve(agent=True)
        self.assertEqual('PASS', result['status'])
        self.assertEqual(1, len(result['jobs'][0]['pkiPlans']))
        self.assertNotIn('pkiPlans', result['jobs'][0]['vault'])

    def test_no_profile_needs_no_pki_and_missing_plan_blocks(self):
        self.assertEqual([], self.resolve(profile=False)['jobs'][0]['pkiPlans'])
        self.assertEqual('APPLICATION_PKI_PROFILE_AMBIGUOUS', self.resolve(plans=[])['code'])

    @unittest.skipUnless(shutil.which('docker'), 'native Docker Compose CLI required')
    def test_all_five_szi_compose_projections_include_standard_pki_directory(self):
        from ansible_collections.platform.core.plugins.module_utils.application_runtime import validate_compose
        environment = Environment()
        environment.filters['to_json'] = json.dumps
        environment.filters['dirname'] = os.path.dirname
        environment.filters['to_nice_yaml'] = lambda value, **kwargs: yaml.safe_dump(value, sort_keys=False, **kwargs)
        for name in ('keycloak', 'grant-access', 'grant-access-audit', 'grant-access-front', 'nginx'):
            with self.subTest(application=name), tempfile.TemporaryDirectory(prefix='szi2-pki-compose-') as folder:
                instance = Path(folder)
                package = ROOT / ('examples/szi/application-packages/%s/1.0.0' % name)
                settings = yaml.safe_load((package / ('roles/application_%s/defaults/main.yml' % name)).read_text())['platform_application_definition']['defaults']
                manifest = json.loads((package / 'application.yml').read_text())
                base = instance / 'base.yml'
                base.write_text('services:\n  base:\n    init: true\n')
                digest = 'sha256:' + 'a' * 64
                compose = instance / 'compose.yml'
                compose.write_text(environment.from_string((package / manifest['render']['compose_template']).read_text()).render(
                    application_instance_id=name, application_effective=settings, application_parameters=settings.get('parameters', {}),
                    application_environment=settings['environment'], application_project_id='project',
                    application_config_digest=digest, library_runtime=dict(library_id='szi', host_id='node2'),
                    application_runtime=dict(base_compose_path=str(base), base_service='base', image=settings['image'],
                        container_name=name+'-node2', pki_path=str(instance/'pki'), vault_path=str(instance/'vault'),
                        config_path=str(instance/'config'))))
                result = subprocess.run(['docker', 'compose', '--project-name', 'szi2-pki', '-f', str(compose),
                                         'config', '--format', 'json'], capture_output=True, text=True, timeout=30)
                self.assertEqual(0, result.returncode, result.stderr)
                job = dict(projectId='project', libraryId='szi', instanceId=name, hostId='node2',
                    placement=dict(composeProject='szi2-pki', containerName=name+'-node2'), settings=settings,
                    agentTemplate=manifest['render'].get('agent_template'), identityNames=[],
                    configs=settings.get('config_files', []), directoryConfigs=settings.get('config_directories', []),
                    archiveConfigs=settings.get('config_archives', []), pkiPlans=[dict(hostId='node2')])
                self.assertTrue(validate_compose(json.loads(result.stdout), job, str(instance), digest))


@unittest.skipUnless(os.environ.get('PLATFORM_QA_APPLICATION_PKI') == '1', 'explicit native rootless PKI fixture')
class NativeApplicationPkiDeliveryTests(unittest.TestCase):
    def test_non_agent_pem_and_stores_private_delivery_repeat(self):
        import pwd
        account = pwd.getpwnam('platform-docker')
        self.assertEqual(0, subprocess.run(['sudo', '-n', 'test', '-f', '/run/user/%s/docker.pid' % account.pw_uid]).returncode)
        with tempfile.TemporaryDirectory(prefix='application-pki-play-') as directory:
            tasks = [dict(name='Create owned source', tempfile=dict(state='directory', path='/etc/platform-installer/pki',
                         prefix='qa-application-pem-'), register='source'),
                     dict(name='Create private fixture parent', file=dict(path=account.pw_dir+'/.runtime/secrets',
                          state='directory', owner='platform-docker', mode='0700')),
                     dict(name='Create owned instance', tempfile=dict(state='directory', path=account.pw_dir+'/.runtime/secrets',
                          prefix='qa-application-pem-'), become_user='platform-docker', register='instance')]
            names = ['keystore.p12', 'truststore.p12', 'ca-chain.pem', 'certificate.pem', 'private-key.pem']
            materialize = {'platform.core.application_identity_files': dict(account='platform-docker', user='1000:1000',
                instance_path='{{ instance.path }}', pki_plans=[dict(targetDirectory='{{ source.path }}')]), 'no_log': True}
            body = [dict(name='Write synthetic fixture bytes', copy=dict(content='synthetic-fixture-{{ item }}',
                         dest='{{ source.path }}/{{ item }}', mode='0600'), loop=names, no_log=True),
                    dict(name='Preflight', **copy.deepcopy(materialize)),
                    dict(name='First delivery', **copy.deepcopy(materialize), register='first'),
                    dict(name='Repeat delivery', **copy.deepcopy(materialize), register='second'),
                    dict(name='Inspect private delivered bytes', stat=dict(path='{{ instance.path }}/pki/{{ item }}',
                         checksum_algorithm='sha256'), loop=names, register='files', no_log=True),
                    {}]
            body[1]['platform.core.application_identity_files']['preflight'] = True
            body[-1] = {'name': 'Require complete private idempotent delivery', 'ansible.builtin.assert': {'that': [
                'first.changed', 'not second.changed',
                "files.results | map(attribute='stat.mode') | unique | list == ['0600']",
                "files.results | map(attribute='stat.uid') | unique | list == [first.host_uid]",
                "files.results | map(attribute='stat.gid') | unique | list == [first.host_gid]"]}}
            for index, name in enumerate(names):
                import hashlib
                checksum = hashlib.sha256(('synthetic-fixture-' + name).encode()).hexdigest()
                body[-1]['ansible.builtin.assert']['that'].append("files.results[%s].stat.checksum == '%s'" % (index, checksum))
            body.append(dict(name='Non-Agent gets no Vault directory', stat=dict(path='{{ instance.path }}/vault'), register='vault'))
            body.append({'ansible.builtin.assert': {'that': ['not vault.stat.exists']}})
            agent_delivery = copy.deepcopy(materialize)
            agent_delivery['platform.core.application_identity_files'].update(agent_required=True,
                role_id='synthetic-role-id', ca='synthetic-public-ca', agent='synthetic-agent-config')
            body.extend([dict(name='Agent delivery preserves existing PKI and adds private Vault files',
                              **copy.deepcopy(agent_delivery), register='agent_first'),
                         dict(name='Agent repeat', **copy.deepcopy(agent_delivery), register='agent_second'),
                         {'ansible.builtin.assert': {'that': ['agent_first.changed', 'not agent_second.changed']}}])
            tasks.append(dict(block=body, always=[dict(file=dict(path='{{ source.path }}', state='absent')),
                          dict(file=dict(path='{{ instance.path }}', state='absent'))]))
            play = Path(directory) / 'play.yml'
            play.write_text(yaml.safe_dump([dict(hosts='localhost', gather_facts=False, become=True, tasks=tasks)]))
            env = dict(os.environ, ANSIBLE_COLLECTIONS_PATHS=str(ROOT / 'ansible-core/collections'), ANSIBLE_NOCOLOR='1')
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', '-c', 'local', str(play)],
                                    env=env, capture_output=True, text=True, timeout=180)
            self.assertEqual(0, result.returncode, result.stdout[-5000:] + result.stderr[-1000:])

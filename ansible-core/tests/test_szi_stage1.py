"""Focused checks for SZI package inputs and generic script placement."""
import ast
import json
import os
import shutil
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest

import yaml
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils'))
from application_libraries import load_package
from application_scripts import prepare_script_jobs
from application_runtime import validate_compose
from schema_validation import SchemaValidator


class SziStage1Tests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('docker'), 'native Docker Compose CLI required')
    def test_grant_hazelcast_addresses_are_resolved_before_compose(self):
        settings=yaml.safe_load((ROOT/'examples/szi/application-packages/grant-access/1.0.0/roles/application_grant-access/defaults/main.yml').read_text())['platform_application_definition']['defaults']
        jobs=[{'hostId':host,'libraryId':'szi','slotId':'grant-access',
            'application':{'definition':{'defaults':settings}},'slot':{'overrides':{}},'instance':{'overrides':{}},
            'hostOverride':{'ports':{'port-2':{'container':5701,'published':port}}}}
            for host,port in [('node2',15701),('node3',25701)]]
        env=Environment();env.filters['combine']=lambda a,b,**kwargs:dict(a,**b)
        values={name:env.from_string(settings['environment'][name]).render(application_job=jobs[0],
            hostvars={'node2':{'ansible_host':'192.0.2.2'},'node3':{'ansible_host':'192.0.2.3'}},
            library_instance_id='szi',_application_inputs={'jobs':jobs})
            for name in ('HZ_NETWORK_PUBLICADDRESS','HZ_NETWORK_PORT','HZ_NETWORK_JOIN_TCPIP_MEMBERS')}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);compose=root/'compose.yml';dotenv=root/'values.env'
            compose.write_text(yaml.safe_dump({'services':{'grant':{'image':'fixture:latest','environment':values}}}))
            dotenv.write_text('SERVER_2_IP=192.0.2.2\nSERVER_3_IP=192.0.2.3\n')
            result=subprocess.run(['docker','compose','--env-file',str(dotenv),'-f',str(compose),'config','--format','json'],capture_output=True,text=True,timeout=30)
            self.assertEqual(0,result.returncode,result.stderr)
            actual=json.loads(result.stdout)['services']['grant']['environment']
            self.assertEqual(values,{key:actual[key] for key in values})
            self.assertEqual('192.0.2.2:15701',actual['HZ_NETWORK_PUBLICADDRESS'])
            self.assertEqual('192.0.2.2:15701,192.0.2.3:25701',actual['HZ_NETWORK_JOIN_TCPIP_MEMBERS'])
            self.assertEqual('5701',actual['HZ_NETWORK_PORT'])

    def test_existing_admin_without_profile_marker_requires_working_runtime_password(self):
        source = (ROOT / 'examples/szi/application-packages/keycloak/1.0.0/assets/scripts/create-admin.sh').read_text()
        wrapper = source.split("<<'WRAPPER'\n", 1)[1].split('\nWRAPPER\n', 1)[0]
        for allowed in (True, False):
            with self.subTest(valid_admin_password=allowed), tempfile.TemporaryDirectory(prefix='szi-existing-admin-') as directory:
                root = Path(directory)
                (root / 'work').mkdir()
                (root / 'bootstrap').write_text('fixture-bootstrap')
                (root / 'password').write_text('fixture-admin')
                binary = root / 'bin'
                binary.mkdir()
                keytool = binary / 'keytool'
                keytool.write_text('#!/bin/sh\nexit 0\n')
                keytool.chmod(0o700)
                cli = binary / 'kcadm'
                cli.write_text('''#!/bin/sh
set -eu
printf '%s\\n' "$*" >> "$TEST_KCADM_LOG"
case "$*" in
  'config truststore '*) exit 0;;
  'config credentials '*)
    case "$*" in
      *'--client temp-admin '*) [ "${KC_CLI_CLIENT_SECRET:-}" = fixture-bootstrap ];;
      *) [ "$TEST_ADMIN_LOGIN_ALLOWED" = 1 ] && [ "${KC_CLI_PASSWORD:-}" = fixture-admin ];;
    esac;;
  'get users -r '*) printf 'id\\n11111111-1111-1111-1111-111111111111\\n';;
  'get users/'*) printf '{}\\n';;
  'get-roles '*) printf 'name\\nadmin\\n';;
  'get clients '*) printf 'id\\n22222222-2222-2222-2222-222222222222\\n';;
  'delete clients/'*) exit 0;;
  *) exit 1;;
esac
''')
                cli.chmod(0o700)
                code = wrapper.replace('/usr/lib/keycloak/bin/kcadm.sh', str(cli))
                for container_path, fixture in (
                    ('/run/platform-admin-work', root / 'work'),
                    ('/run/platform-admin-password', root / 'password'),
                    ('/run/platform-bootstrap-secret', root / 'bootstrap')):
                    code = code.replace(container_path, str(fixture))
                script = root / 'wrapper.sh'
                script.write_text(code)
                log = root / 'commands'
                result = subprocess.run(['sh', str(script), 'https://192.0.2.2:10411'],
                    env=dict(os.environ, PATH=str(binary)+os.pathsep+os.environ['PATH'],
                        TEST_KCADM_LOG=str(log), TEST_ADMIN_LOGIN_ALLOWED='1' if allowed else '0'),
                    capture_output=True, text=True, timeout=15)
                commands = log.read_text()
                self.assertNotIn('set-password ', commands)
                self.assertNotIn('create users ', commands)
                if allowed:
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertEqual('changed', (root / 'work/result').read_text())
                    self.assertIn('delete clients/22222222-', commands)
                else:
                    self.assertNotEqual(0, result.returncode)
                    self.assertNotIn('delete clients/', commands)

    def test_new_admin_password_is_set_before_first_password_login(self):
        source = (ROOT / 'examples/szi/application-packages/keycloak/1.0.0/assets/scripts/create-admin.sh').read_text()
        wrapper = source.split("<<'WRAPPER'\n", 1)[1].split('\nWRAPPER\n', 1)[0]
        with tempfile.TemporaryDirectory(prefix='szi-new-admin-') as directory:
            root = Path(directory)
            (root / 'work').mkdir()
            (root / 'bootstrap').write_text('fixture-bootstrap')
            (root / 'password').write_text('fixture-admin')
            binary = root / 'bin'
            binary.mkdir()
            (binary / 'keytool').write_text('#!/bin/sh\nexit 0\n')
            (binary / 'keytool').chmod(0o700)
            cli = binary / 'kcadm'
            cli.write_text('''#!/bin/sh
set -eu
case "$*" in
  'config truststore '*) exit 0;;
  'config credentials '*)
    case "$*" in
      *'--client temp-admin '*) exit 0;;
      *) [ -f "$TEST_STATE/password-set" ] || { touch "$TEST_STATE/early-login"; exit 1; };;
    esac;;
  'get users -r '*)
    printf 'id\\n'; [ ! -f "$TEST_STATE/created" ] || printf '11111111-1111-1111-1111-111111111111\\n';;
  'create users '*) touch "$TEST_STATE/created";;
  'get-roles '*) printf 'name\\nadmin\\n';;
  'set-password '*) touch "$TEST_STATE/password-set";;
  'get clients '*) printf 'id\\n22222222-2222-2222-2222-222222222222\\n';;
  'delete clients/'*) touch "$TEST_STATE/removed";;
  *) exit 1;;
esac
''')
            cli.chmod(0o700)
            code = wrapper.replace('/usr/lib/keycloak/bin/kcadm.sh', str(cli))
            for container_path, fixture in (
                ('/run/platform-admin-work', root / 'work'),
                ('/run/platform-admin-password', root / 'password'),
                ('/run/platform-bootstrap-secret', root / 'bootstrap')):
                code = code.replace(container_path, str(fixture))
            script = root / 'wrapper.sh'
            script.write_text(code)
            result = subprocess.run(['sh', str(script), 'https://192.0.2.2:10411'],
                env=dict(os.environ, PATH=str(binary)+os.pathsep+os.environ['PATH'], TEST_STATE=str(root)),
                capture_output=True, text=True, timeout=15)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((root / 'password-set').exists())
            self.assertTrue((root / 'removed').exists())
            self.assertFalse((root / 'early-login').exists())

    def test_admin_host_wrapper_does_not_read_container_private_pki(self):
        script = ROOT / 'examples/szi/application-packages/keycloak/1.0.0/assets/scripts/create-admin.sh'
        with tempfile.TemporaryDirectory(prefix='szi-admin-') as directory:
            root = Path(directory)
            instance = root / 'szi/keycloak'
            (instance / '.scripts').mkdir(parents=True)
            pki = instance / 'pki'
            pki.mkdir()
            (pki / 'ca-chain.pem').write_text('fixture-ca')
            pki.chmod(0)
            binary = root / 'bin'
            binary.mkdir()
            docker = binary / 'docker'
            docker.write_text('#!/bin/sh\nset -eu\n'
                'cat "$PWD/.scripts/keycloak-create-admin-wrapper.sh" > "$PWD/captured-wrapper"\n'
                'printf "%s\\n" "$@" > "$PWD/captured-argv"\n'
                'printf unchanged > "$PWD/.scripts/.admin-work/result"\n')
            docker.chmod(0o700)
            fixture_input = root / 'fixture-input'
            fixture_input.write_text('fixture-only')
            try:
                result = subprocess.run(['sh', str(script), '--realm', 'master', '--keycloak-url',
                    'https://192.0.2.2:10411', '--project', 'project', '--library', 'szi',
                    '--instance', 'keycloak', '--host', 'node2'], cwd=instance,
                    env=dict(os.environ, PATH=str(binary)+os.pathsep+os.environ['PATH'],
                        PLATFORM_SCRIPT_SECRET_BOOTSTRAP_CLIENT_SECRET_FILE=str(fixture_input),
                        PLATFORM_SCRIPT_SECRET_ADMIN_PASSWORD_FILE=str(fixture_input)),
                    capture_output=True, text=True, timeout=15)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual({'status': 'ok', 'changed': False}, json.loads(result.stdout))
                self.assertIn('-file /opt/application/pki/ca-chain.pem', (instance / 'captured-wrapper').read_text())
                self.assertNotIn('/run/platform-ca.pem', (instance / 'captured-argv').read_text())
            finally:
                pki.chmod(0o700)

    def test_admin_failure_preserves_only_numeric_step_and_cleans_work(self):
        script = ROOT / 'examples/szi/application-packages/keycloak/1.0.0/assets/scripts/create-admin.sh'
        for internal_step in (None, 50):
            with self.subTest(step=internal_step), tempfile.TemporaryDirectory(prefix='szi-admin-error-') as directory:
                root = Path(directory)
                instance = root / 'szi/keycloak'
                (instance / '.scripts').mkdir(parents=True)
                binary = root / 'bin'
                binary.mkdir()
                docker = binary / 'docker'
                docker.write_text('#!/bin/sh\n'
                    + ('printf 50 > "$PWD/.scripts/.admin-work/failure-step"\n' if internal_step else '')
                    + 'printf "fixture-docker-start-failure\\n" >&2\nexit 7\n')
                docker.chmod(0o700)
                secret = root / 'input'
                secret.write_text('fixture-private-password')
                result = subprocess.run(['sh', str(script), '--realm', 'master', '--keycloak-url',
                    'https://192.0.2.2:10411', '--project', 'project', '--library', 'szi',
                    '--instance', 'keycloak', '--host', 'node2'], cwd=instance,
                    env=dict(os.environ, PATH=str(binary)+os.pathsep+os.environ['PATH'],
                        PLATFORM_SCRIPT_SECRET_BOOTSTRAP_CLIENT_SECRET_FILE=str(secret),
                        PLATFORM_SCRIPT_SECRET_ADMIN_PASSWORD_FILE=str(secret)),
                    capture_output=True, text=True, timeout=15)
                self.assertEqual(1, result.returncode)
                self.assertEqual({'status': 'error', 'step': internal_step or 900}, json.loads(result.stdout))
                self.assertTrue(result.stderr.endswith('APPLICATION_KEYCLOAK_ADMIN_FAILED\n'))
                self.assertIn('fixture-docker-start-failure', result.stderr)
                self.assertNotIn('fixture-private', result.stdout + result.stderr)
                self.assertFalse((instance / '.scripts/.admin-work').exists())
                self.assertFalse((instance / '.scripts/keycloak-create-admin-wrapper.sh').exists())
                self.assertFalse((instance / '.scripts/keycloak-admin-trace.sh').exists())
                self.assertEqual(1, len(list((instance / '.scripts/diagnostics').glob('*.log'))))

    @unittest.skipUnless(shutil.which('jq'), 'jq is required for the actual container trace redactor')
    def test_admin_shell_trace_redacts_secrets_and_preserves_output_and_exit(self):
        for script_name, exit_code in [(name, code) for name in ('create-admin', 'bootstrap-admin') for code in (0, 7)]:
            source = (ROOT / f'examples/szi/application-packages/keycloak/1.0.0/assets/scripts/{script_name}.sh').read_text()
            trace = source.split("<<'TRACE'\n", 1)[1].split('\nTRACE\n', 1)[0]
            with self.subTest(script=script_name, exit_code=exit_code), tempfile.TemporaryDirectory(prefix='szi-admin-trace-') as directory:
                root = Path(directory)
                (root / 'work').mkdir()
                password = "fixture p'ass\\word$\nprivate-second-line"
                bootstrap = 'fixture-bootstrap-частный'
                (root / 'password').write_text(password)
                (root / 'bootstrap').write_text(bootstrap)
                child = root / 'wrapper'
                child.write_text('#!/bin/sh\npassword=$(cat "$1")\n'
                    'printf "stdout-visible %s\\n" "$password"\n'
                    'printf "stderr-visible %s\\n" "$(cat "$2")" >&2\n'
                    'printf "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJmaXh0dXJlIn0.fakeSignature\\n"\n'
                    f'exit {exit_code}\n')
                code = trace
                for original, replacement in (
                    ('/run/platform-admin-work', root / 'work'),
                    ('/run/platform-admin-password', root / 'password'),
                    ('/run/platform-db-password', root / 'password'),
                    ('/run/platform-bootstrap-secret', root / 'bootstrap'),
                    ('/run/platform-admin-wrapper', child),
                    ('/run/platform-bootstrap-wrapper', child)):
                    code = code.replace(original, str(replacement))
                script = root / 'trace'
                script.write_text(code)
                result = subprocess.run(['sh', str(script), str(root / 'password'), str(root / 'bootstrap')],
                    capture_output=True, text=True, timeout=15)
                self.assertEqual(exit_code, result.returncode, result.stderr)
                self.assertEqual('', result.stdout)
                self.assertIn(' trace:', result.stderr)
                self.assertIn('stdout-visible', result.stderr)
                self.assertIn('stderr-visible', result.stderr)
                self.assertIn('[REDACTED_JWT]', result.stderr)
                for value in (password, bootstrap, 'private-second-line', 'eyJhbGciOiJIUzI1NiJ9'):
                    self.assertNotIn(value, result.stderr)

    def test_ordered_library_playbook_runs_keycloak_before_dependent_instances(self):
        tasks = yaml.safe_load((ROOT / 'ansible-core/playbooks/application-libraries-ordered-library.yml').read_text())
        expression = tasks[0]['ansible.builtin.set_fact']['application_library_instance_ids']
        slots = yaml.safe_load((ROOT / 'examples/szi/library-packages/szi/1.0.0/roles/library_szi/defaults/main.yml').read_text())['platform_library_definition']['slots']
        jobs = [{'libraryId': 'szi', 'instanceId': name, 'startupPriority': value.get('start_priority', 100)}
                for name, value in slots.items()]
        rendered = Environment().from_string(expression).render(
            hostvars={'localhost': {'application_runtime_inputs': {'jobs': jobs}}},
            application_library_id='szi')
        order = ast.literal_eval(rendered)
        self.assertEqual('keycloak', order[0])
        self.assertEqual(set(slots), set(order))

    @unittest.skipUnless(shutil.which('docker'), 'native Docker Compose CLI required')
    def test_keycloak_compose_satisfies_existing_runtime_projection(self):
        package = ROOT / 'examples/szi/application-packages/keycloak/1.0.0'
        settings = yaml.safe_load((package / 'roles/application_keycloak/defaults/main.yml').read_text())['platform_application_definition']['defaults']
        with tempfile.TemporaryDirectory(prefix='szi-compose-') as directory:
            root = Path(directory)
            instance = root / 'keycloak'
            instance.mkdir()
            base = root / 'base.yml'
            base.write_text('services:\n  base:\n    init: true\n')
            digest = 'sha256:' + 'a' * 64
            env = Environment()
            env.filters['to_json'] = json.dumps
            env.filters['to_nice_yaml'] = lambda value, **kwargs: yaml.safe_dump(value, sort_keys=False, **kwargs)
            base_template = ROOT / 'examples/szi/library-packages/szi/1.0.0/roles/library_szi/templates/.base_compose.yml.j2'
            base.write_text(env.from_string(base_template.read_text()).render(
                library_runtime={'connections': {'postgres': {'targets': [
                    {'address': '192.168.56.102', 'port': 15432},
                    {'address': '192.168.56.103', 'port': 25432}]}}},
                groups={'all': ['node1', 'node2', 'node3']}))
            template = env.from_string((package / 'roles/application_keycloak/templates/compose.yml.j2').read_text())
            compose = instance / 'compose.yml'
            compose.write_text(template.render(
                application_instance_id='keycloak', application_effective=settings, application_parameters=settings['parameters'],
                application_environment=settings['environment'], application_project_id='project',
                application_config_digest=digest, library_runtime={'library_id': 'szi', 'host_id': 'node2'},
                application_runtime={'base_compose_path': str(base), 'base_service': 'base',
                    'image': settings['image'], 'container_name': 'keycloak-node2',
                    'pki_path': str(instance / 'pki'), 'vault_path': str(instance / 'vault'),
                    'config_path': str(instance / 'config')}))
            result = subprocess.run(['docker', 'compose', '--project-name', 'stage1-keycloak',
                '-f', str(compose), 'config', '--format', 'json'], capture_output=True, text=True, timeout=30)
            self.assertEqual(0, result.returncode, result.stderr)
            job = {'projectId': 'project', 'libraryId': 'szi', 'instanceId': 'keycloak', 'hostId': 'node2',
                'placement': {'composeProject': 'stage1-keycloak', 'containerName': 'keycloak-node2'},
                'settings': settings, 'agentTemplate': 'agent.hcl.j2', 'identityNames': [],
                'configs': settings['config_files'], 'directoryConfigs': settings['config_directories'],
                'archiveConfigs': settings['config_archives'], 'pkiPlans': [{'hostId': 'node2'}]}
            config = json.loads(result.stdout)
            self.assertEqual('192.168.56.102:15432,192.168.56.103:25432', config['services']['keycloak']['environment']['POSTGRES_ADDRESS'])
            # The standard identity delivery supplies these names, not leaf.crt/key.
            pki_files = {'keystore.p12', 'truststore.p12', 'ca-chain.pem'}
            service = config['services']['keycloak']
            pki_mounts = [mount for mount in service['volumes']
                          if mount['target'].startswith('/opt/application/pki')]
            self.assertEqual(['/opt/application/pki'], [mount['target'] for mount in pki_mounts])
            for name in ('KC_HTTPS_KEY_STORE_FILE', 'KC_TRUSTSTORE_PATHS'):
                self.assertIn(Path(service['environment'][name]).name, pki_files)
                self.assertTrue(service['environment'][name].startswith('/opt/application/pki/'))
            self.assertTrue(service['environment']['KC_DB_URL'].endswith('sslrootcert=/opt/application/pki/ca-chain.pem'))
            self.assertNotIn('KC_HTTPS_CERTIFICATE_FILE', service['environment'])
            self.assertEqual({'library_secret': 'java_keystore_password'},
                settings['provisioner']['secret_bindings']['KC_HTTPS_KEY_STORE_PASSWORD']['source'])
            self.assertTrue(validate_compose(config, job, str(instance), digest))
    def test_start_priority_is_available_to_other_library_packages(self):
        validator = SchemaValidator(str(ROOT / 'contracts'))
        schema = ROOT / 'contracts/application-libraries/v1alpha1/library.schema.json'
        for library in ('sdku', 'cspa'):
            with self.subTest(library=library):
                path = (ROOT / f'examples/sdku/library-packages/{library}/1.0.0/roles/'
                        f'library_{library}/defaults/main.yml')
                definition = yaml.safe_load(path.read_text())['platform_library_definition']
                first_slot = next(iter(definition['slots']))
                definition['slots'][first_slot]['start_priority'] = 10
                self.assertEqual([], validator.validate(definition, str(schema)))

    def test_generic_script_arguments_have_no_container_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'application-packages/demo/1.0.0/assets/probe.sh'
            source.parent.mkdir(parents=True)
            source.write_text('#!/bin/sh\n', encoding='utf-8')
            snapshot = {'project': {'id': 'project'}, 'hosts': {'node1': {'ansibleHost': '10.0.0.1'}},
                        'applicationLibraries': {'libraries': {'demo': {'instances': {
                            'probe': {'applicationName': 'probe', 'placements': {'node1': {}}},
                        }}}}}
            script = {'id': 'probe', 'source': 'assets/probe.sh', 'phase': 'after_ready',
                      'argv': ['--project', {'valueFrom': 'projectId'}, '--id',
                               {'valueFrom': 'applicationId'}, '--host',
                               {'valueFrom': 'targetHostId'}],
                      'secretInputs': {'token': {'ref': 'probe-token'}}}
            jobs = [dict(libraryId='demo', instanceId='probe', hostId='node1',
                         applicationPackagePath='application-packages/demo/1.0.0',
                         libraryPackagePath='unused', packageApplicationScripts=[script],
                         packageLibraryScripts=[], settings={})]
            result = prepare_script_jobs(str(root), snapshot, {}, [], jobs)
            self.assertEqual(['--project', 'project', '--id', 'probe', '--host', 'node1'],
                             result[0]['scripts'][0]['argv'])
            self.assertEqual({'token': 'probe-token'}, result[0]['scripts'][0]['secretInputs'])
            self.assertFalse({'composeArgv', 'dockerEnvironment', 'containerName'} &
                             result[0]['scripts'][0].keys())

    def test_library_script_once_uses_a_host_that_has_an_instance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'library-packages/demo/1.0.0/assets/once.sh'
            source.parent.mkdir(parents=True)
            source.write_text('#!/bin/sh\n', encoding='utf-8')
            snapshot = {'hosts': {'node1': {'ansibleHost': '10.0.0.1'},
                                  'node2': {'ansibleHost': '10.0.0.2'}},
                        'applicationLibraries': {'libraries': {'demo': {'instances': {
                            'alpha': {'applicationName': 'alpha', 'placements': {'node2': {}}},
                            'beta': {'applicationName': 'beta', 'placements': {'node1': {}}},
                        }}}}}
            script = {'id': 'once', 'source': 'assets/once.sh', 'phase': 'before_start',
                      'execution': 'once'}
            jobs = [dict(libraryId='demo', instanceId=instance, hostId=host,
                         applicationPackagePath='unused',
                         libraryPackagePath='library-packages/demo/1.0.0',
                         packageApplicationScripts=[], packageLibraryScripts=[script],
                         settings={}) for instance, host in [('alpha', 'node2'), ('beta', 'node1')]]
            result = prepare_script_jobs(str(root), snapshot, {}, [], jobs)
            self.assertEqual([], result[0]['scripts'])
            self.assertEqual(['once'], [item['id'] for item in result[1]['scripts']])

    def test_keycloak_package_resolves_when_external_binary_inputs_are_present(self):
        root = ROOT / 'examples/szi'
        binaries = [root / 'application-packages/keycloak/1.0.0/assets/providers',
                    root / 'application-packages/keycloak/1.0.0/assets/themes.tar.gz',
                    root / 'library-packages/szi/1.0.0/assets/keycloak-clean.dump']
        if not all(path.exists() for path in binaries):
            self.skipTest('SZI binary inputs are supplied outside Git')
        loader = lambda path: yaml.safe_load(Path(path).read_text(encoding='utf-8'))
        validator = SchemaValidator(str(ROOT / 'contracts'))
        library = load_package(str(root), 'szi@1.0.0', 'library', loader, validator)
        keycloak = load_package(str(root), 'keycloak@1.0.0', 'application', loader, validator)
        self.assertIn('assets/keycloak-clean.dump', library['files'])
        self.assertEqual(['bootstrap-admin', 'create-admin'],
                         [item['id'] for item in keycloak['scripts'] if item['phase'] in ('before_start', 'after_ready')])
        self.assertEqual(['integrate-consumer'],
                         [item['id'] for item in keycloak['scripts'] if item['phase'] == 'connection_apply'])


if __name__ == '__main__':
    unittest.main()

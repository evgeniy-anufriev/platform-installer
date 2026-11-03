"""Registry reachability at Plan; image identity and invocation-local reuse at Apply."""
import copy
import hashlib
import http.server
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ansible-core/tools'))
sys.path.insert(0, str(ROOT / 'ansible-core/collections'))
sys.path.insert(0, str(ROOT / 'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils'))
from application_images import cached_image, image_credential_key, image_registry_key, registry_request
from application_plan import application_execution_model
from schema_validation import SchemaValidator
from test_application_plan import application_snapshot
from test_deployment_plan import catalog, runtime, sources
from execution_controller import validate_application_manifest
import execution_protocol as protocol
import execution_image_preparation as preparation
import execution_secret_lease as lease

INTENTS = 'platform.installer/application-image-intents/v1alpha1'


class RegistryAvailabilityTests(unittest.TestCase):
    def test_offline_plan_never_launches_an_ansible_image_child(self):
        with tempfile.TemporaryDirectory() as folder:
            ready = dict(apiVersion=INTENTS, placements={'sdku:gateway:node1': dict(reference='probe:qa', registry=False)})
            inputs = dict(runtimeRelease={}, placements=[], ready=ready, availabilityOnly=True)
            lease._write(str(Path(folder) / 'application-image-inputs.json'), inputs)
            with patch.object(preparation.subprocess, 'Popen', side_effect=AssertionError('offline image preparation forbidden')):
                result = preparation.prepare(SimpleNamespace(directory=folder), dict(inputsDigest=protocol.digest(inputs)), '/must-not-read', {})
            self.assertEqual('READY', result['status'])
            self.assertEqual(ready, json.loads((Path(folder) / 'application-images.json').read_text()))

    @unittest.skipUnless(shutil.which('ansible-playbook'), 'native Ansible required')
    def test_native_execution_preparation_resolves_an_existing_offline_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shutil.copytree(ROOT / 'examples/valid/application-runtime', root / 'project')
            (root / 'manifest.yaml').write_text('{}')
            variables = dict(platform_project_root=str(root / 'project'), platform_execution_bundle_root=str(root),
                platform_application_library_order=['cspa', 'sdku'],
                platform_service_catalog_path=str(ROOT / 'examples/catalog/service-catalog.yml'),
                platform_application_resolved_images_path=str(root / 'resolved.json'))
            (root / 'vars.json').write_text(json.dumps(variables))
            environment = dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'), ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections'))
            result = subprocess.run(['ansible-playbook', '-i', str(root / 'project/inventory/hosts.yml'),
                str(ROOT / 'ansible-core/playbooks/applications/images/execution.yml'), '-e', '@' + str(root / 'vars.json')],
                env=environment, capture_output=True, text=True, timeout=90)
            self.assertEqual(0, result.returncode, (result.stdout + result.stderr)[-2500:])
            self.assertEqual('platform.installer/container-images/v1alpha2', json.loads((root / 'resolved.json').read_text())['apiVersion'])
            # The shared Apply/Verify/post_install entry must read the run result,
            # even when the desired project has no technical image lock.
            resolved = json.loads((root / 'resolved.json').read_text())
            desired_path = root / 'project/inventory/group_vars/all/platform-installer.yml'
            desired = yaml.safe_load(desired_path.read_text())
            desired['platform_artifact_lock'].pop('x-container-images')
            desired_path.write_text(yaml.safe_dump(desired))
            variables.update(platform_application_image_intents=dict(apiVersion=INTENTS,
                placements={key: dict(reference=value['reference'], registry=False) for key, value in resolved['placements'].items()}),
                platform_application_post_install_only=True)
            (root / 'vars.json').write_text(json.dumps(variables))
            reused = subprocess.run(['ansible-playbook', '-i', str(root / 'project/inventory/hosts.yml'),
                str(ROOT / 'ansible-core/playbooks/applications/stages/resolve-runtime.yml'), '-e', '@' + str(root / 'vars.json')],
                env=environment, capture_output=True, text=True, timeout=90)
            self.assertEqual(0, reused.returncode, (reused.stdout + reused.stderr)[-2500:])

    def test_deferred_plan_and_private_manifest_validate_for_all_execution_modes(self):
        spec = importlib.util.spec_from_file_location('availability_plan', ROOT / 'ansible-core/collections/ansible_collections/platform/core/plugins/action/build_deployment_plan.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        validator = SchemaValidator(str(ROOT / 'contracts'))
        lock = dict(apiVersion=INTENTS, placements={'sdku:apigateway-sdku:node1': dict(reference='probe:qa', registry=False)})
        for mode in ('FULL_PROJECT', 'APPLICATION_LIBRARIES_ONLY', 'INFRASTRUCTURE_VERIFY_ONLY'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                action = object.__new__(module.ActionModule)
                action._task = SimpleNamespace(args=dict(snapshot=application_snapshot(), service_catalog=catalog(), runtime_release=runtime(),
                    bundle_artifact_sources=sources(), deployment_order=['provider', 'consumer'], execution_mode=mode,
                    application_image_lock=lock, application_image_metadata=True, deferred_application_images=True,
                    skip_application_libraries=[], application_library_order=['sdku'], skip_infrastructure_verify=False))
                destination = Path(folder) / 'manifest.json'
                with patch.dict(os.environ, PLATFORM_EXECUTION_MANIFEST_OUTPUT=str(destination)):
                    result = action.run()
                self.assertEqual([], validator.validate(result['deployment_plan'], ROOT / 'contracts/plan/v1alpha12/schema.json'))
                if destination.exists():
                    manifest = json.loads(destination.read_text())
                    self.assertEqual([], validator.validate(manifest, ROOT / 'contracts/execution-manifest/v1alpha9/schema.json'))
                    validate_application_manifest(manifest)

    def test_describe_deduplicates_host_registry_without_reading_bundle_or_credentials(self):
        spec = importlib.util.spec_from_file_location('availability_inputs', ROOT / 'ansible-core/collections/ansible_collections/platform/core/plugins/action/prepare_application_images.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        action = object.__new__(module.ActionModule)
        snapshot = application_snapshot(); snapshot['validation'] = {'status': 'PASS'}
        with tempfile.TemporaryDirectory() as folder:
            rows = [dict(libraryId='sdku', instanceId='image' + str(n), hostId=host,
                         settings={'image': 'registry.example/image' + str(n) + ':qa'}, registryCredentials={})
                    for host in ('node1', 'node2', 'offline') for n in range(3)]
            action._task = SimpleNamespace(args=dict(project_root=folder, bundle_root='must-not-read',
                snapshot=snapshot, application_rows=rows, connections={h: {'address': '192.0.2.1', 'port': 22} for h in ('node1', 'node2')}))
            action._loader = SimpleNamespace(load_from_file=lambda _: self.fail('Plan read image metadata'))
            result = action.run(task_vars=dict(platform_application_image_availability_only=True,
                hostvars={h: {'platform_application_approved_registries': [] if h == 'offline' else ['registry.example']} for h in ('node1', 'node2', 'offline')}))
            self.assertFalse(result.get('failed'), result)
            inputs = result['inputs']
            self.assertEqual(2, len(inputs['placements']))
            self.assertEqual([], inputs['requirements'])
            self.assertEqual(9, len(inputs['ready']['placements']))
            self.assertFalse(inputs['ready']['placements']['sdku:image0:offline']['registry'])

    def test_deferred_model_has_no_fabricated_identity_and_binds_declared_reference(self):
        snapshot = application_snapshot()
        lock = dict(apiVersion=INTENTS, placements={'sdku:apigateway-sdku:node1': dict(reference='probe:qa', registry=False)})
        model = application_execution_model(snapshot, lock)
        self.assertEqual([], model['findings'])
        image = model['artifactRequirements'][0]
        self.assertEqual('AT_EXECUTION', image['resolution'])
        self.assertNotIn('imageId', image)
        self.assertNotIn('platform', image)
        changed = copy.deepcopy(lock); changed['placements']['sdku:apigateway-sdku:node1']['reference'] = 'different:qa'
        self.assertNotEqual([], application_execution_model(snapshot, changed)['findings'])

    def test_cache_reuses_only_proved_anonymous_or_identical_explicit_context(self):
        platform = {'os': 'linux', 'architecture': 'amd64'}
        row = dict(hostId='node1', account='', configDirectory='', credentials={}, legacy={},
                   reference='registry.example/image:qa', request=registry_request('registry.example/image:qa'))
        image = dict(imageId='sha256:' + 'a' * 64, platform=platform)
        cache = {image_registry_key(row, platform, True, False): image}
        second = dict(row, hostId='node2')
        contexts = {image_credential_key(row): {'username': '', 'password': ''}}
        self.assertEqual({}, cached_image({}, second, platform, True, contexts, cache))
        contexts[image_credential_key(second)] = {'username': '', 'password': ''}
        self.assertEqual(image, cached_image({}, second, platform, True, contexts, cache)['image'])
        self.assertEqual({}, cached_image({}, second, platform, False, contexts, cache))
        self.assertEqual({}, cached_image({}, second, dict(platform, architecture='arm64'), True, contexts, cache))
        contexts[image_credential_key(second)] = {'username': 'node-login', 'password': 'test-only'}
        self.assertEqual({}, cached_image({}, second, platform, True, contexts, cache))
        explicit = dict(second, credentials={'username': {'source': {'ref': 'u'}}, 'password': {'source': {'ref': 'p'}}})
        explicit_cache = {image_registry_key(explicit, platform, True, False): image}
        self.assertEqual(image, cached_image({}, explicit, platform, True, {}, explicit_cache)['image'])
        other = dict(explicit, credentials={'username': {'source': {'ref': 'other'}}, 'password': {'source': {'ref': 'p'}}})
        self.assertEqual({}, cached_image({}, other, platform, True, {}, explicit_cache))

    def test_new_protocol_and_canonical_schemas_agree(self):
        sha = 'sha256:' + 'a' * 64
        base = dict(apiVersion=protocol.AVAILABILITY_REQUEST_VERSION, runId='installer-contract-123456',
                    runtimeRelease=dict(bundleDigest=sha, catalogDigest=sha, coreVersion='0.1.0', planningProtocol='v1alpha1'))
        scope = dict(executionMode='FULL_PROJECT', deploymentOrder=['docker'], skipInfrastructureVerify=False,
                     applicationLibraryOrder=['sdku'], skipApplicationLibraries=[], skipServiceDeployments=[])
        values = [dict(base, **scope, operation='PrepareApplicationImages', phase='DESCRIBE'),
                  dict(base, operation='PrepareApplicationImages', phase='PREPARE', inputsDigest=sha),
                  dict(base, **scope, operation='BuildDeploymentPlan', project='/var/tmp/project',
                       applicationVaultSources={}, applicationImagePreparation=sha)]
        validator = SchemaValidator(str(ROOT / 'contracts'))
        for mode, skip in [('APPLICATION_LIBRARIES_ONLY', False), ('APPLICATION_LIBRARIES_ONLY', True), ('INFRASTRUCTURE_VERIFY_ONLY', False)]:
            values += [dict(value, executionMode=mode, skipInfrastructureVerify=skip) for value in values[:1] + values[2:3]]
        for value in values:
            name = 'build-deployment-plan' if value['operation'] == 'BuildDeploymentPlan' else 'prepare-application-images'
            self.assertEqual([], validator.validate(value, str(ROOT / ('contracts/execution-runtime/v1alpha9/' + name + '.schema.json'))))
            with patch('sys.stdin', io.StringIO(json.dumps(value))):
                self.assertEqual(value, protocol.request())

    @unittest.skipUnless(shutil.which('ansible-playbook') and shutil.which('openssl'), 'native Ansible/OpenSSL required')
    def test_native_registry_probe_and_metadata_reuse_across_three_nodes(self):
        with tempfile.TemporaryDirectory(prefix='image-registry-') as folder:
            root = Path(folder); key = root / 'key.pem'; cert = root / 'cert.pem'
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1', '-subj', '/CN=localhost',
                            '-addext', 'subjectAltName=DNS:localhost', '-keyout', str(key), '-out', str(cert)],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            key.chmod(0o600)
            config = json.dumps(dict(os='linux', architecture='amd64')).encode()
            image_id = 'sha256:' + hashlib.sha256(config).hexdigest()
            manifest = json.dumps(dict(schemaVersion=2, mediaType='application/vnd.oci.image.manifest.v1+json',
                                       config=dict(digest=image_id))).encode()
            calls = []
            class Handler(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    calls.append(self.path)
                    body = b'{}' if self.path == '/v2/' else config if '/blobs/' in self.path else manifest
                    self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(body)
                def log_message(self, *args): pass
            server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); context.load_cert_chain(cert, key)
            server.socket = context.wrap_socket(server.socket, server_side=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            registry = 'localhost:' + str(server.server_port)
            inventory = {'all': {'hosts': {host: dict(ansible_connection='local', platform_application_approved_registries=[registry]) for host in ('node1', 'node2', 'node3')}}}
            (root / 'inventory.yml').write_text(yaml.safe_dump(inventory))
            placements = []
            for n in (1, 2):
                for host in ('node1', 'node2', 'node3'):
                    reference = registry + '/image' + str(n) + ':qa'
                    placements.append(dict(libraryId='sdku', instanceId='image' + str(n), hostId=host, reference=reference,
                        request=registry_request(reference), account='', configDirectory='', credentials={}, legacy={}))
            variables = dict(platform_application_image_inputs=dict(placements=placements, ready={}, targetConnections={h: {} for h in ('node1', 'node2', 'node3')}),
                             platform_application_image_bundle={}, platform_application_image_secret_values={}, platform_application_image_result_path=str(root / 'images.json'))
            environment = dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'), ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections'))
            try:
                for filename in ('prepare.yml', 'availability.yml'):
                    calls.clear()
                    plays = yaml.safe_load((ROOT / 'ansible-core/playbooks/applications/images' / filename).read_text())
                    for play in plays: play['module_defaults'] = {'ansible.builtin.uri': {'ca_path': str(cert)}}
                    if filename == 'availability.yml':
                        variables['platform_application_image_inputs']['placements'] = [dict(hostId=h, endpoint=registry) for h in ('node1', 'node2', 'node3')]
                    (root / 'probe.yml').write_text(yaml.safe_dump(plays)); (root / 'vars.json').write_text(json.dumps(variables))
                    shutil.copyfile(ROOT / 'ansible-core/playbooks/applications/images/placement.yml', root / 'placement.yml')
                    result = subprocess.run(['ansible-playbook', '-i', str(root / 'inventory.yml'), str(root / 'probe.yml'), '-e', '@' + str(root / 'vars.json')],
                                            env=environment, capture_output=True, text=True, timeout=120)
                    self.assertEqual(0, result.returncode, (result.stdout + result.stderr)[-2500:])
                    if filename == 'prepare.yml':
                        self.assertEqual(2, sum('/manifests/' in path for path in calls), calls)
                        self.assertEqual(2, sum('/blobs/' in path for path in calls), calls)
                        self.assertEqual(6, len(json.loads((root / 'images.json').read_text())['placements']))
                        # Verify must consume this run's exact result without touching the registry.
                        count = len(calls)
                        variables['platform_application_resolved_images_path'] = str(root / 'images.json')
                        (root / 'reuse.json').write_text(json.dumps(variables))
                        reused = subprocess.run(['ansible-playbook', '-i', str(root / 'inventory.yml'),
                            str(ROOT / 'ansible-core/playbooks/applications/images/execution.yml'), '-e', '@' + str(root / 'reuse.json')],
                            env=environment, capture_output=True, text=True, timeout=60)
                        self.assertEqual(0, reused.returncode, (reused.stdout + reused.stderr)[-2500:])
                        self.assertEqual(count, len(calls))
                    else: self.assertEqual(['/v2/'] * 3, calls)
            finally:
                server.shutdown(); server.server_close(); thread.join(timeout=5)

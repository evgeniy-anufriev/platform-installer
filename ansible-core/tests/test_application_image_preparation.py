"""Preparation lease scope and frozen image/legacy authority boundaries."""
import copy
import importlib.util
import json
import os
import subprocess
from pathlib import Path
import sys
import time
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ansible-core/tools'))
sys.path.insert(0, str(ROOT / 'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils'))
import execution_image_preparation as PREPARE
import execution_secret_lease as LEASE
from execution_lifecycle import LifecycleError
from application_images import registry_manifest, registry_config, selected_image, prepared_image
from application_runtime import resolve_image_lock
from application_plan import application_execution_model
from deployment_plan import build_runtime_secret_descriptors
from test_application_plan import application_snapshot, image_lock
from test_deployment_plan import catalog
from schema_validation import SchemaValidator


class ApplicationImagePreparationTests(unittest.TestCase):
    def test_native_ansible_callback_publishes_image_context(self):
        snapshot = application_snapshot()
        snapshot['validation'] = {'status': 'PASS'}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'manifest.yaml').write_text(json.dumps({'containerImages': []}))
            output = root / 'diagnostic.json'
            task = {'name': 'Describe image inputs', 'platform.core.prepare_application_images': {
                'project_root': directory, 'bundle_root': directory, 'snapshot': snapshot, 'connections': {},
                'application_rows': [dict(libraryId='sdku', instanceId='keycloak', hostId='localhost', runtimeRef='docker',
                    settings={'image': 'unassigned.invalid/keycloak:qa'}, registryCredentials={})]}, 'no_log': False}
            playbook = root / 'probe.json'
            playbook.write_text(json.dumps([dict(hosts='localhost', connection='local', gather_facts=False, tasks=[task])]))
            environment = dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
                ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections'),
                ANSIBLE_CALLBACKS_ENABLED='platform.core.deployment_plan_json', PLATFORM_CORE_DIAGNOSTIC_OUTPUT=str(output))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(playbook)], env=environment,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
            self.assertNotEqual(result.returncode, 0)
            diagnostic = json.loads(output.read_text())
            self.assertEqual(diagnostic['errorCode'], 'APPLICATION_IMAGE_NOT_LOCKED', result.stdout.decode(errors='replace')[-3000:])
            for value in ('sdku', 'keycloak', 'localhost', 'unassigned.invalid/keycloak:qa', 'Registry образа не разрешён'):
                self.assertIn(value, diagnostic['findings'][0]['safeMessage'])

    def test_library_registry_source_is_scoped_to_the_selected_row(self):
        path = ROOT / 'ansible-core/collections/ansible_collections/platform/core/plugins/action/prepare_application_images.py'
        spec = importlib.util.spec_from_file_location('prepare_images_action_test', path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        action = object.__new__(module.ActionModule)
        snapshot = application_snapshot()
        snapshot['validation'] = {'status': 'PASS'}
        snapshot['effectiveConfiguration'] = {'services': {'docker': {'configuration': {}}}}
        pair = {name: {'source': {'kind': 'runtime_secret_ref', 'ref': 'registry-' + name}} for name in ('username', 'password')}
        with tempfile.TemporaryDirectory() as root:
            action._task = SimpleNamespace(args={'project_root': root, 'bundle_root': root, 'snapshot': snapshot,
                'connections': {'node1': {'address': '192.0.2.1', 'port': 22}}})
            action._loader = SimpleNamespace(load_from_file=lambda _: {'containerImages': []})
            row = dict(libraryId='sdku', instanceId='apigateway-sdku', hostId='node1', runtimeRef='docker',
                       settings={'image': 'registry.example/probe:qa'}, registryCredentials={'registry.example': pair})
            values = {'platform_application_rows': [row], 'hostvars': {'node1': {'platform_application_approved_registries': []}}}
            with patch.object(module, 'application_execution_model', return_value={'runtimeSecretRequirements': []}):
                result = action.run(task_vars=values)
                self.assertFalse(result.get('failed'), result)
                self.assertEqual(result['inputs']['placements'][0]['credentials'], pair)
                row['registryCredentials'] = {'other.example': pair}
                failure = action.run(task_vars=values)
                self.assertEqual(failure['error_code'], 'APPLICATION_IMAGE_NOT_LOCKED')
                diagnostic = failure['finding']
                for text in ('sdku', 'apigateway-sdku', 'node1', 'registry.example/probe:qa', 'Registry образа не разрешён'):
                    self.assertIn(text, diagnostic['safeMessage'])
                self.assertNotIn('registry-username', diagnostic['safeMessage'])
                self.assertNotIn('registry-password', diagnostic['safeMessage'])
                self.assertLessEqual(len(diagnostic['safeMessage']), 512)
                self.assertEqual(diagnostic['field'], 'applicationImages.sdku.apigateway-sdku.node1')
                # The same code on a mismatched placement pin needs a different concrete reason.
                values['platform_artifact_lock'] = {'x-container-images': {'apiVersion': 'platform.installer/container-images/v1alpha2',
                    'placements': {'sdku:apigateway-sdku:node1': {'reference': 'registry.example/old:qa', 'image': {}}}}}
                failure = action.run(task_vars=values)
                self.assertEqual(failure['error_code'], 'APPLICATION_IMAGE_NOT_LOCKED')
                self.assertIn('Запись фиксации размещения', failure['finding']['safeMessage'])
                self.assertNotIn('не разрешён', failure['finding']['safeMessage'])
                row['settings']['image'] = 'https://user:private-test-value@registry.example/app:qa'
                failure = action.run(task_vars=values)
                self.assertNotIn('private-test-value', json.dumps(failure['finding']))

    def test_registry_assignment_requires_authority_and_never_a_url(self):
        validator = SchemaValidator(str(ROOT / 'contracts'))
        path = str(ROOT / 'contracts/application-libraries/v1alpha1/deployments.schema.json')
        pair = {name: dict(source=dict(kind='runtime_secret_ref', ref='registry-' + name)) for name in ('username', 'password')}
        library = dict(libraryRef='sdku@1.0.0', runtimeRef='docker')
        for authority in ('registry.example', 'localhost:5000', '192.168.56.101:5000'):
            self.assertEqual([], validator.validate(dict(sdku=dict(library, registry_credentials={authority: pair})), path))
        for authority in ('https://registry.example', 'registry.example/team', 'user@registry.example', '*.example',
                          '[::1]:5000', 'registry.example:', 'registry.example:port', 'Registry.example'):
            self.assertTrue(validator.validate(dict(sdku=dict(library, registry_credentials={authority: pair})), path), authority)

    def test_preparation_lease_is_not_an_execution_lease_and_cannot_change_scope(self):
        ref = 'application-secret-' + 'a' * 32
        inputs = dict(projectIdentity='fixture', projectRevision='sha256:' + 'b' * 64,
                      descriptorSetFingerprint='sha256:' + 'c' * 64, expiresAt=int(time.time()) + 120,
                      requirements=[dict(requirementRef=ref, runtimeReference='registry-user')], targetConnections={})
        journal = SimpleNamespace(run_id='installer-12345')
        release = {'bundleDigest': 'sha256:' + 'd' * 64}
        payload = dict(apiVersion=LEASE.TYPED_RUNTIME_SECRET_PAYLOAD_VERSION, kind='TargetCredentialLeasePayload',
                       username='fixture-user', password='fixture-ssh-only', privateKey=None, sudoPassword=None,
                       pkiStorePassword=None, runtimeSecretValues={ref: 'fixture-registry-only'}, runtimeSecretInputs=[])
        lease = dict(apiVersion=PREPARE.LEASE_VERSION, binding=PREPARE.binding(journal, inputs, release),
                     payload=payload, approvals=[])
        with patch.object(PREPARE.trust, '_known_hosts', return_value=b'fixture-trust'):
            _, _, values = PREPARE.preparation_payload(journal, inputs, release, lease)
            self.assertEqual(values, {'registry-user': 'fixture-registry-only'})
            other = copy.deepcopy(lease); other['binding']['preparationId'] = 'installer-54321'
            with self.assertRaises(LifecycleError):
                PREPARE.preparation_payload(journal, inputs, release, other)
            other = copy.deepcopy(lease); other['payload']['runtimeSecretValues']['unrelated-service'] = 'fixture-only'
            with self.assertRaises(LifecycleError):
                PREPARE.preparation_payload(journal, inputs, release, other)
            inputs['expiresAt'] = 0
            with self.assertRaisesRegex(LifecycleError, 'EXPIRED'):
                PREPARE.preparation_payload(journal, inputs, release, lease)
        with self.assertRaises(LifecycleError):
            LEASE._binding(lease['binding'])

    def test_frozen_placement_identity_cannot_override_a_legacy_pin(self):
        legacy = image_lock()
        entry = copy.deepcopy(legacy['images']['probe:qa'])
        frozen = dict(apiVersion='platform.installer/container-images/v1alpha2', placements={
            'sdku:apigateway-sdku:node1': dict(reference='probe:qa', image=entry)})
        wrapper = {'x-container-images': legacy}
        self.assertEqual(resolve_image_lock(wrapper, None, frozen), frozen)
        entry['imageId'] = 'sha256:' + 'e' * 64
        with self.assertRaisesRegex(ValueError, 'CONFLICT'):
            resolve_image_lock(wrapper, None, frozen)

    def test_registry_digests_and_fallback_are_bound_to_content(self):
        import hashlib
        config = json.dumps(dict(os='linux', architecture='amd64'))
        image_id = 'sha256:' + hashlib.sha256(config.encode()).hexdigest()
        raw = json.dumps(dict(mediaType='application/vnd.oci.image.manifest.v1+json', config=dict(digest=image_id)))
        descriptor = registry_manifest(raw, dict(os='linux', architecture='amd64'))
        image = registry_config(config, descriptor, 'nginx:qa', dict(os='linux', architecture='amd64'))
        self.assertEqual(image['registry']['reference'], 'docker.io/library/nginx:qa')
        with self.assertRaisesRegex(ValueError, 'DIGEST'):
            registry_manifest(raw, dict(os='linux', architecture='amd64'), 'sha256:' + 'f' * 64)
        older = dict(imageId='sha256:' + 'f' * 64, platform=image['platform'], archive={'ref': 'runtime/artifacts/old.tar'})
        self.assertNotIn('archive', prepared_image(image, older))
        for config_platform, target, compatible in [
                (dict(os='windows', architecture='amd64'), dict(os='linux', architecture='amd64'), False),
                (dict(os='linux', architecture='arm64', variant='v8'), dict(os='linux', architecture='arm64'), True)]:
            other = json.dumps(config_platform)
            other_descriptor = dict(descriptor, configDigest='sha256:' + hashlib.sha256(other.encode()).hexdigest())
            result = registry_config(other, other_descriptor, 'example.test/app:qa', target)
            self.assertEqual(bool(result), compatible)
            if compatible:
                self.assertEqual(result['platform'], config_platform)

    def test_registry_descriptors_precede_image_preparation_and_follow_actual_source(self):
        snapshot = application_snapshot()
        library = snapshot['applicationLibraries']['libraries']['sdku']
        library['registryCredentials'] = {'registry.example': {
            name: dict(source=dict(kind='runtime_secret_ref', ref='registry-' + name)) for name in ('username', 'password')}}
        descriptors = build_runtime_secret_descriptors(snapshot, catalog(), application_image_lock=image_lock())
        self.assertEqual(descriptors['apiVersion'], 'BuildRuntimeSecretDescriptors/v1alpha4')
        self.assertEqual({item['purpose'] for item in descriptors['applicationInputs']},
                         {'APPLICATION_REGISTRY_USERNAME', 'APPLICATION_REGISTRY_PASSWORD'})
        validator = SchemaValidator(str(ROOT / 'contracts'))
        self.assertEqual([], validator.validate(descriptors, str(ROOT / 'contracts/runtime-secret-descriptors/v1alpha4/schema.json')))
        lock = image_lock(); lock['images']['probe:qa'].pop('registry')
        lock['images']['probe:qa']['archive'] = dict(ref='runtime/artifacts/app.tar', sha256='sha256:' + 'a' * 64, size=1)
        self.assertEqual(application_execution_model(snapshot, lock)['runtimeSecretRequirements'], [])

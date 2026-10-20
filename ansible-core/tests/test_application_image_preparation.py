"""Preparation lease scope and frozen image/legacy authority boundaries."""
import copy
import json
from pathlib import Path
import sys
import time
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

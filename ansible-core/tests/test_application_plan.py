"""A7 contracts: target-free descriptions and the fixed existing execution path."""
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'ansible-core/tools'))
from test_deployment_plan import snapshot, catalog, runtime, sources, _build_deployment_plan, DIGEST
from application_plan import application_execution_model, application_operation, OPERATIONS
from deployment_plan import build_runtime_secret_descriptors
from schema_validation import SchemaValidator
import execution_controller as CONTROLLER
import execution_secret_lease as LEASE
from execution_lifecycle import Journal, LifecycleError
from test_execution_secret_lease import request, runtime_secret_payload


def application_snapshot():
    value = snapshot()
    value['apiVersion'] = 'platform.installer/project-snapshot/v2alpha1'
    value['applicationLibraries'] = dict(status='PASS', findings=[], libraries={
        'sdku': dict(resources={}, packages={'apigateway': dict(application=DIGEST, library=DIGEST)},
                     sharedSecretRequirements={}, instances={
            'apigateway-sdku': dict(slotId='api', imageRequirement={'image': 'probe:qa'}, agentRequired=False,
                                   placements={'node1': {}}, credentialRequirements={}, connections={})})})
    return value


def image_lock():
    return dict(apiVersion='platform.installer/container-images/v1alpha1', images={
        'probe:qa': dict(imageId=DIGEST, platform={'os': 'linux', 'architecture': 'amd64'},
                         registry={'reference': 'registry.example/probe:qa', 'manifestDigest': DIGEST})})


class ApplicationPlanTests(unittest.TestCase):
    def test_multiple_libraries_require_explicit_order_bound_to_plan_fingerprint(self):
        value = application_snapshot()
        value['applicationLibraries']['libraries']['szi'] = copy.deepcopy(
            value['applicationLibraries']['libraries']['sdku'])
        self.assertIn('APPLICATION_LIBRARY_ORDER_REQUIRED',
                      [item['code'] for item in application_execution_model(value, image_lock())['findings']])
        first = application_execution_model(value, image_lock(), ['szi', 'sdku'])
        reverse = application_execution_model(value, image_lock(), ['sdku', 'szi'])
        self.assertEqual([], first['findings'])
        self.assertEqual(['szi', 'sdku'], first['libraryIds'])
        self.assertNotEqual(first['semanticFingerprint'], reverse['semanticFingerprint'])
        self.assertIn('APPLICATION_LIBRARY_ORDER_INVALID', [item['code'] for item in
                      application_execution_model(value, image_lock(), ['szi', 'szi'])['findings']])

    def build(self, value=None, lock=None):
        return _build_deployment_plan(value or application_snapshot(), catalog(), runtime(),
                                      application_image_lock=lock or image_lock(),
                                      bundle_artifact_sources=sources(),
                                      deployment_order=['provider', 'consumer'])

    def test_application_plan_has_executable_manifest_and_all_infrastructure_barrier(self):
        result = self.build()
        plan = result['deploymentPlan']
        self.assertEqual('platform.installer/plan/v1alpha4', plan['apiVersion'])
        self.assertEqual('EXECUTABLE', plan['status'])
        self.assertIsNotNone(result['executionManifest'])
        self.assertIsNotNone(result['executionManifestDigest'])
        self.assertEqual(['verify:consumer', 'verify:provider'], plan['phases'][-1]['actions'][0]['dependsOn'])
        self.assertEqual(OPERATIONS, [a['type'] for a in plan['phases'][-1]['actions']])
        validator = SchemaValidator(str(REPO / 'contracts'))
        self.assertEqual([], validator.validate(plan, str(REPO / 'contracts/plan/v1alpha4/schema.json')))
        self.assertEqual([], validator.validate(result['executionManifest'], str(REPO / 'contracts/execution-manifest/v1alpha2/schema.json')))
        for operation in result['executionManifest']['operations'][-2:]:
            self.assertEqual([], validator.validate(operation, str(REPO / 'contracts/execution-manifest/v1alpha2/application-operation.schema.json')))

    def test_no_network_probe_or_observation_in_plan(self):
        with patch('socket.socket', side_effect=AssertionError('Target contact forbidden')):
            first = self.build()
            second = self.build()
        self.assertEqual(first, second)
        self.assertNotIn('packageSource', json.dumps(first))
        images = [item for item in first['deploymentPlan']['artifactRequirements'] if item.get('artifactType') == 'container-image']
        self.assertNotIn('OFFLINE_BUNDLE', json.dumps(images))

    def test_changed_placement_image_and_binding_change_fingerprint(self):
        original = self.build()['deploymentPlan']['fingerprints']['plan']
        for section in ('resources', 'packages', 'sharedSecretRequirements'):
            value = application_snapshot()
            library = value['applicationLibraries']['libraries']['sdku']
            if section == 'sharedSecretRequirements':
                library[section]['shared'] = {'source': {'kind': 'runtime_secret_ref', 'ref': 'shared-key'}}
            else:
                library[section]['new'] = {'id': 'changed'}
            self.assertNotEqual(original, self.build(value)['deploymentPlan']['fingerprints']['plan'])

    def test_host_image_overrides_are_distinct_requirements(self):
        value, lock = application_snapshot(), image_lock()
        value['hosts']['node2'] = {}
        value['applicationLibraries']['libraries']['sdku']['instances']['apigateway-sdku']['placements']['node2'] = {
            'imageRequirement': {'image': 'probe:other'}}
        lock['images']['probe:other'] = dict(lock['images']['probe:qa'], imageId='sha256:' + 'b' * 64)
        requirements = application_execution_model(value, lock)['artifactRequirements']
        self.assertEqual([['node1'], ['node2']], [r['hosts'] for r in requirements])
        self.assertNotEqual(requirements[0]['imageId'], requirements[1]['imageId'])

    def test_missing_or_unknown_major_lock_has_precise_finding(self):
        for lock in ({}, dict(image_lock(), apiVersion='platform.installer/container-images/v9')):
            findings = application_execution_model(application_snapshot(), lock)['findings']
            self.assertTrue(any(f['field'] == 'artifactLock.x-container-images' for f in findings))

    def test_account_and_shared_secret_refs_deduplicate_without_values(self):
        value = application_snapshot()
        library = value['applicationLibraries']['libraries']['sdku']
        source = dict(kind='runtime_secret_ref', ref='common-password')
        library['sharedSecretRequirements']['shared'] = {'source': source}
        library['instances']['apigateway-sdku']['credentialRequirements']['redis'] = {'credentials': {'password': {'source': source}}}
        model = application_execution_model(value, image_lock())
        self.assertEqual(1, len(model['runtimeSecretRequirements']))
        descriptors = build_runtime_secret_descriptors(value, catalog())
        self.assertEqual('BuildRuntimeSecretDescriptors/v1alpha3', descriptors['apiVersion'])
        self.assertEqual(1, len(descriptors['applicationInputs']))
        self.assertNotIn('value', descriptors['applicationInputs'][0])
        validator = SchemaValidator(str(REPO / 'contracts'))
        self.assertEqual([], validator.validate(descriptors, str(REPO / 'contracts/runtime-secret-descriptors/v1alpha3/schema.json')))

    def test_script_and_application_bindings_share_one_runtime_reference(self):
        value = application_snapshot()
        library = value['applicationLibraries']['libraries']['sdku']
        instance = library['instances']['apigateway-sdku']
        instance['scripts'] = [
            {'id': 'before', 'secretInputs': {'shared': {'ref': 'shared-key'}, 'script': {'ref': 'script-key'}}},
            {'id': 'after', 'secretInputs': {'script': {'ref': 'script-key'}}},
        ]
        library['sharedSecretRequirements']['shared'] = {
            'source': {'kind': 'runtime_secret_ref', 'ref': 'shared-key'}}
        requirements = application_execution_model(value, image_lock())['runtimeSecretRequirements']
        self.assertEqual(2, len(requirements))
        by_ref = {item['runtimeReference']: item for item in requirements}
        self.assertEqual('APPLICATION_SECRET', by_ref['shared-key']['purpose'])
        self.assertEqual(OPERATIONS, by_ref['shared-key']['operations'])
        self.assertEqual('APPLICATION_SECRET', by_ref['script-key']['purpose'])
        self.assertEqual(OPERATIONS, by_ref['script-key']['operations'])
        with patch.object(LEASE, 'runtime_secret_values_for_run', return_value={
                item['requirementRef']: 'synthetic-value' for item in requirements}):
            self.assertEqual({'shared-key': 'synthetic-value', 'script-key': 'synthetic-value'},
                LEASE.application_secret_values_for_operation('/unused', 'run-1', OPERATIONS[0], requirements))
        descriptors = build_runtime_secret_descriptors(value, catalog())
        self.assertEqual(2, len(descriptors['applicationInputs']))
        validator = SchemaValidator(str(REPO / 'contracts'))
        self.assertEqual([], validator.validate(descriptors, str(REPO / 'contracts/runtime-secret-descriptors/v1alpha3/schema.json')))
        result = _build_deployment_plan(value, catalog(), runtime(), application_image_lock=image_lock(),
            deployment_order=['provider', 'consumer'], bundle_artifact_sources=sources())
        self.assertEqual('EXECUTABLE', result['deploymentPlan']['status'])
        CONTROLLER.validate_application_manifest(result['executionManifest'])

    def test_no_accounts_or_agent_requires_no_application_secrets(self):
        self.assertEqual([], application_execution_model(application_snapshot(), image_lock())['runtimeSecretRequirements'])

    def test_descriptor_quantity_uses_response_byte_bound(self):
        value = application_snapshot()
        library = value['applicationLibraries']['libraries']['sdku']
        library['sharedSecretRequirements'] = {
            'secret-%s' % i: {'source': {'kind': 'runtime_secret_ref', 'ref': 'secret-%s' % i}}
            for i in range(40)}
        result = build_runtime_secret_descriptors(value, catalog())
        self.assertEqual(40, len(result['applicationInputs']))
        validator = SchemaValidator(str(REPO / 'contracts'))
        self.assertEqual([], validator.validate(result, str(REPO / 'contracts/runtime-secret-descriptors/v1alpha3/schema.json')))
        library['sharedSecretRequirements'] = {
            'secret-%s' % i: {'source': {'kind': 'runtime_secret_ref', 'ref': 'secret-%s' % i}}
            for i in range(600)}
        with self.assertRaisesRegex(ValueError, 'RUNTIME_SECRET_DESCRIPTORS_BLOCKED'):
            build_runtime_secret_descriptors(value, catalog())

    def test_vault_token_has_explicit_provider_and_application_scope(self):
        value = application_snapshot()
        instance = value['applicationLibraries']['libraries']['sdku']['instances']['apigateway-sdku']
        instance.update(agentRequired=True, connections={'vault': {'deploymentRef': 'vault-main', 'serviceType': 'vault'}})
        requirement = application_execution_model(value, image_lock())['runtimeSecretRequirements'][0]
        self.assertEqual('APPLICATION_VAULT_ADMIN_TOKEN', requirement['purpose'])
        self.assertEqual('vault-main', requirement['providerDeployment'])
        self.assertEqual(['sdku'], requirement['applicationLibraries'])

    def test_fixed_command_and_closed_descriptor_reject_extra_argv(self):
        model = application_execution_model(application_snapshot(), image_lock())
        with tempfile.TemporaryDirectory() as directory:
            journal = SimpleNamespace(directory=directory)
            for action in model['actions']:
                operation = application_operation(action, model)
                import hashlib
                path = Path(directory) / ('.runtime-projection-' + hashlib.sha256(operation['operationId'].encode()).hexdigest() + '.json')
                path.write_text('{}')
                command = CONTROLLER._command('/release', journal, operation)
                self.assertIn('application-libraries-' + operation['operationId'].split(':')[1] + '.yml', command[3])
                self.assertEqual('localhost:node1', command[-1])
                with self.assertRaisesRegex(LifecycleError, 'EXECUTION_MANIFEST_INVALID'):
                    CONTROLLER._command('/release', journal, dict(operation, argv=['bad']))

    def test_attached_lease_scope_missing_and_tampered_requirement(self):
        value = application_snapshot()
        library = value['applicationLibraries']['libraries']['sdku']
        library['sharedSecretRequirements']['shared'] = {'source': {'kind': 'runtime_secret_ref', 'ref': 'shared-key'}}
        requirements = application_execution_model(value, image_lock())['runtimeSecretRequirements']
        with tempfile.TemporaryDirectory() as root:
            req = request()
            result = LEASE.put(root, req, runtime_secret_payload({requirements[0]['requirementRef']: 'synthetic-value'}))
            LEASE.attach(root, result['leaseId'], req, 'run-1')
            self.assertEqual({'shared-key': 'synthetic-value'}, LEASE.application_secret_values_for_operation(root, 'run-1', OPERATIONS[0], requirements))
            numeric_host = dict(requirements[0], hosts=['1node'])
            self.assertEqual({'shared-key': 'synthetic-value'}, LEASE.application_secret_values_for_operation(root, 'run-1', OPERATIONS[0], [numeric_host]))
            for host in ('node.one', 'node_one', 'n' * 64, '-node'):
                with self.subTest(host=host), self.assertRaisesRegex(LifecycleError, 'EXECUTION_MANIFEST_INVALID'):
                    LEASE.application_secret_values_for_operation(root, 'run-1', OPERATIONS[0], [dict(requirements[0], hosts=[host])])
            for bad in (dict(requirements[0], operations=['SERVICE_APPLY']), dict(requirements[0], providerDeployment='other')):
                with self.assertRaisesRegex(LifecycleError, 'EXECUTION_MANIFEST_INVALID'):
                    LEASE.application_secret_values_for_operation(root, 'run-1', OPERATIONS[0], [bad])

    def test_exact_application_credential_cleanup_preserves_unrelated_and_symlinks(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, 'run-1')
            os.makedirs(journal.directory, mode=0o700)
            secret = Path(journal.directory) / ('.runtime-application-secret-' + 'a' * 64)
            secret.write_text('synthetic-value')
            unrelated = Path(journal.directory) / 'preserved'
            unrelated.write_text('public')
            link = Path(journal.directory) / ('.runtime-application-secret-' + 'b' * 64)
            link.symlink_to(unrelated)
            journal.cleanup_runtime_secret_inputs()
            self.assertFalse(secret.exists())
            self.assertTrue(unrelated.exists())
            self.assertTrue(link.is_symlink())

    def test_private_projection_reuses_run_custody_and_native_runtime_inputs(self):
        value = application_snapshot()
        library = value['applicationLibraries']['libraries']['sdku']
        library['sharedSecretRequirements']['shared'] = {'source': {'kind': 'runtime_secret_ref', 'ref': 'shared-key'}}
        model = application_execution_model(value, image_lock())
        operations = [application_operation(action, model) for action in model['actions']]
        manifest = dict(operations=operations, artifactRequirements=[], artifactSourceAuthorities=[],
                        runtimeSecretRequirements=[], pkiMaterializationPlans=[],
                        applicationSecretRequirements=model['runtimeSecretRequirements'])
        metadata = dict(runId='run-1', projectIdentity='project-a', planFingerprint=DIGEST,
                        manifestDigest=DIGEST, runtimeRelease=DIGEST)
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, 'run-1')
            os.makedirs(journal.directory, mode=0o700)
            with patch.object(LEASE, 'target_username_for_run', return_value=None), \
                 patch.object(LEASE, 'application_secret_values_for_operation', return_value={'shared-key': 'synthetic-value'}):
                CONTROLLER._materialize_runtime_projection(journal, metadata, manifest)
                self.assertFalse(list(Path(journal.directory).glob('.runtime-application-secret-*')))
                CONTROLLER._materialize_application_projection(journal, manifest)
            import hashlib
            paths = []
            for operation in operations:
                path = Path(journal.directory) / ('.runtime-projection-' + hashlib.sha256(operation['operationId'].encode()).hexdigest() + '.json')
                projection = json.loads(path.read_text())
                self.assertEqual(journal.directory, projection['platform_application_secret_root'])
                self.assertEqual(model['semanticFingerprint'], projection['platform_application_expected_fingerprint'])
                self.assertEqual(['sdku'], projection['platform_application_expected_library_ids'])
                secret_path = Path(projection['platform_application_secret_files']['shared-key'])
                self.assertEqual(0o600, secret_path.stat().st_mode & 0o777)
                paths.append(secret_path)
            self.assertEqual(paths[0], paths[1])
            journal.cleanup_runtime_secret_inputs()
            self.assertFalse(paths[0].exists())


if __name__ == '__main__':
    unittest.main()

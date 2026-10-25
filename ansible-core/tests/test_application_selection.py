"""Selection never removes the definitions needed by an existing provider."""
import copy
import json
from pathlib import Path
import sys
import unittest
import hashlib
import importlib
import os
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils'))
from application_selection import execution_scope, scoped_snapshot, selected_rows, integration_consumers
from schema_validation import SchemaValidator
from test_application_plan import application_snapshot, image_lock
from application_plan import application_execution_model, application_operation


def fixture():
    connection = dict(serviceType='application', libraryId='identity', applicationId='api')
    return {'applicationLibraries': {'libraries': {
        'identity': {'instances': {'api': {}, 'internal': {'connections': {'auth': connection}}}},
        'first': {'instances': {'web-first': {'connections': {'auth': connection}, 'placements': {}}}},
        'second': {'instances': {'web-second': {'connections': {'auth': connection}, 'placements': {}}}},
    }}}


class ApplicationSelectionTests(unittest.TestCase):
    def test_invalid_action_input_returns_only_a_safe_code(self):
        sys.path.insert(0, str(ROOT/'ansible-core/collections'))
        module = importlib.import_module('ansible_collections.platform.core.plugins.action.prepare_application_selection')
        action = module.ActionModule.__new__(module.ActionModule)
        action._task = SimpleNamespace(args={'snapshot_result': {'snapshot': fixture()}})
        result = action.run(task_vars={'platform_application_skip_libraries': ['unknown']})
        self.assertEqual(dict(changed=False, status='BLOCKED', code='APPLICATION_LIBRARY_SELECTION_INVALID'), result)

    def test_skipped_library_remains_provider_but_not_consumer(self):
        snapshot = fixture()
        scope = execution_scope(snapshot, ['identity', 'first', 'second'], ['identity'])
        self.assertEqual(['first', 'second'], scope['installLibraries'])
        self.assertEqual(['identity/api'], scope['providerInstances'])
        self.assertNotIn('identity/internal', scope['consumerInstances'])
        derived = scoped_snapshot(snapshot, scope)
        self.assertIs(derived['applicationLibraries'], snapshot['applicationLibraries'])
        self.assertNotIn('applicationExecutionScope', snapshot)

    def test_route_consumers_exclude_skipped_libraries(self):
        snapshot = fixture()
        scope = execution_scope(snapshot, skipped=['identity', 'second'])
        rows = integration_consumers(scoped_snapshot(snapshot, scope), 'identity')
        self.assertEqual(['web-first'], [row['applicationId'] for row in rows])

    def test_no_skip_preserves_every_instance(self):
        scope = execution_scope(fixture())
        self.assertEqual(['first', 'identity', 'second'], scope['installLibraries'])
        self.assertEqual(4, len(scope['consumerInstances']))

    def test_selection_is_normalized_without_changing_order(self):
        a = execution_scope(fixture(), ['identity', 'second', 'first'], ['first', 'identity'])
        b = execution_scope(fixture(), ['identity', 'second', 'first'], ['identity', 'first'])
        self.assertEqual(a, b)
        self.assertEqual(['second'], a['installLibraries'])

    def test_invalid_selection_and_order_are_rejected(self):
        for skipped in (['missing'], ['first', 'first'], 'first', [None]):
            with self.subTest(skipped=skipped), self.assertRaisesRegex(ValueError, 'SELECTION_INVALID'):
                execution_scope(fixture(), skipped=skipped)
        with self.assertRaisesRegex(ValueError, 'ORDER_INVALID'):
            execution_scope(fixture(), ['first'])

    def test_disabled_connection_and_unrelated_library_add_no_provider(self):
        snapshot = fixture()
        snapshot['applicationLibraries']['libraries']['first']['instances']['web-first']['connections'] = {}
        scope = execution_scope(snapshot, skipped=['identity', 'second'])
        self.assertEqual([], scope['providerLibraries'])

    def test_all_skipped_has_no_jobs_or_integrations(self):
        snapshot = fixture()
        scope = execution_scope(snapshot, skipped=['identity', 'first', 'second'])
        self.assertEqual([], scope['consumerInstances'])
        self.assertEqual([], scope['providerInstances'])
        self.assertEqual([], selected_rows([{'libraryId': 'first'}], scope))

    def test_projection_does_not_revalidate_resolver_connections(self):
        snapshot = copy.deepcopy(fixture())
        del snapshot['applicationLibraries']['libraries']['identity']
        scope = execution_scope(snapshot)
        self.assertEqual(['first', 'second'], scope['installLibraries'])
        self.assertEqual(['identity/api'], scope['providerInstances'])
        self.assertEqual([], scope['providerLibraries'])

    def test_integration_metadata_does_not_copy_credentials_or_runtime_fields(self):
        snapshot = fixture()
        snapshot['applicationLibraries']['libraries']['first']['instances']['web-first']['placements'] = {
            'node': {'endpoint': {'enabled': True}, 'parameters': {'mode': 'public'},
                     'accounts': {'password': 'fixture-not-for-argv'}, 'image': 'not-for-argv'}}
        rows = integration_consumers(snapshot, 'identity')
        self.assertEqual({'endpoint', 'parameters'}, set(rows[0]['placements']['node']))

    def test_startup_routes_use_the_same_selected_core_projection_as_integration_argv(self):
        from jinja2 import Environment
        snapshot = fixture()
        consumer = snapshot['applicationLibraries']['libraries']['first']['instances']['web-first']
        consumer['placements'] = {'node-b': {'endpoint': {'enabled': True, 'endpoint_group': 'apps'},
                                           'parameters': {'IDENTITY_ROUTE': {'site': 'b'}}},
                                  'node-a': {'endpoint': {'enabled': True, 'endpoint_group': 'apps'},
                                           'parameters': {'IDENTITY_ROUTE': {'site': 'a'}}}}
        snapshot = scoped_snapshot(snapshot, execution_scope(snapshot, skipped=['identity', 'second']))
        rows = integration_consumers(snapshot, 'identity', {'endpointGroups': {'apps': {'address': {'domain': 'example.test'}}}})
        template = ROOT/'examples/szi/application-packages/nginx/1.0.0/assets/routes.requested.json.j2'
        environment = Environment()
        environment.filters['to_json'] = json.dumps
        result = json.loads(environment.from_string(template.read_text()).render(
            application_runtime_job=dict(projectId='project', libraryId='identity', integrationConsumers=rows),
            application_instance_id='gateway'))
        self.assertEqual({'web-first'}, set(result['routes']))
        self.assertEqual('https://web-first.example.test', result['routes']['web-first']['endpoint'])
        self.assertEqual({'site': 'a'}, result['routes']['web-first']['parameters'])


class IntegrationScriptSchemaTests(unittest.TestCase):
    def validate(self, version, phase='integration_apply', execution='each_target', run_on='target'):
        manifest = dict(apiVersion='platform.installer/application-package/' + version,
                        kind='ApplicationPackage', name='sample', version='1.0.0',
                        files=['roles/application_sample/defaults/main.yml', 'assets/integration.sh'],
                        scripts=[dict(id='integrate', source='assets/integration.sh', phase=phase,
                                      execution=execution, run_on=run_on,
                                      argv=[{'valueFrom': 'integration_consumers'}])])
        validator = SchemaValidator(str(ROOT/'contracts'))
        return validator.validate(manifest, str(ROOT/'contracts/application-libraries'/version/'package.schema.json'))

    def test_new_package_supports_each_target_and_execution_node_once(self):
        self.assertFalse(self.validate('v1alpha2'))
        self.assertFalse(self.validate('v1alpha2', execution='once'))
        self.assertFalse(self.validate('v1alpha2', execution='once', run_on='execution_node'))

    def test_old_schema_cannot_silently_accept_new_script_feature(self):
        self.assertTrue(self.validate('v1alpha1'))

    def test_execution_node_cannot_repeat_per_target(self):
        self.assertTrue(self.validate('v1alpha2', run_on='execution_node'))


class ApplicationSelectionPlanTests(unittest.TestCase):
    def test_standalone_action_returns_digest_of_the_written_versioned_manifest(self):
        sys.path.insert(0, str(ROOT/'ansible-core/collections'))
        module = importlib.import_module('ansible_collections.platform.core.plugins.action.build_deployment_plan')
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder)/'manifest.json'
            action = module.ActionModule.__new__(module.ActionModule)
            action._task = SimpleNamespace(args=dict(snapshot=fixture(), application_library_order=['identity', 'first', 'second'],
                                                    skip_application_libraries=['identity']))
            result = dict(deploymentPlan={}, executionManifest={'kind': 'ExecutionManifest'}, executionManifestDigest='old')
            with patch.object(module, 'build_deployment_plan', return_value=result), \
                 patch('infrastructure_verification.scope_plan', side_effect=lambda result, *args: result), \
                 patch.dict(os.environ, {'PLATFORM_EXECUTION_MANIFEST_OUTPUT': str(destination)}):
                actual = action.run()
            self.assertEqual('sha256:' + hashlib.sha256(destination.read_bytes()).hexdigest(), actual['execution_manifest_digest'])
            self.assertEqual('platform.installer/execution-manifest/v1alpha6', json.loads(destination.read_text())['apiVersion'])

    def project(self):
        snapshot = application_snapshot()
        libraries = snapshot['applicationLibraries']['libraries']
        libraries['provider'] = copy.deepcopy(libraries['sdku'])
        provider = libraries['provider']
        provider['instances'] = {'api': provider['instances'].pop('apigateway-sdku')}
        provider['instances']['api']['placements'] = {'node2': {}}
        provider['instances']['api']['scripts'] = [dict(
            id='client', phase='connection_apply', execution='once', secretInputs={
                'TOKEN': dict(valueFrom='provided_connection', name='api', credential='token')})]
        provider['providedConnections'] = {'api': {'credentials': {'token': {'source': {
            'kind': 'runtime_secret_ref', 'ref': 'provider-token'}}}}}
        provider['sharedSecretRequirements'] = {'own': {'source': {
            'kind': 'runtime_secret_ref', 'ref': 'unneeded-own-secret'}}}
        provider['instances']['api']['placements']['node2']['imageRequirement'] = {'image': 'unneeded:qa'}
        consumer = libraries['sdku']['instances']['apigateway-sdku']
        consumer['connections']['sso'] = dict(serviceType='application', libraryId='provider',
            applicationId='api', startupPriority=0, targets=[{'hostId': 'node2'}],
            connectionProvisioner={'apply_script': 'client'})
        return snapshot

    def model(self, snapshot=None, skipped=None):
        return application_execution_model(snapshot or self.project(), image_lock(),
                                           ['provider', 'sdku'], skipped)

    def test_skip_omits_own_images_and_secrets_but_keeps_callback_credential(self):
        model = self.model(skipped=['provider'])
        self.assertEqual([], model['findings'])
        self.assertEqual(['sdku'], model['libraryIds'])
        self.assertEqual(['sdku'], [x['applicationLibrary'] for x in model['artifactRequirements']])
        self.assertEqual(['provider-token'], [x['runtimeReference'] for x in model['runtimeSecretRequirements']])
        self.assertEqual(['APPLICATION_LIBRARIES_APPLY'], model['runtimeSecretRequirements'][0]['operations'])
        self.assertEqual(['node2'], model['runtimeSecretRequirements'][0]['hosts'])
        self.assertEqual(['node1', 'node2'], model['actions'][0]['targets'])

    def test_full_definitions_are_preserved_and_selection_changes_fingerprint(self):
        snapshot = self.project()
        before = copy.deepcopy(snapshot)
        selected = self.model(snapshot, ['provider'])
        full = self.model(snapshot)
        self.assertEqual(before, snapshot)
        self.assertNotEqual(full['semanticFingerprint'], selected['semanticFingerprint'])
        operation = application_operation(selected['actions'][0], selected)
        self.assertEqual(['provider'], operation['applicationExecutionScope']['skippedLibraries'])

    def test_all_skipped_has_no_application_actions_or_requirements(self):
        model = self.model(skipped=['provider', 'sdku'])
        self.assertEqual([], model['findings'])
        for key in ('actions', 'artifactRequirements', 'runtimeSecretRequirements'):
            self.assertEqual([], model[key], key)

    def test_empty_skip_preserves_legacy_fingerprint_and_operation(self):
        self.assertEqual(self.model(), self.model(skipped=[]))
        model = self.model()
        self.assertNotIn('applicationExecutionScope', application_operation(model['actions'][0], model))

    def test_invalid_selection_is_a_blocking_finding(self):
        self.assertIn('APPLICATION_LIBRARY_SELECTION_INVALID',
                      [x['code'] for x in self.model(skipped=['unknown'])['findings']])

    def test_integration_hook_credentials_are_apply_only(self):
        snapshot = application_snapshot()
        snapshot['applicationLibraries']['libraries']['sdku']['scripts'] = [dict(
            id='routes', phase='integration_apply', secretInputs={'TOKEN': {'ref': 'hook-token'}})]
        model = application_execution_model(snapshot, image_lock())
        self.assertEqual([], model['findings'])
        self.assertEqual(['APPLICATION_LIBRARIES_APPLY'], model['runtimeSecretRequirements'][0]['operations'])


if __name__ == '__main__':
    unittest.main()

"""Selection exercises the actual request -> Core plan -> manifest admission path."""
import copy
import os
import shutil
import subprocess
import yaml
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_application_plan import application_snapshot, image_lock, CONTROLLER
from test_deployment_plan import _build_deployment_plan, catalog, runtime, sources
from service_selection import execution_scope, select_pki, promote
from application_selection import execution_scope as library_scope
from application_progress import describe_progress
from infrastructure_verification import scope_plan
from schema_validation import SchemaValidator
import execution_protocol as protocol

ROOT = Path(__file__).resolve().parents[2]

class ServiceSelectionTests(unittest.TestCase):
    def build(self, skipped=None, state=None, sources_override=None, definitions=None, vault_sources=None):
        state = state or application_snapshot()
        result = _build_deployment_plan(state, definitions or catalog(), runtime(), application_vault_sources=vault_sources, bundle_artifact_sources=sources() if sources_override is None else sources_override,
            deployment_order=['provider', 'consumer'], application_image_lock=image_lock(), skip_service_deployments=skipped)
        result = scope_plan(result, 'FULL_PROJECT', '/nonexistent-qa')
        scope = library_scope(state)
        result['executionManifest'].update(apiVersion='platform.installer/execution-manifest/v1alpha6',
            skipApplicationLibraries=scope['skippedLibraries'], applicationExecutionScope=scope, skipInfrastructureVerify=False)
        describe_progress(result, scope)
        if skipped is not None:
            promote(result, execution_scope(state['serviceDeployments'], ['provider', 'consumer'], skipped))
        return result

    def test_partial_skip_removes_lifecycle_preserves_snapshot_and_application(self):
        state = application_snapshot()
        state['applicationLibraries']['libraries']['sdku']['instances']['apigateway-sdku']['connections']['db'] = {
            'serviceType': 'provider', 'deploymentRef': 'provider'}
        original = copy.deepcopy(state)
        result = self.build(['provider'], state)
        self.assertEqual(original, state)
        plan, manifest = result['deploymentPlan'], result['executionManifest']
        self.assertEqual('EXECUTABLE', plan['status'])
        self.assertEqual(['consumer', 'consumer'], [op['serviceDeployment'] for op in manifest['operations'] if op['operation'].startswith('SERVICE_')])
        actions = [a for p in plan['phases'] for a in p['actions']]
        self.assertNotIn('verify:provider', [d for a in actions for d in a['dependsOn']])
        self.assertTrue(any(op['operation'] == 'APPLICATION_LIBRARIES_APPLY' for op in manifest['operations']))
        for directory, version, value in [('plan','v1alpha11',plan), ('execution-manifest','v1alpha8',manifest)]:
            self.assertEqual([], SchemaValidator(str(ROOT/'contracts')).validate(value, ROOT/'contracts'/directory/version/'schema.json'))
        CONTROLLER.validate_application_manifest(manifest)

    def test_skipped_artifacts_do_not_require_offline_source(self):
        result = self.build(['consumer'], sources_override=[])
        self.assertEqual('EXECUTABLE', result['deploymentPlan']['status'])
        self.assertTrue(all(item.get('serviceDeployment') != 'consumer' for item in result['deploymentPlan']['artifactRequirements']))

    def test_selection_bound_to_fingerprint_and_repeat_deterministic(self):
        self.assertEqual(self.build(['provider']), self.build(['provider']))
        self.assertNotEqual(self.build([])['deploymentPlan']['id'], self.build(['provider'])['deploymentPlan']['id'])

    def test_duplicate_unknown_and_all_selection(self):
        for skipped in (['unknown'], ['provider', 'provider'], 'provider'):
            with self.subTest(skipped=skipped), self.assertRaisesRegex(ValueError, 'SERVICE_SELECTION_INVALID'):
                self.build(skipped)
        with self.assertRaisesRegex(ValueError, 'SERVICE_SELECTION_USE_SKIP_INFRA_VERIFY'):
            self.build(['provider', 'consumer'])
        # Whole-infrastructure skip keeps the already supported mechanism.
        result = scope_plan(_build_deployment_plan(application_snapshot(), catalog(), runtime(), deployment_order=['provider','consumer'],
            bundle_artifact_sources=sources(), application_image_lock=image_lock()), 'APPLICATION_LIBRARIES_ONLY', '/nonexistent-qa', True)
        self.assertTrue(all(op['operation'].startswith('APPLICATION_LIBRARIES_') for op in result['executionManifest']['operations']))

    def test_pki_filters_consumers_and_hosts_without_mutation(self):
        pki = {'requests': [{'id':'shared','consumers':[{'deploymentId':'provider','hostId':'node1'},{'deploymentId':'consumer','hostId':'node2'}]}],
            'materializationPlans':[{'requestId':'shared','hostId':'node1'},{'requestId':'shared','hostId':'node2'}]}
        self.assertEqual([{'requestId':'shared','hostId':'node2'}], select_pki(pki, {'consumer'})['materializationPlans'])
        self.assertEqual(2, len(pki['requests'][0]['consumers']))

    def test_manifest_cannot_smuggle_skipped_operation(self):
        manifest = self.build(['provider'])['executionManifest']
        next(op for op in manifest['operations'] if op['operation'] == 'SERVICE_APPLY')['serviceDeployment'] = 'provider'
        with self.assertRaisesRegex(Exception, 'SERVICE_SELECTION_MANIFEST_MISMATCH'):
            CONTROLLER.validate_application_manifest(manifest)

    def test_all_service_passwords_retained_like_skip_infra_verify(self):
        state, definitions = application_snapshot(), catalog()
        definitions['definitions']['provider']['configuration'] = {'settings': {'admin': {
            'ui': {'x-runtimeSecretRequirement': {'requirementRef':'existing-password', 'purpose':'SERVICE_PASSWORD'}},
            'schema': {'type':'object','additionalProperties':False,'required':['passwordSecretRef'],
                       'properties':{'passwordSecretRef':{'type':'string'}}}}}}
        state['serviceDeployments']['provider']['configuration'] = {'admin': {'passwordSecretRef':'runtime:existing-admin'}}
        self.assertTrue(any(r['requirementRef'] == 'existing-password' for r in self.build(['provider'],state,definitions=definitions)['deploymentPlan']['requiredCredentials']))
        state['applicationLibraries']['libraries']['sdku']['connections'] = {'database': {'deploymentRef':'provider'}}
        result = self.build(['provider'],state,definitions=definitions)
        self.assertTrue(any(r['requirementRef'] == 'existing-password' for r in result['deploymentPlan']['requiredCredentials']))
        self.assertFalse(any(op.get('serviceDeployment') == 'provider' for op in result['executionManifest']['operations']))

    def test_skipped_service_has_no_installation_secret_inputs(self):
        definitions = catalog()
        definitions['definitions']['provider']['x-secretInputs'] = {'apiVersion':'ServiceSecretInputs/v1alpha1','inputs':[
            {'requirementRef':'admin-token','purpose':'SERVICE_ADMIN_TOKEN','displayLabel':'Admin token',
             'requiredWhen':'INITIALIZED','operations':['SERVICE_APPLY','SERVICE_VERIFY']}]}
        result = self.build(['provider'], definitions=definitions)
        self.assertEqual('EXECUTABLE', result['deploymentPlan']['status'])
        self.assertEqual([], result['executionManifest']['runtimeSecretInputs'])

    def test_skipped_vault_requires_runtime_token_and_preserves_consumer(self):
        state, definitions = application_snapshot(), catalog()
        definitions['definitions']['vault'] = definitions['definitions'].pop('provider')
        definitions['definitions']['vault']['x-secretOutputs'] = {'protocol':'SecretOutputDelivery/v1alpha1','entries':['admin-token','unseal-shares']}
        state['serviceDeployments']['provider']['serviceType'] = 'vault'
        instance = state['applicationLibraries']['libraries']['sdku']['instances']['apigateway-sdku']
        instance['connections']['vault'] = {'deploymentRef':'provider','serviceType':'vault'}
        instance['agentRequired'] = True
        result = self.build(['provider'], state, definitions=definitions)
        self.assertEqual('EXECUTABLE', result['deploymentPlan']['status'])
        self.assertTrue(any(item['purpose']=='APPLICATION_VAULT_ADMIN_TOKEN' for item in result['executionManifest']['applicationSecretRequirements']))
        CONTROLLER.validate_application_manifest(result['executionManifest'])
        blocked = _build_deployment_plan(state, definitions, runtime(), bundle_artifact_sources=sources(), application_image_lock=image_lock(),
            deployment_order=['provider','consumer'], skip_service_deployments=['provider'], application_vault_sources={'provider':'CURRENT_RUN_BOOTSTRAP'})
        self.assertIn('APPLICATION_BOOTSTRAP_PROVIDER_INVALID',[f['code'] for f in blocked['deploymentPlan']['findings']])

    def test_real_request_parser_matches_schema(self):
        request = dict(apiVersion=protocol.SERVICE_SELECTION_REQUEST_VERSION, operation='BuildDeploymentPlan', runId='run-selection', project='/project',
            runtimeRelease=runtime(), deploymentOrder=['provider','consumer'], applicationLibraryOrder=['sdku'], applicationVaultSources={},
            executionMode='FULL_PROJECT', skipInfrastructureVerify=False, applicationImagePreparation='sha256:'+'a'*64,
            skipApplicationLibraries=[], skipServiceDeployments=['provider'])
        self.assertEqual([], SchemaValidator(str(ROOT/'contracts')).validate(request, ROOT/'contracts/execution-runtime/v1alpha8/build-deployment-plan.schema.json'))
        with patch.object(sys, 'stdin', io.StringIO(json.dumps(request))):
            self.assertEqual(request, protocol.request())
        request['skipServiceDeployments'] = ['provider','provider']
        with patch.object(sys, 'stdin', io.StringIO(json.dumps(request))), self.assertRaisesRegex(Exception, 'SERVICE_SELECTION_INVALID'):
            protocol.request()

class NativeServiceSelectionTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('ansible-playbook'), 'native Ansible required')
    def test_actual_planner_action_repeat_and_manifest_admission(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            args = dict(snapshot=application_snapshot(), service_catalog=catalog(), runtime_release=runtime(),
                bundle_artifact_sources=sources(), application_image_lock=image_lock(),
                application_image_metadata=True, deployment_order=['provider','consumer'],
                application_library_order=['sdku'], skip_application_libraries=[], skip_service_deployments=['provider'],
                execution_mode='FULL_PROJECT', pki_state_root=str(root/'state'))
            play = [{'hosts':'localhost', 'connection':'local', 'gather_facts':False, 'tasks':[
                {'name':'Plan selected service lifecycle', 'platform.core.build_deployment_plan':args, 'register':'first'},
                {'name':'Repeat the same planner call', 'platform.core.build_deployment_plan':args, 'register':'second'},
                {'name':'Assert deterministic target-free selection', 'ansible.builtin.assert':{'that':[
                    'first.deployment_plan.id == second.deployment_plan.id', 'not first.changed', 'not second.changed',
                    "first.deployment_plan.skipServiceDeployments == ['provider']",
                    "first.deployment_plan.phases | selectattr('id', 'equalto', 'services') | map(attribute='actions') | flatten | map(attribute='serviceDeployment') | list == ['consumer','consumer']"]}}
            ]}]
            (root/'play.yml').write_text(yaml.safe_dump(play, allow_unicode=True))
            env = dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(ROOT/'ansible-core/collections'),
                PLATFORM_EXECUTION_MANIFEST_OUTPUT=str(root/'manifest.json'))
            result = subprocess.run(['ansible-playbook','-i','localhost,',str(root/'play.yml')],env=env,text=True,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60)
            self.assertEqual(0,result.returncode,result.stdout[-3000:]+result.stderr[-700:])
            manifest = json.loads((root/'manifest.json').read_text())
            CONTROLLER.validate_application_manifest(manifest)
            self.assertEqual('platform.installer/execution-manifest/v1alpha8',manifest['apiVersion'])

    @unittest.skipUnless(shutil.which('ansible-playbook'), 'native Ansible required')
    def test_actual_pki_module_scopes_shared_consumers_and_repeats(self):
        from test_pki_resolution import PkiResolutionTests
        desired = PkiResolutionTests().topology()
        desired['serviceDeployments'].pop('keepalived-asutp')
        desired['serviceDeployments']['service-a'].pop('endpointGroup')
        desired['serviceDeployments']['service-b'] = copy.deepcopy(desired['serviceDeployments']['service-a'])
        hosts = {'node1': {'ansible_host':'192.0.2.10','platform_deployments': {
            key: {'members': {key+'-member': {'roles':['server']}}} for key in ('service-a','service-b')}}}
        args = dict(desired_state=desired,inventory_hosts=hosts,project_id='pki-selection',
            pki_defaults=PkiResolutionTests.defaults,deployment_selection=['service-a'])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            play = [{'hosts':'localhost','connection':'local','gather_facts':False,'tasks':[
                {'platform.core.resolve_pki_requests':args,'register':'first'},
                {'platform.core.resolve_pki_requests':args,'register':'second'},
                {'ansible.builtin.assert':{'that':['first.pki == second.pki','not first.changed',
                    "first.pki.requests | map(attribute='consumers') | flatten | map(attribute='deploymentId') | unique | list == ['service-a']",
                    'first.pki.materializationPlans | length == 1']}}
            ]}]
            (root/'play.yml').write_text(yaml.safe_dump(play))
            env=dict(os.environ,ANSIBLE_COLLECTIONS_PATH=str(ROOT/'ansible-core/collections'))
            result=subprocess.run(['ansible-playbook','-i','localhost,',str(root/'play.yml')],env=env,text=True,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60)
            self.assertEqual(0,result.returncode,result.stdout[-2500:]+result.stderr[-700:])

if __name__ == '__main__':
    unittest.main()

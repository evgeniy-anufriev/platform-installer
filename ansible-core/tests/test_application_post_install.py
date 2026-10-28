"""Terminal scripts through the real plan/manifest admission and native runner."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'ansible-core/tools'), str(ROOT/'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils')]
from application_post_install import OPERATION, promote, validation_prefix, script_queue
from application_plan import application_execution_model
from application_selection import execution_scope
from schema_validation import SchemaValidator
from test_application_plan import ApplicationPlanTests, application_snapshot, image_lock
from infrastructure_verification import scope_plan
from execution_controller import validate_application_manifest, _command
from execution_lifecycle import LifecycleError
from unittest.mock import patch
import tempfile
import execution_controller as controller
import execution_secret_lease as lease
from execution_lifecycle import Journal
from test_deployment_plan import DIGEST


class PostInstallTests(unittest.TestCase):
    def fixture(self):
        value = application_snapshot()
        value['applicationLibraries']['libraries']['sdku']['instances']['apigateway-sdku']['scripts'] = [dict(
            id='finish', phase='post_install', order=0, secretInputs={'TOKEN': {'ref': 'finish-token'}})]
        return value

    def build(self, mode='FULL_PROJECT'):
        snapshot = self.fixture()
        result = ApplicationPlanTests().build(snapshot)
        result = scope_plan(result, mode, '/nonexistent-post-install-qa', mode == 'APPLICATION_LIBRARIES_ONLY')
        return promote(result, execution_scope(snapshot), mode == 'APPLICATION_LIBRARIES_ONLY')

    def test_schemas_and_controller_accept_the_same_real_plan(self):
        validator = SchemaValidator(str(ROOT/'contracts'))
        for mode in ('FULL_PROJECT', 'APPLICATION_LIBRARIES_ONLY'):
            result = self.build(mode)
            plan, manifest = result['deploymentPlan'], result['executionManifest']
            self.assertEqual(OPERATION, manifest['operations'][-1]['operation'])
            self.assertEqual(['APPLICATION_LIBRARIES_POST_INSTALL'], next(
                item for item in manifest['applicationSecretRequirements'] if item['runtimeReference'] == 'finish-token')['operations'])
            self.assertEqual([], validator.validate(plan, ROOT/'contracts/plan/v1alpha9/schema.json'))
            self.assertEqual([], validator.validate(manifest, ROOT/'contracts/execution-manifest/v1alpha7/schema.json'))
            validate_application_manifest(manifest)
            command = _command('/release', type('Journal', (), {'directory': '/run'})(), manifest['operations'][-1])
            self.assertEqual('/release/ansible-core/playbooks/applications/post-install.yml', command[3])
            self.assertNotIn('applications/verify.yml', command)

    def test_verify_only_has_no_terminal_operation(self):
        result = self.build('INFRASTRUCTURE_VERIFY_ONLY')
        self.assertFalse(any(item['operation'] == OPERATION for item in result['executionManifest']['operations']))

    def test_terminal_suffix_preserves_planned_infrastructure_verify_prefix(self):
        import infrastructure_verification as infra
        snapshot = self.fixture()
        result = ApplicationPlanTests().build(snapshot)
        result = scope_plan(result, 'APPLICATION_LIBRARIES_ONLY', '/nonexistent-post-install-qa', False)
        manifest = promote(result, execution_scope(snapshot))['executionManifest']
        self.assertTrue(infra.has_library_verify_prefix(manifest))
        infra.assert_admission('/nonexistent-post-install-qa', manifest)
        validate_application_manifest(manifest)

    def test_skip_omits_terminal_actions_and_requirements(self):
        model = application_execution_model(self.fixture(), image_lock(), ['sdku'], ['sdku'])
        self.assertFalse(model['postInstall'])
        self.assertEqual([], model['actions'])
        self.assertEqual([], model['runtimeSecretRequirements'])

    def test_old_package_rejects_new_phase(self):
        validator = SchemaValidator(str(ROOT/'contracts'))
        for version in ('v1alpha2', 'v1alpha3'):
            package = dict(apiVersion='platform.installer/application-package/'+version, kind='ApplicationPackage',
                           name='sample', version='1.0.0', files=['assets/finish.sh'],
                           scripts=[dict(id='finish', source='assets/finish.sh', phase='post_install', execution='once', run_on='execution_node')])
            self.assertEqual(version == 'v1alpha2', bool(validator.validate(package, ROOT/'contracts/application-libraries'/version/'package.schema.json')))

    def test_invalid_order_duplicate_scope_and_permissions_are_rejected(self):
        original = self.build()['executionManifest']
        mutations = [lambda m: m['operations'].reverse(),
                     lambda m: m['operations'].append(copy.deepcopy(m['operations'][-1])),
                     lambda m: m['operations'][-1].update(applicationLibraries=['other']),
                     lambda m: m['applicationSecretRequirements'][0].update(operations=[OPERATION, OPERATION])]
        for mutate in mutations:
            manifest = copy.deepcopy(original)
            mutate(manifest)
            with self.assertRaises((LifecycleError, ValueError)):
                validate_application_manifest(manifest)

    def test_generated_binding_resolves_to_existing_account_custody(self):
        from application_scripts import _secret_reference
        from runtime_secret_identity import generated_password_ref
        job = dict(projectId='project', libraryId='sdku', instanceId='data-manager-sdku',
                   secretBindings={'DB_PASSWORD': {'source': {'account': 'postgres', 'field': 'password'}}})
        reference = _secret_reference({'kind': 'generated'}, {'valueFrom': 'secret_binding', 'binding': 'DB_PASSWORD'}, job)
        self.assertEqual(generated_password_ref('project', 'sdku', 'data-manager-sdku', 'postgres'), reference)

    def test_terminal_private_inputs_are_removed_by_run_cleanup(self):
        import hashlib
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, 'run-post-cleanup')
            journal.initialize(dict(projectIdentity='project-a', planFingerprint=DIGEST,
                manifestDigest=DIGEST, runtimeRelease=DIGEST, unit='platform-installer-run-run-post-cleanup.service'))
            names = ['.runtime-projection-'+hashlib.sha256(b'applications:post-install').hexdigest()+'.json',
                     'pla-generated-'+'a'*40, 'pla-vault-'+'b'*32]
            for name in names + ['keep.txt']:
                path = Path(journal.directory)/name
                path.write_text('private fixture')
                path.chmod(0o600)
            journal.cleanup_runtime_secret_inputs()
            self.assertFalse(any((Path(journal.directory)/name).exists() for name in names))
            self.assertTrue((Path(journal.directory)/'keep.txt').exists())

    def test_queue_orders_mixed_scopes_and_hosts(self):
        jobs = [dict(libraryId=lib, instanceId=instance, hostId=host, scripts=[dict(
            id='finish', order=0, phase='post_install', scope=scope)])
            for lib, instance, host, scope in [('a', 'z', 'b', 'instance'), ('b', 'x', 'a', 'instance'),
                                             ('a', 'a', 'a', 'instance'), ('a', 'z', 'a', 'library')]]
        queue = script_queue(jobs, ['b', 'a'])
        self.assertEqual([('b', 'instance', 'x', 'a'), ('a', 'library', 'z', 'a'),
                          ('a', 'instance', 'a', 'a'), ('a', 'instance', 'z', 'b')],
                         [(x['libraryId'], x['scope'], x['instanceId'], x['hostId']) for x in queue])

    def test_dispatch_runs_terminal_last_and_stops_after_failure_or_cancel(self):
        manifest = self.build()['executionManifest']
        manifest['operations'] = [x for x in manifest['operations'] if x['operation'] != 'PKI_APPLY']
        for outcome in ('success', 'failure', 'cancel'):
            with tempfile.TemporaryDirectory() as root:
                journal = Journal(root, 'run-post-install-test')
                journal.initialize(dict(projectIdentity='project-a', planFingerprint=DIGEST,
                    manifestDigest=DIGEST, runtimeRelease=DIGEST, unit='platform-installer-run-run-post-install-test.service'))
                stopped, executed = [False], []
                def wait(process, *_args):
                    executed.append(process.args[0])
                    if process.args[0] == 'applications:apply':
                        if outcome == 'cancel':
                            stopped[0] = True
                        if outcome == 'failure':
                            return 1, 'SYNTHETIC_FAILURE', None
                    return 0, '', None
                with patch.object(controller, '_command', side_effect=lambda _r, _j, op: [op['operationId']]), \
                     patch.object(controller, '_claim_raw_ansible_failure_capture', return_value=False), \
                     patch.object(controller, '_environment', return_value={}), \
                     patch.object(controller.subprocess, 'Popen', side_effect=lambda args, **kw: type('P', (), {'args': args})()), \
                     patch.object(controller, '_wait_for_operation', side_effect=wait), \
                     patch.object(controller.execution_target_trust, 'verify'), \
                     patch.object(lease, 'ansible_connection_credentials_for_run', return_value=None), \
                     patch.object(lease, 'runtime_secret_inputs_for_operation', return_value=[]), \
                     patch.object(controller, '_materialize_application_projection'):
                    if outcome == 'failure':
                        with self.assertRaises(LifecycleError):
                            controller._dispatch(root, journal, manifest, stopped)
                    else:
                        self.assertEqual('SUCCEEDED' if outcome == 'success' else 'CANCELLED', controller._dispatch(root, journal, manifest, stopped))
                self.assertEqual(outcome == 'success', 'applications:post-install' in executed)
                if outcome == 'success':
                    self.assertEqual('applications:post-install', executed[-1])


if __name__ == '__main__':
    unittest.main()

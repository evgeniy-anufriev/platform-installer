"""A8 mixed graph, secret handoff and failure/cancel boundary regression."""
import copy
from contextlib import ExitStack
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from test_application_plan import application_snapshot, image_lock, REPO
from test_deployment_plan import catalog, runtime, sources, _build_deployment_plan, DIGEST
import execution_controller as controller
import execution_protocol as protocol
import execution_secret_lease as lease
import execution_secret_output as output
from execution_lifecycle import Journal, LifecycleError


def mixed(vault=False, source='RUNTIME_INPUT'):
    value, definitions = application_snapshot(), catalog()
    if vault:
        value['serviceDeployments']['provider']['serviceType'] = 'vault'
        definitions['definitions']['vault'] = dict(definitions['definitions']['provider'],
            **{'x-secretOutputs': {'protocol': 'SecretOutputDelivery/v1alpha1', 'entries': ['admin-token', 'unseal-shares']}})
        app = value['applicationLibraries']['libraries']['sdku']['instances']['apigateway-sdku']
        app['agentRequired'] = True
        app['connections']['vault'] = {'serviceType': 'vault', 'deploymentRef': 'provider',
                                      'targets': [{'hostId': 'node1'}]}
    return _build_deployment_plan(value, definitions, runtime(), application_image_lock=image_lock(),
        deployment_order=['provider', 'consumer'], bundle_artifact_sources=sources(),
        application_vault_sources={'provider': source} if vault else {})


class MixedExecutionTests(unittest.TestCase):
    def test_closed_manifest_rejects_reorder_missing_verify_and_unknown_field(self):
        valid = mixed()['executionManifest']
        controller.validate_application_manifest(valid)
        for change in ('reorder', 'missing', 'unknown', 'duplicate', 'source'):
            bad = copy.deepcopy(valid)
            if change == 'reorder':
                bad['operations'][-3], bad['operations'][-2] = bad['operations'][-2], bad['operations'][-3]
            elif change == 'missing':
                bad['operations'] = [op for op in bad['operations'] if op['operationId'] != 'verify:consumer']
            elif change == 'unknown':
                bad['argv'] = ['unsafe']
            elif change == 'duplicate':
                bad['operations'].insert(0, bad['operations'][1])
            else:
                bad = mixed(True)['executionManifest']
                bad['applicationSecretRequirements'][0]['source'] = 'LATEST_TOKEN'
            with self.subTest(change=change), self.assertRaises(LifecycleError):
                controller.validate_application_manifest(bad)

    def test_bootstrap_source_is_manifest_bound_and_not_operator_requirement(self):
        fresh, existing = mixed(True, 'CURRENT_RUN_BOOTSTRAP'), mixed(True)
        self.assertEqual('EXECUTABLE', fresh['deploymentPlan']['status'])
        self.assertEqual([], fresh['deploymentPlan']['requiredCredentials'])
        self.assertEqual(1, len(existing['deploymentPlan']['requiredCredentials']))
        self.assertNotEqual(fresh['deploymentPlan']['fingerprints']['plan'], existing['deploymentPlan']['fingerprints']['plan'])
        controller.validate_application_manifest(fresh['executionManifest'])
        with patch.object(lease, 'runtime_secret_values_for_run', side_effect=AssertionError('No operator token')):
            self.assertEqual({}, lease.application_secret_values_for_operation('/unused', 'run-1',
                'APPLICATION_LIBRARIES_APPLY', fresh['executionManifest']['applicationSecretRequirements']))

    def test_unrelated_inventory_host_is_not_application_target(self):
        snapshot = application_snapshot()
        snapshot['hosts']['unrelated'] = {}
        result = _build_deployment_plan(snapshot, catalog(), runtime(), application_image_lock=image_lock(),
                                       deployment_order=['provider', 'consumer'], bundle_artifact_sources=sources())
        self.assertEqual(['node1'], result['deploymentPlan']['phases'][-1]['actions'][0]['targets'])

    def test_current_run_token_uses_existing_custody_and_rejects_other_run_provider(self):
        with tempfile.TemporaryDirectory() as root:
            journal = Journal(root, 'installer-test')
            os.makedirs(journal.directory, mode=0o700)
            directory = output.prepare_retained_output_directory(root, journal.directory,
                'project-a', 'provider', journal.run_id, DIGEST)
            token = Path(directory, 'admin-token')
            token.write_text('synthetic-token'); token.chmod(0o600)
            self.assertEqual('synthetic-token', output.current_run_admin_token(root, journal.directory,
                'project-a', 'provider', journal.run_id))
            for provider, run in [('other', journal.run_id), ('provider', 'installer-other')]:
                with self.assertRaises(output.OutputWireError):
                    output.current_run_admin_token(root, journal.directory, 'project-a', provider, run)
            token.unlink(); token.symlink_to('/etc/passwd')
            with self.assertRaises((OSError, output.OutputWireError)):
                output.current_run_admin_token(root, journal.directory, 'project-a', 'provider', journal.run_id)

    def test_failure_and_boundary_cancel_never_materialize_application_secrets(self):
        manifest = mixed()['executionManifest']
        # Avoid PKI in this dispatch fixture: the barrier under test is service Verify.
        manifest['operations'] = [op for op in manifest['operations'] if op['operation'] != 'PKI_APPLY']
        for outcome in ('failure', 'application-failure', 'cancel', 'success'):
            with tempfile.TemporaryDirectory() as root:
                journal = Journal(root, 'run-test')
                journal.initialize(dict(projectIdentity='project-a', planFingerprint=DIGEST,
                    manifestDigest=DIGEST, runtimeRelease=DIGEST, unit='platform-installer-run-run-test.service'))
                stopped, executed = [False], []
                def command(_release, _journal, op):
                    return [op['operationId']]
                def wait(process, *_args):
                    executed.append(process.args[0])
                    if outcome == 'cancel' and process.args[0] == 'verify:consumer':
                        stopped[0] = True
                    failed = outcome == 'failure' or (outcome == 'application-failure' and process.args[0] == 'applications:apply')
                    return (1, 'SYNTHETIC_FAILURE', None) if failed else (0, '', None)
                with patch.object(controller, '_command', side_effect=command), \
                     patch.object(controller, '_claim_raw_ansible_failure_capture', return_value=False), \
                     patch.object(controller, '_environment', return_value={}), \
                     patch.object(controller.subprocess, 'Popen') as popen, \
                     patch.object(controller, '_wait_for_operation', side_effect=wait), \
                     patch.object(controller.execution_target_trust, 'verify'), \
                     patch.object(lease, 'ansible_connection_credentials_for_run', return_value=None), \
                     patch.object(lease, 'runtime_secret_inputs_for_operation', return_value=[]), \
                     patch.object(controller, '_materialize_application_projection') as materialize:
                    popen.side_effect = lambda args, **_kwargs: type('Process', (), {'args': args})()
                    if outcome in ('failure', 'application-failure'):
                        with self.assertRaises(LifecycleError):
                            controller._dispatch(root, journal, manifest, stopped)
                    else:
                        self.assertEqual('CANCELLED' if outcome == 'cancel' else 'SUCCEEDED',
                                         controller._dispatch(root, journal, manifest, stopped))
                    self.assertEqual(1 if outcome in ('success', 'application-failure') else 0, materialize.call_count)
                    if outcome == 'application-failure':
                        self.assertIn('applications:apply', executed)
                        self.assertNotIn('applications:verify', executed)
                    elif outcome != 'success':
                        self.assertFalse(any(name.startswith('applications:') for name in executed))

    def test_materialization_errors_and_cancel_use_existing_terminal_cleanup(self):
        for failure in ('read', 'secret_written', 'projection_write', 'cancel'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as root:
                manifest = mixed(True, 'CURRENT_RUN_BOOTSTRAP')['executionManifest']
                manifest['operations'] = [op for op in manifest['operations'] if op['operation'] != 'PKI_APPLY']
                journal = Journal(root, 'installer-test')
                journal.initialize(dict(projectIdentity=manifest['projectIdentity'],
                    planFingerprint=manifest['planFingerprint'], manifestDigest=controller.digest(manifest),
                    runtimeRelease=DIGEST, unit='platform-installer-run-installer-test.service'))
                Path(journal.directory, 'manifest.json').write_text(json.dumps(manifest))
                projection = Path(journal.directory, 'runtime-projection.json')
                projection.write_text('invalid-json' if failure == 'read' else json.dumps({'platform_pki_secret_files': {}}))
                retained = output.prepare_retained_output_directory(root, journal.directory,
                    manifest['projectIdentity'], 'provider', journal.run_id, DIGEST)
                token = Path(retained, 'admin-token')
                token.write_text('synthetic-token'); token.chmod(0o600)
                # Existing attached custody; cleanup must remove the payload, not bootstrap output.
                lease_root, lease_id = lease._root(root), 'a' * 32
                lease_dir = lease._lease_dir(lease_root, lease_id)
                lease._write(os.path.join(lease_dir, 'record.json'), {'state': 'ATTACHED', 'runId': journal.run_id})
                lease._write(os.path.join(lease_dir, 'payload.json'), {'synthetic': True})
                lease._write(os.path.join(lease_root, 'attached', journal.run_id + '.json'), {'leaseId': lease_id})
                args = ['controller', '--state-root', root, '--run-id', journal.run_id,
                        '--runtime-release', root, '--bundle-digest', DIGEST]
                executed, handlers = [], {}
                original_open, original_dump = os.open, json.dump
                original_materialize = controller._materialize_application_projection
                def open_file(path, *values, **options):
                    if failure == 'secret_written' and '.runtime-projection-' in str(path):
                        self.assertTrue(list(Path(journal.directory).glob('.runtime-application-secret-*')))
                        raise OSError('synthetic-sensitive-error')
                    return original_open(path, *values, **options)
                def dump(value, *values, **options):
                    if failure == 'projection_write' and isinstance(value, dict) and 'platform_application_secret_root' in value:
                        raise OSError('synthetic-sensitive-error')
                    return original_dump(value, *values, **options)
                def materialize(*values):
                    original_materialize(*values)
                    if failure == 'cancel':
                        handlers[controller.signal.SIGTERM](None, None)
                def wait(process, *_args):
                    executed.append(process.args[0])
                    return (0, '', None)
                with ExitStack() as stack:
                    patches = [patch('sys.argv', args), patch.object(controller.signal, 'signal', side_effect=lambda key, handler: handlers.update({key: handler})),
                        patch.object(controller, '_materialize_runtime_projection'), patch.object(controller, '_validate_runtime_projection'),
                        patch.object(controller, '_capture_secret_outputs'), patch.object(controller, '_complete_secret_outputs'),
                        patch.object(controller, 'retain'), patch.object(controller, '_claim_raw_ansible_failure_capture', return_value=False),
                        patch.object(controller, '_command', side_effect=lambda _r, _j, op: [op['operationId']]),
                        patch.object(controller, '_environment', return_value={}), patch.object(controller.execution_target_trust, 'verify'),
                        patch.object(lease, 'ansible_connection_credentials_for_run', return_value=None),
                        patch.object(lease, 'runtime_secret_inputs_for_operation', return_value=[]),
                        patch.object(lease, 'application_secret_values_for_operation', return_value={}),
                        patch.object(controller, '_materialize_application_projection', side_effect=materialize),
                        patch.object(controller.subprocess, 'Popen', side_effect=lambda args, **_kw: SimpleNamespace(args=args)),
                        patch.object(controller, '_wait_for_operation', side_effect=wait),
                        patch.object(controller.os, 'open', side_effect=open_file), patch.object(controller.json, 'dump', side_effect=dump)]
                    for mocked in patches:
                        stack.enter_context(mocked)
                    self.assertEqual(0 if failure == 'cancel' else 2, controller.main())
                self.assertEqual('CANCELLED' if failure == 'cancel' else 'FAILED', journal.status()['state'])
                if failure != 'cancel':
                    result = json.loads(Path(journal.result_path).read_text())
                    self.assertEqual('APPLICATION_RUNTIME_PREPARATION_FAILED', result['error']['code'])
                    self.assertNotIn('synthetic-sensitive-error', Path(journal.result_path).read_text())
                self.assertFalse(any(name.startswith('applications:') for name in executed))
                self.assertEqual([], list(Path(journal.directory).glob('.runtime-application-secret-*')))
                self.assertEqual([], list(Path(journal.directory).glob('.runtime-projection-*')))
                self.assertFalse(Path(lease_dir).exists())
                self.assertFalse(Path(lease_root, 'attached', journal.run_id + '.json').exists())
                self.assertEqual('synthetic-token', token.read_text())

    def test_v3_request_source_is_closed_and_v2_stays_unchanged(self):
        request = dict(apiVersion=protocol.APPLICATION_PLAN_REQUEST_VERSION, operation='BuildDeploymentPlan',
                       runId='qa', project='/project', runtimeRelease=runtime(), deploymentOrder=['provider'],
                       applicationVaultSources={'provider': 'CURRENT_RUN_BOOTSTRAP'})
        with patch('sys.stdin', io.StringIO(json.dumps(request))):
            self.assertEqual(request, protocol.request())
        request['applicationVaultSources']['provider'] = 'auto-latest'
        with patch('sys.stdin', io.StringIO(json.dumps(request))), self.assertRaises(LifecycleError):
            protocol.request()

    def test_opt_in_capability_validates_new_contract_and_preserves_old_response(self):
        with tempfile.TemporaryDirectory() as root:
            import yaml
            Path(root, 'manifest.yaml').write_text(yaml.safe_dump(dict(bundleVersion='qa',
                bootstrapProtocol='v1alpha1', coreVersion='qa', catalogDigest=DIGEST, schemaDigest=DIGEST)))
            args = SimpleNamespace(runtime_release=root, bundle_digest=DIGEST)
            old, new = protocol._capabilities_v4(args), protocol._application_capabilities(args)
            self.assertEqual('platform.installer/execution-capabilities/v1alpha6', old['apiVersion'])
            self.assertEqual([protocol.DEPLOYMENT_PLAN_REQUEST_VERSION], old['deploymentPlanRequestVersions'])
            self.assertNotIn('applicationExecution', old)
            from schema_validation import SchemaValidator
            self.assertEqual([], SchemaValidator(str(REPO / 'contracts')).validate(new,
                str(REPO / 'contracts/execution-capabilities/v1alpha7/schema.json')))


if __name__ == '__main__':
    unittest.main()

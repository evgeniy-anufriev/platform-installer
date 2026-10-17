"""B0 fixed scopes, journal authority and stale-admission boundaries."""
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import tempfile
import unittest
from unittest.mock import patch

from test_application_mixed_execution import mixed
from test_deployment_plan import DIGEST
import infrastructure_verification as infra
import execution_controller as controller
import execution_protocol as protocol
import execution_secret_lease as secret_lease
from execution_lifecycle import Journal, LifecycleError, digest


def record_coverage(journal, operation):
    counters = dict(ok=1, changed=0, failures=0, unreachable=0, ignored=0, rescued=0)
    infra.verify_pending(journal, operation)
    infra.record_stats(journal, operation['operationId'], {host: counters for host in operation['targets']})
    return infra.verified(journal, operation)

class InfrastructureVerificationTests(unittest.TestCase):
    def test_skip_request_is_typed_and_old_protocol_cannot_ignore_it(self):
        request = dict(apiVersion=protocol.SKIP_PLAN_REQUEST_VERSION, operation='BuildDeploymentPlan',
                       runId='installer-request', project={}, runtimeRelease={}, deploymentOrder=[],
                       applicationVaultSources={}, executionMode='APPLICATION_LIBRARIES_ONLY',
                       skipInfrastructureVerify=True)
        with patch('sys.stdin', io.StringIO(json.dumps(request))):
            self.assertTrue(protocol.request()['skipInfrastructureVerify'])
        for bad in (1, 'true', None):
            with patch('sys.stdin', io.StringIO(json.dumps(dict(request, skipInfrastructureVerify=bad)))), self.assertRaises(LifecycleError):
                protocol.request()
        request['apiVersion'] = protocol.B0_PLAN_REQUEST_VERSION
        with patch('sys.stdin', io.StringIO(json.dumps(request))), self.assertRaises(LifecycleError):
            protocol.request()

    def test_explicit_skip_is_plan_bound_without_fabricating_infrastructure_evidence(self):
        result = infra.scope_plan(self.base, 'APPLICATION_LIBRARIES_ONLY', self.root, True)
        plan, manifest = result['deploymentPlan'], result['executionManifest']
        self.assertTrue(plan['skipInfrastructureVerify'])
        self.assertNotEqual('PASS', plan['infrastructureVerification']['status'])
        self.assertEqual(['APPLICATION_LIBRARIES_APPLY', 'APPLICATION_LIBRARIES_VERIFY'],
                         [op['operation'] for op in manifest['operations']])
        controller.validate_application_manifest(manifest)
        infra.assert_admission(self.root, manifest)
        ordinary = infra.scope_plan(self.base, 'APPLICATION_LIBRARIES_ONLY', self.root)
        self.assertNotEqual(ordinary['deploymentPlan']['fingerprints']['plan'], plan['fingerprints']['plan'])
        self.assertFalse(Path(self.root, 'infrastructure-verification').exists())
        for mode in ('FULL_PROJECT', 'INFRASTRUCTURE_VERIFY_ONLY'):
            with self.assertRaises(LifecycleError):
                infra.scope_plan(self.base, mode, self.root, True)
        tampered = copy.deepcopy(manifest)
        tampered['skipInfrastructureVerify'] = False
        with self.assertRaises(LifecycleError):
            controller.validate_application_manifest(tampered)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = self.temporary.name
        self.base = mixed()
        self.full = infra.scope_plan(self.base, 'FULL_PROJECT', self.root)
        self.expected = self.full['executionManifest']['infrastructureVerification']['model']

    def journal(self, manifest, name='installer-test'):
        journal = Journal(self.root, name)
        journal.initialize(dict(runId=name, projectIdentity=manifest['projectIdentity'], planFingerprint=manifest['planFingerprint'],
            manifestDigest=digest(manifest), runtimeRelease=DIGEST, unit='platform-installer-run-' + name + '.service'))
        Path(journal.directory, 'manifest.json').write_text(json.dumps(manifest))
        Path(journal.directory, 'manifest.json').chmod(0o600)
        journal.transition('STARTING')
        journal.transition('RUNNING')
        return journal

    def complete(self, manifest=None, selected=None, state='SUCCEEDED', name='installer-test'):
        manifest = manifest or self.full['executionManifest']
        journal = self.journal(manifest, name)
        infra.begin(journal, manifest)
        for operation in manifest['operations']:
            if operation['operation'] == 'SERVICE_VERIFY' and (selected is None or operation['serviceDeployment'] in selected):
                record_coverage(journal, operation)
        journal.terminal(state, '', '')
        infra.publish(journal, manifest)
        return journal

    def observation(self):
        return infra.summary(self.root, self.full['executionManifest']['projectIdentity'], self.expected)

    def test_missing_evidence_builds_verify_then_library_plan(self):
        base = copy.deepcopy(self.base)
        service_password = dict(requirementRef='service-password-test', purpose='SERVICE_PASSWORD', hosts=['node1'])
        service_input = dict(requirementRef='service-admin-token-provider', purpose='SERVICE_ADMIN_TOKEN',
                             serviceDeployment='provider', hosts=['node1'], requiredWhen='INITIALIZED',
                             operations=['SERVICE_APPLY', 'SERVICE_VERIFY'],
                             manifestRequirementRef='service-secret-provider-admin-token')
        base['executionManifest']['runtimeSecretRequirements'] = [service_password]
        base['executionManifest']['runtimeSecretInputs'] = [service_input]
        base['executionManifest']['requiredCredentials'] += [
            {key: service_password[key] for key in ('requirementRef', 'purpose', 'hosts')},
            {key: service_input[key] for key in ('requirementRef', 'purpose', 'hosts')}]
        result = infra.scope_plan(base, 'APPLICATION_LIBRARIES_ONLY', self.root)
        self.assertEqual('EXECUTABLE', result['deploymentPlan']['status'])
        manifest = result['executionManifest']
        self.assertEqual(['services', 'applications'], [phase['id'] for phase in result['deploymentPlan']['phases']])
        self.assertEqual(['SERVICE_VERIFY', 'SERVICE_VERIFY',
                          'APPLICATION_LIBRARIES_APPLY', 'APPLICATION_LIBRARIES_VERIFY'],
                         [op['operation'] for op in manifest['operations']])
        self.assertEqual('BLOCKED', result['deploymentPlan']['infrastructureVerification']['status'])
        self.assertIsNone(manifest['infrastructureVerification']['evidenceRevision'])
        self.assertEqual([service_password], manifest['runtimeSecretRequirements'])
        self.assertEqual(['SERVICE_APPLY', 'SERVICE_VERIFY'], manifest['runtimeSecretInputs'][0]['operations'])
        self.assertEqual(1, len(secret_lease._validate_typed_secret_requirements(manifest['runtimeSecretInputs'])))
        self.assertEqual([], manifest['runtimeSecretOutputs'])
        controller.validate_application_manifest(manifest)
        infra.validate_manifest(manifest)

    def test_verify_scopes_preserve_existing_pkcs12_password_requirement(self):
        base = copy.deepcopy(self.base)
        private = dict(requirementRef='pki-store-password', purpose='PKI_STORE_PASSWORD',
                       hosts=['node1'], runtimeReference='runtime:pki-store-password')
        public = {key: private[key] for key in ('requirementRef', 'purpose', 'hosts')}
        base['executionManifest']['runtimeSecretRequirements'] = [private]
        base['executionManifest']['requiredCredentials'] = [public]
        for mode in ('APPLICATION_LIBRARIES_ONLY', 'INFRASTRUCTURE_VERIFY_ONLY'):
            with self.subTest(mode=mode):
                result = infra.scope_plan(base, mode, self.root)
                manifest = result['executionManifest']
                self.assertEqual([private], manifest['runtimeSecretRequirements'])
                self.assertIn(public, manifest['requiredCredentials'])
                self.assertFalse(any(op['operation'] in ('SERVICE_APPLY', 'PKI_APPLY', 'PKI_REISSUE')
                                     for op in manifest['operations']))
                infra.validate_manifest(manifest)

        self.complete()
        provider_password = dict(requirementRef='service-provider-password', purpose='SERVICE_PASSWORD',
                                 serviceDeployment='provider', hosts=['node1'], runtimeReference='runtime:provider-password')
        base['executionManifest']['runtimeSecretRequirements'].append(provider_password)
        provider_public = {key: provider_password[key] for key in ('requirementRef', 'purpose', 'hosts')}
        base['executionManifest']['requiredCredentials'].append(provider_public)
        manifest = infra.scope_plan(base, 'APPLICATION_LIBRARIES_ONLY', self.root)['executionManifest']
        self.assertEqual(['APPLICATION_LIBRARIES_APPLY', 'APPLICATION_LIBRARIES_VERIFY'],
                         [op['operation'] for op in manifest['operations']])
        self.assertEqual([private, provider_password], manifest['runtimeSecretRequirements'])
        self.assertIn(public, manifest['requiredCredentials'])
        self.assertIn(provider_public, manifest['requiredCredentials'])
        controller.validate_application_manifest(manifest)
        infra.validate_manifest(manifest)

    def test_fixed_library_scope_after_success(self):
        self.complete()
        result = infra.scope_plan(self.base, 'APPLICATION_LIBRARIES_ONLY', self.root)
        self.assertEqual('EXECUTABLE', result['deploymentPlan']['status'])
        manifest = result['executionManifest']
        self.assertEqual(['APPLICATION_LIBRARIES_APPLY', 'APPLICATION_LIBRARIES_VERIFY'],
                         [op['operation'] for op in manifest['operations']])
        controller.validate_application_manifest(manifest)
        infra.assert_admission(self.root, manifest)

    def test_failed_in_plan_verify_stops_before_library_apply(self):
        base = copy.deepcopy(self.base)
        base['executionManifest']['targetConnections'] = {
            'node1': dict(address='192.0.2.1', port=22, mode='ssh', unsupportedOptions=False)}
        manifest = infra.scope_plan(base, 'APPLICATION_LIBRARIES_ONLY', self.root)['executionManifest']
        journal = self.journal(manifest, 'installer-verify-before-library')
        connection = manifest['targetConnections']['node1']
        endpoint = connection['address']
        if connection['port'] != 22:
            endpoint = '[%s]:%s' % (endpoint, connection['port'])
        (Path(journal.directory) / 'known_hosts').write_text(endpoint + ' ssh-ed25519 synthetic-key\n')
        (Path(journal.directory) / 'known_hosts').chmod(0o600)
        executed = []
        def wait(process, *_args):
            executed.append(process.args[0])
            return (1, 'SYNTHETIC_VERIFY_FAILURE', None)
        with patch.object(controller, '_command', side_effect=lambda _release, _journal, operation: [operation['operationId']]), \
             patch.object(controller, '_claim_raw_ansible_failure_capture', return_value=False), \
             patch.object(controller, '_environment', return_value={}), \
             patch.object(controller.subprocess, 'Popen', side_effect=lambda args, **_kwargs: type('Process', (), {'args': args})()), \
             patch.object(controller, '_wait_for_operation', side_effect=wait), \
             patch.object(controller.execution_target_trust, 'verify'), \
             patch.object(controller.execution_secret_lease, 'ansible_connection_credentials_for_run', return_value=None), \
             patch.object(controller.execution_secret_lease, 'runtime_secret_inputs_for_operation', return_value=[]), \
             patch.object(controller, '_materialize_application_projection') as materialize:
            with self.assertRaisesRegex(LifecycleError, 'EXECUTION_OPERATION_FAILED'):
                controller._dispatch('/runtime/release', journal, manifest, [False])
        self.assertEqual([manifest['operations'][0]['operationId']], executed)
        self.assertFalse(any(action.startswith('applications:') for action in executed))
        materialize.assert_not_called()

    def test_verify_only_contains_no_apply_and_has_full_coverage(self):
        result = infra.scope_plan(self.base, 'INFRASTRUCTURE_VERIFY_ONLY', self.root)
        manifest = result['executionManifest']
        self.assertTrue(all(op['operation'] == 'SERVICE_VERIFY' for op in manifest['operations']))
        self.assertTrue(all(not a['dependsOn'] for p in result['deploymentPlan']['phases'] for a in p['actions']))
        controller.validate_application_manifest(manifest)
        self.complete(manifest)
        self.assertEqual('PASS', self.observation()['status'])

    def test_full_v3_preserves_mixed_barrier(self):
        manifest = self.full['executionManifest']
        controller.validate_application_manifest(manifest)
        bad = copy.deepcopy(manifest)
        bad['operations'] = bad['operations'][-2:]
        with self.assertRaises(LifecycleError):
            controller.validate_application_manifest(bad)

    def test_failed_run_retains_completed_verifies_not_run_success(self):
        journal = self.complete(state='FAILED')
        self.assertEqual('PASS', self.observation()['status'])
        self.assertEqual('FAILED', journal.status()['state'])

    def test_partial_failed_then_verify_only_aggregates_generation(self):
        selected = [next(iter(self.expected['coverage']))]
        self.complete(selected=selected, state='FAILED')
        self.assertEqual('BLOCKED', self.observation()['status'])
        verify = infra.scope_plan(self.base, 'INFRASTRUCTURE_VERIFY_ONLY', self.root)['executionManifest']
        remaining = set(self.expected['coverage']) - set(selected)
        self.complete(verify, remaining, name='installer-second')
        self.assertEqual('PASS', self.observation()['status'])
        self.assertEqual(2, len({item['sourceRunId'] for item in self.observation()['deployments']}))

    def test_new_mutation_invalidates_even_if_failed_before_verify(self):
        self.complete()
        self.complete(selected=[], state='FAILED', name='installer-second')
        self.assertEqual('BLOCKED', self.observation()['status'])

    def test_begin_once_does_not_erase_prior_verify_in_same_run(self):
        journal = self.journal(self.full['executionManifest'])
        infra.begin(journal, self.full['executionManifest'])
        operation = next(op for op in self.full['executionManifest']['operations'] if op['operation'] == 'SERVICE_VERIFY')
        record_coverage(journal, operation)
        before = Path(journal.directory, 'infrastructure-verifies.json').read_bytes()
        infra.begin(journal, self.full['executionManifest'])
        self.assertEqual(before, Path(journal.directory, 'infrastructure-verifies.json').read_bytes())

    def test_stale_plan_fails_start_admission_after_mutation(self):
        self.complete()
        manifest = infra.scope_plan(self.base, 'APPLICATION_LIBRARIES_ONLY', self.root)['executionManifest']
        self.complete(selected=[], state='FAILED', name='installer-second')
        with self.assertRaisesRegex(LifecycleError, 'INFRA_EVIDENCE_CHANGED'):
            infra.assert_admission(self.root, manifest)

    def test_durable_terminal_and_verified_proofs_allow_safe_recovery_without_publisher(self):
        journal = self.journal(self.full['executionManifest'])
        infra.begin(journal, self.full['executionManifest'])
        for op in self.full['executionManifest']['operations']:
            if op['operation'] == 'SERVICE_VERIFY':
                record_coverage(journal, op)
        journal.terminal('SUCCEEDED', '', '')
        # The pre-operation latest-attempt references remain unusable until all
        # source proofs and terminal are durable. No mutation replay is needed.
        self.assertEqual('PASS', self.observation()['status'])

    def test_running_source_cannot_authorize(self):
        journal = self.complete()
        status = json.loads(Path(journal.status_path).read_text())
        status['state'] = 'RUNNING'
        Path(journal.status_path).write_text(json.dumps(status))
        self.assertEqual('BLOCKED', self.observation()['status'])

    def test_missing_manifest_and_tamper_fail_closed(self):
        journal = self.complete()
        Path(journal.directory, 'manifest.json').write_text('{}')
        self.assertEqual('BLOCKED', self.observation()['status'])

    def test_source_symlink_rejected(self):
        journal = self.complete()
        path = Path(journal.directory, 'infrastructure-verifies.json')
        path.unlink()
        path.symlink_to('/etc/passwd')
        self.assertEqual('BLOCKED', self.observation()['status'])

    def test_revision_only_change_preserves_infrastructure_model(self):
        changed = copy.deepcopy(self.base['executionManifest'])
        changed['projectRevision'] = 'sha256:' + 'a' * 64
        changed['operations'][-1]['applicationSemanticFingerprint'] = 'sha256:' + 'b' * 64
        self.assertEqual(self.expected, infra.model(changed))

    def test_infra_configuration_bundle_and_targets_invalidate(self):
        for field in ('bundle', 'targets', 'variables'):
            manifest = copy.deepcopy(self.base['executionManifest'])
            if field == 'bundle':
                manifest['runtimeRelease']['bundleDigest'] = 'sha256:' + 'b' * 64
            else:
                op = next(op for op in manifest['operations'] if op['operation'] == 'SERVICE_APPLY')
                op['targets' if field == 'targets' else 'roleVariablesByHost'] = ['other'] if field == 'targets' else {'changed': {}}
            self.assertNotEqual(self.expected, infra.model(manifest))

    def test_no_coverage_rejected(self):
        manifest = copy.deepcopy(self.base['executionManifest'])
        manifest['operations'] = manifest['operations'][-2:]
        with self.assertRaises(LifecycleError):
            infra.model(manifest)

    def test_skipped_changed_missing_or_failed_host_never_produces_coverage(self):
        manifest = self.full['executionManifest']
        journal = self.journal(manifest)
        infra.begin(journal, manifest)
        operation = next(op for op in manifest['operations'] if op['operation'] == 'SERVICE_VERIFY')
        self.assertFalse(infra.verified(journal, operation))
        for field in ('changed', 'failures', 'unreachable', 'ignored', 'rescued', 'ok'):
            counters = dict(ok=1, changed=0, failures=0, unreachable=0, ignored=0, rescued=0)
            counters[field] = 0 if field == 'ok' else 1
            infra.record_stats(journal, operation['operationId'], {'node1': counters})
            self.assertFalse(infra.verified(journal, operation), field)
        infra.record_stats(journal, operation['operationId'], {})
        self.assertFalse(infra.verified(journal, operation))

    def test_bootstrap_not_supported_for_library_only(self):
        with self.assertRaisesRegex(LifecycleError, 'APPLICATION_BOOTSTRAP_PROVIDER_INVALID'):
            infra.scope_plan(mixed(True, 'CURRENT_RUN_BOOTSTRAP'), 'APPLICATION_LIBRARIES_ONLY', self.root)

    def test_unknown_mode_rejected(self):
        with self.assertRaisesRegex(LifecycleError, 'EXECUTION_MODE_UNSUPPORTED'):
            infra.scope_plan(self.base, 'SKIP_BARRIER', self.root)

    def test_authoritative_start_rejects_stale_evidence_before_launch(self):
        self.complete()
        manifest = infra.scope_plan(self.base, 'APPLICATION_LIBRARIES_ONLY', self.root)['executionManifest']
        self.complete(selected=[], state='FAILED', name='installer-second')
        directory = Path(self.root, 'runs', 'installer-library')
        directory.mkdir(mode=0o700)
        source = directory / 'manifest.json'
        source.write_text(json.dumps(manifest))
        source.chmod(0o600)
        with patch.object(protocol.subprocess, 'check_call') as launch, self.assertRaisesRegex(LifecycleError, 'INFRA_EVIDENCE_CHANGED'):
            protocol.start(dict(runId='installer-library', projectIdentity=manifest['projectIdentity'],
                planFingerprint=manifest['planFingerprint'], runtimeRelease=manifest['runtimeRelease']), self.root, '/runtime', '/controller')
        launch.assert_not_called()
        self.assertFalse((directory / 'metadata.json').exists())

    def test_account_is_independent_but_changed_host_key_invalidates_admission(self):
        manifest = copy.deepcopy(self.full['executionManifest'])
        manifest['targetConnections'] = {'node1': dict(address='192.0.2.1', port=22, mode='ssh', unsupportedOptions=False)}
        manifest['infrastructureVerification']['model'] = infra.model(manifest)
        journal = self.journal(manifest)
        trust = Path(journal.directory, 'known_hosts')
        trust.write_text('192.0.2.1 ssh-ed25519 synthetic-key\n')
        trust.chmod(0o600)
        infra.begin(journal, manifest)
        for operation in manifest['operations']:
            if operation['operation'] == 'SERVICE_VERIFY':
                record_coverage(journal, operation)
        journal.terminal('SUCCEEDED', '', '')
        infra.publish(journal, manifest)
        # Use the exact source binding in this admission test (Build is tested separately).
        candidate = copy.deepcopy(manifest)
        candidate['executionMode'] = 'APPLICATION_LIBRARIES_ONLY'
        candidate['infrastructureVerification']['evidenceRevision'] = infra.summary(
            self.root, manifest['projectIdentity'], manifest['infrastructureVerification']['model'])['evidenceRevision']
        target = self.journal(candidate, 'installer-library')
        path = Path(target.directory, 'known_hosts')
        path.write_text(trust.read_text())
        path.chmod(0o600)
        infra.assert_admission(self.root, candidate, target.run_id)
        with patch.object(protocol.execution_secret_lease, 'target_username_for_run', return_value='different-account'):
            infra.assert_admission(self.root, candidate, target.run_id)
        path.write_text('192.0.2.1 ssh-ed25519 changed-key\n')
        with self.assertRaises(LifecycleError):
            infra.assert_admission(self.root, candidate, target.run_id)

    def test_failed_or_incomplete_new_verify_revokes_previous_success(self):
        for outcome in ('failed', 'incomplete'):
            with self.subTest(outcome=outcome):
                self.complete(name='installer-baseline-' + outcome)
                manifest = infra.scope_plan(self.base, 'INFRASTRUCTURE_VERIFY_ONLY', self.root)['executionManifest']
                journal = self.journal(manifest, 'installer-new-' + outcome)
                infra.begin(journal, manifest)
                operation = manifest['operations'][0]
                infra.verify_pending(journal, operation)
                if outcome == 'incomplete':
                    infra.record_stats(journal, operation['operationId'], {})
                    self.assertFalse(infra.verified(journal, operation))
                journal.terminal('FAILED' if outcome == 'failed' else 'SUCCEEDED', '', '')
                infra.publish(journal, manifest)
                self.assertEqual('BLOCKED', self.observation()['status'])

    def test_late_publisher_cannot_restore_superseded_verify_in_same_generation(self):
        old = self.complete()
        manifest = infra.scope_plan(self.base, 'INFRASTRUCTURE_VERIFY_ONLY', self.root)['executionManifest']
        new = self.journal(manifest, 'installer-failed-new-verify')
        infra.begin(new, manifest)
        infra.verify_pending(new, manifest['operations'][0])
        infra.publish(old, self.full['executionManifest'])
        new.terminal('FAILED', '', '')
        infra.publish(new, manifest)
        self.assertEqual('BLOCKED', self.observation()['status'])

    def test_application_stage_failure_preserves_evidence_regardless_of_task_domain(self):
        for domain in ('APPLICATION_ONLY', 'UNKNOWN', 'MISSING', 'APP_THEN_PROVIDER'):
            with self.subTest(domain=domain):
                self.complete(name='installer-baseline-' + domain)
                manifest = infra.scope_plan(self.base, 'APPLICATION_LIBRARIES_ONLY', self.root)['executionManifest']
                journal = self.journal(manifest, 'installer-library-' + domain)
                journal.terminal('FAILED', '', '')
                infra.publish(journal, manifest)
                self.assertEqual('PASS', self.observation()['status'])

    def test_library_failure_preserves_evidence_before_and_after_terminal(self):
        self.complete()
        manifest = infra.scope_plan(self.base, 'APPLICATION_LIBRARIES_ONLY', self.root)['executionManifest']
        journal = self.journal(manifest, 'installer-failed-library')
        terminal = controller._terminal
        def observe(*args):
            self.assertEqual('RUNNING', journal.status()['state'])
            self.assertEqual('PASS', self.observation()['status'])
            return terminal(*args)
        with patch.object(controller, '_terminal', side_effect=observe):
            controller._finish_run_with_outputs(journal, 'FAILED', 'EXECUTION_OPERATION_FAILED', '', manifest, '/unused')

    def test_mixed_application_provider_failure_preserves_completed_infra_success(self):
        manifest = self.full['executionManifest']
        journal = self.journal(manifest)
        infra.begin(journal, manifest)
        for operation in manifest['operations']:
            if operation['operation'] == 'SERVICE_VERIFY':
                record_coverage(journal, operation)
        journal.event('ACTION_STARTED', 'RUNNING', '', actionId='applications:apply')
        controller._finish_run_with_outputs(journal, 'FAILED', 'EXECUTION_OPERATION_FAILED', '', manifest, '/unused')
        self.assertEqual('PASS', self.observation()['status'])

    def test_callback_failure_domain_requires_managed_tag_role_and_inspect_success(self):
        from types import SimpleNamespace
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'collections'))
        from ansible_collections.platform.core.plugins.callback.execution_events_json import CallbackModule
        self.complete()
        for role, tags, rc, expected in (
                ('platform.core.application_runtime', ['platform_application_instance_state'], 0, 'APPLICATION_ONLY'),
                ('platform.core.application_runtime', ['platform_application_instance_state'], 1, 'UNKNOWN'),
                ('platform.vault.application_provider', ['platform_application_instance_state'], 0, 'UNKNOWN'),
                ('platform.core.application_runtime', [], 0, 'UNKNOWN')):
            manifest = infra.scope_plan(self.base, 'APPLICATION_LIBRARIES_ONLY', self.root)['executionManifest']
            journal = self.journal(manifest, 'installer-domain-' + str(len(list(Path(self.root, 'runs').iterdir()))))
            callback = CallbackModule()
            result = SimpleNamespace(_task=SimpleNamespace(tags=tags), _result={'rc': rc, '_ansible_no_log': True})
            with patch.object(callback, '_emit'), patch.object(callback, '_role', return_value=role), patch.object(callback, '_journal', return_value=journal):
                callback.v2_runner_on_failed(result)
            self.assertFalse(Path(journal.directory, 'application-failure-domain.json').exists())
            journal.terminal('FAILED', '', '')

    def test_old_publisher_cannot_overwrite_new_generation(self):
        for terminal in ('FAILED', 'CANCELLED'):
            with self.subTest(terminal=terminal):
                manifest = self.full['executionManifest']
                old = self.journal(manifest, 'installer-old-' + terminal)
                infra.begin(old, manifest)
                for operation in manifest['operations']:
                    if operation['operation'] == 'SERVICE_VERIFY':
                        record_coverage(old, operation)
                old_generation = infra._read(Path(old.directory, 'infrastructure-verifies.json'))['generation']
                old.terminal('SUCCEEDED', '', '')
                new = self.journal(manifest, 'installer-new-' + terminal)
                read_done, allow_write, attempting, begun = [threading.Event() for _ in range(4)]
                errors = []
                original = infra._write
                def write(path, value):
                    if threading.current_thread().name == 'old-publisher' and str(path).endswith('.json'):
                        read_done.set()
                        if not allow_write.wait(5):
                            raise AssertionError('Publisher release timed out')
                    return original(path, value)
                def publish():
                    try:
                        infra.publish(old, manifest)
                    except BaseException as error:
                        errors.append(error)
                def begin():
                    attempting.set()
                    try:
                        infra.begin(new, manifest)
                        begun.set()
                    except BaseException as error:
                        errors.append(error)
                with patch.object(infra, '_write', side_effect=write):
                    publisher = threading.Thread(target=publish, name='old-publisher')
                    starter = threading.Thread(target=begin, name='new-begin')
                    publisher.start()
                    self.assertTrue(read_done.wait(5))
                    starter.start()
                    self.assertTrue(attempting.wait(5))
                    self.assertFalse(begun.wait(0.1))
                    allow_write.set()
                    publisher.join(5)
                    starter.join(5)
                self.assertFalse(publisher.is_alive() or starter.is_alive())
                self.assertEqual([], errors)
                self.assertTrue(begun.is_set())
                self.assertNotEqual(old_generation, infra._read(Path(new.directory, 'infrastructure-verifies.json'))['generation'])
                new.terminal(terminal, '', '')
                infra.publish(new, manifest)
                self.assertEqual('BLOCKED', self.observation()['status'])

    def test_blocked_base_plan_and_closed_evidence_schemas(self):
        from schema_validation import SchemaValidator
        from test_application_plan import REPO
        validator = SchemaValidator(str(REPO / 'contracts'))
        for mode in infra.MODES:
            base = copy.deepcopy(self.base)
            base['executionManifest'] = None
            base['executionManifestDigest'] = None
            base['deploymentPlan'].update(status='BLOCKED', readiness='BLOCKED')
            result = infra.scope_plan(base, mode, self.root)
            self.assertEqual('UNKNOWN', result['deploymentPlan']['infrastructureVerification']['status'])
            self.assertIsNone(result['executionManifest'])
            self.assertEqual([], validator.validate(result['deploymentPlan'], str(REPO / 'contracts/plan/v1alpha5/schema.json')))
            result['deploymentPlan']['infrastructureVerification']['untrusted'] = 'extra'
            self.assertTrue(validator.validate(result['deploymentPlan'], str(REPO / 'contracts/plan/v1alpha5/schema.json')))

    def test_real_start_v2_with_typed_credentials_is_account_independent(self):
        import base64
        from test_execution_secret_lease import typed_runtime_secret_payload
        kind = 'ssh-ed25519'
        key = base64.b64encode(len(kind).to_bytes(4, 'big') + kind.encode() + b'a' * 32).decode()
        def stage_trust(run_id, manifest):
            protocol.execution_target_trust.stage(self.root, dict(stagingId=run_id,
                projectIdentity=manifest['projectIdentity'], projectRevision=manifest['projectRevision'],
                planFingerprint=manifest['planFingerprint'], runtimeRelease=manifest['runtimeRelease'],
                manifestDigest=digest(manifest), approvals=[dict(hostId='node1', address='192.0.2.1', port=22,
                    keyType=kind, publicKey=key)]))
        base = copy.deepcopy(self.base)
        base['executionManifest']['targetConnections'] = {
            'node1': dict(address='192.0.2.1', port=22, mode='ssh', unsupportedOptions=False)}
        full = infra.scope_plan(base, 'FULL_PROJECT', self.root)['executionManifest']
        baseline = self.journal(full, 'installer-11111111111111111111111111111111')
        stage_trust(baseline.run_id, full)
        infra.begin(baseline, full)
        for operation in full['operations']:
            if operation['operation'] == 'SERVICE_VERIFY':
                record_coverage(baseline, operation)
        baseline.terminal('SUCCEEDED', '', '')
        infra.publish(baseline, full)
        for number, username in enumerate(('operator-one', 'operator-two')):
            manifest = infra.scope_plan(base, 'APPLICATION_LIBRARIES_ONLY', self.root)['executionManifest']
            stage = 'installer-' + str(111 + number)
            path = Path(self.root, 'runs', stage)
            path.mkdir(mode=0o700)
            (path / 'manifest.json').write_text(json.dumps(manifest))
            (path / 'manifest.json').chmod(0o600)
            stage_trust(stage, manifest)
            lease = protocol.execution_secret_lease
            lease.register_plan(self.root, stage, digest(manifest), manifest)
            metadata = dict(requestId=str(number + 1) * 32, startAttemptId=str(number + 3) * 32,
                projectIdentity=manifest['projectIdentity'], projectRevision=manifest['projectRevision'],
                planFingerprint=manifest['planFingerprint'], executionManifestDigest=digest(manifest), runtimeRelease=manifest['runtimeRelease'])
            payload = typed_runtime_secret_payload([])
            payload['username'] = username
            stored = lease.put(self.root, metadata, payload)
            request = dict(apiVersion='platform.installer/execution-start/v1alpha2', kind='StartExecutionRequest',
                **{key: value for key, value in metadata.items() if key != 'requestId'}, leaseId=stored['leaseId'])
            with patch.object(protocol.subprocess, 'check_call') as launch:
                response = protocol._start_v2(request, self.root, '/release', '/controller', '')
                retry = protocol._start_v2(request, self.root, '/release', '/controller', '')
            self.assertEqual('STARTED', response['status'])
            self.assertEqual('ALREADY_STARTED', retry['status'])
            self.assertEqual(response['runId'], retry['runId'])
            launch.assert_called_once()
            self.assertEqual(username, lease.target_username_for_run(self.root, response['runId']))
            Journal(self.root, response['runId']).terminal('SUCCEEDED', '', '')
            lease.cleanup_run(self.root, response['runId'])

    def test_public_new_plan_and_capabilities_match_schemas(self):
        from schema_validation import SchemaValidator
        from test_application_plan import REPO
        from types import SimpleNamespace
        validator = SchemaValidator(str(REPO / 'contracts'))
        self.assertEqual([], validator.validate(self.full['deploymentPlan'], str(REPO / 'contracts/plan/v1alpha5/schema.json')))
        release = Path(self.root, 'release')
        release.mkdir()
        (release / 'manifest.yaml').write_text('bundleVersion: test\nbootstrapProtocol: v1alpha1\ncoreVersion: test\ncatalogDigest: ' + DIGEST + '\nschemaDigest: ' + DIGEST + '\n')
        capabilities = protocol._b0_capabilities(SimpleNamespace(runtime_release=str(release), bundle_digest=DIGEST))
        self.assertEqual([], validator.validate(capabilities, str(REPO / 'contracts/execution-capabilities/v1alpha8/schema.json')))

    def test_request_version_and_explicit_scope(self):
        value = dict(apiVersion=protocol.B0_PLAN_REQUEST_VERSION, operation='BuildDeploymentPlan',
                     runId='installer-plan', project='/project', runtimeRelease={}, deploymentOrder=[],
                     applicationVaultSources={}, executionMode='INFRASTRUCTURE_VERIFY_ONLY')
        with patch('sys.stdin', io.StringIO(json.dumps(value))):
            self.assertEqual(value, protocol.request())
        value['executionMode'] = 'SKIP_BARRIER'
        with patch('sys.stdin', io.StringIO(json.dumps(value))), self.assertRaises(LifecycleError):
            protocol.request()


@unittest.skipUnless(os.environ.get('PLATFORM_B0_NATIVE_QA') == '1', 'Explicit isolated RED OS native gate')
class NativeInfrastructureScopeTests(unittest.TestCase):
    setUp = InfrastructureVerificationTests.setUp
    journal = InfrastructureVerificationTests.journal
    def test_real_action_builds_verify_and_library_scopes_without_targets(self):
        """Real Ansible controller action, current code; all data is synthetic."""
        from test_application_plan import REPO, application_snapshot, image_lock
        from test_deployment_plan import catalog, runtime, sources
        for mode in ('INFRASTRUCTURE_VERIFY_ONLY', 'APPLICATION_LIBRARIES_ONLY'):
            with self.subTest(mode=mode):
                play = Path(self.root, mode + '-plan.yml')
                args = dict(snapshot=application_snapshot(), service_catalog=catalog(), runtime_release=runtime(),
                            bundle_artifact_sources=sources(), application_image_lock=image_lock(),
                            deployment_order=['provider', 'consumer'], pki_state_root=self.root,
                            execution_mode=mode)
                output = Path(self.root, mode + '-manifest.json')
                play.write_text(json.dumps([dict(hosts='localhost', gather_facts=False, tasks=[
                    {'name': 'Build fixed Core scope via real action', 'platform.core.build_deployment_plan': args}])]))
                env = dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(REPO / 'ansible-core/collections'),
                           PLATFORM_EXECUTION_MANIFEST_OUTPUT=str(output))
                completed = subprocess.run(['ansible-playbook', '-i', 'localhost,', '-c', 'local', str(play)],
                                           env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                self.assertEqual(0, completed.returncode, completed.stdout[-3000:])
                manifest = json.loads(output.read_text())
                controller.validate_application_manifest(manifest)
                if mode == 'INFRASTRUCTURE_VERIFY_ONLY':
                    self.assertTrue(all(op['operation'] == 'SERVICE_VERIFY' for op in manifest['operations']))
                else:
                    self.assertEqual(['SERVICE_VERIFY', 'SERVICE_VERIFY',
                                      'APPLICATION_LIBRARIES_APPLY', 'APPLICATION_LIBRARIES_VERIFY'],
                                     [op['operation'] for op in manifest['operations']])

    def test_real_controller_verifies_then_applies_libraries_in_one_run(self):
        """Isolated fixture runtime: real controller, trust, projection and Ansible.

        Fixture service Verify bodies are localhost assertions, not service acceptance.
        No protocol accepts a playbook or command supplied by a client.
        """
        import base64
        from test_application_plan import REPO
        import execution_target_trust
        base = copy.deepcopy(self.base)
        for operation in base['executionManifest']['operations']:
            if operation['operation'] in ('SERVICE_APPLY', 'SERVICE_VERIFY'):
                operation['serviceType'] = 'docker' if operation['serviceDeployment'] == 'provider' else 'redis'
                operation['roleVariablesPrefix'] = 'platform_fixture_'
                operation['roleVariablesByHost'] = {'node1': {'platform_fixture_enabled': True}}
        base['executionManifest']['targetConnections'] = {
            'node1': dict(address='192.0.2.1', port=22, mode='ssh', unsupportedOptions=False)}
        manifest = infra.scope_plan(base, 'APPLICATION_LIBRARIES_ONLY', self.root)['executionManifest']
        journal = self.journal(manifest, 'installer-0123456789abcdef0123456789abcdef')
        project = Path(journal.directory, 'project', 'inventory')
        project.mkdir(parents=True)
        (project / 'hosts.yml').write_text('all:\n  hosts:\n    node1:\n      ansible_connection: local\n')
        release = Path(self.root, 'fixture-release')
        core = release / 'ansible-core'
        core.mkdir(parents=True)
        (core / 'collections').symlink_to(REPO / 'ansible-core/collections', target_is_directory=True)
        (core / 'ansible.cfg').symlink_to(REPO / 'ansible-core/ansible.cfg')
        for service in ('docker', 'redis'):
            play = release / 'services' / service / 'playbooks'
            play.mkdir(parents=True)
            (play / 'verify.yml').write_text('- hosts: node1\n  gather_facts: false\n  tasks:\n    - ansible.builtin.assert:\n        that: platform_execution_service_deployment in ["provider", "consumer"]\n')
        kind = 'ssh-ed25519'
        key = base64.b64encode(len(kind).to_bytes(4, 'big') + kind.encode() + b'a' * 32).decode()
        execution_target_trust.stage(self.root, dict(stagingId=journal.run_id,
            projectIdentity=manifest['projectIdentity'], projectRevision=manifest['projectRevision'],
            planFingerprint=manifest['planFingerprint'], runtimeRelease=manifest['runtimeRelease'],
            manifestDigest=digest(manifest), approvals=[dict(hostId='node1', address='192.0.2.1', port=22,
                keyType=kind, publicKey=key)]))
        controller._materialize_runtime_projection(journal, journal.metadata(), manifest)
        self.assertEqual(['SERVICE_VERIFY', 'SERVICE_VERIFY', 'APPLICATION_LIBRARIES_APPLY', 'APPLICATION_LIBRARIES_VERIFY'],
                         [op['operation'] for op in manifest['operations']])
        playbooks = core / 'playbooks'
        playbooks.mkdir()
        for action in ('apply', 'verify'):
            (playbooks / ('application-libraries-' + action + '.yml')).write_text(
                '- hosts: node1\n  gather_facts: false\n  tasks:\n    - ansible.builtin.assert:\n        that: platform_application_expected_library_ids == ["sdku"]\n')
        execution_target_trust.stage(self.root, dict(stagingId=journal.run_id,
            projectIdentity=manifest['projectIdentity'], projectRevision=manifest['projectRevision'],
            planFingerprint=manifest['planFingerprint'], runtimeRelease=manifest['runtimeRelease'],
            manifestDigest=digest(manifest), approvals=[dict(hostId='node1', address='192.0.2.1', port=22,
                keyType=kind, publicKey=key)]))
        controller._materialize_runtime_projection(journal, journal.metadata(), manifest)
        self.assertEqual('SUCCEEDED', controller._dispatch(str(release), journal, manifest, [False]))
        expected = manifest['infrastructureVerification']['model']
        self.assertEqual('BLOCKED', infra.summary(self.root, manifest['projectIdentity'], expected)['status'])
        controller._finish_run_with_outputs(journal, 'SUCCEEDED', '', '', manifest, str(release))
        self.assertEqual('PASS', infra.summary(self.root, manifest['projectIdentity'], expected)['status'])
        actions = [event['actionId'] for event in journal.events() if event['eventType'] == 'ACTION_COMPLETED']
        self.assertEqual(['verify:provider', 'verify:consumer', 'applications:apply', 'applications:verify'], actions)


if __name__ == '__main__':
    unittest.main()

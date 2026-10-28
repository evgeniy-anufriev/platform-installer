"""New plans omit global Verify; fixed legacy manifests remain admissible."""
import copy
import tempfile
import unittest
from pathlib import Path

import test_application_plan as fixture
import test_application_post_install as terminal_fixture
import infrastructure_verification as infra
from application_progress import describe_progress
from application_selection import execution_scope
from execution_controller import validate_application_manifest
from execution_lifecycle import LifecycleError
from schema_validation import SchemaValidator

ROOT = Path(__file__).resolve().parents[2]


class ApplyOnlyApplicationTests(unittest.TestCase):
    def test_new_modes_and_progress_have_no_global_verify(self):
        for mode, skip in [('FULL_PROJECT', False), ('APPLICATION_LIBRARIES_ONLY', False), ('APPLICATION_LIBRARIES_ONLY', True)]:
            with self.subTest(mode=mode, skip=skip), tempfile.TemporaryDirectory() as root:
                result = infra.scope_plan(fixture.ApplicationPlanTests().build(), mode, root, skip)
                result = describe_progress(result, execution_scope(fixture.application_snapshot()), skip)
                manifest = result['executionManifest']
                self.assertEqual(['APPLICATION_LIBRARIES_APPLY'],
                    [op['operation'] for op in manifest['operations'] if op['phaseId'] == 'applications'])
                self.assertFalse(any(a['id'] == 'applications:verify' for p in result['deploymentPlan']['phases'] for a in p['actions']))
                validate_application_manifest(manifest)
                validator = SchemaValidator(str(ROOT / 'contracts'))
                version = manifest['apiVersion'].rsplit('/', 1)[1]
                self.assertEqual([], validator.validate(manifest, ROOT / 'contracts/execution-manifest' / version / 'schema.json'))

    def test_legacy_global_verify_remains_valid_with_and_without_terminal(self):
        for mode in ('FULL_PROJECT', 'APPLICATION_LIBRARIES_ONLY'):
            for terminal in (False, True):
                with self.subTest(mode=mode, terminal=terminal), tempfile.TemporaryDirectory() as root:
                    manifest = (terminal_fixture.PostInstallTests().build(mode)['executionManifest'] if terminal else
                        infra.scope_plan(fixture.ApplicationPlanTests().build(), mode, root, mode == 'APPLICATION_LIBRARIES_ONLY')['executionManifest'])
                    original = next(op for op in manifest['operations'] if op['operation'] == 'APPLICATION_LIBRARIES_APPLY')
                    legacy = dict(original, operationId='applications:verify', operation='APPLICATION_LIBRARIES_VERIFY')
                    index = manifest['operations'].index(original) + 1
                    manifest['operations'].insert(index, legacy)
                    validate_application_manifest(manifest)

    def test_terminal_runs_after_apply_without_verify_dependency(self):
        result = terminal_fixture.PostInstallTests().build()
        actions = [a for p in result['deploymentPlan']['phases'] for a in p['actions'] if a['type'].startswith('APPLICATION_LIBRARIES_')]
        self.assertEqual(['applications:apply', 'applications:post-install'], [a['id'] for a in actions])
        self.assertEqual(['applications:apply'], actions[-1]['dependsOn'])
        validate_application_manifest(result['executionManifest'])

    def test_admission_still_rejects_bad_order_duplicate_and_legacy_scope(self):
        original = fixture.ApplicationPlanTests().build()['executionManifest']
        apply = next(op for op in original['operations'] if op['operation'] == 'APPLICATION_LIBRARIES_APPLY')
        for mutate in ('duplicate', 'verify_only', 'wrong_scope', 'before_infra'):
            with self.subTest(mutate=mutate):
                manifest = copy.deepcopy(original)
                if mutate == 'duplicate':
                    manifest['operations'].append(copy.deepcopy(apply))
                elif mutate == 'verify_only':
                    manifest['operations'][-1] = dict(apply, operation='APPLICATION_LIBRARIES_VERIFY', operationId='applications:verify')
                elif mutate == 'wrong_scope':
                    manifest['operations'].append(dict(apply, operation='APPLICATION_LIBRARIES_VERIFY', operationId='applications:verify', targets=['other']))
                else:
                    manifest['operations'].insert(0, manifest['operations'].pop())
                with self.assertRaises(LifecycleError):
                    validate_application_manifest(manifest)

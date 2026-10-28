"""Opt-in hook grouping preserves provider ordering and secret isolation."""
import copy
import hashlib
import sys
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils'))
from application_integrations import prepare_integrations
from test_application_integration_batches import fixture
from test_application_connection_callbacks import fixture as callback_fixture
from application_scripts import prepare_script_jobs


class ProviderHookBatchingTests(unittest.TestCase):
    def test_real_script_projection_carries_opt_in_source_digest_and_consumer_arguments(self):
        with tempfile.TemporaryDirectory(prefix='qa-hook-projection-') as directory:
            root = Path(directory)
            snapshot, jobs, desired = callback_fixture(root)
            libraries = snapshot['applicationLibraries']['libraries']
            libraries['provider']['instances']['server']['scripts'][0]['batch'] = True
            libraries['consumer']['instances']['other'] = copy.deepcopy(libraries['consumer']['instances']['frontend'])
            jobs.append(dict(jobs[1], instanceId='other'))
            prepared = prepare_script_jobs(directory, snapshot, desired, [], jobs)
            hooks = prepare_integrations(snapshot, prepared)['batches'][0]['hooks']
            self.assertEqual(1, len(hooks))
            self.assertEqual(['frontend', 'other'], [argv[0] for argv in hooks[0]['invocations']])
            self.assertEqual(['https://frontend.example.test', 'https://other.example.test'],
                             [argv[3] for argv in hooks[0]['invocations']])
            source = root / 'application-packages/server/1.0.0/integrate.sh'
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), hooks[0]['sourceDigest'])

    def inputs(self):
        snapshot, jobs = fixture(3)
        for job in jobs:
            script = job['scripts'][1]
            script.update(batch=True, sourceDigest='abc', path='/provider/client.sh', argv=[job['instanceId']],
                          secretInputs={'admin': 'ref'}, runOn='execution_node')
        return snapshot, jobs

    def test_compatible_callbacks_group_without_losing_dependencies(self):
        snapshot, jobs = self.inputs()
        result = prepare_integrations(snapshot, jobs)
        hooks = result['batches'][0]['hooks']
        self.assertEqual(2, len(hooks))
        self.assertEqual([['consumer-0'], ['consumer-1'], ['consumer-2']], hooks[1]['invocations'])
        self.assertEqual([], hooks[1]['argv'])
        self.assertEqual(3, len(result['dependencies']))
        self.assertEqual({'consumer/client-token'}, set(result['sharedDependencies']))

    def test_different_secret_references_do_not_share_a_call(self):
        snapshot, jobs = self.inputs()
        for job in jobs:
            job['scripts'][1]['secretInputs']['client'] = job['instanceId']
        hooks = prepare_integrations(snapshot, jobs)['batches'][0]['hooks']
        self.assertEqual(4, len(hooks))
        self.assertTrue(all(len(hook['invocations']) == 1 for hook in hooks[1:]))

    def test_no_grouping_across_order_target_source_or_id(self):
        for field, value in [('order', 10), ('target', {'hostId': 'other'}),
                             ('sourceDigest', 'different'), ('id', 'other')]:
            with self.subTest(field=field):
                snapshot, jobs = self.inputs()
                for job in jobs:
                    if job['instanceId'] == 'consumer-1':
                        job['scripts'][1][field] = copy.deepcopy(value)
                hooks = prepare_integrations(snapshot, jobs)['batches'][0]['hooks']
                # Order sorting can put the different hook last; it still remains distinct.
                self.assertGreaterEqual(len(hooks), 3)

    def test_source_paths_may_differ_only_with_identical_declared_source_bytes(self):
        snapshot, jobs = self.inputs()
        for job in jobs:
            job['scripts'][1]['path'] = '/' + job['instanceId'] + '/same.sh'
        hooks = prepare_integrations(snapshot, jobs)['batches'][0]['hooks']
        self.assertEqual(2, len(hooks))

    def test_legacy_hooks_keep_individual_invocation_semantics(self):
        snapshot, jobs = self.inputs()
        for job in jobs:
            job['scripts'][1].pop('batch')
        hooks = prepare_integrations(snapshot, jobs)['batches'][0]['hooks']
        self.assertEqual(4, len(hooks))
        self.assertTrue(all('invocations' not in hook for hook in hooks))

    def test_opt_in_does_not_mutate_source_jobs(self):
        snapshot, jobs = self.inputs()
        original = copy.deepcopy(jobs)
        prepare_integrations(snapshot, jobs)
        self.assertEqual(original, jobs)

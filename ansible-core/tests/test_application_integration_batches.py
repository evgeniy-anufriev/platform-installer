"""Provider batches and delivery dependencies use resolved data, never product names."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils'))
from application_integrations import prepare_integrations, pending_instances, ready_vault_jobs, shared_vault_jobs, shared_vault_fields, script_jobs


def fixture(count=2):
    connection = dict(serviceType='application', libraryId='provider', applicationId='api', name='admin',
                      accountProvisioner={'apply_script': 'accounts'}, targets=[{'hostId': 'node2'}])
    accounts = dict(mode='managed', parameters={'groups': ['operators']}, credentials={
        'username': {'source': {'kind': 'literal', 'value': 'service-user'}},
        'password': {'source': {'kind': 'runtime_secret_ref', 'ref': 'consumer-password'}}})
    instances, jobs = {}, []
    for i in range(count):
        instance = 'consumer-' + str(i)
        instances[instance] = dict(connections={'identity': copy.deepcopy(connection)},
                                   credentialRequirements={'identity': copy.deepcopy(accounts)})
        instances[instance]['credentialRequirements']['identity']['credentials']['username']['source']['value'] = 'service-user-' + str(i)
        for host in ('node1', 'node2'):
            jobs.append(dict(libraryId='consumer', instanceId=instance, hostId=host, scripts=[dict(
                id='groups', phase='provider_prepare', scope='library', sharedInputs=[],
                target={'libraryId': 'provider', 'instanceId': 'api', 'hostId': 'node2'}, targetConnection='identity'), dict(
                id='client', phase='provider_prepare', scope='instance', sharedInputs=['client-token'],
                target={'libraryId': 'provider', 'instanceId': 'api', 'hostId': 'node2'}, targetConnection='identity')]))
    return dict(applicationLibraries={'libraries': {'consumer': {'instances': instances}}}), jobs


class IntegrationBatchTests(unittest.TestCase):
    def test_one_callback_for_one_hundred_accounts_and_duplicate_placements(self):
        snapshot, jobs = fixture(100)
        result = prepare_integrations(snapshot, jobs)
        self.assertEqual(1, len(result['batches']))
        batch = result['batches'][0]
        self.assertEqual(100, len(batch['accounts']))
        self.assertEqual(101, len(batch['hooks']))
        self.assertEqual('library', batch['hooks'][0]['scope'])
        self.assertTrue(all(hook['scope'] == 'instance' for hook in batch['hooks'][1:]))

    def test_no_delivery_until_the_complete_provider_batch_succeeds(self):
        snapshot, jobs = fixture()
        result = prepare_integrations(snapshot, jobs)
        deliveries = [dict(libraryId='consumer', instanceId='consumer-' + str(i)) for i in range(2)]
        self.assertEqual([], ready_vault_jobs(deliveries, result, [], []))
        completed = [result['batches'][0]['id']]
        self.assertEqual(deliveries, ready_vault_jobs(deliveries, result, completed, []))
        self.assertEqual([], pending_instances(result, completed))
        self.assertEqual(deliveries[1:], ready_vault_jobs(deliveries, result, completed, ['consumer/consumer-0']))

    def test_declared_hook_order_places_role_assignments_after_all_clients(self):
        snapshot, jobs = fixture(2)
        for job in jobs:
            job['scripts'][0]['order'] = -100
            job['scripts'].append(dict(job['scripts'][0], id='group-roles', order=100))
        result = prepare_integrations(snapshot, jobs)
        hooks = result['batches'][0]['hooks']
        self.assertEqual(['groups', 'client', 'client', 'group-roles'], [hook['id'] for hook in hooks])
        self.assertEqual('library', hooks[-1]['scope'])

    def test_infrastructure_accounts_do_not_enter_application_batches(self):
        snapshot, jobs = fixture(1)
        snapshot['applicationLibraries']['libraries']['consumer']['instances']['consumer-0']['connections']['database'] = {
            'serviceType': 'postgresql', 'deploymentRef': 'db'}
        result = prepare_integrations(snapshot, jobs)
        self.assertEqual(1, len(result['batches'][0]['accounts']))

    def test_multiple_providers_require_both_completions(self):
        snapshot, jobs = fixture(1)
        instance = snapshot['applicationLibraries']['libraries']['consumer']['instances']['consumer-0']
        instance['connections']['second'] = dict(instance['connections']['identity'], name='second')
        instance['credentialRequirements']['second'] = copy.deepcopy(instance['credentialRequirements']['identity'])
        result = prepare_integrations(snapshot, jobs)
        ids = [batch['id'] for batch in result['batches']]
        self.assertEqual(['consumer/consumer-0'], pending_instances(result, ids[:1]))
        self.assertEqual([], pending_instances(result, ids))

    def test_public_connection_without_account_still_publishes_provider_endpoint(self):
        snapshot, _ = fixture(1)
        instance = snapshot['applicationLibraries']['libraries']['consumer']['instances']['consumer-0']
        instance['credentialRequirements'] = {}
        instance['connections']['identity']['accountProvisioner'] = {}
        result = prepare_integrations(snapshot, [])
        self.assertEqual(1, len(result['batches']))
        self.assertEqual([], result['batches'][0]['accounts'])
        self.assertEqual({}, result['dependencies'])

    def test_missing_account_capability_blocks_before_any_callback(self):
        snapshot, jobs = fixture(1)
        snapshot['applicationLibraries']['libraries']['consumer']['instances']['consumer-0']['connections']['identity']['accountProvisioner'] = {}
        with self.assertRaisesRegex(ValueError, 'CAPABILITY_UNSUPPORTED'):
            prepare_integrations(snapshot, jobs)

    def test_shared_client_source_is_published_only_after_its_hook(self):
        snapshot, jobs = fixture(1)
        result = prepare_integrations(snapshot, jobs)
        documents = [dict(libraryId='consumer', documents=[dict(document='shared', fields={
            'ordinary': {'source': {}}, 'client-token': {'source': {}}})])]
        self.assertEqual({'ordinary'}, set(shared_vault_jobs(documents, result, [])[0]['documents'][0]['fields']))
        self.assertEqual({'ordinary', 'client-token'}, set(shared_vault_jobs(
            documents, result, [result['batches'][0]['id']])[0]['documents'][0]['fields']))
        self.assertEqual(2, len(documents[0]['documents'][0]['fields']))

    def test_shared_delivery_only_selects_new_fields_and_keeps_document_identity(self):
        jobs = [dict(providerId=provider, libraryId='consumer', documents=[
            dict(mount='secret', document='shared', fields={'early': {}, 'late': {}})])
            for provider in ('vault-a', 'vault-b')]
        inputs = dict(sharedDependencies={'consumer/late': ['ready']})
        first = shared_vault_jobs(jobs, inputs, [])
        delivered = shared_vault_fields(first)
        self.assertEqual(2, len(delivered))
        self.assertEqual([], shared_vault_jobs(jobs, inputs, [], delivered))
        late = shared_vault_jobs(jobs, inputs, ['ready'], delivered)
        self.assertEqual([{'late': {}}, {'late': {}}], [job['documents'][0]['fields'] for job in late])
        self.assertEqual([], shared_vault_jobs(jobs, inputs, ['ready'], delivered + shared_vault_fields(late)))
        self.assertEqual(2, len(shared_vault_jobs(jobs, inputs, [])))  # fresh invocation
        self.assertEqual(2, len(jobs[0]['documents'][0]['fields']))

    def test_script_selection_preserves_order_and_excludes_other_phases(self):
        jobs = [dict(instanceId='empty'), dict(instanceId='wrong', scripts=[dict(phase='after_ready', scope='library')]),
                dict(instanceId='first', scripts=[dict(phase='before_start', scope='instance')]),
                dict(instanceId='second', scripts=[dict(phase='before_start', scope='instance')])]
        self.assertEqual(['first', 'second'], [job['instanceId'] for job in script_jobs(jobs, 'before_start', 'instance')])


class RetainedPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / 'services/vault/ansible_collections/platform/vault/plugins/filter/application_provider.py'
        spec = importlib.util.spec_from_file_location('batch_vault_filter', path)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def policy(self, paths, owner='platform.application/v1:project:consumer:consumer-0'):
        import json
        return '# ' + owner + '\n' + ''.join('path %s { capabilities = ["read"] }\n' % json.dumps(path) for path in paths)

    def test_disabled_connection_retains_owned_document_read_without_field_isolation(self):
        owner = 'platform.application/v1:project:consumer:consumer-0'
        old = self.policy(['secret/data/project/consumer/consumer-0/accounts/identity'])
        desired = self.policy(['secret/data/project/consumer/shared'])
        actual = self.module.retained_policy({'status': 200, 'json': {'data': {'policy': old}}}, desired, owner)
        self.assertIn('accounts/identity', actual)
        self.assertIn('/shared', actual)
        self.assertEqual(actual, self.module.retained_policy({'status': 200, 'json': {'data': {'policy': actual}}}, desired, owner))

    def test_foreign_owner_or_wildcard_is_never_accepted(self):
        owner = 'platform.application/v1:project:consumer:consumer-0'
        for old in [self.policy([], 'foreign'), self.policy(['secret/data/*']),
                    self.policy(['secret/data/project/another/shared'])]:
            with self.assertRaises(Exception):
                self.module.retained_policy({'status': 200, 'json': {'data': {'policy': old}}}, self.policy([]), owner)

    def test_no_existing_policy_uses_current_desired(self):
        policy = self.policy([])
        self.assertEqual(policy, self.module.retained_policy({'status': 404}, policy, 'platform.application/v1:project:consumer:consumer-0'))

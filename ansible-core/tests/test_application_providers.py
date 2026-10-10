"""Provider projection boundaries; target contacts and secret values excluded."""
import copy
import json
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, os.path.join(ROOT, 'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils'))
from application_providers import project_providers, normalize_grants, identifier


class ApplicationProvidersTest(unittest.TestCase):
    def setUp(self):
        self.resources = {'db': {'kind': 'postgresql.database', 'binding': 'pg', 'parameters': {'name': 'app'}},
                          'schema': {'kind': 'postgresql.schema', 'binding': 'pg', 'databaseRef': 'db', 'parameters': {'name': 'api'}}}
        self.accounts = {'postgres': {'mode': 'managed', 'databaseRef': 'db', 'credentials': {
            'username': {'source': {'kind': 'literal', 'value': 'gateway-lib'}},
            'password': {'source': {'kind': 'runtime_secret_ref', 'ref': 'app-password'}}},
            'grants': [{'schema': 'api', 'privileges': ['USAGE']}]}}
        self.rows = [dict(libraryId='lib', instanceId='gateway-lib', hostId=h, resources=self.resources,
                          bindings={'pg': {'deploymentRef': 'pg'}}, connectionDefaults={}, settings={'accounts': self.accounts}) for h in ('h1', 'h2')]
        self.snapshot = {'project': {'id': 'qa'}, 'hosts': {'h1': {'ansibleHost': '192.0.2.1'}},
                         'topology': {'resolved': {'serviceDeployments': {'pg': {'members': {'data': {'host': 'h1', 'roles': ['database']}}}}}},
                         'applicationLibraries': {'status': 'PASS', 'libraries': {'lib': {'resources': self.resources,
                         'instances': {'gateway-lib': {'connections': {'postgres': {'serviceType': 'postgresql', 'deploymentRef': 'pg'}},
                                                      'credentialRequirements': self.accounts}}}}}}
        self.desired = {'serviceDeployments': {'pg': {'serviceType': 'postgresql', 'mode': 'standalone'}}}
        self.config = {'services': {'pg': {'configuration': {'port': {'state': 'RESOLVED', 'value': 5432}}}}}
        self.catalog = {'definitions': {'postgresql': {'capabilities': ['service.postgresql.' + s for s in ('client', 'database', 'schema', 'account')]}}}

    def resolve(self):
        return project_providers(self.rows, self.snapshot, self.config, self.desired, self.catalog)

    def test_deduplicates_hosts_and_has_no_secret_values(self):
        result = self.resolve()
        self.assertEqual('PASS', result['status'])
        self.assertEqual(1, len(result['jobs']))
        job = result['jobs'][0]
        self.assertEqual(1, len(job['databases']))
        self.assertEqual(1, len(job['accounts']))
        self.assertEqual('app-password', job['accounts'][0]['passwordRef'])
        self.assertEqual(['USAGE'], job['accounts'][0]['grants'][0]['privileges'])
        self.assertTrue(job['databases'][0]['owner'].startswith('pla_'))
        self.assertEqual(1, len(result['libraryJobs']))
        self.assertEqual([], result['libraryJobs'][0]['accounts'])
        self.assertEqual([], result['libraryJobs'][0]['databases'][0]['accounts'])
        self.assertEqual(1, len(result['instanceJobs']))
        self.assertEqual('gateway-lib', result['instanceJobs'][0]['instanceId'])

    def test_conflicting_host_resources_bindings_and_accounts_block(self):
        for field in ('resources', 'bindings', 'settings'):
            with self.subTest(field=field):
                rows = copy.deepcopy(self.rows)
                rows[1][field] = {}
                result = project_providers(rows, self.snapshot, self.config, self.desired, self.catalog)
                self.assertEqual('BLOCKED', result['status'])
                self.assertEqual([], result['jobs'])

    def test_capability_and_deferred_modes_fail_closed(self):
        self.catalog['definitions']['postgresql']['capabilities'] = ['service.postgresql.client']
        self.assertEqual('BLOCKED', self.resolve()['status'])
        self.catalog['definitions']['postgresql']['capabilities'] += ['service.postgresql.' + s for s in ('database', 'schema', 'account')]
        self.desired['serviceDeployments']['pg']['mode'] = 'patroni'
        self.assertEqual('BLOCKED', self.resolve()['status'])

    def test_ha_candidates_exclude_monitor(self):
        self.desired['serviceDeployments']['pg']['mode'] = 'pg_auto_failover'
        self.snapshot['topology']['resolved']['serviceDeployments']['pg']['members'] = {
            'monitor': {'host': 'h1', 'roles': ['monitor']},
            'data1': {'host': 'h1', 'roles': ['database']}, 'data2': {'host': 'h2', 'roles': ['database']}}
        self.snapshot['hosts']['h2'] = {'ansibleHost': '192.0.2.2'}
        self.assertEqual(['data1', 'data2'], [c['memberId'] for c in self.resolve()['jobs'][0]['candidates']])

    def test_password_sources_and_missing_database_ref_block(self):
        self.accounts['postgres']['credentials']['password']['source'] = {'kind': 'generated'}
        self.assertEqual('APPLICATION_PROVIDER_CREDENTIAL_SOURCE_DEFERRED', self.resolve()['findings'][0]['code'])
        self.accounts['postgres']['credentials']['password']['source'] = {'kind': 'runtime_secret_ref', 'ref': 'app-password'}
        self.accounts['postgres']['databaseRef'] = 'missing'
        self.assertEqual('BLOCKED', self.resolve()['status'])

    def test_resources_without_accounts_and_no_actions(self):
        self.accounts.clear()
        self.assertEqual([], self.resolve()['jobs'][0]['accounts'])
        self.resources.clear()
        self.assertEqual([], self.resolve()['jobs'])

    def test_managed_account_in_existing_database_blocks(self):
        self.resources['db']['mode'] = 'existing'
        self.resources['schema']['mode'] = 'existing'
        self.assertEqual('BLOCKED', self.resolve()['status'])

    def test_name_conflict_between_libraries_blocks(self):
        library = copy.deepcopy(self.snapshot['applicationLibraries']['libraries']['lib'])
        self.snapshot['applicationLibraries']['libraries']['other'] = library
        self.rows.append(dict(self.rows[0], libraryId='other'))
        self.assertEqual('APPLICATION_PROVIDER_NAME_CONFLICT', self.resolve()['findings'][0]['code'])

    def test_explicit_privilege_types_and_merge(self):
        values = [{'schema': 'api', 'tables': ['events'], 'privileges': ['SELECT']},
                  {'schema': 'api', 'tables': ['events'], 'privileges': ['INSERT', 'SELECT']}]
        self.assertEqual(['INSERT', 'SELECT'], normalize_grants(values)[0]['privileges'])
        for grant in ({'schema': 'api', 'privileges': ['CREATE']}, {'schema': 'api', 'tables': ['*'], 'privileges': ['SELECT']},
                      {'schema': 'api', 'tables': ['t'], 'sequences': ['s'], 'privileges': ['SELECT']},
                      {'schema': 'api', 'sql': 'anything', 'privileges': ['USAGE']}):
            with self.subTest(grant=grant), self.assertRaises(ValueError):
                normalize_grants([grant])

    def test_identifiers_fail_without_truncation(self):
        self.assertEqual('gateway-lib', identifier('gateway-lib', True))
        for name in ('postgres', 'pg_authid', 'template0', 'x' * 64, 'x;drop role y', 'api"'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                identifier(name)


if __name__ == '__main__':
    unittest.main()

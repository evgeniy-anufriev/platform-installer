"""Provider projection boundaries; target contacts and secret values excluded."""
import copy
import json
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
for service in ('redis', 'clickhouse'):
    sys.path.insert(0, os.path.join(ROOT, 'services', service))
sys.path.insert(0, os.path.join(ROOT, 'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils'))
from application_providers import project_providers, normalize_grants, identifier, normalize_redis_grants, normalize_clickhouse_grants


class ApplicationProvidersTest(unittest.TestCase):
    def test_database_access_multi_database_and_removed_scope(self):
        self.resources['other'] = dict(kind='postgresql.database', binding='pg', parameters={'name':'reports'})
        self.catalog['definitions']['postgresql']['capabilities'].append('service.postgresql.database-access')
        account = self.accounts['postgres']
        del account['databaseRef']
        del account['grants']
        account['databaseAccess'] = [{'databaseRef':'db','privileges':['INSERT','SELECT']},
                                     {'databaseRef':'other','privileges':['SELECT']}]
        result = self.resolve()
        self.assertEqual('PASS', result['status'],result['findings'])
        job = result['instanceJobs'][0]
        self.assertEqual(1,len(job['accounts']))
        self.assertEqual({'app','reports'},{row['database'] for row in job['loginAccounts']})
        account['databaseAccess'] = []
        result = self.resolve()
        self.assertEqual('PASS',result['status'],result['findings'])
        self.assertEqual({'app','reports'},{db['name'] for db in result['instanceJobs'][0]['databases']})
        self.assertTrue(all(len(db['accounts'])==1 for db in result['instanceJobs'][0]['databases']))

    def test_database_access_conflicts_fail_closed(self):
        self.catalog['definitions']['postgresql']['capabilities'].append('service.postgresql.database-access')
        account = self.accounts['postgres']
        account['databaseAccess'] = [{'databaseRef':'db','privileges':['SELECT']}]
        self.assertEqual('BLOCKED',self.resolve()['status'])  # legacy policy is not broadened silently
        del account['databaseRef']; del account['grants']
        for entries in ([{'databaseRef':'missing','privileges':['SELECT']}],
                        [{'databaseRef':'db','privileges':['CREATE']}],
                        [{'databaseRef':'db','privileges':['SELECT'],'additionalCreatorRoles':['postgres']}],
                        [{'databaseRef':'db','privileges':['SELECT']}]*2):
            account['databaseAccess']=entries
            self.assertEqual('BLOCKED',self.resolve()['status'])

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

    def test_two_libraries_two_placements_keep_one_hook_per_provider_scope(self):
        """Two Docker placements must not duplicate the two library account hooks."""
        applications = self.snapshot['applicationLibraries']['libraries']
        applications.clear()
        rows = []
        desired = {'serviceDeployments': {}}
        placements = {'h1': '192.0.2.1', 'h2': '192.0.2.2'}
        for library_id, provider_id, host in [('sdku', 'redis-sdku', 'h1'), ('cspa', 'redis-cspa', 'h2')]:
            account_id = 'redis'
            instance_id = 'gateway-' + library_id
            account = {'mode': 'managed', 'credentials': {
                'username': {'source': {'kind': 'literal', 'value': 'gateway_' + library_id}},
                'password': {'source': {'kind': 'runtime_secret_ref', 'ref': library_id + '-redis-password'}}},
                'grants': {'commands': ['ping', 'get'], 'keys': [library_id + ':*']}}
            connection = {'serviceType': 'redis', 'deploymentRef': provider_id}
            applications[library_id] = {'resources': {}, 'instances': {instance_id: {
                'connections': {account_id: connection}, 'credentialRequirements': {account_id: account}}}}
            for placement_host in ('h1', 'h2'):
                rows.append(dict(libraryId=library_id, instanceId=instance_id, hostId=placement_host,
                                 resources={}, bindings={'redis': {'deploymentRef': provider_id}}, connectionDefaults={},
                                 settings={'accounts': {account_id: account}}))
            desired['serviceDeployments'][provider_id] = {'serviceType': 'redis', 'mode': 'standalone'}
        self.snapshot['applicationLibraries']['status'] = 'PASS'
        self.snapshot['hosts'].update({host: {'ansibleHost': address} for host, address in placements.items()})
        self.snapshot['topology']['resolved']['serviceDeployments'] = {
            provider: {'members': {'member': {'host': host, 'roles': ['redis']}}}
            for provider, host in [('redis-sdku', 'h1'), ('redis-cspa', 'h2')]}
        self.config['services'] = {provider: {'configuration': {
            'redisPort': {'state': 'RESOLVED', 'value': 6379}, 'sentinelPort': {'state': 'RESOLVED', 'value': 26379}}}
                                   for provider in ('redis-sdku', 'redis-cspa')}
        self.catalog['definitions']['redis'] = {'capabilities': ['service.redis.account']}

        result = project_providers(rows, self.snapshot, self.config, desired, self.catalog)
        self.assertEqual('PASS', result['status'], result['findings'])
        self.assertEqual({'redis-sdku', 'redis-cspa'}, {job['providerId'] for job in result['jobs']})
        self.assertEqual(2, len(result['instanceJobs']))
        self.assertEqual({'sdku', 'cspa'}, {job['libraryId'] for job in result['instanceJobs']})
        self.assertEqual({'gateway-sdku', 'gateway-cspa'}, {job['instanceId'] for job in result['instanceJobs']})
        self.assertEqual(1, sum(account['libraryId'] == 'sdku' for job in result['instanceJobs'] for account in job['accounts']))
        self.assertEqual(1, sum(account['libraryId'] == 'cspa' for job in result['instanceJobs'] for account in job['accounts']))
        self.assertEqual({'h1', 'h2'}, {candidate['hostId'] for job in result['jobs'] for candidate in job['candidates']})
        self.assertEqual({'redis-sdku': {'sdku'}, 'redis-cspa': {'cspa'}}, {
            job['providerId']: {account['libraryId'] for account in job['accounts']} for job in result['jobs']})

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

    def test_redis_acl_typed_grants_and_sentinel_discovery_only(self):
        result = normalize_redis_grants({'commands': ['set', 'ping', 'ping'], 'keys': ['sdku:*']})
        self.assertEqual({'commands': ['ping', 'set'], 'keys': ['sdku:*'], 'channels': []}, result)
        self.assertEqual(['ping', 'sentinel|get-master-addr-by-name'], normalize_redis_grants(
            {'commands': ['ping', 'sentinel|get-master-addr-by-name']}, True)['commands'])
        for value, sentinel in [({'commands': ['+@all']}, False), ({'commands': ['acl']}, False),
                                ({'commands': ['ping'], 'keys': ['safe:* +@all']}, False),
                                ({'commands': ['sentinel|monitor']}, True),
                                ({'commands': ['ping'], 'keys': ['sdku:*']}, True), ([], False)]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_redis_grants(value, sentinel)

    def test_clickhouse_explicit_scopes_and_no_global_privileges(self):
        databases = {'analytics': {'providerId': 'ch', 'name': 'sdku'}}
        grants = [{'databaseRef': 'analytics', 'tables': ['events'], 'privileges': ['SELECT']},
                  {'databaseRef': 'analytics', 'tables': ['events'], 'privileges': ['INSERT']}]
        self.assertEqual([{'database': 'sdku', 'table': 'events', 'privileges': ['INSERT', 'SELECT']}],
                         normalize_clickhouse_grants(grants, databases, 'ch'))
        for value in [dict(grants[0], privileges=['ALL']), dict(grants[0], databaseRef='foreign'),
                      dict(grants[0], tables=['events;DROP']), dict(grants[0], sql='GRANT ALL')]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_clickhouse_grants([value], databases, 'ch')

    def test_redis_and_sentinel_one_instance_job_distinct_listener_accounts(self):
        self.resources.clear()
        self.accounts.clear()
        for alias in ('redis', 'sentinel'):
            self.accounts[alias] = {'mode': 'managed', 'credentials': {
                'username': {'source': {'kind': 'literal', 'value': 'gateway-lib'}},
                'password': {'source': {'kind': 'runtime_secret_ref', 'ref': alias + '-password'}}},
                'grants': {'commands': ['ping']}}
        self.desired['serviceDeployments']['pg'] = {'serviceType': 'redis', 'mode': 'sentinel-ha'}
        self.snapshot['topology']['resolved']['serviceDeployments']['pg']['members'] = {
            'r-1': {'host': 'h1', 'roles': ['redis']}, 'r-2': {'host': 'h1', 'roles': ['redis', 'sentinel']}}
        instance = self.snapshot['applicationLibraries']['libraries']['lib']['instances']['gateway-lib']
        instance['connections'] = {alias: {'serviceType': 'redis', 'deploymentRef': 'pg', 'connectionRef':
                                  'client' if alias == 'redis' else 'sentinel', 'targets': [{'memberId': alias}]} for alias in self.accounts}
        self.config['services']['pg']['configuration'] = {key: {'state': 'RESOLVED', 'value': value}
                                                        for key, value in [('redisPort', 6379), ('sentinelPort', 26379)]}
        self.catalog['definitions']['redis'] = {'capabilities': ['service.redis.account', 'service.redis.sentinel.account']}
        result = self.resolve()
        self.assertEqual('PASS', result['status'], result['findings'])
        self.assertEqual([], result['libraryJobs'])
        self.assertEqual(1, len(result['instanceJobs']))
        self.assertEqual(2, len(result['instanceJobs'][0]['accounts']))
        self.catalog['definitions']['redis']['capabilities'].remove('service.redis.sentinel.account')
        self.assertEqual('BLOCKED', self.resolve()['status'])

    def test_clickhouse_database_library_barrier_and_instance_scope(self):
        self.resources.clear()
        self.resources['db'] = {'kind': 'clickhouse.database', 'binding': 'pg', 'parameters': {'name': 'analytics'}}
        self.accounts['postgres']['grants'] = [{'databaseRef': 'db', 'tables': ['events'], 'privileges': ['SELECT']}]
        self.desired['serviceDeployments']['pg'] = {'serviceType': 'clickhouse', 'mode': 'standalone'}
        self.snapshot['topology']['resolved']['serviceDeployments']['pg']['members']['data']['roles'] = ['server']
        self.snapshot['applicationLibraries']['libraries']['lib']['instances']['gateway-lib']['connections']['postgres']['serviceType'] = 'clickhouse'
        self.config['services']['pg']['configuration']['port']['value'] = 8443
        self.config['services']['pg']['configuration']['nativePort'] = {'state': 'RESOLVED', 'value': 9440}
        self.catalog['definitions']['clickhouse'] = {'capabilities': ['service.clickhouse.database', 'service.clickhouse.account']}
        result = self.resolve()
        self.assertEqual('PASS', result['status'], result['findings'])
        self.assertEqual(1, len(result['libraryJobs']))
        self.assertEqual(1, len(result['instanceJobs']))
        self.assertEqual([], result['libraryJobs'][0]['accounts'])
        self.assertEqual([], result['libraryJobs'][0]['libraries'])
        self.assertEqual('analytics', result['instanceJobs'][0]['accounts'][0]['grants'][0]['database'])
        self.resources['retired'] = {'kind': 'clickhouse.database', 'binding': 'pg', 'parameters': {'name': 'archive'}}
        self.resources['external'] = {'kind': 'clickhouse.database', 'binding': 'pg', 'mode':'existing', 'parameters': {'name': 'external'}}
        self.accounts['postgres']['grants'] = []
        result = self.resolve()
        self.assertEqual('PASS',result['status'],result['findings'])
        self.assertEqual({'analytics','archive'}, {db['name'] for db in result['instanceJobs'][0]['databases']})
        self.assertEqual([],result['instanceJobs'][0]['accounts'][0]['grants'])


if __name__ == '__main__':
    unittest.main()

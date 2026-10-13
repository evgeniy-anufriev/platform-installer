"""The same service-owned allocation feeds infrastructure and connections."""
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
for service in ('redis', 'clickhouse'):
    sys.path.insert(0, os.path.join(ROOT, 'services', service))
sys.path.insert(0, os.path.join(ROOT, 'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils'))
from ansible_collections.platform.redis.plugins.module_utils.member_projection import project_members as redis_members
from ansible_collections.platform.clickhouse.plugins.module_utils.member_projection import project_members as clickhouse_members
from application_libraries import resolve_connection
from application_libraries import project


class MemberProjectionTests(unittest.TestCase):
    def test_redis_global_slots_match_role_and_sentinel_role_filter(self):
        members = {'r-2': {'host': 'h2', 'roles': ['redis', 'sentinel']},
                   'r-1': {'host': 'h1', 'roles': ['redis']}}
        projected = redis_members([dict(value, id=key) for key, value in members.items()], 'r',
                                  {'port': 6379, 'sentinel_port': 26379, 'config_root': '/etc/platform-redis'})
        self.assertEqual([6379, 6380], [item['redis_port'] for item in projected])
        self.assertEqual('/etc/platform-redis/r-2', projected[1]['config_directory'])
        desired = {'serviceDeployments': {'r': {'serviceType': 'redis', 'members': members}}}
        config = {'services': {'r': {'configuration': {key: {'state': 'RESOLVED', 'value': value}
                  for key, value in [('redisPort', 6379), ('sentinelPort', 26379)]}}}}
        hosts = {key: {'ansibleHost': '192.0.2.' + str(index + 1)} for index, key in enumerate(['h1', 'h2'])}
        targets = resolve_connection('r', {'purpose': 'sentinel'}, None, desired, config, {}, hosts)['targets']
        self.assertEqual([('r-2', 26380)], [(item['memberId'], item['port']) for item in targets])
        with self.assertRaises(ValueError):
            resolve_connection('r', {'purpose': 'sentinel'}, 'client', desired, config, {}, hosts)

    def test_clickhouse_host_ordinals_explicit_https_and_keeper_exclusion(self):
        members = [{'id': 'c-3', 'host': 'h2', 'roles': ['server']},
                   {'id': 'c-1', 'host': 'h1', 'roles': ['server'], 'port': 10443},
                   {'id': 'c-2', 'host': 'h1', 'roles': ['server', 'keeper']}]
        result = clickhouse_members(members, 'c', {'port': 8443, 'native_port': 9440, 'config_root': '/etc/c'})
        self.assertEqual([10443, 8444, 8443], [item['https_port'] for item in result])
        self.assertEqual([9440, 9441, 9440], [item['native_port'] for item in result])
        self.assertEqual('/etc/c/c/c-2', result[1]['config_directory'])
        self.assertEqual('platform-clickhouse-server@c-2.service', result[1]['server_unit_name'])
        desired = {'serviceDeployments': {'c': {'serviceType': 'clickhouse', 'members': {
            item['id']: item for item in members + [{'id': 'c-4', 'host': 'h2', 'roles': ['keeper']}]}}}}
        config = {'services': {'c': {'configuration': {'port': {'state': 'RESOLVED', 'value': 8443}}}}}
        targets = resolve_connection('c', {'purpose': 'client'}, None, desired, config, {},
                                    {'h1': {'ansibleHost': '192.0.2.1'}, 'h2': {'ansibleHost': '192.0.2.2'}})['targets']
        self.assertEqual(['c-1', 'c-2', 'c-3'], [item['memberId'] for item in targets])

    def test_overflow_fails_before_target_contact(self):
        for project, settings in [(redis_members, {'port': 65535, 'sentinel_port': 26379}),
                                  (clickhouse_members, {'port': 65535})]:
            with self.assertRaises(ValueError):
                project([{'id': 'a', 'host': 'h'}, {'id': 'b', 'host': 'h'}], 'scope', settings)

    def test_optional_connection_prunes_account_and_agent_but_not_secret_guards(self):
        account = {'mode': 'managed', 'credentials': {
            'username': {'source': {'kind': 'literal', 'value': 'api-sdku'}},
            'password': {'source': {'kind': 'runtime_secret_ref', 'ref': 'app-password'}}},
            'grants': {'commands': ['ping']}}
        row = {'libraryId': 'sdku', 'instanceId': 'api-sdku', 'hostId': 'h1', 'applicationName': 'api', 'applicationVersion': '1.0.0',
               'slotId': 'api', 'resources': {}, 'sharedSecrets': {}, 'identityNames': [],
               'libraryRef': 'sdku@1.0.0', 'packageIdentity': {}, 'runtimeRef': 'docker',
               'settings': {'accounts': {'sentinel': account}, 'provisioner': {'type': 'vault-agent',
                            'secret_bindings': {'SENTINEL_PASSWORD': {'source': {'account': 'sentinel', 'field': 'password'}}}}},
               'connections': {'sentinel': {'library_binding': 'sentinel', 'purpose': 'sentinel'}},
               'bindings': {}, 'connectionDefaults': {}}
        desired = {'serviceDeployments': {'docker': {'serviceType': 'docker', 'members': {'d': {'host': 'h1'}}}}}
        hosts = {'h1': {'ansibleHost': '192.0.2.1'}}
        result = project([row], desired, {}, {}, hosts)
        self.assertEqual('PASS', result['status'], result['findings'])
        instance = result['libraries']['sdku']['instances']['api-sdku']
        self.assertEqual({}, instance['connections'])
        self.assertEqual({}, instance['credentialRequirements'])
        self.assertEqual({}, instance['secretBindings'])
        self.assertFalse(instance['agentRequired'])
        self.assertIn('sentinel', row['settings']['accounts'])
        account['credentials']['password']['source'] = {'kind': 'literal', 'value': 'forbidden-value'}
        result = project([row], desired, {}, {}, hosts)
        self.assertEqual('BLOCKED', result['status'])
        self.assertIn('APPLICATION_PLAINTEXT_FORBIDDEN', [item['code'] for item in result['findings']])


if __name__ == '__main__':
    unittest.main()

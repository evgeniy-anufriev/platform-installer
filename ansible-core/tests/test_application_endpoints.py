import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'collections', 'ansible_collections',
                              'platform', 'core', 'plugins', 'module_utils'))
from application_endpoints import project_endpoint_sources
from service_endpoint_resolution import resolve_service_endpoints
from haproxy_resolution import resolve_haproxy_backends
from service_integration_resolution import resolve_service_integrations


class ApplicationEndpointsTest(unittest.TestCase):
    def setUp(self):
        self.desired = {'endpointGroups': {'apps': {'address': {'domain': 'apps.example.test'}}},
                        'serviceDeployments': {'vip': {'serviceType': 'keepalived', 'endpointGroupRef': 'apps'},
                                              'proxy': {'serviceType': 'haproxy', 'endpointGroup': 'apps'}}}
        self.hosts = {'node1': {'ansible_host': '192.0.2.1'}, 'node2': {'ansible_host': '192.0.2.2'}}
        self.placements = {'node1': {'vip': {}, 'proxy': {}}, 'node2': {'vip': {}, 'proxy': {}}}
        self.catalog = {'definitions': {'haproxy': {'endpoint': {}}}}
        self.rows = [{'instanceId': 'gateway-sdku', 'libraryId': 'sdku', 'hostId': host,
                      'settings': {'ports': {'http': {'published': 18081}},
                                   'endpoint': {'enabled': True, 'listener': 'http', 'endpoint_group': 'apps',
                                                'probe': {'path': '/status'}}}} for host in self.hosts]

    def resolve(self):
        sources = project_endpoint_sources(self.rows, self.desired, self.hosts)
        endpoints = resolve_service_endpoints(self.desired, self.catalog, endpoint_sources=sources)
        backends = resolve_haproxy_backends(self.desired, self.catalog, self.hosts, self.placements,
                                           endpoints, endpoint_sources=sources)
        return sources, endpoints, backends

    def test_two_hosts_one_logical_source_and_existing_backend_shape(self):
        sources, endpoints, backends = self.resolve()
        self.assertEqual('PASS', endpoints['status'])
        self.assertEqual('PASS', backends['status'])
        record = backends['backends']['proxy'][0]
        self.assertEqual('gateway-sdku-apps', record['backendName'])
        self.assertEqual([18081, 18081], [target['port'] for target in record['targets']])
        self.assertEqual(['node1', 'node2'], record['providerHostIds'])
        relation = resolve_service_integrations(self.desired, [], 'gateway-sdku', self.placements, sources)
        self.assertEqual(['proxy'], relation['integrations']['haproxyDeployments'])

    def test_disabled_has_no_sources(self):
        for row in self.rows:
            row['settings']['endpoint']['enabled'] = False
        self.assertEqual({}, project_endpoint_sources(self.rows, self.desired, self.hosts))

    def test_different_host_ports_allowed_but_settings_mismatch_blocked(self):
        self.rows[1]['settings']['ports']['http']['published'] = 18082
        self.assertEqual([18081, 18082], [t['port'] for t in self.resolve()[0]['gateway-sdku']['targets']])
        self.rows[1]['settings']['endpoint']['probe']['path'] = '/other'
        with self.assertRaisesRegex(ValueError, 'HOST_ENDPOINT_CONFLICT'):
            self.resolve()

    def test_service_identity_collision_blocks_before_mutation(self):
        self.desired['serviceDeployments']['gateway-sdku'] = {'serviceType': 'other'}
        self.assertEqual('BLOCKED', self.resolve()[1]['status'])

    def test_duplicate_normalized_domain_blocked_parent_child_allowed(self):
        self.desired['endpointGroups']['other'] = {'address': {'domain': 'APPS.EXAMPLE.TEST.'}}
        self.assertEqual('BLOCKED', self.resolve()[1]['status'])
        self.desired['endpointGroups']['other']['address']['domain'] = 'example.test'
        self.assertEqual('PASS', self.resolve()[1]['status'])

    def test_backend_override_and_typed_bounds(self):
        for row in self.rows:
            row['settings']['endpoint']['haproxy'] = {'backend': {'balance': 'leastconn', 'timeoutServer': '60s'}}
        self.assertEqual('leastconn', self.resolve()[2]['backends']['proxy'][0]['settings']['balance'])
        self.rows[0]['settings']['endpoint']['haproxy']['backend']['timeoutServer'] = '301s'
        with self.assertRaisesRegex(ValueError, 'BACKEND_INVALID'):
            self.resolve()

    def test_unsupported_protocol_and_unverified_tls_blocked(self):
        self.rows[0]['settings']['endpoint']['protocol'] = 'tcp'
        with self.assertRaisesRegex(ValueError, 'ENDPOINT_INVALID'):
            self.resolve()
        self.rows[0]['settings']['endpoint'].update(protocol='https', haproxy={'backend': {'sslVerify': 'none'}})
        with self.assertRaisesRegex(ValueError, 'BACKEND_INVALID'):
            self.resolve()

    def test_provider_input_rejects_target_config_injection(self):
        sources, endpoints, _ = self.resolve()
        sources['gateway-sdku']['targets'][0]['serverName'] = 'node1\nbackend injected'
        result = resolve_haproxy_backends(self.desired, self.catalog, self.hosts, self.placements,
                                         endpoints, endpoint_sources=sources)
        self.assertEqual('BLOCKED', result['status'])
        self.assertEqual({}, result['backends'])


if __name__ == '__main__':
    unittest.main()

"""Generic provided connections: no product names, target contact or credentials."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils'))
from application_connections import (provided_connections, application_connection, enabled,
                                     connection_order_findings, active_script, script_secret_source)
from schema_validation import SchemaValidator


def topology():
    exports = {'api': {'application': 'server', 'protocol': 'https', 'parameters': {'tenant': 'test'},
                       'credentials': {'token': {'source': {'kind': 'runtime_secret_ref', 'ref': 'api-token'}}}}}
    return [dict(libraryId='provider', instanceId='service-provider', slotId='server',
                 hostId=host, startupPriority=0, providedConnections=exports,
                 settings={'endpoint': {'enabled': True, 'protocol': 'https', 'endpoint_group': 'apps', 'listener': 'web'},
                           'ports': {'web': {'published': port, 'container': 8443}}})
            for host, port in [('node1', 10443), ('node2', 11443)]]


class ApplicationConnectionsTests(unittest.TestCase):
    def test_public_https_url_does_not_require_tls_on_the_provider_backend(self):
        rows = topology()
        for row in rows:
            row['settings']['endpoint']['protocol'] = 'http'
        connection = provided_connections(rows, self.desired, self.hosts)['provider']['api']
        self.assertEqual('https://service-provider.example.test', connection['url'])
        self.assertEqual(['http', 'http'], [target['protocol'] for target in connection['targets']])

    def setUp(self):
        self.desired = {'endpointGroups': {'apps': {'address': {'domain': 'example.test'}}}}
        self.hosts = {'node1': {'ansibleHost': '192.0.2.1'}, 'node2': {'ansibleHost': '192.0.2.2'}}

    def test_one_public_url_preserves_all_backend_placements_and_ports(self):
        value = provided_connections(topology(), self.desired, self.hosts)['provider']['api']
        self.assertEqual('https://service-provider.example.test', value['url'])
        self.assertEqual([10443, 11443], [target['port'] for target in value['targets']])
        self.assertEqual({'tenant': 'test'}, value['parameters'])
        self.assertEqual('api-token', value['credentials']['token']['source']['ref'])

    def test_missing_endpoint_is_not_offered_and_selected_reference_fails(self):
        rows = topology()
        for row in rows:
            row['settings']['endpoint']['enabled'] = False
        exports = provided_connections(rows, self.desired, self.hosts)
        self.assertEqual({}, exports)
        with self.assertRaisesRegex(ValueError, 'CONNECTION_INVALID'):
            application_connection({'providedConnectionRef': {'libraryId': 'provider', 'name': 'api'}}, {}, exports)

    def test_export_host_conflicts_fail(self):
        rows = topology()
        rows[1]['providedConnections'] = copy.deepcopy(rows[1]['providedConnections'])
        rows[1]['providedConnections']['api']['parameters']['tenant'] = 'different'
        with self.assertRaises(ValueError):
            provided_connections(rows, self.desired, self.hosts)

    def test_protocol_filter_and_copy(self):
        exports = provided_connections(topology(), self.desired, self.hosts)
        binding = {'providedConnectionRef': {'libraryId': 'provider', 'name': 'api'}}
        with self.assertRaises(ValueError):
            application_connection(binding, {'protocol': 'http'}, exports)
        value = application_connection(binding, {'protocol': 'https'}, exports)
        value['parameters']['tenant'] = 'changed'
        self.assertEqual('test', exports['provider']['api']['parameters']['tenant'])

    def test_explicit_scope_and_order_without_auto_expansion(self):
        connection = provided_connections(topology(), self.desired, self.hosts)['provider']['api']
        libs = {'consumer': {'instances': {'front': {'connections': {'api': connection}}}}}
        self.assertTrue(connection_order_findings(libs, ['consumer']))
        self.assertTrue(connection_order_findings(libs, ['consumer', 'provider']))
        self.assertEqual([], connection_order_findings(libs, ['provider', 'consumer']))

    def test_internal_provider_must_precede_consumer(self):
        connection = provided_connections(topology(), self.desired, self.hosts)['provider']['api']
        libs = {'provider': {'instances': {'front': {'startupPriority': 1, 'connections': {'api': connection}}}}}
        self.assertEqual([], connection_order_findings(libs, ['provider']))
        libs['provider']['instances']['front']['startupPriority'] = 0
        self.assertTrue(connection_order_findings(libs, ['provider']))

    def test_legacy_enabled_and_explicit_false(self):
        self.assertTrue(enabled({}, 'api'))
        self.assertFalse(enabled({'connections': {'api': {'enabled': False}}}, 'api'))

    def test_disabled_hook_does_not_resolve_secrets(self):
        hook = {'phase': 'provider_prepare', 'requires_connections': ['api']}
        self.assertFalse(active_script(hook, {'connections': {}}))
        self.assertTrue(active_script(hook, {'connections': {'api': {}}}))
        self.assertFalse(active_script({'phase': 'account_apply'}, {'connections': {'api': {}}}))

    def test_single_export_credential_source_for_bootstrap(self):
        library = {'providedConnections': provided_connections(topology(), self.desired, self.hosts)['provider']}
        source = script_secret_source({'valueFrom': 'provided_connection', 'name': 'api', 'credential': 'token'}, library, {})
        self.assertEqual({'kind': 'runtime_secret_ref', 'ref': 'api-token'}, source)

    def test_provided_contract_disallows_sensitive_literals_and_arbitrary_code(self):
        validator = SchemaValidator(str(ROOT / 'contracts'))
        schema = str(ROOT / 'contracts/application-libraries/v1alpha1/provided-connections.schema.json') + '#/$defs/exports'
        # Validate through the same root document used by real library imports.
        lib_schema = str(ROOT / 'contracts/application-libraries/v1alpha1/library.schema.json')
        value = dict(name='provider', version='1.0.0', slots={}, provided_connections=topology()[0]['providedConnections'])
        self.assertEqual([], validator.validate(value, lib_schema))
        value['provided_connections']['api']['credentials']['token']['source'] = {'kind': 'literal', 'value': 'fixture'}
        self.assertTrue(validator.validate(value, lib_schema))
        value['provided_connections']['api']['credentials']['token']['sensitive'] = False
        self.assertEqual([], validator.validate(value, lib_schema))

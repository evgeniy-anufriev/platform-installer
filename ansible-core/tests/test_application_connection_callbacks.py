"""A connection owns its callback; consumers own settings and secret bindings."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils'))
from application_scripts import prepare_script_jobs
from application_connections import used_script_sources
from application_integrations import prepare_integrations


def fixture(root):
    package = root / 'application-packages/server/1.0.0'
    package.mkdir(parents=True)
    (package / 'integrate.sh').write_text('#!/bin/sh\nexit 0\n')
    callback = dict(id='integrate', source='integrate.sh', phase='connection_apply', execution='once',
        argv=[{'valueFrom': 'applicationId'}, {'valueFrom': 'libraryId'},
              {'valueFrom': 'parameter', 'name': 'OPTIONS'}, {'valueFrom': 'endpoint'},
              {'valueFrom': 'provided_connection', 'name': 'api', 'field': 'parameters.tenant'}],
        secretInputs={'token': {'valueFrom': 'provided_connection', 'name': 'api', 'credential': 'token'},
                      'consumer_token': {'valueFrom': 'secret_binding', 'binding': 'TOKEN', 'optional': True}})
    export = dict(serviceType='application', name='api', libraryId='provider', applicationId='server',
                  connectionProvisioner={'apply_script': 'integrate'}, targets=[{'hostId': 'node2'}],
                  parameters={'tenant': 'provider-value'}, credentials={'token': {'source': {
                      'kind': 'runtime_secret_ref', 'ref': 'provider-token'}}})
    consumer = dict(placements={'node1': {}, 'node2': {}}, connections={'api': export},
                    scripts=[], secretBindings={'TOKEN': {'source': {'library_secret': 'client-token'}}})
    provider = dict(placements={'node2': {}}, connections={}, scripts=[callback])
    libraries = {'provider': dict(providedConnections={'api': export}, instances={'server': provider}),
                 'consumer': dict(instances={'frontend': consumer}, sharedSecretRequirements={'client-token': {
                     'source': {'kind': 'runtime_secret_ref', 'ref': 'consumer-token'}}})}
    jobs = [dict(libraryId=lib, instanceId=app, hostId=host, projectId='project',
                 applicationPackagePath='application-packages/server/1.0.0', libraryPackagePath='unused',
                 packageApplicationScripts=([callback] if lib == 'provider' else []), packageLibraryScripts=[],
                 settings={'parameters': {'OPTIONS': {'public': True}}, 'ports': {'web': {}},
                           'endpoint': {'enabled': True, 'endpoint_group': 'apps', 'listener': 'web'}})
            for lib, app, host in [('provider', 'server', 'node2'), ('consumer', 'frontend', 'node1'),
                                   ('consumer', 'frontend', 'node2')]]
    snapshot = dict(applicationLibraries={'libraries': libraries}, hosts={'node1': {'ansibleHost': '192.0.2.1'},
                                                                       'node2': {'ansibleHost': '192.0.2.2'}})
    desired = {'endpointGroups': {'apps': {'address': {'domain': 'example.test'}}}}
    return snapshot, jobs, desired


class ConnectionCallbackTests(unittest.TestCase):
    def test_integration_hook_uses_declaring_placement_and_selected_consumers(self):
        import json
        from application_selection import execution_scope
        with tempfile.TemporaryDirectory() as folder:
            snapshot, jobs, desired = fixture(Path(folder))
            library = snapshot['applicationLibraries']['libraries']['provider']
            hook = dict(id='routes', source='integrate.sh', phase='integration_apply', execution='each_target',
                        argv=[{'valueFrom': 'targetHostId'}, {'valueFrom': 'integration_consumers'}])
            library['instances']['gateway'] = dict(placements={'node3': {}}, connections={}, scripts=[hook])
            gateway = dict(jobs[0], instanceId='gateway', hostId='node3', packageApplicationScripts=[hook], scriptContextOnly=True)
            jobs[0]['scriptContextOnly'] = True
            jobs.append(gateway)
            snapshot['hosts']['node3'] = {'ansibleHost': '192.0.2.3'}
            snapshot['applicationExecutionScope'] = execution_scope(snapshot, ['provider', 'consumer'], ['provider'])
            result = prepare_script_jobs(folder, snapshot, desired, [], jobs)
            script = result[-1]['scripts'][0]
            self.assertEqual('node3', script['argv'][0])
            self.assertEqual(['frontend'], [item['applicationId'] for item in json.loads(script['argv'][1])])
            self.assertEqual('node2', result[1]['scripts'][0]['target']['hostId'])

    def test_skipped_provider_uses_minimal_context_and_has_no_own_callback(self):
        from application_selection import execution_scope
        with tempfile.TemporaryDirectory() as folder:
            snapshot, jobs, desired = fixture(Path(folder))
            snapshot['applicationExecutionScope'] = execution_scope(snapshot, ['provider', 'consumer'], ['provider'])
            jobs[0]['scriptContextOnly'] = True
            snapshot['applicationLibraries']['libraries']['provider']['instances']['server']['connections']['unused'] = dict(
                serviceType='application', connectionProvisioner={'apply_script': 'must-not-run'})
            result = prepare_script_jobs(folder, snapshot, desired, [], jobs)
            self.assertEqual([], result[0]['scripts'])
            self.assertEqual('node2', result[1]['scripts'][0]['target']['hostId'])
            batches = prepare_integrations(snapshot, result[1:])
            self.assertEqual(['frontend'], [hook['consumerInstanceId'] for hook in batches['batches'][0]['hooks']])

    def test_execution_node_location_keeps_provider_dependency_and_consumer_context(self):
        with tempfile.TemporaryDirectory() as folder:
            snapshot, jobs, desired = fixture(Path(folder))
            callback = snapshot['applicationLibraries']['libraries']['provider']['instances']['server']['scripts'][0]
            callback['run_on'] = 'execution_node'
            result = prepare_script_jobs(folder, snapshot, desired, [], jobs)
            script = result[1]['scripts'][0]
            self.assertEqual('execution_node', script['runOn'])
            self.assertEqual('node2', script['target']['hostId'])
            self.assertEqual(['frontend', 'consumer'], script['argv'][:2])

    def test_callback_keeps_consumer_connections_and_provider_exports_distinct(self):
        with tempfile.TemporaryDirectory() as folder:
            snapshot, jobs, desired = fixture(Path(folder))
            libraries = snapshot['applicationLibraries']['libraries']
            consumer = libraries['consumer']['instances']['frontend']
            consumer['connections']['database'] = {'serviceType': 'postgresql', 'targets': [
                {'hostId': 'node2', 'address': '192.0.2.20', 'port': 5432}]}
            consumer['connections']['public'] = dict(consumer['connections']['api'],
                url='https://consumer-binding.example.test', connectionProvisioner=None)
            callback = libraries['provider']['instances']['server']['scripts'][0]
            callback['argv'] += [dict(valueFrom='connection', name='database'),
                                 dict(valueFrom='connection', name='public'), dict(valueFrom='targetHostId')]
            result = prepare_script_jobs(folder, snapshot, desired, [], jobs)
            self.assertEqual(['192.0.2.20:5432', 'https://consumer-binding.example.test', 'node2'],
                             result[1]['scripts'][0]['argv'][-3:])

    def test_retargeted_execution_uses_provider_hosts_in_both_scopes(self):
        for consumers, providers in [(('node1',), ('node1', 'node2')),
                                     (('node1', 'node2'), ('node2',))]:
            for execution in ('once', 'each_target'):
                for scope in ('instance', 'library'):
                    with self.subTest(consumers=consumers, providers=providers, execution=execution, scope=scope), tempfile.TemporaryDirectory() as folder:
                        snapshot, jobs, desired = fixture(Path(folder))
                        libraries = snapshot['applicationLibraries']['libraries']
                        consumer = libraries['consumer']['instances']['frontend']
                        consumer['placements'] = {host: {} for host in consumers}
                        consumer['connections']['api']['connectionProvisioner'] = None
                        consumer['connections']['api']['targets'] = [{'hostId': host} for host in providers]
                        script = dict(id='prepare', source='integrate.sh', phase='provider_prepare',
                                      execution=execution, target={'connection': 'api'},
                                      argv=[dict(valueFrom='targetHostId')])
                        jobs = [job for job in jobs if job['libraryId'] == 'consumer' and job['hostId'] in consumers]
                        for job in jobs:
                            job['libraryPackagePath'] = job['applicationPackagePath']
                            job['packageApplicationScripts' if scope == 'instance' else 'packageLibraryScripts'] = [script]
                        result = prepare_script_jobs(folder, snapshot, desired, [], jobs)
                        hooks = prepare_integrations(snapshot, result)['batches'][0]['hooks']
                        expected = sorted(providers)[:1] if execution == 'once' else sorted(providers)
                        self.assertEqual(expected, sorted(hook['target']['hostId'] for hook in hooks))
                        for hook in hooks:
                            self.assertEqual([hook['target']['hostId']], hook['argv'])

    def test_provider_source_consumer_context_and_one_invocation_across_placements(self):
        with tempfile.TemporaryDirectory() as folder:
            snapshot, jobs, desired = fixture(Path(folder))
            jobs = prepare_script_jobs(folder, snapshot, desired, [], jobs)
            self.assertEqual([], jobs[0]['scripts'])
            self.assertEqual([], jobs[2]['scripts'])
            script = jobs[1]['scripts'][0]
            self.assertTrue(script['path'].endswith('application-packages/server/1.0.0/integrate.sh'))
            self.assertEqual(['frontend', 'consumer', '{"public":true}',
                              'https://frontend.example.test', 'provider-value'], script['argv'])
            self.assertEqual({'token': 'provider-token', 'consumer_token': 'consumer-token'}, script['secretInputs'])
            self.assertEqual({'libraryId': 'provider', 'instanceId': 'server', 'hostId': 'node2'}, script['target'])
            self.assertEqual(['client-token'], script['sharedInputs'])
            self.assertEqual(1, len(prepare_integrations(snapshot, jobs)['batches'][0]['hooks']))

    def test_optional_binding_and_credential_custody(self):
        with tempfile.TemporaryDirectory() as folder:
            snapshot, jobs, desired = fixture(Path(folder))
            libraries = snapshot['applicationLibraries']['libraries']
            self.assertEqual({'provider': [{'kind': 'runtime_secret_ref', 'ref': 'provider-token'}],
                              'consumer': [{'kind': 'runtime_secret_ref', 'ref': 'consumer-token'}]},
                             used_script_sources(libraries))
            libraries['consumer']['instances']['frontend']['secretBindings'] = {}
            result = prepare_script_jobs(folder, snapshot, desired, [], jobs)
            self.assertEqual({'token': 'provider-token'}, result[1]['scripts'][0]['secretInputs'])

    def test_disabled_connection_never_calls_provider_or_requests_its_secrets(self):
        with tempfile.TemporaryDirectory() as folder:
            snapshot, jobs, desired = fixture(Path(folder))
            snapshot['applicationLibraries']['libraries']['consumer']['instances']['frontend']['connections'] = {}
            self.assertEqual({}, used_script_sources(snapshot['applicationLibraries']['libraries']))
            self.assertTrue(all(not job['scripts'] for job in prepare_script_jobs(folder, snapshot, desired, [], jobs)))

    def test_invalid_callback_and_private_argv_are_rejected(self):
        for private_argv in (False, True):
            with self.subTest(private_argv=private_argv), tempfile.TemporaryDirectory() as folder:
                snapshot, jobs, desired = fixture(Path(folder))
                callback = snapshot['applicationLibraries']['libraries']['provider']['instances']['server']['scripts'][0]
                if private_argv:
                    callback['argv'].append({'valueFrom': 'provided_connection', 'name': 'api',
                                             'field': 'credentials.token.source.ref'})
                else:
                    callback['phase'] = 'after_ready'
                    jobs[0]['packageApplicationScripts'] = []
                with self.assertRaisesRegex(ValueError, 'APPLICATION_'):
                    prepare_script_jobs(folder, snapshot, desired, [], jobs)

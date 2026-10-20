import copy
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
UTILS = os.path.join(REPO, "ansible-core/collections/ansible_collections/platform/core/plugins/module_utils")
sys.path.insert(0, UTILS)
import application_libraries as APP
import project_snapshot as SNAPSHOT
from schema_validation import SchemaValidator

FIXTURE = os.path.join(REPO, "examples/valid/application-libraries")
CONTRACTS = os.path.join(REPO, "contracts")


def load(path):
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


class ApplicationLibrariesTest(unittest.TestCase):
    def test_redis_key_references_do_not_accept_data_lifecycle_fields(self):
        schema = os.path.join(CONTRACTS, 'application-libraries/v1alpha1/deployments.schema.json')
        validator = SchemaValidator(CONTRACTS)
        values = load(os.path.join(FIXTURE, 'inventory/group_vars/all/platform-installer.yml'))['platform_desired_state']['applicationLibraryDeployments']
        resource = dict(kind='redis.key', binding='cache', parameters={})
        values['sdku']['resources']['dm-meta'] = resource
        self.assertFalse(validator.validate(values, schema))
        resource['mode'] = 'existing'
        self.assertTrue(validator.validate(values, schema))
        resource.pop('mode')
        resource['parameters']['ttl'] = 30
        self.assertTrue(validator.validate(values, schema))

    def test_application_connection_keys_keep_library_declarations_complete(self):
        validator = SchemaValidator(CONTRACTS)
        app = load(os.path.join(FIXTURE, 'application-packages/apigateway/1.0.0/roles/application_apigateway/defaults/main.yml'))['platform_application_definition']
        library = load(os.path.join(FIXTURE, 'library-packages/sdku/1.0.0/roles/library_sdku/defaults/main.yml'))['platform_library_definition']
        app_schema = os.path.join(CONTRACTS, 'application-libraries/v1alpha1/application.schema.json')
        library_schema = os.path.join(CONTRACTS, 'application-libraries/v1alpha1/library.schema.json')
        declarations = app['connections']
        self.assertFalse(validator.validate(app, app_schema))
        app['connections'] = list(declarations)
        self.assertFalse(validator.validate(app, app_schema))
        library['connections'] = declarations
        self.assertFalse(validator.validate(library, library_schema))
        library['connections'] = list(declarations)
        self.assertTrue(validator.validate(library, library_schema))
        app['connections'] = ['kafka', 'kafka']
        self.assertTrue(validator.validate(app, app_schema))

    def test_topics_use_the_selected_deployment_mode_and_effective_replication_factor(self):
        deployments = {'single': {'serviceType': 'kafka', 'mode': 'kraft-standalone',
                                  'members': {'b': {'roles': ['broker', 'controller'], 'host': 'h'}}}}
        bindings = {'single': {'deploymentRef': 'single'}, 'cluster': {'deploymentRef': 'cluster'}}
        resources = {'one': {'kind': 'kafka.topic', 'binding': 'single', 'parameters': {'name': 'SDKU.events'}}}
        for count in (1, 2, 3, 4):
            deployments['cluster'] = {'serviceType': 'kafka', 'mode': 'kraft-distributed',
                                     'members': dict({'b%d' % i: {'roles': ['broker'], 'host': 'h'} for i in range(count)},
                                                     controller={'roles': ['controller'], 'host': 'other'})}
            resources['many'] = {'kind': 'kafka.topic', 'binding': 'cluster', 'parameters': {'name': 'cluster.events'}}
            values = APP.resolve_topics(resources, bindings, {'serviceDeployments': deployments})
            self.assertEqual((1, '1', 1), (values['one']['replicationFactor'], values['one']['config']['min.insync.replicas'], values['one']['partitions']))
            self.assertEqual(min(3, count), values['many']['replicationFactor'])
            self.assertEqual(str(min(2, count)), values['many']['config']['min.insync.replicas'])
        resources['many']['parameters']['replication_factor'] = 1
        self.assertEqual('1', APP.resolve_topics(resources, bindings, {'serviceDeployments': deployments})['many']['config']['min.insync.replicas'])
        resources['many']['parameters'].update(partitions=5, replication_factor=1,
                                              config={'cleanup.policy': 'compact', 'min.insync.replicas': '3'})
        result = APP.resolve_topics(resources, bindings, {'serviceDeployments': deployments})['many']
        self.assertEqual((5, 1, True), (result['partitions'], result['replicationFactor'], result['minISRWarning']))
        self.assertEqual('compact', result['config']['cleanup.policy'])
        for change in ({'replication_factor': 5}, {'partitions': 0}, {'partitions': True}, {'name': '..'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                changed = copy.deepcopy(resources)
                changed['many']['parameters'].update(change)
                APP.resolve_topics(changed, bindings, {'serviceDeployments': deployments})

    def test_registry_connection_projects_all_brokers_and_member_ports(self):
        desired = {'serviceDeployments': {'kafka': {'serviceType': 'kafka', 'members': {
            'kafka-%d' % n: {'host': 'node%d' % n, 'roles': ['broker'], 'node_id': n} for n in (1, 2, 3)}}}}
        config = {'schemaRegistryEnabled': {'state': 'RESOLVED', 'value': True},
                  'schemaRegistryHttpPort': 8081, 'schemaRegistryHttpsPort': 8082,
                  'schemaRegistryKafkaListener': 'SSL', 'tlsProfile': 'application-tls',
                  'listeners': {'SSL': {'purpose': 'interBroker', 'securityProtocol': 'SSL', 'port': 9094}}}
        config = {key: value if key == 'schemaRegistryEnabled' else {'state': 'RESOLVED', 'value': value}
                  for key, value in config.items()}
        effective = {'services': {'kafka': {'configuration': config, 'members': {
            'kafka-2': {'configuration': {'schemaRegistryHttpsPort': {'state': 'RESOLVED', 'value': 18082}}}}}}}
        hosts = {'node%d' % n: {'ansibleHost': '192.0.2.%d' % n} for n in (1, 2, 3)}
        result = APP.resolve_connection('kafka', {'purpose': 'schema-registry', 'protocol': 'https'},
                                        'CLIENT_SSL', desired, effective, {}, hosts)
        self.assertEqual([8082, 18082, 8082], [t['port'] for t in result['targets']])
        self.assertEqual(['192.0.2.1', '192.0.2.2', '192.0.2.3'], [t['address'] for t in result['targets']])
        self.assertTrue(all(t['tlsProfileRef'] == 'application-tls' for t in result['targets']))
        config['schemaRegistryEnabled'] = False
        with self.assertRaises(ValueError):
            APP.resolve_connection('kafka', {'purpose': 'schema-registry'}, 'SSL', desired, effective, {}, hosts)

    def test_account_policy_switch_is_atomic_without_replacing_credentials(self):
        base = {'accounts': {'pg': {'databaseRef': 'db', 'grants': [{'schema':'api','privileges':['USAGE']}],
                                    'credentials': {'username': 'unchanged'}}}}
        override = {'accounts': {'pg': {'databaseAccess': []}}}
        merged = copy.deepcopy(base)
        merged['accounts']['pg']['databaseAccess'] = []
        actual = APP.account_policies(merged, [base, override])
        self.assertEqual({'databaseAccess': [], 'credentials': {'username':'unchanged'}},actual['accounts']['pg'])
        self.assertIn('databaseRef',base['accounts']['pg'])
        self.assertNotIn('databaseAccess',APP.account_policies(merged,[override,base])['accounts']['pg'])
        with self.assertRaises(ValueError):
            APP.account_policies(merged,[{'accounts': {'pg': {'databaseAccess':[], 'grants':[]}}}])

    def setUp(self):
        self.desired = load(os.path.join(FIXTURE, "inventory/group_vars/all/platform-installer.yml"))["platform_desired_state"]
        self.memberships = {host: load(os.path.join(FIXTURE, "inventory/host_vars", host, "platform-installer.yml"))["platform_application_libraries"] for host in ("node1", "node2")}

    def prepare(self, root=FIXTURE):
        return APP.prepare(root, self.desired, self.memberships, APP.CONTRACT, load, CONTRACTS)

    def test_package_closure_two_libraries_two_hosts(self):
        prepared = self.prepare()
        self.assertEqual([], prepared["findings"])
        self.assertEqual([("cspa", "node1"), ("sdku", "node1"), ("sdku", "node2")], [(job["libraryId"], job["hostId"]) for job in prepared["jobs"]])
        self.assertEqual(1, len({job["application"]["digest"] for job in prepared["jobs"]}))
        self.assertNotEqual(prepared["jobs"][0]["library"]["digest"], prepared["jobs"][1]["library"]["digest"])

    def test_preparation_scans_once_and_loads_each_shared_package_once(self):
        with patch.object(APP, "package_inputs", wraps=APP.package_inputs) as scans, \
                patch.object(APP, "load_package", wraps=APP.load_package) as loads:
            prepared = self.prepare()
        self.assertEqual([], prepared["findings"])
        self.assertEqual(1, scans.call_count)
        self.assertEqual(3, loads.call_count)  # Two libraries share one application.
        self.assertEqual(3, len({(call.args[2], call.args[1]) for call in loads.call_args_list}))

    def test_preparation_cache_does_not_hide_changes_in_next_invocation(self):
        with tempfile.TemporaryDirectory() as directory:
            shutil.copytree(FIXTURE, directory, dirs_exist_ok=True)
            before = self.prepare(directory)
            self.assertEqual([], before["findings"])
            with open(os.path.join(directory, "library-packages/sdku/1.0.0/files/.env"), "a") as stream:
                stream.write("PASSWORD=password=synthetic-user-value\n")
            after = self.prepare(directory)
            self.assertEqual([], after["findings"])
            before_digests = {job["libraryId"]: job["library"]["digest"] for job in before["jobs"]}
            after_digests = {job["libraryId"]: job["library"]["digest"] for job in after["jobs"]}
            self.assertNotEqual(before_digests["sdku"], after_digests["sdku"])
            self.assertEqual(before_digests["cspa"], after_digests["cspa"])

    def test_explicit_version_and_legacy_compatibility(self):
        self.assertEqual("v2alpha1", APP.schema_version({"serviceDeployments": {}}, None))
        self.assertEqual("v3alpha1", APP.schema_version(self.desired, APP.CONTRACT))
        with self.assertRaises(ValueError):
            APP.schema_version(self.desired, None)

    def test_unknown_membership_and_slot_are_safe(self):
        self.memberships["node2"]["unknown"] = {}
        prepared = self.prepare()
        self.assertFalse(prepared["jobs"])
        self.assertTrue(prepared["findings"])
        self.memberships["node2"].pop("unknown")
        self.desired["applicationLibraryDeployments"]["sdku"]["applications"]["wrong"] = {}
        self.assertEqual("APPLICATION_PACKAGE_INVALID", self.prepare()["findings"][0]["code"])

    def test_desired_schema_rejects_plaintext_password_field(self):
        self.desired["applicationLibraryDeployments"]["sdku"]["applications"]["gateway"]["password"] = "DO-NOT-PRINT"
        prepared = self.prepare()
        self.assertFalse(prepared["jobs"])
        self.assertNotIn("DO-NOT-PRINT", json.dumps(prepared["findings"]))

    def test_package_and_env_changes_affect_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            shutil.copytree(FIXTURE, directory, dirs_exist_ok=True)
            before = SNAPSHOT.project_documents(directory)[1]
            with open(os.path.join(directory, "library-packages/sdku/1.0.0/files/.env"), "a") as stream:
                stream.write("PASSWORD=password=synthetic-user-value\n")
            self.assertNotEqual(before, SNAPSHOT.project_documents(directory)[1])

    def test_symlink_escape_and_allowlist_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            shutil.copytree(FIXTURE, directory, dirs_exist_ok=True)
            app = os.path.join(directory, "application-packages/apigateway/1.0.0")
            os.symlink("/etc/passwd", os.path.join(app, "escape"))
            self.assertEqual("APPLICATION_PACKAGE_INVALID", self.prepare(directory)["findings"][0]["code"])
            os.unlink(os.path.join(app, "escape"))
            with open(os.path.join(app, "unlisted"), "w") as stream:
                stream.write("extra")
            self.assertTrue(self.prepare(directory)["findings"])

    def test_dotenv_reserved_identity_rejected_and_user_password_allowed(self):
        for key in ("SERVER_ID", "REDIS_PASSWORD"):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                shutil.copytree(FIXTURE, directory, dirs_exist_ok=True)
                with open(os.path.join(directory, "library-packages/sdku/1.0.0/files/.env"), "a") as stream:
                    stream.write(key + "=DO-NOT-PRINT\n")
                result = self.prepare(directory)
                if key == "SERVER_ID":
                    self.assertTrue(result["findings"])
                    self.assertNotIn("DO-NOT-PRINT", json.dumps(result))
                else:
                    self.assertEqual([], result["findings"])

    def test_kafka_uses_selected_client_advertised_address_and_port(self):
        desired = {"serviceDeployments": {"kafka": {"serviceType": "kafka", "members": {"broker": {"host": "node1", "roles": ["broker"]}}}}}
        effective = {"services": {"kafka": {"configuration": {"listeners": {"state": "RESOLVED", "value": {"CLIENT_SSL": {"purpose": "client", "securityProtocol": "SSL", "port": 19094, "advertisedAddress": "kafka.example"}, "SSL": {"purpose": "interBroker", "securityProtocol": "SSL", "port": 9094}}}}}}}
        result = APP.resolve_connection("kafka", {}, "CLIENT_SSL", desired, effective, {}, {"node1": {"ansibleHost": "192.0.2.1"}})
        self.assertEqual(19094, result["targets"][0]["port"])
        self.assertTrue(result["targets"][0]["tls"])
        shared = APP.resolve_connection("kafka", {}, "SSL", desired, effective, {}, {"node1": {"ansibleHost": "192.0.2.1"}})
        self.assertEqual(9094, shared["targets"][0]["port"])
        self.assertTrue(shared["targets"][0]["tls"])
        effective['services']['kafka']['configuration']['listeners']['value']['CONTROLLER'] = {
            'purpose': 'controller', 'securityProtocol': 'SSL', 'port': 9093}
        for selector in (None, "CONTROLLER", "UNKNOWN"):
            with self.subTest(selector=selector), self.assertRaises(ValueError):
                APP.resolve_connection("kafka", {}, selector, desired, effective, {}, {"node1": {"ansibleHost": "192.0.2.1"}})

    def test_non_kafka_uses_effective_member_override(self):
        desired = {"serviceDeployments": {"pg": {"serviceType": "postgresql", "members": {"pg1": {"host": "node1", "roles": ["database"]}}}}}
        effective = {"services": {"pg": {"configuration": {"port": {"state": "RESOLVED", "value": 5432}}, "members": {"pg1": {"configuration": {"port": {"state": "RESOLVED", "value": 6543}}}}}}}
        result = APP.resolve_connection("pg", {}, None, desired, effective, {}, {"node1": {"ansibleHost": "192.0.2.1"}})
        self.assertEqual(6543, result["targets"][0]["port"])
        with self.assertRaises(ValueError):
            APP.resolve_connection("pg", {}, "missing", desired, effective, {}, {})

    def test_snapshot_v3_schema_accepts_fixture_and_keeps_v2_strict(self):
        validator = SchemaValidator(CONTRACTS)
        self.assertFalse(validator.validate(self.desired, os.path.join(CONTRACTS, "project/v3alpha1/desired-state.schema.json")))
        self.assertTrue(validator.validate(self.desired, os.path.join(CONTRACTS, "project/v2alpha1/desired-state.schema.json")))

    def test_secret_binding_source_is_exclusive_and_complete(self):
        validator = SchemaValidator(CONTRACTS)
        schema = os.path.join(CONTRACTS, "project/v3alpha1/desired-state.schema.json")
        overrides = self.desired["applicationLibraryDeployments"]["sdku"]["applications"]["gateway"]["overrides"]
        for source, valid in [({"account": "redis", "field": "password"}, True),
                              ({"library_secret": "java_keystore_password"}, True),
                              ({}, False), ({"account": "redis"}, False),
                              ({"field": "password"}, False),
                              ({"account": "redis", "field": "password", "library_secret": "java_keystore_password"}, False),
                              ({"library_secret": "java_keystore_password", "field": "password"}, False)]:
            with self.subTest(source=source):
                overrides["provisioner"] = {"type": "vault-agent", "mode": "process-supervisor",
                                            "secret_bindings": {"REDIS_PASSWORD": {"source": source}}}
                self.assertEqual(valid, not validator.validate(self.desired, schema))

    def test_postgresql_database_members_only(self):
        members = {"monitor": {"host": "node1", "roles": ["monitor"]},
                   "db1": {"host": "node2", "roles": ["database"]},
                   "db2": {"host": "node3", "roles": ["database"]}}
        desired = {"serviceDeployments": {"pg": {"serviceType": "postgresql", "mode": "pg_auto_failover", "members": members}}}
        effective = {"services": {"pg": {"configuration": {"port": {"state": "RESOLVED", "value": 5432}}}}}
        hosts = {name: {"ansibleHost": "192.0.2.%d" % index} for index, name in enumerate(("node1", "node2", "node3"), 1)}
        result = APP.resolve_connection("pg", {}, None, desired, effective, {}, hosts)
        self.assertEqual(["db1", "db2"], [target["memberId"] for target in result["targets"]])
        desired["serviceDeployments"]["pg"]["members"] = {"monitor": members["monitor"]}
        with self.assertRaises(ValueError):
            APP.resolve_connection("pg", {}, None, desired, effective, {}, hosts)

    def test_compose_name_rejects_dots_in_each_identity_component(self):
        for component in ("project", "libraryId", "instanceId", "hostId"):
            with self.subTest(component=component):
                row = {"libraryId": "sdku", "instanceId": "apigateway-sdku", "hostId": "node1"}
                project_id = "project"
                if component == "project":
                    project_id = "project.test"
                else:
                    row[component] += ".test"
                result = APP.project([row], {}, {}, {}, {}, project_id)
                self.assertEqual("BLOCKED", result["status"])
                self.assertEqual({}, result["libraries"])
                self.assertEqual("APPLICATION_COMPOSE_PROJECT_INVALID", result["findings"][0]["code"])

    def test_execution_not_silently_limited_to_infrastructure(self):
        from test_deployment_plan import _build_deployment_plan, catalog, runtime, sources
        from test_application_plan import application_snapshot, image_lock
        result = _build_deployment_plan(application_snapshot(), catalog(), runtime(),
            deployment_order=['provider', 'consumer'], bundle_artifact_sources=sources(), application_image_lock=image_lock())
        self.assertEqual('EXECUTABLE', result['deploymentPlan']['status'])
        self.assertEqual(['APPLICATION_LIBRARIES_APPLY', 'APPLICATION_LIBRARIES_VERIFY'],
                         [item['operation'] for item in result['executionManifest']['operations'][-2:]])

    def test_final_projection_boundary_preserves_refs_and_user_parameters(self):
        projection = {"libraries": {"sdku": {"resources": {}, "instances": {"apigateway-sdku": {
            "credentialRequirements": {"redis": {"credentials": {"password": {"source": {"kind": "runtime_secret_ref", "ref": "redis-password"}}}, "grants": []}},
            "placements": {"node1": {"parameters": {"redis": {"password_ref": "redis-password"}}}}
        }}}}}
        self.assertEqual([], APP.validate_public_projection(projection))
        projection["libraries"]["sdku"]["instances"]["apigateway-sdku"]["credentialRequirements"]["redis"]["grants"] = [{"token": "DO-NOT-PRINT"}]
        findings = APP.validate_public_projection(projection)
        self.assertEqual([], findings)
        APP.nonsecret_values({"PASSWORD": "password=synthetic", "token": "user-data"}, "parameters", findings)
        self.assertEqual([], findings)
        APP.nonsecret_values("-----BEGIN PRIVATE KEY-----synthetic", "parameters", findings)
        self.assertTrue(findings)


if __name__ == "__main__":
    unittest.main()

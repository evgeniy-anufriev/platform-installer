"""Real target-free Ansible acceptance; run only on the Execution Node."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import yaml

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
FIXTURE = os.path.join(REPO, "examples/valid/application-libraries")


class StandaloneLibrariesQA(unittest.TestCase):
    def test_scram_listener_accounts_and_jaas_bindings_resolve_target_free(self):
        def desired(data):
            state = data['platform_desired_state']
            configuration = state['serviceDeployments']['kafka-main']['configuration']
            configuration['listeners']['SASL_SSL'] = dict(purpose='client', securityProtocol='SASL_SSL', port=9096)
            configuration['adminCredential'] = dict(passwordSecretRef='runtime:kafka-admin-password')
            for key, library in state['applicationLibraryDeployments'].items():
                library.setdefault('resources', {})['events'] = dict(kind='kafka.topic', binding='messaging', parameters=dict(name=key + '-events'))
        self.edit(self.vars, desired)
        for library in ('sdku', 'cspa'):
            path = os.path.join(self.root, 'library-packages', library, '1.0.0/roles/library_' + library + '/defaults/main.yml')
            self.edit(path, lambda data: data['platform_library_definition'].update(
                connection_defaults={'kafka': {'connectionRef': 'SASL_SSL'}}))
        def application(data):
            defaults = data['platform_application_definition']['defaults']
            defaults['accounts']['kafka'] = dict(mode='managed', credentials={
                'username': dict(source=dict(kind='literal', value="{{ application_instance_id | replace('-', '_') }}")),
                'password': dict(source=dict(kind='runtime_secret_ref', ref='{{ application_instance_id }}-kafka-password'))},
                grants=[dict(topicRef='events', operations=['Read', 'Write'])])
            for name in ('KAFKA_PRODUCER_SASL_JAAS_CONFIG', 'KAFKA_CONSUMER_SASL_JAAS_CONFIG'):
                defaults['provisioner']['secret_bindings'][name] = dict(source=dict(account='kafka', field='password'), format='kafka_scram_jaas')
        self.edit(self.defaults, application)
        result = self.snapshot()
        self.assertEqual('PASS', result['status'], result['findings'])
        for library in ('sdku', 'cspa'):
            instance = result['applicationLibraries']['libraries'][library]['instances']['apigateway-' + library]
            self.assertEqual('SASL_SSL', instance['connections']['kafka']['connectionRef'])
            self.assertTrue(all(target['securityProtocol'] == 'SASL_SSL' and target['port'] == 9096
                                for target in instance['connections']['kafka']['targets']))
            self.assertIn('kafka', instance['credentialRequirements'])
            self.assertEqual('kafka_scram_jaas', instance['secretBindings']['KAFKA_PRODUCER_SASL_JAAS_CONFIG']['format'])

    def test_library_connection_keys_and_clickhouse_history_defaults(self):
        with open(self.defaults) as stream:
            connections = json.load(stream)['platform_application_definition']['connections']
        connections['archive'] = dict(connections['clickhouse'])
        for library in ('sdku', 'cspa'):
            path = os.path.join(self.root, 'library-packages', library, '1.0.0/roles/library_' + library + '/defaults/main.yml')
            self.edit(path, lambda d: d['platform_library_definition'].update(
                connections=connections, resource_defaults={'clickhouse': {'databases': {
                    'history': {'name': "{{ library_instance_id | replace('-', '_') }}"},
                    'unused': {'name': 'not_created'}}}}))
        def setup(d):
            for lib in d['platform_desired_state']['applicationLibraryDeployments'].values():
                lib['resources']['history'] = dict(kind='clickhouse.database', binding='analytics', parameters={})
        self.edit(self.vars, setup)
        def app(d):
            definition = d['platform_application_definition']
            definition['connections'] = list(connections)
            definition['defaults']['environment'].update(
                HISTORY_DB='{{ application_databases.clickhouse.history.name }}',
                ARCHIVE_DB='{{ application_databases.archive.history.name }}')
            definition['defaults']['accounts']['clickhouse']['databaseAccess'] = [dict(databaseRef='history', privileges=['SELECT'])]
        self.edit(self.defaults, app)
        def projected(expected='sdku'):
            result = self.snapshot()
            self.assertEqual('PASS', result['status'], [(f['code'], f.get('field')) for f in result['findings']])
            for key, library in result['applicationLibraries']['libraries'].items():
                name = expected if key == 'sdku' else 'cspa'
                self.assertNotIn('unused', library['resources'])
                self.assertEqual(name, library['resources']['history']['parameters']['name'])
                instance = library['instances']['apigateway-' + key]
                self.assertEqual('clickhouse', instance['connections']['archive']['serviceType'])
                for placement in instance['placements'].values():
                    self.assertEqual(name, placement['environment']['HISTORY_DB'])
                    self.assertEqual(name, placement['environment']['ARCHIVE_DB'])
            return result
        projected()
        self.edit(self.vars, lambda d: d['platform_desired_state']['applicationLibraryDeployments']['sdku'].update(
            resource_defaults={'clickhouse': {'databases': {'history': {'name': 'group_history'}}}}))
        projected('group_history')
        self.edit(self.vars, lambda d: d['platform_desired_state']['applicationLibraryDeployments']['sdku']['resources']['history']['parameters'].update(name='resource_history'))
        projected('resource_history')
        self.edit(self.vars, lambda d: d['platform_desired_state']['applicationLibraryDeployments']['sdku']['resources']['history']['parameters'].pop('name'))
        projected('group_history')
        self.edit(self.vars, lambda d: d['platform_desired_state']['applicationLibraryDeployments']['sdku'].pop('resource_defaults'))
        projected()
        self.edit(self.defaults, lambda d: d['platform_application_definition']['connections'].append('missing'))
        self.snapshot(expected_error='Unknown library connection:')

    def test_direct_resource_keys_and_legacy_collision_reset(self):
        for library in ('sdku', 'cspa'):
            path = os.path.join(self.root, 'library-packages', library, '1.0.0/roles/library_' + library + '/defaults/main.yml')
            self.edit(path, lambda d: d['platform_library_definition'].update(resource_defaults={
                'kafka': {'topics': {'main': {'name': 'package.events'}, 'unused': {'name': 'not.created'}}},
                'postgresql': {'databases': {'model': {'name': 'package-db'}, 'unused_db': {'name': 'not-created'}}}}))
        def setup(d):
            for key, lib in d['platform_desired_state']['applicationLibraryDeployments'].items():
                lib['resources']['model'] = lib['resources'].pop('applicationDatabase')
                lib['resources']['model']['parameters'] = {}
                lib['resources'].update(main={'kind': 'kafka.topic', 'binding': 'messaging', 'parameters': {}},
                                        alternate={'kind': 'kafka.topic', 'binding': 'messaging', 'parameters': {'name': key + '.alternate'}})
                lib['resource_defaults'] = {'postgresql': {'databases': {'model': {'name': key + '-db'}}}}
        self.edit(self.vars, setup)
        def defaults(d):
            app = d['platform_application_definition']
            app['connections']['pg_alias'] = dict(library_binding='database', protocol='tcp')
            app['defaults']['environment'].update(
                MAIN_TOPIC='{{ application_topics.kafka.main.name }}',
                DB_NAME='{{ application_databases.postgres.model.name }}',
                DB_ALIAS='{{ application_databases.pg_alias.model.name }}')
            app['defaults']['accounts']['postgres']['databaseAccess'] = [dict(databaseRef='model', privileges=['SELECT'])]
        self.edit(self.defaults, defaults)
        def projected(topic='package.events', database='sdku-db'):
            result = self.snapshot()
            self.assertEqual('PASS', result['status'], [(f['code'], f.get('field')) for f in result['findings']])
            for key, lib in result['applicationLibraries']['libraries'].items():
                self.assertNotIn('unused', lib['resources'])
                self.assertNotIn('unused_db', lib['resources'])
                db = database if key == 'sdku' else key + '-db'
                self.assertEqual(db, lib['resources']['model']['parameters']['name'])
                for row in lib['instances']['apigateway-' + key]['placements'].values():
                    self.assertEqual(topic if key == 'sdku' else 'package.events', row['environment']['MAIN_TOPIC'])
                    self.assertEqual(db, row['environment']['DB_NAME'])
                    self.assertEqual(db, row['environment']['DB_ALIAS'])
            return result
        projected()
        def resources(d):
            return d['platform_desired_state']['applicationLibraryDeployments']['sdku']['resources']
        self.edit(self.vars, lambda d: resources(d)['model']['parameters'].update(name='explicit-db'))
        projected(database='explicit-db')
        self.edit(self.vars, lambda d: resources(d)['model']['parameters'].pop('name'))
        projected()
        self.edit(self.vars, lambda d: d['platform_desired_state']['applicationLibraryDeployments']['sdku']['applications']['gateway'].setdefault('overrides', {}).update(topicBindings={'kafka': {'main': 'alternate'}}))
        projected(topic='sdku.alternate')
        self.edit(self.vars, lambda d: d['platform_desired_state']['applicationLibraryDeployments']['sdku']['applications']['gateway']['overrides'].pop('topicBindings'))
        projected()
        self.edit(self.vars, lambda d: resources(d)['main'].update(binding='database'))
        self.snapshot(expected_error='FAILED!')
        self.edit(self.vars, lambda d: resources(d).pop('main'))
        self.snapshot(expected_error='FAILED!')

    def test_named_topic_roles_inherit_names_and_reset_without_target_writes(self):
        library_defaults = os.path.join(self.root, 'library-packages/sdku/1.0.0/roles/library_sdku/defaults/main.yml')
        self.edit(library_defaults, lambda d: d['platform_library_definition'].update(resource_defaults={'kafka': {'topics': {
            'events': {'name': 'package.events', 'partitions': 2, 'config': {'cleanup.policy': 'compact', 'retention.ms': 1000}},
            'unused': {'name': 'not.created'}}}}))
        def resources(d):
            for key, lib in d['platform_desired_state']['applicationLibraryDeployments'].items():
                lib['resources'].update(events={'kind': 'kafka.topic', 'binding': 'messaging', 'parameters': {}},
                                        alternate={'kind': 'kafka.topic', 'binding': 'messaging', 'parameters': {'name': key + '.alternate'}})
                lib['resource_defaults'] = {'kafka': {'topics': {'events': {'name': key + '.events', 'config': {'retention.ms': 2000}}}}}
        self.edit(self.vars, resources)
        self.edit(self.defaults, lambda d: d['platform_application_definition']['defaults'].update(
            topicBindings={'kafka': {'main': 'events'}}, environment={'MAIN_TOPIC': '{{ application_topics.kafka.main.name }}'}))
        def projected():
            value = self.snapshot()
            self.assertEqual('PASS', value['status'], [(f['code'], f.get('field')) for f in value['findings']])
            for key, lib in value['applicationLibraries']['libraries'].items():
                self.assertNotIn('unused', lib['topics'])
                instance = lib['instances']['apigateway-' + key]
                name = instance['topics']['kafka']['main']['name']
                self.assertTrue(all(p['environment']['MAIN_TOPIC'] == name for p in instance['placements'].values()))
            return value['applicationLibraries']['libraries']['sdku']
        lib = projected()
        self.assertEqual(('sdku.events', 2, 'compact', '2000'), (lib['topics']['events']['name'], lib['topics']['events']['partitions'],
                         lib['topics']['events']['config']['cleanup.policy'], lib['topics']['events']['config']['retention.ms']))
        self.edit(self.vars, lambda d: d['platform_desired_state']['applicationLibraryDeployments']['sdku']['resources']['events']['parameters'].update(name='resource.events'))
        self.assertEqual('resource.events', projected()['instances']['apigateway-sdku']['topics']['kafka']['main']['name'])
        self.edit(self.vars, lambda d: d['platform_desired_state']['applicationLibraryDeployments']['sdku']['applications']['gateway'].setdefault('overrides', {}).update(topicBindings={'kafka': {'main': 'alternate'}}))
        self.assertEqual('sdku.alternate', projected()['instances']['apigateway-sdku']['topics']['kafka']['main']['name'])
        self.edit(self.vars, lambda d: d['platform_desired_state']['applicationLibraryDeployments']['sdku']['applications']['gateway']['overrides'].pop('topicBindings'))
        self.assertEqual('resource.events', projected()['instances']['apigateway-sdku']['topics']['kafka']['main']['name'])
        self.edit(self.vars, lambda d: d['platform_desired_state']['applicationLibraryDeployments']['sdku']['resources']['events']['parameters'].pop('name'))
        self.assertEqual('sdku.events', projected()['topics']['events']['name'])
        # An ordinary ENV override remains independent; removing it restores the role template.
        self.edit(self.vars, lambda d: d['platform_desired_state']['applicationLibraryDeployments']['sdku']['applications']['gateway'].setdefault('overrides', {}).update(environment={'MAIN_TOPIC': 'explicit.env'}))
        value = self.snapshot()
        instance = value['applicationLibraries']['libraries']['sdku']['instances']['apigateway-sdku']
        self.assertTrue(all(p['environment']['MAIN_TOPIC'] == 'explicit.env' for p in instance['placements'].values()))
        self.edit(self.vars, lambda d: d['platform_desired_state']['applicationLibraryDeployments']['sdku']['applications']['gateway']['overrides'].pop('environment'))
        projected()
        for ref in ('', 'missing'):
            self.edit(self.vars, lambda d: d['platform_desired_state']['applicationLibraryDeployments']['sdku']['applications']['gateway']['overrides'].update(topicBindings={'kafka': {'main': ref}}))
            self.snapshot(expected_error='Invalid Kafka topic role: sdku/gateway/kafka/main')
        self.edit(self.vars, lambda d: d['platform_desired_state']['applicationLibraryDeployments']['sdku']['applications']['gateway']['overrides'].pop('topicBindings'))
        self.edit(self.vars, lambda d: d['platform_desired_state']['applicationLibraryDeployments']['sdku']['resources']['events'].update(binding='wrong'))
        self.snapshot(expected_error='Invalid Kafka topic role: sdku/gateway/kafka/main')

    def test_required_environment_resolves_after_package_parameter_defaults(self):
        def defaults(data):
            settings = data['platform_application_definition']['defaults']
            settings['parameters']['package_only'] = '{{ application_instance_id }}'
            settings['environment']['REQUIRED_PARAMETER'] = '{{ application_parameters.package_only }}'
        self.edit(self.defaults, defaults)
        result = self.snapshot()
        self.assertEqual('PASS', result['status'], [(f['code'], f.get('field')) for f in result['findings']])
        for library in ('sdku', 'cspa'):
            instance = result['applicationLibraries']['libraries'][library]['instances']['apigateway-' + library]
            for row in instance['placements'].values():
                self.assertEqual('apigateway-' + library, row['environment']['REQUIRED_PARAMETER'])

    def test_table_defaults_merge_reset_and_native_ddl_render_without_execution(self):
        source = os.path.join(REPO, 'examples/sdku/library-packages/sdku/1.0.0/roles/library_sdku/defaults/main.yml')
        with open(source) as stream:
            defaults = yaml.safe_load(stream)['platform_library_definition']['resource_defaults']
        path = os.path.join(self.root, 'library-packages/sdku/1.0.0/roles/library_sdku/defaults/main.yml')
        self.edit(path, lambda d: d['platform_library_definition'].update(resource_defaults=defaults))
        def resource_defaults():
            snapshot = self.snapshot()
            self.assertEqual('PASS', snapshot['status'], [(f['code'], f.get('field')) for f in snapshot['findings']])
            return snapshot['applicationLibraries']['libraries']['sdku']['resourceDefaults']
        self.assertEqual(8192, resource_defaults()['clickhouse']['tables']['records']['settings']['index_granularity'])
        self.edit(self.vars, lambda d: d['platform_desired_state']['applicationLibraryDeployments']['sdku'].update(
            resource_defaults={'clickhouse': {'tables': {'records': {'settings': {'index_granularity': 4096}}}}}))
        self.assertEqual(4096, resource_defaults()['clickhouse']['tables']['records']['settings']['index_granularity'])
        self.edit(self.vars, lambda d: d['platform_desired_state']['applicationLibraryDeployments']['sdku'].pop('resource_defaults'))
        self.assertEqual(8192, resource_defaults()['clickhouse']['tables']['records']['settings']['index_granularity'])
        template = os.path.join(REPO, 'services/clickhouse/ansible_collections/platform/clickhouse/roles/application_provider/templates/application-table.sql.j2')
        for mode in ('standalone', 'raft-ha'):
            for name, table in defaults['clickhouse']['tables'].items():
                table = dict(table, name=name, engine=('Replicated' if mode == 'raft-ha' else '') + table['engine'], replicationPath='/clickhouse/tables/qa/ch/{shard}/analytics/' + name)
                output = os.path.join(self.tmp.name, mode + '-' + name + '.sql')
                play = [dict(hosts='localhost', connection='local', gather_facts=False,
                    vars=dict(item=[dict(name='analytics'), table], platform_clickhouse_application_job=dict(mode=mode)),
                    tasks=[{'ansible.builtin.template': dict(src=template, dest=output)}])]
                play_path = os.path.join(self.tmp.name, 'render.json')
                with open(play_path, 'w') as stream:
                    json.dump(play, stream)
                rendered = subprocess.run(['ansible-playbook', '-i', 'localhost,', play_path], capture_output=True, timeout=30)
                self.assertEqual(0, rendered.returncode, rendered.stdout.decode(errors='replace')[-1600:])
                with open(output) as stream:
                    sql = stream.read()
                self.assertIn('`analytics`.`' + name + '`', sql)
                self.assertEqual(mode == 'raft-ha', 'ON CLUSTER default' in sql)
                self.assertNotIn('ALTER ', sql)
                if shutil.which('clickhouse'):
                    parsed = subprocess.run(['clickhouse', 'format', '--query', sql], capture_output=True, timeout=30)
                    self.assertEqual(0, parsed.returncode, parsed.stderr.decode(errors='replace')[-1000:])
        if shutil.which('clickhouse'):
            # SELECT-only local process; it neither connects to a server nor executes DDL.
            probe = subprocess.run(['clickhouse', 'local', '--query',
                "SELECT arrayMap(x -> formatQuerySingleLine(x), ['SELECT (a,b)', 'SELECT (a, b)']) AS expressions FORMAT JSONEachRow"], capture_output=True, timeout=30)
            self.assertEqual(0, probe.returncode, probe.stderr.decode(errors='replace')[-1000:])
            values = json.loads(probe.stdout)['expressions']
            self.assertEqual(values[0], values[1])
            names = sorted(defaults['clickhouse']['tables']['records']['settings'])
            settings = subprocess.run(['clickhouse', 'local', '--query',
                'SELECT name FROM system.merge_tree_settings WHERE name IN (' + ','.join("'" + n + "'" for n in names) + ') FORMAT JSONEachRow'], capture_output=True, timeout=30)
            self.assertEqual(0, settings.returncode, settings.stderr.decode(errors='replace')[-1000:])
            self.assertEqual(set(names), {json.loads(line)['name'] for line in settings.stdout.splitlines()})

    def test_topic_tasks_create_once_verify_and_sanitize_errors(self):
        # Exercise the production tasks with a bounded CLI fixture, not a Kafka acceptance substitute.
        cli = os.path.join(self.tmp.name, 'cli')
        os.makedirs(os.path.join(cli, 'bin'))
        state = os.path.join(self.tmp.name, 'topic-created')
        failure = os.path.join(self.tmp.name, 'connection-failure')
        script = '''#!/bin/sh
set -eu
action=; partitions=1; topic=
while [ "$#" -gt 0 ]; do
 case "$1" in
 --describe|--create) action=$1; shift;;
 --partitions) partitions=$2; shift 2;;
 --topic) topic=$2; shift 2;;
 --command-config) test "$(stat -c %a "$2")" = 600; shift 2;;
 --bootstrap-server|--replication-factor|--config|--entity-type|--entity-name) shift 2;;
 *) shift;;
 esac
done
if [ -e 'FAILURE' ]; then echo SECRET_RESPONSE_CANARY >&2; exit 7; fi
if [ "$action" = --create ]; then
 test "$topic" = qa.events
 printf '%s' "$partitions" > 'STATE'
 exit 0
fi
if [ ! -e 'STATE' ]; then exit 0; fi
test "$topic" = '^qa\\.events$'
printf 'Topic: qa.events\\tPartitionCount: %s\\tReplicationFactor: 1\\n' "$(cat 'STATE')"
i=0
while [ "$i" -lt "$(cat 'STATE')" ]; do
 printf 'Topic: qa.events\\tPartition: %s\\tLeader: 1\\tReplicas: 1\\tIsr: 1\\n' "$i"
 i=$((i+1))
done
'''.replace('STATE', state).replace('FAILURE', failure)
        for name, contents in [('kafka-topics.sh', script), ('kafka-configs.sh',
                '#!/bin/sh\nprintf "  min.insync.replicas=1 sensitive=false synonyms={}\\n  cleanup.policy=compact sensitive=false synonyms={}\\n"\n')]:
            path = os.path.join(cli, 'bin', name)
            with open(path, 'w') as stream:
                stream.write(contents)
            os.chmod(path, 0o755)
        job = dict(providerId='qa', candidates=[dict(hostId='localhost', address='127.0.0.1', port=1, tls=False)],
                   topics=[dict(name='qa.events', mode='managed', partitions=2, replicationFactor=1,
                                config={'min.insync.replicas': '1', 'cleanup.policy': 'compact'})])
        env = dict(os.environ, ANSIBLE_CONFIG=os.path.join(REPO, 'ansible-core/ansible.cfg'),
                   ANSIBLE_COLLECTIONS_PATH=os.pathsep.join([os.path.join(REPO, 'ansible-core/collections'), os.path.join(REPO, 'services/kafka')]))
        def run(phase, expected=0):
            play = [dict(hosts='localhost', gather_facts=False, connection='local',
                         vars=dict(platform_kafka_install_directory=cli, platform_kafka_application_job=job,
                                   platform_kafka_application_phase=phase,
                                   platform_kafka_startup_readiness_retries=1,
                                   platform_kafka_startup_readiness_delay=0),
                         tasks=[{'ansible.builtin.include_role': {'name': 'platform.kafka.kafka_kraft', 'tasks_from': 'application_topics'}}])]
            path = os.path.join(self.tmp.name, 'topics.json')
            with open(path, 'w') as stream:
                json.dump(play, stream)
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', path], env=env, capture_output=True, timeout=45)
            self.assertNotIn(b'SECRET_RESPONSE_CANARY', result.stdout + result.stderr)
            self.assertEqual(expected, result.returncode, (result.stdout + result.stderr).decode(errors='replace').replace('SECRET_RESPONSE_CANARY', '[REDACTED]')[-2400:])
            return result.stdout
        run('preflight')
        self.assertFalse(os.path.exists(state))
        job['topics'][0]['mode'] = 'existing'
        self.assertIn(b'TOPIC_MISSING', run('preflight', 2))
        self.assertIn(b'TOPIC_MISSING', run('verify', 2))
        job['topics'][0]['mode'] = 'managed'
        run('apply')
        self.assertTrue(os.path.exists(state))
        self.assertIn(b'changed=0', run('apply'))
        self.assertIn(b'changed=0', run('verify'))
        job['topics'][0]['partitions'] = 1
        run('preflight', 2)
        with open(state) as stream:
            self.assertEqual('2', stream.read())
        with open(failure, 'w') as stream:
            stream.write('fail')
        run('verify', 2)

    def test_kafka_resource_bindings_use_core_and_reset_to_application_defaults(self):
        self.edit(self.vars, lambda d: d['platform_desired_state']['applicationLibraryDeployments']['sdku']['resources'].update(
            events=dict(kind='kafka.topic', binding='messaging', parameters={'name': 'sdku.events'})))
        self.edit(self.vars, lambda d: d['platform_desired_state']['applicationLibraryDeployments']['cspa']['resources'].update(
            events=dict(kind='kafka.topic', binding='messaging', parameters={'name': 'cspa.events'})))
        self.edit(self.defaults, lambda d: d['platform_application_definition']['defaults'].update(topicBindings={'kafka': ['events']}))
        def projected():
            value = self.snapshot()
            self.assertEqual('PASS', value['status'], [(f['code'], f.get('field')) for f in value['findings']])
            return value['applicationLibraries']['libraries']['sdku']
        self.assertEqual(1, projected()['topics']['events']['replicationFactor'])
        self.assertEqual('sdku.events', projected()['instances']['apigateway-sdku']['topics']['kafka'][0]['name'])
        self.edit(self.vars, lambda d: d['platform_desired_state']['applicationLibraryDeployments']['sdku']['applications']['gateway'].setdefault('overrides', {}).update(topicBindings={'kafka': []}))
        self.assertEqual([], projected()['instances']['apigateway-sdku']['topics']['kafka'])
        self.edit(self.vars, lambda d: d['platform_desired_state']['applicationLibraryDeployments']['sdku']['applications']['gateway']['overrides'].pop('topicBindings'))
        self.assertEqual(1, len(projected()['instances']['apigateway-sdku']['topics']['kafka']))

    def test_shared_runtime_paths_with_builtin_tasks_and_no_target_writes(self):
        tasks = os.path.join(REPO, 'ansible-core/collections/ansible_collections/platform/core/roles/application_runtime/tasks/resolve_paths.yml')
        for directory, previous, expected in [
                ('~/sdku', [], '/home/docker-qa/sdku'),
                ('/data/scada/sdku', [], '/data/scada/sdku'),
                ('~/../foreign', [], None),
                ('~/sdku', [{'libraryId': 'other', 'libraryPath': '/home/docker-qa/sdku'}], None),
                ('/data/sdk/api-a', [{'libraryId': 'other', 'libraryPath': '/data/sdk'}], None),
                ('/data/sdk', [{'libraryId': 'other', 'libraryPath': '/data/sdk/api-a'}], None),
                ('/data/sdk-a', [{'libraryId': 'other', 'libraryPath': '/data/sdk'}], '/data/sdk-a'),
                ('~/sdku', [{'libraryId': 'sdku', 'libraryPath': '/home/docker-qa/sdku'}], '/home/docker-qa/sdku')]:
            play = [{'hosts': 'localhost', 'gather_facts': False, 'connection': 'local',
                     'vars': {'application_path_home': '/home/docker-qa',
                              'platform_application_preflight_jobs': previous,
                              'application_runtime_job': {'libraryId': 'sdku', 'placement': {'runtimeDirectory': directory, 'runtimePath': 'dm-sdku'}}},
                     'tasks': [{'ansible.builtin.include_tasks': tasks}]}]
            if expected:
                play[0]['tasks'].append({'ansible.builtin.assert': {'that': [
                    'application_library_path == ' + json.dumps(expected),
                    'application_instance_path == ' + json.dumps(expected + '/dm-sdku')]}})
            path = os.path.join(self.tmp.name, 'paths.json')
            with open(path, 'w') as stream:
                json.dump(play, stream)
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', path], capture_output=True, timeout=30)
            self.assertEqual(0 if expected else 2, result.returncode, 'Native builtin path tasks failed')

    def test_library_runtime_directory_default_override_and_reset(self):
        def directory():
            library = self.snapshot()['applicationLibraries']['libraries']['sdku']
            placements = library['instances']['apigateway-sdku']['placements']
            self.assertTrue(all(p['runtimeDirectory'] == library['runtimeDirectory'] for p in placements.values()))
            return library['runtimeDirectory']
        self.assertEqual('~/sdku', directory())
        self.edit(self.vars, lambda data: data['platform_desired_state']['applicationLibraryDeployments']['sdku'].update(
            runtime_directory='/data/scada/sdku'))
        self.assertEqual('/data/scada/sdku', directory())
        self.edit(self.vars, lambda data: data['platform_desired_state']['applicationLibraryDeployments']['sdku'].update(
            runtime_directory=''))
        self.assertEqual('~/sdku', directory())

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="a1-standalone-")
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, "project")
        shutil.copytree(FIXTURE, self.root)
        self.vars = os.path.join(self.root, "inventory/group_vars/all/platform-installer.yml")
        self.defaults = os.path.join(self.root, "application-packages/apigateway/1.0.0/roles/application_apigateway/defaults/main.yml")

    def edit(self, path, mutate):
        with open(path) as stream:
            data = json.load(stream)
        mutate(data)
        with open(path, "w") as stream:
            json.dump(data, stream, sort_keys=True)

    def snapshot(self, expected_error=None):
        output = os.path.join(self.tmp.name, "snapshot.json")
        env = dict(os.environ, ANSIBLE_CONFIG=os.path.join(REPO, "ansible-core/ansible.cfg"),
                   ANSIBLE_COLLECTIONS_PATH=os.pathsep.join([os.path.join(REPO, "ansible-core/collections")] +
                       [os.path.join(REPO, 'services', name) for name in os.listdir(os.path.join(REPO, 'services'))]),
                   ANSIBLE_CALLBACKS_ENABLED="platform.core.project_snapshot_json",
                   PLATFORM_PROJECT_SNAPSHOT_OUTPUT=output)
        command = ["ansible-playbook", "-i", os.path.join(self.root, "inventory/hosts.yml"),
                   os.path.join(REPO, "ansible-core/playbooks/project-snapshot-machine.yml"),
                   "-e", "platform_project_root=" + self.root,
                   "-e", "platform_service_catalog_path=" + os.path.join(REPO, "examples/catalog/service-catalog.yml")]
        completed = subprocess.run(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        if expected_error:
            self.assertNotEqual(0, completed.returncode)
            self.assertIn(expected_error.encode(), completed.stdout)
            return
        # Don't include raw Ansible output in assertion errors.
        self.assertEqual(0, completed.returncode, "Standalone Ansible failed; inspect protected temporary output")
        self.assertNotIn(b"changed=1", completed.stdout)
        with open(output) as stream:
            return json.load(stream)

    def test_two_libraries_multihost_and_parameter_isolation(self):
        snapshot = self.snapshot()
        self.assertEqual("PASS", snapshot["status"], [(f["code"], f.get("field")) for f in snapshot["findings"]])
        libraries = snapshot["applicationLibraries"]["libraries"]
        sdku = libraries["sdku"]["instances"]["apigateway-sdku"]
        cspa = libraries["cspa"]["instances"]["apigateway-cspa"]
        self.assertEqual({"node1", "node2"}, set(sdku["placements"]))
        self.assertEqual("DEBUG", sdku["placements"]["node1"]["parameters"]["log_level"])
        self.assertEqual("TRACE", sdku["placements"]["node2"]["parameters"]["log_level"])
        self.assertEqual("WARN", cspa["placements"]["node1"]["parameters"]["log_level"])
        self.assertEqual("test-user", sdku["credentialRequirements"]["redis"]["credentials"]["username"]["source"]["value"])
        self.assertEqual("sdku-redis-password", sdku["credentialRequirements"]["redis"]["credentials"]["password"]["source"]["ref"])
        self.assertEqual("postgres-sdku", sdku["connections"]["postgres"]["deploymentRef"])
        self.assertEqual("postgres-cspa", cspa["connections"]["postgres"]["deploymentRef"])
        self.assertEqual("node2", sdku["placements"]["node2"]["SERVER_ID"])
        self.assertEqual("project-sdku-apigateway-sdku-node1", sdku["placements"]["node1"]["composeProject"])
        self.assertEqual("apigateway-sdku-node1", sdku["placements"]["node1"]["containerName"])
        self.assertEqual("CLIENT_SSL", sdku["connections"]["kafka"]["connectionRef"])
        self.assertTrue(sdku["agentRequired"])
        self.assertEqual({"account": "redis", "field": "password"}, sdku["secretBindings"]["REDIS_PASSWORD"]["source"])
        self.assertEqual({"library_secret": "java_keystore_password"}, sdku["secretBindings"]["JAVA_KEYSTORE_PASSWORD"]["source"])
        self.assertEqual(snapshot["snapshotFingerprint"], self.snapshot()["snapshotFingerprint"])

    def test_library_defaults_inheritance_resets_and_opt_out(self):
        library = os.path.join(self.root, 'library-packages/sdku/1.0.0/roles/library_sdku/defaults/main.yml')
        self.edit(library, lambda d: d['platform_library_definition'].update(defaults={
            'environment': {'COMMON': 'library', 'LEVEL': 'library'},
            'parameters': {'common_number': 7}}))
        self.edit(self.defaults, lambda d: d['platform_application_definition']['defaults'].setdefault('environment', {}).update(LEVEL='application'))
        def instance(d):
            lib = d['platform_desired_state']['applicationLibraryDeployments']['sdku']
            lib['overrides'] = {'environment': {'LEVEL': 'library-instance'}}
            lib['applications']['gateway'].setdefault('overrides', {})['environment'] = {'LEVEL': 'instance'}
        self.edit(self.vars, instance)
        def placement():
            result = self.snapshot()
            self.assertEqual('PASS', result['status'], [(f['code'], f.get('field')) for f in result['findings']])
            return result['applicationLibraries']['libraries']['sdku']['instances']['apigateway-sdku']['placements']['node1']
        row = placement()
        self.assertEqual('instance', row['environment']['LEVEL'])
        self.assertEqual('library-instance', row['inherited']['environment']['LEVEL'])
        self.assertEqual('library', row['environment']['COMMON'])
        self.assertEqual(7, row['parameters']['common_number'])
        self.assertEqual('library-instance', row['commonDefaults']['environment']['LEVEL'])
        self.edit(self.vars, lambda d: d['platform_desired_state']['applicationLibraryDeployments']['sdku']['applications']['gateway']['overrides'].pop('environment'))
        self.assertEqual('library-instance', placement()['environment']['LEVEL'])
        self.edit(self.vars, lambda d: d['platform_desired_state']['applicationLibraryDeployments']['sdku'].pop('overrides'))
        self.assertEqual('application', placement()['environment']['LEVEL'])
        self.edit(library, lambda d: d['platform_library_definition']['slots']['gateway'].update(inherit_defaults=False))
        row = placement()
        self.assertNotIn('COMMON', row['environment'])
        self.assertNotIn('common_number', row['parameters'])

    def test_common_defaults_cannot_use_indirect_application_context(self):
        library = os.path.join(self.root, 'library-packages/sdku/1.0.0/roles/library_sdku/defaults/main.yml')
        self.edit(library, lambda d: d['platform_library_definition'].update(defaults={'environment': {'INVALID': '{{ indirect_application }}'}}))
        self.edit(self.vars, lambda d: d.update(application_name='stale-application', indirect_application='{{ application_name }}'))
        self.snapshot(expected_error='PROJECT_SNAPSHOT_INPUT_INVALID')

    def test_dotted_project_id_blocks_compose_projection(self):
        dotted_root = os.path.join(self.tmp.name, "project.test")
        os.rename(self.root, dotted_root)
        self.root = dotted_root
        snapshot = self.snapshot()
        self.assertIn("APPLICATION_COMPOSE_PROJECT_INVALID", [f["code"] for f in snapshot["findings"]])
        self.assertEqual({}, snapshot["applicationLibraries"]["libraries"])

    def test_infrastructure_only_without_library_selection(self):
        def infrastructure(data):
            data.pop("platform_desired_state_contract")
            data["platform_desired_state"].pop("applicationLibraryDeployments")
        self.edit(self.vars, infrastructure)
        for host in ("node1", "node2"):
            self.edit(os.path.join(self.root, "inventory/host_vars", host, "platform-installer.yml"), lambda data: data.pop("platform_application_libraries"))
        shutil.rmtree(os.path.join(self.root, "application-packages"))
        shutil.rmtree(os.path.join(self.root, "library-packages"))
        snapshot = self.snapshot()
        self.assertEqual("PASS", snapshot["status"])
        self.assertEqual("platform.installer/project-snapshot/v1alpha1", snapshot["apiVersion"])
        self.assertNotIn("applicationLibraries", snapshot)

    def test_no_accounts_no_agent_or_credentials(self):
        def no_secrets(data):
            defaults = data["platform_application_definition"]["defaults"]
            defaults.pop("accounts")
            defaults.pop("provisioner")
        self.edit(self.defaults, no_secrets)
        snapshot = self.snapshot()
        self.assertEqual("PASS", snapshot["status"])
        instance = snapshot["applicationLibraries"]["libraries"]["sdku"]["instances"]["apigateway-sdku"]
        self.assertFalse(instance["agentRequired"])
        self.assertEqual({}, instance["credentialRequirements"])
        self.assertIsNone(instance["approle"])

    def test_shared_only_requires_agent_without_account_hooks(self):
        def shared_only(data):
            defaults = data["platform_application_definition"]["defaults"]
            defaults.pop("accounts")
            bindings = defaults["provisioner"]["secret_bindings"]
            defaults["provisioner"]["secret_bindings"] = {"JAVA_KEYSTORE_PASSWORD": bindings["JAVA_KEYSTORE_PASSWORD"]}
        self.edit(self.defaults, shared_only)
        snapshot = self.snapshot()
        self.assertEqual("PASS", snapshot["status"])
        for library in snapshot["applicationLibraries"]["libraries"].values():
            for instance in library["instances"].values():
                self.assertTrue(instance["agentRequired"])
                self.assertEqual({}, instance["credentialRequirements"])
                self.assertIsNotNone(instance["approle"])
                self.assertIn("A4_PROVIDER_PROVISIONING", instance["executionPrerequisites"])
                self.assertEqual({"JAVA_KEYSTORE_PASSWORD"}, set(instance["secretBindings"]))
            self.assertEqual({"java_keystore_password"}, set(library["sharedSecretRequirements"]))

    def test_ambiguous_secret_binding_blocks(self):
        self.edit(self.defaults, lambda data: data["platform_application_definition"]["defaults"]["provisioner"]["secret_bindings"]["REDIS_PASSWORD"]["source"].update(library_secret="java_keystore_password"))
        snapshot = self.snapshot()
        self.assertNotEqual("PASS", snapshot["status"])
        self.assertEqual({}, snapshot["applicationLibraries"]["libraries"])

    def test_unknown_shared_secret_blocks(self):
        self.edit(self.defaults, lambda data: data["platform_application_definition"]["defaults"]["provisioner"]["secret_bindings"]["JAVA_KEYSTORE_PASSWORD"].update(source={"library_secret": "unknown"}))
        snapshot = self.snapshot()
        self.assertIn("APPLICATION_SECRET_BINDING_INVALID", [f["code"] for f in snapshot["findings"]])
        self.assertEqual({}, snapshot["applicationLibraries"]["libraries"])

    def test_shared_only_requires_vault_ref(self):
        def shared_only(data):
            defaults = data["platform_application_definition"]["defaults"]
            defaults.pop("accounts")
            defaults["provisioner"]["secret_bindings"] = {"JAVA_KEYSTORE_PASSWORD": {"source": {"library_secret": "java_keystore_password"}}}
        self.edit(self.defaults, shared_only)
        self.edit(self.vars, lambda data: data["platform_desired_state"]["applicationLibraryDeployments"]["sdku"]["bindings"].pop("secrets"))
        snapshot = self.snapshot()
        self.assertIn("APPLICATION_VAULT_REQUIRED", [f["code"] for f in snapshot["findings"]])
        self.assertEqual({}, snapshot["applicationLibraries"]["libraries"])

    def test_missing_service_ref_skips_unused_hook(self):
        def no_accounts(data):
            defaults = data["platform_application_definition"]["defaults"]
            defaults.pop("accounts")
            defaults.pop("provisioner")
        self.edit(self.defaults, no_accounts)
        self.edit(self.vars, lambda data: data["platform_desired_state"]["applicationLibraryDeployments"]["sdku"]["bindings"].pop("cache"))
        instance = self.snapshot()["applicationLibraries"]["libraries"]["sdku"]["instances"]["apigateway-sdku"]
        self.assertNotIn("redis", instance["connections"])

    def test_same_host_port_collision_blocks(self):
        self.edit(self.vars, lambda data: data["platform_desired_state"]["applicationLibraryDeployments"]["cspa"]["applications"]["gateway"]["overrides"]["ports"]["http"].update(published=18081))
        snapshot = self.snapshot()
        self.assertIn("APPLICATION_PORT_COLLISION", [f["code"] for f in snapshot["findings"]])
        self.assertEqual({}, snapshot["applicationLibraries"]["libraries"])

    def test_missing_kafka_selector_blocks(self):
        for library in ("sdku", "cspa"):
            path = os.path.join(self.root, "library-packages", library, "1.0.0/roles/library_" + library + "/defaults/main.yml")
            self.edit(path, lambda data: data["platform_library_definition"].pop("connection_defaults"))
        snapshot = self.snapshot()
        self.assertIn("APPLICATION_CONNECTION_INVALID", [f["code"] for f in snapshot["findings"]])

    def test_validate_entrypoint_consumes_shared_projection(self):
        output = os.path.join(self.tmp.name, "validation.json")
        env = dict(os.environ, ANSIBLE_CONFIG=os.path.join(REPO, "ansible-core/ansible.cfg"),
                   ANSIBLE_COLLECTIONS_PATH=os.pathsep.join([os.path.join(REPO, "ansible-core/collections")] +
                       [os.path.join(REPO, 'services', name) for name in os.listdir(os.path.join(REPO, 'services'))]))
        completed = subprocess.run(["ansible-playbook", "-i", os.path.join(self.root, "inventory/hosts.yml"),
                                    os.path.join(REPO, "ansible-core/playbooks/validate.yml"),
                                    "-e", "platform_project_root=" + self.root,
                                    "-e", "platform_service_catalog_path=" + os.path.join(REPO, "examples/catalog/service-catalog.yml"),
                                    "-e", "platform_validation_artifact=" + output],
                                   env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        self.assertEqual(0, completed.returncode, "Standalone validation failed")
        with open(output) as stream:
            self.assertEqual("PASS", json.load(stream)["status"])

    def test_private_key_never_returned_in_projection(self):
        self.edit(self.vars, lambda data: data["platform_desired_state"]["applicationLibraryDeployments"]["sdku"]["applications"]["gateway"]["overrides"]["parameters"].update(password="-----BEGIN PRIVATE KEY-----DO-NOT-PRINT"))
        snapshot = self.snapshot()
        self.assertNotIn("-----BEGIN PRIVATE KEY-----DO-NOT-PRINT", json.dumps(snapshot))
        self.assertIn("APPLICATION_PLAINTEXT_FORBIDDEN", [f["code"] for f in snapshot["findings"]])

    def test_free_resources_grants_endpoint_never_leak_secrets(self):
        with open(self.vars) as stream:
            original_vars = json.load(stream)
        with open(self.defaults) as stream:
            original_defaults = json.load(stream)
        for section in ("resources", "grants", "endpoint"):
            with self.subTest(section=section):
                with open(self.vars, "w") as stream:
                    json.dump(original_vars, stream)
                with open(self.defaults, "w") as stream:
                    json.dump(original_defaults, stream)
                if section == "resources":
                    self.edit(self.vars, lambda data: data["platform_desired_state"]["applicationLibraryDeployments"]["sdku"]["resources"]["applicationDatabase"]["parameters"].update(password="-----BEGIN PRIVATE KEY-----DO-NOT-PRINT"))
                elif section == "grants":
                    self.edit(self.defaults, lambda data: data["platform_application_definition"]["defaults"]["accounts"]["redis"].update(grants=[{"token": "-----BEGIN PRIVATE KEY-----DO-NOT-PRINT"}]))
                else:
                    self.edit(self.vars, lambda data: data["platform_desired_state"]["applicationLibraryDeployments"]["sdku"]["applications"]["gateway"]["overrides"].update(endpoint={"enabled": False, "haproxy": {"password": "-----BEGIN PRIVATE KEY-----DO-NOT-PRINT"}}))
                snapshot = self.snapshot()
                self.assertNotIn("-----BEGIN PRIVATE KEY-----DO-NOT-PRINT", json.dumps(snapshot))
                self.assertEqual("BLOCKED", snapshot["applicationLibraries"]["status"])
                self.assertEqual({}, snapshot["applicationLibraries"]["libraries"])



if __name__ == "__main__":
    unittest.main()

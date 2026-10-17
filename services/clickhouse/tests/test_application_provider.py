"""Native TLS role acceptance, isolated from deployed ClickHouse instances."""
import getpass
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import re
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from contextlib import nullcontext
import xml.etree.ElementTree as ET

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ansible_collections.platform.clickhouse.plugins.module_utils.application_sql import NativeClient, user_batch, ProviderFailure, managed_grant_delta, table_matches
from ansible_collections.platform.clickhouse.plugins.modules import application_scope as scope


class ApplicationProviderTests(unittest.TestCase):
    def test_table_metadata_drift_and_replication_identity_without_mutations(self):
        table = dict(name='records', engine='MergeTree', columns=[dict(name='systemId', type='UInt32', codec='T64, LZ4')], order_by='systemId',
                     settings={'index_granularity': 8192, 'columns_to_prewarm_mark_cache': 'systemId,ts'})
        metadata = dict(engine='MergeTree', partition_key='', primary_key='systemId', sorting_key='systemId', sampling_key='',
                        create_table_query="CREATE TABLE records SETTINGS index_granularity = 8192, columns_to_prewarm_mark_cache = 'systemId,ts'")
        columns = [dict(name='systemId', type='UInt32', compression_codec='CODEC(T64, LZ4)')]
        class Client:
            def query(self, sql):
                if 'FROM system.tables' in sql:
                    return json.dumps(metadata) if metadata else ''
                if 'FROM system.columns' in sql:
                    return '\n'.join(map(json.dumps, columns))
                if 'FROM system.data_skipping_indices' in sql:
                    return ''
                if 'arrayMap' in sql:
                    return json.dumps(dict(expressions=['normalized', 'normalized'] * 3))
                if 'FROM system.replicas' in sql:
                    return json.dumps(dict(zookeeper_path='/qa/1/analytics/records', replica_name='r1', shard='1', replica='r1'))
                raise AssertionError('Unexpected query (must remain read-only)')
        client = Client()
        self.assertTrue(table_matches(client, 'analytics', table))
        for field, wrong in [('engine', 'ReplacingMergeTree'), ('sorting_key', ''), ('create_table_query', 'SETTINGS index_granularity = 4096')]:
            original = metadata[field]
            metadata[field] = wrong
            with self.subTest(field=field), self.assertRaises(ProviderFailure):
                table_matches(client, 'analytics', table)
            metadata[field] = original
        columns[0]['type'] = 'UInt64'
        with self.assertRaisesRegex(ProviderFailure, 'COLUMNS_DRIFT'):
            table_matches(client, 'analytics', table)
        columns[0]['type'] = 'UInt32'
        table.update(engine='ReplicatedMergeTree', replicationPath='/qa/{shard}/analytics/records')
        metadata['engine'] = table['engine']
        self.assertTrue(table_matches(client, 'analytics', table))
        table['replicationPath'] = '/foreign/{shard}/analytics/records'
        with self.assertRaisesRegex(ProviderFailure, 'REPLICATION_DRIFT'):
            table_matches(client, 'analytics', table)
        metadata.clear()
        self.assertFalse(table_matches(client, 'analytics', table))

    def test_table_resource_retry_preserves_database_ownership_and_verify_never_writes(self):
        witness, present, writes = {}, set(), []
        database = dict(name='analytics', mode='managed', marker='platform.application/v1:qa:ch:lib:db')
        job = dict(serviceType='clickhouse', mode='standalone', candidates=[dict(memberId='ch1', hostId='localhost')], databases=[database], accounts=[])
        table = dict(database='analytics', definition=dict(name='records'), sql='CREATE TABLE IF NOT EXISTS analytics.records;')
        args = dict(job=job, tables=[table], directory='/unused', admin_password='qa-secret-canary', passwords={},
                    phase='preflight', lock_timeout=15, query_timeout=1)
        class Finished(Exception):
            pass
        class Module:
            params = args
            def exit_json(self, **value):
                raise Finished(value)
            def fail_json(self, **value):
                raise Finished(dict(value, failed=True))
        class Client:
            fail = False
            def query(self, sql):
                writes.append(sql)
                if sql.startswith('CREATE DATABASE'):
                    present.add('database')
                if 'CREATE TABLE' in sql:
                    if self.fail:
                        raise ProviderFailure('CLICKHOUSE_APPLICATION_QUERY_FAILED_123')
                    present.add('table')
                return ''
            def close(self):
                pass
        def state(*unused):
            return [dict(kind='database', name='analytics', id='stable-id')] if 'database' in present else []
        client = Client()
        with patch.object(scope, 'AnsibleModule', return_value=Module()), patch.object(scope, 'NativeClient', return_value=client), \
                patch.object(scope, 'custody', return_value=nullcontext(witness)), patch.object(scope, 'publish'), \
                patch.object(scope, 'state', side_effect=state), patch.object(scope, 'table_matches', side_effect=lambda *a: 'table' in present):
            def run(phase):
                args['phase'] = phase
                with self.assertRaises(Finished) as done:
                    scope.main()
                return done.exception.args[0]
            self.assertFalse(run('preflight')['changed'])
            self.assertEqual([], writes)
            client.fail = True
            self.assertTrue(run('resources')['failed'])
            self.assertEqual({'ch1': 'stable-id'}, witness['database/analytics']['ids'])
            client.fail = False
            self.assertTrue(run('resources')['changed'])
            writes.clear()
            self.assertFalse(run('resources')['changed'])
            self.assertFalse(run('verify')['changed'])
            self.assertEqual([], writes)
            present.remove('table')
            self.assertIn('TABLE_MISSING', run('verify')['msg'])
            self.assertEqual([], writes)
            database['mode'] = 'existing'
            witness.clear()
            self.assertTrue(run('resources')['changed'])
            self.assertTrue(all('CREATE TABLE' in statement for statement in writes))

    def test_revoke_delta_is_limited_to_witnessed_library_databases(self):
        account = {'name':'app','marker':'platform.application/v1:qa:ch:lib:account:app/ch','grants':[]}
        database = {'name':'analytics','mode':'managed','marker':'platform.application/v1:qa:ch:lib:clickhouse.database:db'}
        row = {'kind':'grant','name':'app','database':'analytics','table':'*','privilege':'INSERT',
               'column':None,'is_partial_revoke':False,'grant_option':False}
        self.assertEqual((set(),{('analytics','*','INSERT')}),managed_grant_delta(account,[row],[database]))
        for update in ({'database':'foreign'}, {'privilege':'DROP TABLE'}, {'column':'id'}, {'grant_option':True}, {'is_partial_revoke':True}):
            with self.subTest(update=update), self.assertRaises(ProviderFailure):
                managed_grant_delta(account,[dict(row,**update)],[database])
        with self.assertRaises(ProviderFailure):
            managed_grant_delta(account,[row,{'kind':'role','name':'app'}],[database])
        self.assertEqual('REVOKE ON CLUSTER default INSERT ON `analytics`.* FROM `app`;',
                         user_batch(account,'unused',set(),False,True,{('analytics','*','INSERT')}))

    def test_cluster_batch_has_one_create_and_cluster_grants_without_plaintext(self):
        password = secrets.token_urlsafe(24)
        text = user_batch({'name': 'api-lib'}, password, {('analytics', 'events', 'SELECT'), ('analytics', 'events', 'INSERT')}, True, True)
        self.assertEqual(1, text.count('CREATE USER'))
        self.assertEqual(3, text.count('ON CLUSTER default'))
        self.assertNotIn(password, text)
        self.assertIn(hashlib.sha256(password.encode()).hexdigest(), text)
        self.assertNotIn('OR REPLACE', text)

    def test_native_standalone_resources_accounts_repeat_verify_and_foreign_denial(self):
        self.native_scope(False)

    def test_native_three_servers_cluster_accounts_grants_repeat_verify(self):
        if not shutil.which('clickhouse-keeper'):
            self.skipTest('Pinned Keeper runtime required')
        self.native_scope(True)

    def native_scope(self, clustered):
        if not all(shutil.which(name) for name in ['clickhouse-server', 'clickhouse-client', 'openssl', 'ansible-playbook']):
            self.skipTest('Pinned ClickHouse and Ansible runtime required')
        with tempfile.TemporaryDirectory(prefix='platform-clickhouse-app-') as temporary:
            root = Path(temporary)
            directory = root / 'config' / 'ch-qa' / 'ch-1'
            directory.mkdir(parents=True, mode=0o700)
            pki = directory / 'pki'
            pki.mkdir(mode=0o700)
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                            '-subj', '/CN=localhost', '-addext', 'subjectAltName=IP:127.0.0.1',
                            '-keyout', str(pki / 'private-key.pem'), '-out', str(pki / 'certificate.pem')],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            shutil.copyfile(pki / 'certificate.pem', pki / 'ca-chain.pem')
            with socket.socket() as reservation:
                reservation.bind(('127.0.0.1', 0))
                port = reservation.getsockname()[1]
            secret_root = root / 'secrets'
            secret_root.mkdir(mode=0o700)
            admin_password, user_password = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
            for name, password in [('admin', admin_password), ('app', user_password)]:
                path = secret_root / name
                path.write_text(password)
                path.chmod(0o600)
            users = directory / 'users.xml'
            users.write_text('<clickhouse><users><default><password_sha256_hex>' + hashlib.sha256(admin_password.encode()).hexdigest()
                             + '</password_sha256_hex><networks><ip>127.0.0.1</ip></networks><profile>default</profile><quota>default</quota>'
                             '<access_management>1</access_management></default></users><profiles><default/></profiles><quotas><default/></quotas></clickhouse>')
            users.chmod(0o600)
            config = directory / 'server.xml'
            config.write_text('<clickhouse><logger><level>information</level><log>' + str(root / 'server.log')
                              + '</log><errorlog>' + str(root / 'error.log') + '</errorlog></logger><listen_host>127.0.0.1</listen_host>'
                              '<tcp_port_secure>' + str(port) + '</tcp_port_secure><path>' + str(root / 'data') + '/</path>'
                              '<access_control_path>' + str(root / 'access') + '/</access_control_path><users_config>' + str(users) + '</users_config>'
                              '<openSSL><server><certificateFile>' + str(pki / 'certificate.pem') + '</certificateFile><privateKeyFile>'
                              + str(pki / 'private-key.pem') + '</privateKeyFile><caConfig>' + str(pki / 'ca-chain.pem')
                              + '</caConfig><verificationMode>none</verificationMode></server></openSSL>'
                              '<background_schedule_pool_size>16</background_schedule_pool_size><background_buffer_flush_schedule_pool_size>4</background_buffer_flush_schedule_pool_size>'
                              '<background_message_broker_schedule_pool_size>4</background_message_broker_schedule_pool_size><background_distributed_schedule_pool_size>4</background_distributed_schedule_pool_size>'
                              '<max_thread_pool_size>256</max_thread_pool_size>'
                              '<max_server_memory_usage>1073741824</max_server_memory_usage></clickhouse>')
            server_template = Path(__file__).resolve().parents[1] / 'ansible_collections/platform/clickhouse/roles/clickhouse_tls/templates/server.xml.j2'
            mask = re.search(r'<query_masking_rules>.*?</query_masking_rules>', server_template.read_text(), re.S).group()
            config_xml = ET.fromstring(config.read_text())
            config_xml.append(ET.fromstring(mask))
            ET.ElementTree(config_xml).write(config)
            targets = [{'hostId': 'localhost', 'memberId': 'ch-1', 'address': '127.0.0.1', 'port': port}]
            processes, configs = [], [config]
            def unused_port():
                with socket.socket() as reservation:
                    reservation.bind(('127.0.0.1', 0))
                    return reservation.getsockname()[1]
            def launch(binary, path):
                process = subprocess.Popen([binary, '--config-file', str(path)],
                                           env=dict(os.environ, CLICKHOUSE_WATCHDOG_ENABLE='0'),
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                processes.append(process)
                return process
            if clustered:
                keeper_port, raft_port = unused_port(), unused_port()
                keeper = ET.Element('clickhouse')
                ET.SubElement(keeper, 'listen_host').text = '127.0.0.1'
                settings = ET.SubElement(keeper, 'keeper_server')
                for key, value in {'tcp_port_secure': keeper_port, 'server_id': 1,
                                   'log_storage_path': root / 'keeper-log', 'snapshot_storage_path': root / 'keeper-snapshot'}.items():
                    ET.SubElement(settings, key).text = str(value)
                raft = ET.SubElement(settings, 'raft_configuration')
                node = ET.SubElement(raft, 'server')
                for key, value in {'id': 1, 'hostname': '127.0.0.1', 'port': raft_port}.items():
                    ET.SubElement(node, key).text = str(value)
                tls = ET.SubElement(keeper, 'openSSL')
                tls.append(ET.fromstring(config.read_text()).find('openSSL/server'))
                keeper_config = root / 'keeper.xml'
                ET.ElementTree(keeper).write(keeper_config)
                launch('clickhouse-keeper', keeper_config)
                for index in range(2, 4):
                    targets.append({'hostId': 'localhost', 'memberId': 'ch-' + str(index), 'address': '127.0.0.1', 'port': unused_port()})
                original = config.read_text()
                for target in targets:
                    member = root / 'config' / 'ch-qa' / target['memberId']
                    if member != directory:
                        member.mkdir(mode=0o700)
                        shutil.copytree(pki, member / 'pki')
                    xml = ET.fromstring(original)
                    xml.find('tcp_port_secure').text = str(target['port'])
                    for key, suffix in [('path', 'data/'), ('access_control_path', 'access/')]:
                        xml.find(key).text = str(member / suffix) + '/'
                    xml.find('logger/log').text = str(member / 'server.log')
                    xml.find('logger/errorlog').text = str(member / 'error.log')
                    client_tls = ET.SubElement(xml.find('openSSL'), 'client')
                    for key, value in {'caConfig': pki / 'ca-chain.pem', 'verificationMode': 'strict', 'loadDefaultCAFile': 'false'}.items():
                        ET.SubElement(client_tls, key).text = str(value)
                    replicas = ET.SubElement(ET.SubElement(ET.SubElement(xml, 'remote_servers'), 'default'), 'shard')
                    for replica in targets:
                        node = ET.SubElement(replicas, 'replica')
                        for key, value in {'host': replica['address'], 'port': replica['port'], 'secure': 1}.items():
                            ET.SubElement(node, key).text = str(value)
                    worker = ET.SubElement(xml, 'distributed_ddl')
                    ET.SubElement(worker, 'path').text = '/clickhouse/task_queue/ddl'
                    node = ET.SubElement(ET.SubElement(xml, 'zookeeper'), 'node')
                    for key, value in {'host': '127.0.0.1', 'port': keeper_port, 'secure': 1}.items():
                        ET.SubElement(node, key).text = str(value)
                    member_config = member / 'server.xml'
                    ET.ElementTree(xml).write(member_config)
                    if member_config not in configs:
                        configs.append(member_config)
            for member_config in configs:
                launch('clickhouse-server', member_config)
            target = targets[0]
            process = processes[-1]
            admin = NativeClient(target, str(directory), admin_password, timeout=3)
            try:
                ready = False
                for _ in range(100):
                    try:
                        ready = admin.query('SELECT 1;').strip() == '1'
                    except (ProviderFailure, subprocess.SubprocessError):
                        pass
                    if ready or process.poll() is not None:
                        break
                    time.sleep(0.1)
                if not ready:
                    diagnostic = '\n'.join(path.read_text() for path in [root / 'error.log', root / 'server.log'] if path.exists())
                    codes = diagnostic.splitlines()[-12:]
                    safe = re.sub(r'[0-9a-fA-F]{64}', '[redacted-verifier]', '\n'.join(codes))
                    safe = safe.replace(admin_password, '[redacted]').replace(user_password, '[redacted]')
                    self.fail('Isolated ClickHouse TLS startup failed: ' + safe[:1600])
                database = {'resourceId': 'analytics', 'name': 'analytics', 'mode': 'managed',
                            'marker': 'platform.application/v1:qa:ch-qa:lib:clickhouse.database:analytics'}
                job = {'serviceType': 'clickhouse', 'providerId': 'ch-qa', 'mode': 'raft-ha' if clustered else 'standalone', 'candidates': targets,
                       'adminPasswordRef': 'admin', 'databases': [database,dict(database,name='archive',resourceId='archive',
                           marker='platform.application/v1:qa:ch-qa:lib:clickhouse.database:archive')], 'accounts': []}
                variables = {'platform_clickhouse_application_job': job, 'platform_clickhouse_config_root': str(root / 'config'),
                             'platform_clickhouse_user': getpass.getuser(), 'platform_application_secret_root': str(secret_root),
                             'platform_clickhouse_application_credential_files': {'admin': str(secret_root / 'admin'), 'app': str(secret_root / 'app')}}

                def role(stage, expected=0, publication_marker=None):
                    play = [{
                        'hosts': 'localhost', 'connection': 'local', 'gather_facts': False, 'vars': variables,
                        'tasks': [{
                            'block': [{'ansible.builtin.include_role': {
                                'name': 'platform.clickhouse.application_provider', 'tasks_from': stage}}],
                            'rescue': [{'ansible.builtin.fail': {'msg': "{{ ansible_failed_result.msg | default('') | regex_search('CLICKHOUSE_APPLICATION_[A-Z_0-9]+') | default('PROVIDER_TEST_FAILED', true) }}"}}]}]}]
                    if publication_marker:
                        play[0]['tasks'].append({'ansible.builtin.file': {'path': str(publication_marker), 'state': 'touch', 'mode': '0600'}})
                    path = root / ('play-' + secrets.token_hex(4) + '.yml')
                    path.write_text(yaml.safe_dump(play))
                    result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(path)], capture_output=True, text=True, timeout=90)
                    self.assertEqual(expected, result.returncode, result.stdout + result.stderr)
                    return result.stdout

                self.assertIn('changed=0', role('preflight'))
                role('resources')
                self.assertIn('changed=0', role('resources'))
                self.assertIn('changed=0', role('verify'))
                # Fixture table preparation is outside the application resource hook.
                admin.query('CREATE TABLE analytics.events (id UInt64) ENGINE = Memory;')
                for other in targets[1:]:
                    replica = NativeClient(other, str(directory), admin_password)
                    try:
                        replica.query('CREATE TABLE analytics.events (id UInt64) ENGINE = Memory;')
                    finally:
                        replica.close()
                account = {'name': 'api-lib', 'mode': 'managed', 'passwordRef': 'app',
                           'marker': 'platform.application/v1:qa:ch-qa:lib:account:api-lib/analytics',
                           'grants': [{'database': 'analytics', 'table': 'events', 'privileges': ['SELECT', 'INSERT']}]}
                job['accounts'] = [account]
                role('preflight')
                publication_marker = root / 'vault-publication-barrier'
                if clustered:
                    # A same-name object on one member without this run's witness
                    # must block the fan-out before Vault publication. Removing
                    # that foreign fixture permits a safe retry on all members.
                    foreign = NativeClient(targets[-1], str(directory), admin_password)
                    try:
                        foreign.query("CREATE USER `api-lib` IDENTIFIED WITH sha256_hash BY '%s';" % hashlib.sha256(user_password.encode()).hexdigest())
                    finally:
                        foreign.close()
                    witness_before = (directory / 'application-objects.json').read_bytes()
                    role('accounts', expected=2, publication_marker=publication_marker)
                    self.assertFalse(publication_marker.exists(), 'Vault publication task ran after a member ownership failure')
                    self.assertEqual(witness_before, (directory / 'application-objects.json').read_bytes())
                    foreign = NativeClient(targets[-1], str(directory), admin_password)
                    try:
                        foreign.query('DROP USER `api-lib`;')
                    finally:
                        foreign.close()
                    role('accounts', publication_marker=publication_marker)
                    self.assertTrue(publication_marker.exists())
                    with ThreadPoolExecutor(max_workers=2) as executor:
                        outputs = list(executor.map(lambda _: role('accounts'), range(2)))
                    self.assertTrue(all('changed=0' in output for output in outputs))
                else:
                    role('accounts')
                self.assertIn('changed=0', role('accounts'))
                witness_before = (directory / 'application-objects.json').read_bytes()
                self.assertIn('changed=0', role('verify'))
                self.assertEqual(witness_before, (directory / 'application-objects.json').read_bytes())
                # SEC-D02: one owned account, two owned databases; exact revoke
                # and neighbor isolation on standalone and all cluster members.
                original_grants = account['grants']
                account['grants'] = [{'database': name,'table':'*','privileges':['SELECT','INSERT']}
                                     for name in ('analytics','archive')]
                role('accounts')
                cluster = ' ON CLUSTER default' if clustered else ''
                admin.query('CREATE USER neighbor%s IDENTIFIED WITH sha256_hash BY \'%s\'; GRANT%s SELECT ON archive.* TO neighbor;' %
                            (cluster,hashlib.sha256(user_password.encode()).hexdigest(),cluster))
                neighbor_before = admin.query("SHOW GRANTS FOR neighbor;")
                for member in targets:
                    client = NativeClient(member,str(directory),admin_password)
                    try:
                        client.query('CREATE TABLE analytics.future(id UInt64) ENGINE=Memory; CREATE TABLE archive.future(id UInt64) ENGINE=Memory;')
                    finally: client.close()
                account['grants'][0]['privileges'] = ['SELECT']
                role('verify',expected=2)
                role('accounts'); role('verify')
                for member in targets:
                    client = NativeClient(member,str(directory),user_password,'api-lib')
                    try:
                        self.assertEqual('0',client.query('SELECT count() FROM analytics.future;').strip())
                        with self.assertRaises(ProviderFailure): client.query('INSERT INTO analytics.future VALUES (1);')
                        client.query('INSERT INTO archive.future VALUES (1);')
                    finally: client.close()
                account['grants'] = [account['grants'][0]]
                role('accounts'); role('verify')
                for member in targets:
                    client = NativeClient(member,str(directory),user_password,'api-lib')
                    try:
                        with self.assertRaises(ProviderFailure): client.query('SELECT count() FROM archive.future;')
                    finally: client.close()
                account['grants'] = []
                role('accounts'); role('verify')
                self.assertIn('changed=0',role('accounts'))
                self.assertEqual(neighbor_before,admin.query('SHOW GRANTS FOR neighbor;'))
                self.assertEqual(witness_before,(directory/'application-objects.json').read_bytes())
                admin.query('GRANT%s SELECT ON system.one TO `api-lib`;' % cluster)
                foreign_before = admin.query('SHOW GRANTS FOR `api-lib`;')
                role('preflight',expected=2)
                self.assertEqual(foreign_before,admin.query('SHOW GRANTS FOR `api-lib`;'))
                admin.query('REVOKE%s SELECT ON system.one FROM `api-lib`;' % cluster)
                account['grants'] = original_grants
                role('accounts'); role('verify')
                if not clustered:
                    witness = json.loads(witness_before)
                    witness['user/api-lib'] = 'corrupted-record'
                    (directory / 'application-objects.json').write_text(json.dumps(witness))
                    try:
                        role('verify', expected=2)
                    finally:
                        (directory / 'application-objects.json').write_bytes(witness_before)
                for member_config in configs:
                    logs = '\n'.join(path.read_text() for path in [member_config.parent / 'server.log', member_config.parent / 'error.log', root / 'server.log', root / 'error.log'] if path.exists())
                    self.assertTrue(user_password not in logs and hashlib.sha256(user_password.encode()).hexdigest() not in logs,
                                    'Application credential appeared in native server logs')
                if clustered:
                    queue = admin.query('SELECT query FROM system.distributed_ddl_queue FORMAT JSONEachRow;')
                    self.assertTrue(user_password not in queue, 'Plaintext credential appeared in native DDL queue')
                user = NativeClient(target, str(directory), user_password, 'api-lib')
                try:
                    self.assertEqual('0', user.query('SELECT count() FROM analytics.events;').strip())
                    with self.assertRaises(ProviderFailure):
                        user.query('CREATE DATABASE forbidden;')
                finally:
                    user.close()
                admin.query("CREATE USER foreign IDENTIFIED WITH sha256_hash BY '%s';" % hashlib.sha256(user_password.encode()).hexdigest())
                account['name'] = 'foreign'
                role('preflight', expected=2)
                self.assertNotIn('user/foreign', json.loads((directory / 'application-objects.json').read_text()))
            finally:
                admin.close()
                for process in reversed(processes):
                    process.terminate()
                for process in reversed(processes):
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()

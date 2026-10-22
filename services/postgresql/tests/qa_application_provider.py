"""Explicit owner-authorized isolated RED OS PostgreSQL hook QA. No deployed DBs."""
import copy
import hashlib
import json
import os
from pathlib import Path
import pwd
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import threading
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils'))
from application_providers import split_provider_jobs
ROLE = ROOT / 'services/postgresql/ansible_collections/platform/postgresql/roles/application_provider'


class ApplicationProviderQA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='platform-a3-')
        cls.runtime = Path(cls.temporary.name)
        cls.runtime.chmod(0o755)
        cls.pg = pwd.getpwnam('postgres')
        cls.data = cls.runtime / 'postgres'
        cls.data.mkdir(mode=0o700)
        subprocess.run(['sudo','-n','chown',str(cls.pg.pw_uid)+':'+str(cls.pg.pw_gid),str(cls.data)],check=True)
        cls.secret_root = cls.runtime / '.runtime/secrets'
        cls.secret_root.mkdir(parents=True, mode=0o700)
        cls.secret_root.parent.chmod(0o700)
        cls.passwords = {}
        for ref in ('gateway-password', 'manager-password'):
            file = cls.secret_root / ref
            # Quote/backslash characters exercise real SQL/password handling.
            file.write_text(secrets.token_hex(20) + "'\\")
            file.chmod(0o600)
            cls.passwords[ref] = str(file)
        cls.port = 28432
        cls.initdb = shutil.which('initdb') or '/usr/pgsql-16/bin/initdb'
        cls.pgctl = shutil.which('pg_ctl') or '/usr/pgsql-16/bin/pg_ctl'
        cls.pgcmd = ['sudo', '-n', '-u', 'postgres']
        try:
            subprocess.run(cls.pgcmd + [cls.initdb, '-D', str(cls.data), '--no-locale', '--encoding=UTF8', '--auth-local=trust', '--auth-host=scram-sha-256'], capture_output=True, check=True)
            subprocess.run(cls.pgcmd + ['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', str(cls.data/'private-key.pem'), '-out', str(cls.data/'ca-chain.pem'), '-days', '1', '-subj', '/CN=127.0.0.1', '-addext', 'subjectAltName=IP:127.0.0.1'], capture_output=True, check=True)
            subprocess.run(cls.pgcmd + ['chmod', '600', str(cls.data/'private-key.pem')], check=True)
            config="\nport=28432\nlisten_addresses='127.0.0.1'\nunix_socket_directories='%s'\nssl=on\nssl_cert_file='ca-chain.pem'\nssl_key_file='private-key.pem'\nlog_statement='none'\n" % cls.data
            subprocess.run(cls.pgcmd + ['tee','-a',str(cls.data/'postgresql.conf')], input=config.encode(), stdout=subprocess.DEVNULL, check=True)
            subprocess.run(cls.pgcmd + ['tee',str(cls.data/'pg_hba.conf')], input=b'local all all trust\nhostssl all all 127.0.0.1/32 scram-sha-256\n', stdout=subprocess.DEVNULL, check=True)
            subprocess.run(cls.pgcmd + [cls.pgctl, '-D', str(cls.data), '-l', str(cls.data/'server.log'), '-w', 'start'], capture_output=True, check=True)
        except Exception:
            cls.remove_data()
            cls.temporary.cleanup()
            raise RuntimeError('A3_ISOLATED_POSTGRES_PREREQUISITE') from None
        cls.job = cls.make_job('a3qa', 2)
        cls.inventory = cls.runtime / 'hosts.yml'
        cls.inventory.write_text(json.dumps({'all': {'hosts': {'localhost': {'ansible_connection': 'local'}, 'node1': {'ansible_connection': 'local', 'platform_postgresql_user': 'postgres'}, 'node2': {'ansible_connection': 'local', 'platform_postgresql_user': 'postgres'}}}}))
        cls.env = dict(os.environ, ANSIBLE_COLLECTIONS_PATH=':'.join([str(ROOT/'ansible-core/collections'), str(ROOT/'services/postgresql')]),
                       ANSIBLE_NOCOLOR='1', ANSIBLE_LOCAL_TEMP=str(cls.runtime/'ansible-tmp'))

    @classmethod
    def tearDownClass(cls):
        result = subprocess.run(cls.pgcmd + [cls.pgctl, '-D', str(cls.data), '-m', 'immediate', '-w', 'stop'], capture_output=True)
        if result.returncode:
            raise RuntimeError('A3_ISOLATED_CLUSTER_CLEANUP_FAILED')
        cls.remove_data()
        cls.temporary.cleanup()

    @classmethod
    def remove_data(cls):
        if cls.data.parent != cls.runtime or not cls.runtime.name.startswith('platform-a3-') or cls.data.is_symlink():
            raise RuntimeError('A3_CLEANUP_PATH_INVALID')
        subprocess.run(['sudo','-n','rm','-rf','--',str(cls.data)],check=True)

    @classmethod
    def make_job(cls, project, account_count):
        owner = 'pla_' + hashlib.sha256((project+':pg:lib').encode()).hexdigest()[:24]
        prefix = 'platform.application/v1:' + project + ':pg:lib:'
        accounts = [{'name': project+'_user_'+str(i), 'mode': 'managed', 'passwordRef': 'gateway-password' if i%2 == 0 else 'manager-password',
                     'marker': prefix+'account:app-'+str(i)+'/postgres', 'instanceId': 'app-'+str(i), 'accountId': 'postgres',
                     'database': project+'_db', 'libraryId': 'lib',
                     'grants': [{'kind': 'schema', 'schema': 'api', 'name': 'api', 'privileges': ['USAGE']}]} for i in range(account_count)]
        database = {'name': project+'_db', 'mode': 'managed', 'resourceId': 'db', 'libraryId': 'lib', 'providerId': 'pg',
                    'owner': owner, 'ownerMarker': prefix+'owner:lib', 'marker': prefix+'postgresql.database:db',
                    'schemas': [{'name': 'api', 'mode': 'managed', 'resourceId': 'api', 'marker': prefix+'postgresql.schema:api'}], 'accounts': accounts}
        target = {'hostId': 'node1', 'memberId': 'data1', 'address': '127.0.0.1', 'port': cls.port,
                  'pkiPlans': [{'targetDirectory': str(cls.data)}]}
        return {'projectId': project, 'serviceType': 'postgresql', 'providerId': 'pg', 'mode': 'standalone', 'libraries': [{'name': owner, 'marker': database['ownerMarker']}],
                'databases': [database], 'accounts': accounts, 'candidates': [target]}

    @classmethod
    def sql(cls, query, database='postgres', success=True):
        result = subprocess.run(cls.pgcmd + ['psql', '-X', '-h', str(cls.data), '-p', str(cls.port), '-d', database, '-Atqc', query], capture_output=True)
        if (result.returncode == 0) != success:
            raise AssertionError('A3_FIXTURE_SQL_UNEXPECTED_RESULT')
        return result.stdout.decode().strip()

    def play(self, job=None, phases=('preflight', 'resources', 'accounts'), success=True):
        job = job or self.job
        variables = {'platform_postgresql_application_job': job, 'platform_postgresql_secret_files': self.passwords,
                     'platform_postgresql_application_secret_root': str(self.secret_root),
                     'platform_postgresql_application_socket': str(self.data)}
        libraries, instances = split_provider_jobs([job])
        variables.update(library_jobs=libraries,instance_jobs=instances)
        tasks = []
        for phase in phases:
            if phase == 'preflight':
                tasks.append({'ansible.builtin.include_role':{'name':'platform.postgresql.application_provider','tasks_from':'discover'}})
                scopes=('library_jobs','instance_jobs')
            elif phase == 'resources': scopes=('library_jobs',)
            elif phase == 'accounts': scopes=('instance_jobs',)
            else: scopes=('library_jobs','instance_jobs')
            for scope in scopes:
                tasks.append({'ansible.builtin.include_role':{'name':'platform.postgresql.application_provider','tasks_from':phase},
                              'loop':'{{ '+scope+' }}','loop_control':{'loop_var':'platform_postgresql_application_job'}})
        play = [{'hosts': 'localhost', 'connection': 'local', 'gather_facts': False, 'vars': variables, 'tasks': tasks}]
        path = self.runtime/'play.yml'
        path.write_text(yaml.safe_dump(play))
        started = time.monotonic()
        result = subprocess.run(['ansible-playbook', '-i', str(self.inventory), str(path)], env=self.env, capture_output=True, timeout=600)
        # Logs are protected, safe externally reported output is metadata only.
        log = self.runtime/'last-play.log'
        log.write_bytes(result.stdout+result.stderr)
        log.chmod(0o600)
        if (result.returncode == 0) != success:
            preserved=Path('/tmp/a3-native-last-protected.log')
            preserved.write_bytes(result.stdout+result.stderr)
            preserved.chmod(0o600)
        self.assertEqual(success, result.returncode == 0, 'A3_PLAY_RESULT protected log: '+str(log))
        for path in self.passwords.values():
            self.assertNotIn(Path(path).read_bytes(), result.stdout+result.stderr)
        elapsed = time.monotonic()-started
        print('A3_TIMING phases=%s accounts=%d seconds=%.3f' % ('+'.join(phases), len(job['accounts']), elapsed), flush=True)
        return result.stdout.decode(), elapsed

    def test_database_access_existing_future_revoke_and_repeat(self):
        job = self.make_job('bulkqa', 1)
        first = job['databases'][0]
        for index in range(1, 4):
            db = copy.deepcopy(first)
            db.update(name='bulkqa_db_'+str(index), resourceId='db'+str(index),
                      marker=first['marker']+str(index), accounts=[])
            job['databases'].append(db)
        self.play(job)
        account = job['accounts'][0]
        for db in job['databases']:
            self.sql('SET ROLE "%s"; CREATE TABLE api.before_apply(id serial, value text)' % db['owner'], db['name'])
        migration = 'bulkqa_migrator'
        self.sql("CREATE ROLE %s NOLOGIN; COMMENT ON ROLE %s IS '%s'" %
                 (migration, migration, account['marker'].rsplit('account:',1)[0]+'account:migration/postgres'))
        self.sql('GRANT CREATE ON DATABASE bulkqa_db TO '+migration)
        account['grants'] = []
        account['databaseAccess'] = [dict(database=db['name'], privileges=['SELECT','INSERT'],
                                         creatorRoles=[db['owner']] + ([migration] if i == 0 else []))
                                     for i, db in enumerate(job['databases'])]
        self.play(job, phases=('preflight','accounts','verify'))
        before = self.sql("SELECT oid FROM pg_roles WHERE rolname='bulkqa_user_0'")
        output, _ = self.play(job, phases=('preflight','accounts','verify'))
        self.assertRegex(output, r'localhost\s+:\s+ok=\d+\s+changed=0')
        self.assertEqual(before,self.sql("SELECT oid FROM pg_roles WHERE rolname='bulkqa_user_0'"))
        for db in job['databases']:
            self.sql('SET ROLE "%s"; CREATE SCHEMA later; CREATE TABLE later.new_table(id serial, value text)' % db['owner'], db['name'])
            self.sql("SET ROLE bulkqa_user_0; INSERT INTO later.new_table(value) VALUES ('ok'); SELECT * FROM later.new_table",db['name'])
            self.sql('SET ROLE bulkqa_user_0; DELETE FROM later.new_table',db['name'],success=False)
        self.sql('SET ROLE '+migration+'; CREATE SCHEMA migration; CREATE TABLE migration.new_table(id serial)', first['name'])
        self.sql('SET ROLE bulkqa_user_0; INSERT INTO migration.new_table DEFAULT VALUES',first['name'])
        account['databaseAccess'] = []
        self.play(job, phases=('preflight','accounts','verify'))
        for db in job['databases']:
            self.sql('SET ROLE bulkqa_user_0; SELECT * FROM later.new_table',db['name'],success=False)
            self.assertEqual('0',self.sql("SELECT count(*) FROM pg_default_acl d, LATERAL aclexplode(d.defaclacl) x WHERE x.grantee=(SELECT oid FROM pg_roles WHERE rolname='bulkqa_user_0')",db['name']))
        output, _ = self.play(job, phases=('preflight','accounts','verify'))
        self.assertRegex(output, r'localhost\s+:\s+ok=\d+\s+changed=0')

    def test_database_access_create_existing_future_revoke_and_repeat(self):
        job = self.make_job('createqa', 1)
        self.play(job)
        account, db = job['accounts'][0], job['databases'][0]
        user, owner = account['name'], db['owner']
        self.sql('SET ROLE "%s"; CREATE TABLE api.reference(id int)' % owner, db['name'])
        migration = 'createqa_migrator'
        self.sql("CREATE ROLE %s NOLOGIN; COMMENT ON ROLE %s IS '%s'" %
                 (migration, migration, account['marker'].rsplit('account:',1)[0]+'account:migration/postgres'))
        self.sql('GRANT CREATE ON DATABASE %s TO %s' % (db['name'], migration))
        account['grants'] = []
        access = dict(database=db['name'], privileges=['CREATE'], creatorRoles=[owner, migration])
        account['databaseAccess'] = [access]
        self.play(job, phases=('verify',), success=False)
        self.play(job, phases=('preflight','accounts','verify'))
        self.sql('SET ROLE "%s"; CREATE TABLE api.created(id int)' % user, db['name'])
        self.sql('SET ROLE "%s"; SELECT * FROM api.reference' % user, db['name'], success=False)
        self.sql('SET ROLE "%s"; CREATE SCHEMA forbidden' % user, db['name'], success=False)
        self.sql('SET ROLE "%s"; CREATE SCHEMA future; CREATE TABLE future.reference(id int)' % owner, db['name'])
        self.sql('SET ROLE "%s"; CREATE TABLE future.created(id int)' % user, db['name'])
        self.sql('SET ROLE %s; CREATE SCHEMA migration_before' % migration, db['name'])
        self.sql('SET ROLE "%s"; CREATE TABLE migration_before.created(id int)' % user, db['name'])
        access['creatorRoles'] = [owner]
        access['privileges'] = ['CREATE','SELECT']
        self.play(job, phases=('preflight','accounts','verify'))
        self.sql('SET ROLE %s; CREATE SCHEMA migration_after' % migration, db['name'])
        self.sql('SET ROLE "%s"; CREATE TABLE migration_after.forbidden(id int)' % user, db['name'], success=False)
        self.sql('SET ROLE "%s"; SELECT * FROM future.reference' % user, db['name'])
        access['privileges'] = ['SELECT']
        self.play(job, phases=('verify',), success=False)
        self.play(job, phases=('preflight','accounts','verify'))
        self.sql('SET ROLE "%s"; CREATE TABLE api.forbidden(id int)' % user, db['name'], success=False)
        self.sql('SET ROLE "%s"; CREATE TABLE future.forbidden(id int)' % user, db['name'], success=False)
        self.sql('SET ROLE "%s"; CREATE SCHEMA after_revoke; CREATE TABLE after_revoke.reference(id int)' % owner, db['name'])
        self.sql('SET ROLE "%s"; SELECT * FROM after_revoke.reference' % user, db['name'])
        self.sql('SET ROLE "%s"; CREATE TABLE after_revoke.forbidden(id int)' % user, db['name'], success=False)
        self.sql('SET ROLE "%s"; INSERT INTO api.created VALUES (1)' % user, db['name'])
        output, _ = self.play(job, phases=('preflight','accounts','verify'))
        self.assertRegex(output, r'localhost\s+:\s+ok=\d+\s+changed=0')

    def test_database_access_public_schema_and_public_role_conflict(self):
        job = self.make_job('createpublicqa', 2)
        self.play(job)
        account, db = job['accounts'][0], job['databases'][0]
        account['grants'] = []
        account['databaseAccess'] = [dict(database=db['name'], privileges=['CREATE','SELECT'], creatorRoles=[db['owner']])]
        self.play(job, phases=('preflight','accounts','verify'))
        self.sql('SET ROLE "%s"; CREATE TABLE public.created(id int)' % account['name'], db['name'])
        self.assertEqual('f', self.sql("SELECT has_schema_privilege('%s','public','CREATE')" % job['accounts'][1]['name'], db['name']))
        self.sql('ALTER DEFAULT PRIVILEGES FOR ROLE "%s" GRANT CREATE ON SCHEMAS TO PUBLIC' % db['owner'], db['name'])
        query = "SELECT json_agg(a) FROM (SELECT defaclrole,defaclnamespace,defaclobjtype,defaclacl::text FROM pg_default_acl ORDER BY oid) a"
        before = self.sql(query, db['name'])
        for phase in ('preflight','accounts','verify'):
            self.play(job, phases=(phase,), success=False)
            self.assertEqual(before, self.sql(query, db['name']))
        self.sql('ALTER DEFAULT PRIVILEGES FOR ROLE "%s" REVOKE CREATE ON SCHEMAS FROM PUBLIC' % db['owner'], db['name'])
        self.play(job, phases=('preflight','accounts','verify'))

    def test_database_access_conflicts_and_missing_defaults(self):
        job = self.make_job('bulknegative', 1)
        self.play(job)
        account, db = job['accounts'][0], job['databases'][0]
        self.sql('SET ROLE "%s"; CREATE TABLE api.items(id serial)' % db['owner'],db['name'])
        access = dict(database=db['name'], privileges=['SELECT','INSERT'],creatorRoles=[db['owner']])
        account['databaseAccess'] = [access]; account['grants'] = []
        access['creatorRoles'].append('unregistered_creator')
        self.play(job, phases=('preflight',), success=False)
        access['creatorRoles'].pop()
        self.sql('GRANT DELETE ON api.items TO PUBLIC',db['name'])
        self.play(job, phases=('preflight',), success=False)
        self.sql('REVOKE DELETE ON api.items FROM PUBLIC',db['name'])
        self.sql('CREATE TABLE api.foreign_owned(id int)',db['name'])
        self.play(job, phases=('preflight',), success=False)
        self.sql('DROP TABLE api.foreign_owned',db['name'])
        self.sql('ALTER DEFAULT PRIVILEGES FOR ROLE "%s" GRANT DELETE ON TABLES TO PUBLIC' % db['owner'],db['name'])
        self.play(job, phases=('preflight',), success=False)
        self.sql('ALTER DEFAULT PRIVILEGES FOR ROLE "%s" REVOKE DELETE ON TABLES FROM PUBLIC' % db['owner'],db['name'])
        self.play(job, phases=('preflight','accounts','verify'))
        self.sql('ALTER DEFAULT PRIVILEGES FOR ROLE "%s" REVOKE SELECT ON TABLES FROM "%s"' % (db['owner'],account['name']),db['name'])
        self.play(job, phases=('verify',), success=False)
        access['privileges'] = ['SELECT']
        self.play(job, phases=('preflight','accounts','verify'))
        self.assertEqual('f',self.sql("SELECT has_sequence_privilege('bulknegative_user_0','api.items_id_seq','USAGE')",db['name']))
        self.sql('GRANT SELECT(id) ON api.items TO bulknegative_user_0',db['name'])
        self.play(job, phases=('preflight',), success=False)

    def test_database_access_owner_authority_is_preserved(self):
        job = self.make_job('bulkowner', 1)
        self.play(job)
        account, db = job['accounts'][0], job['databases'][0]
        self.sql('CREATE SCHEMA app_owned AUTHORIZATION bulkowner_user_0; SET ROLE bulkowner_user_0; '
                 'CREATE TABLE app_owned.items(id serial, value text)',db['name'])
        query = "SELECT relname,relowner,coalesce(relacl::text,'') FROM pg_class WHERE relnamespace='app_owned'::regnamespace ORDER BY relname"
        before = self.sql(query,db['name'])
        account['databaseAccess'] = [dict(database=db['name'],privileges=['SELECT'],creatorRoles=[db['owner'],account['name']])]
        account['grants'] = []
        output,_ = self.play(job, phases=('preflight','accounts','verify'))
        self.assertEqual(before,self.sql(query,db['name']))
        self.sql('SET ROLE bulkowner_user_0; CREATE TABLE app_owned.future(id serial)',db['name'])
        account['databaseAccess'] = []
        self.play(job, phases=('preflight','accounts','verify'))
        self.sql("SET ROLE bulkowner_user_0; INSERT INTO app_owned.items(value) VALUES ('owned'); ALTER TABLE app_owned.items ADD COLUMN later int",db['name'])
        output,_ = self.play(job, phases=('preflight','accounts','verify'))
        self.assertRegex(output,r'localhost\s+:\s+ok=\d+\s+changed=0')
        self.assertEqual('1',self.sql('SELECT count(*) FROM app_owned.items',db['name']))

    def test_01_resources_accounts_verify_repeat(self):
        self.play()
        self.play(phases=('preflight', 'verify'))
        before = self.sql("SELECT oid FROM pg_roles WHERE rolname LIKE 'a3qa_user_%' ORDER BY rolname")
        hashes = self.sql("SELECT rolpassword FROM pg_authid WHERE rolname LIKE 'a3qa_user_%' ORDER BY rolname")
        result, _ = self.play()
        self.assertRegex(result, r'localhost\s+:\s+ok=\d+\s+changed=0')
        self.assertEqual(before, self.sql("SELECT oid FROM pg_roles WHERE rolname LIKE 'a3qa_user_%' ORDER BY rolname"))
        self.assertEqual(hashes, self.sql("SELECT rolpassword FROM pg_authid WHERE rolname LIKE 'a3qa_user_%' ORDER BY rolname"))

    def test_02_application_password_reconciliation_and_foreign_owner_fail_closed(self):
        job = self.make_job('a3negative', 1)
        self.play(job)
        ref = job['accounts'][0]['passwordRef']
        path = Path(self.passwords[ref]); original = path.read_text()
        try:
            for locale in ('C', 'ru_RU.utf8'):
                self.sql("ALTER SYSTEM SET lc_messages = '"+locale+"'")
                self.sql('SELECT pg_reload_conf()')
                path.write_text(secrets.token_hex(20))
                self.play(job)
                repeat, _ = self.play(job)
                self.assertRegex(repeat, r'localhost\s+:\s+ok=\d+\s+changed=0')
        finally:
            self.sql("ALTER SYSTEM SET lc_messages = 'C'")
            self.sql('SELECT pg_reload_conf()')
            path.write_text(original)
            self.play(job)
        other = self.make_job('a3foreign', 0)
        self.sql('CREATE DATABASE a3foreign_db')
        self.play(other, success=False)
        self.assertEqual('0', self.sql("SELECT count(*) FROM pg_roles WHERE rolname='"+other['libraries'][0]['name']+"'"))

    def test_password_probe_sqlstate_and_non_auth_failures(self):
        job = self.make_job('a3state', 1)
        self.play(job)
        wrong = self.secret_root/'probe-wrong'
        wrong.write_text(secrets.token_urlsafe(32)); wrong.chmod(0o600)
        correct = self.passwords[job['accounts'][0]['passwordRef']]
        tasks = []
        for name, password, ca, host, port, authenticated, state in [
            ('correct', correct, self.data/'ca-chain.pem', '127.0.0.1', self.port, True, ''),
            ('wrong', wrong, self.data/'ca-chain.pem', '127.0.0.1', self.port, False, '28P01'),
            ('missing_ca', wrong, self.data/'absent.pem', '127.0.0.1', self.port, False, ''),
            ('tls_identity', wrong, self.data/'ca-chain.pem', 'localhost', self.port, False, ''),
            ('closed_port', wrong, self.data/'ca-chain.pem', '127.0.0.1', self.port+1, False, ''),
        ]:
            tasks += [dict(name='Probe '+name, **{'platform.postgresql.application_password_probe': dict(
                host=host, port=port, username=job['accounts'][0]['name'],
                password="{{ lookup('ansible.builtin.file', '"+str(password)+"', rstrip=False) }}",
                ca_file=str(ca), timeout=2), 'register':'probe', 'no_log':True, 'become':True}),
                {'name':'Safe probe status', 'ansible.builtin.debug':{'msg':
                    "{{ {'authenticated':probe.authenticated,'sqlstate':probe.sqlstate,'changed':probe.changed} }}"}},
                {'name':'Check '+name, 'ansible.builtin.assert':{'that':[
                    'probe.authenticated == '+str(authenticated).lower(),
                    "probe.sqlstate == '"+state+"'", 'not probe.changed']}}]
        play = self.runtime/'probe.yml'
        play.write_text(yaml.safe_dump([dict(hosts='localhost', gather_facts=False, tasks=tasks)]))
        self.sql("ALTER SYSTEM SET lc_messages = 'ru_RU.utf8'")
        self.sql('SELECT pg_reload_conf()')
        try:
            result = subprocess.run(['ansible-playbook','-i',str(self.inventory),str(play)],
                                    env=self.env,capture_output=True,timeout=60)
            if result.returncode:
                import re
                names = re.findall(r'TASK \[(.*?)\]', result.stdout.decode(errors='replace'))
                safe = re.findall(r'"(?:authenticated|sqlstate|changed)":\s*(?:true|false|"[A-Z0-9]*")', result.stdout.decode(errors='replace'))
                self.fail('A3_SQLSTATE_PROBE_FAILED tasks='+repr(names[-3:])+' statuses='+repr(safe))
            self.assertNotIn(wrong.read_bytes(),result.stdout+result.stderr)
            self.assertNotIn(Path(correct).read_bytes(),result.stdout+result.stderr)
        finally:
            self.sql("ALTER SYSTEM SET lc_messages = 'C'")
            self.sql('SELECT pg_reload_conf()')

    def test_03_existing_readonly_and_required_grants(self):
        job = self.make_job('a3existing', 1)
        self.play(job)
        existing = copy.deepcopy(job)
        existing['libraries'] = []
        existing['databases'][0]['mode'] = 'existing'
        existing['databases'][0]['schemas'][0]['mode'] = 'existing'
        existing['accounts'][0]['mode'] = 'existing'
        existing['databases'][0]['accounts'][0]['mode'] = 'existing'
        result, _ = self.play(existing)
        self.assertRegex(result, r'localhost\s+:\s+ok=\d+\s+changed=0')
        self.sql('GRANT CREATE ON SCHEMA api TO '+job['accounts'][0]['name'], job['databases'][0]['name'])
        self.play(job, phases=('preflight','verify'))
        self.play(job)
        self.play(job, phases=('preflight','verify'))

    def test_04_table_sequence_additive_grants(self):
        job = self.make_job('a3tables', 1)
        self.play(job)
        db = job['databases'][0]
        self.sql('SET ROLE '+db['owner']+'; CREATE TABLE api.events(id serial, value text)', db['name'])
        account=job['accounts'][0]
        account['grants'] += [{'kind':'table','schema':'api','name':'events','privileges':['INSERT','SELECT']},
                              {'kind':'sequence','schema':'api','name':'events_id_seq','privileges':['USAGE']}]
        self.play(job)
        self.sql('SET ROLE '+account['name']+"; INSERT INTO api.events(value) VALUES('ok'); SELECT * FROM api.events", db['name'])
        self.sql('SET ROLE '+account['name']+'; DELETE FROM api.events', db['name'], success=False)
        self.sql('GRANT DELETE ON api.events TO PUBLIC', db['name'])
        self.play(job)
        self.sql('REVOKE DELETE ON api.events FROM PUBLIC', db['name'])
        account['grants']=[{'kind':'schema','schema':'api','name':'api','privileges':['USAGE']}]
        self.play(job)
        self.sql('SET ROLE '+account['name']+'; SELECT * FROM api.events', db['name'])
        self.sql('REVOKE USAGE ON SCHEMA api FROM '+account['name'], db['name'])
        self.play(job, phases=('preflight','verify'), success=False)
        self.play(job)
        self.play(job, phases=('preflight','verify'))

    def test_05_existing_login_declared_database(self):
        job = self.make_job('a3limited', 1)
        self.play(job)
        existing = copy.deepcopy(job)
        existing['libraries'] = []
        existing['databases'][0]['mode'] = 'existing'
        existing['databases'][0]['schemas'][0]['mode'] = 'existing'
        existing['accounts'][0]['mode'] = 'existing'
        existing['databases'][0]['accounts'][0]['mode'] = 'existing'
        self.sql('REVOKE CONNECT ON DATABASE postgres FROM PUBLIC')
        try:
            self.play(existing, phases=('preflight','verify'))
        finally:
            self.sql('GRANT CONNECT ON DATABASE postgres TO PUBLIC')
        # Maintenance trust must not turn a wrong password into Verify success.
        hba = self.data/'pg_hba.conf'
        original = subprocess.run(self.pgcmd+['cat',str(hba)],capture_output=True,check=True).stdout
        password = Path(self.passwords[job['accounts'][0]['passwordRef']])
        original_password = password.read_text()
        try:
            rules = b'local all all trust\nhostssl all all 127.0.0.1/32 scram-sha-256\n'
            rules = b'hostssl postgres all 127.0.0.1/32 trust\n'+rules
            subprocess.run(self.pgcmd+['tee',str(hba)],input=rules,stdout=subprocess.DEVNULL,check=True)
            subprocess.run(self.pgcmd+[self.pgctl,'-D',str(self.data),'reload'],capture_output=True,check=True)
            password.write_text(secrets.token_hex(20))
            self.play(job, phases=('preflight','verify'), success=False)
        finally:
            password.write_text(original_password)
            subprocess.run(self.pgcmd+['tee',str(hba)],input=original,stdout=subprocess.DEVNULL,check=True)
            subprocess.run(self.pgcmd+[self.pgctl,'-D',str(self.data),'reload'],capture_output=True,check=True)

    def test_06_native_primary_standby_selection(self):
        standby = self.runtime/'standby'
        standby.mkdir(mode=0o700)
        subprocess.run(['sudo','-n','chown',str(self.pg.pw_uid)+':'+str(self.pg.pw_gid),str(standby)],check=True)
        backup = shutil.which('pg_basebackup') or '/usr/pgsql-16/bin/pg_basebackup'
        hba = self.data/'pg_hba.conf'
        original = subprocess.run(self.pgcmd+['cat',str(hba)],capture_output=True,check=True).stdout
        started = False
        try:
            subprocess.run(self.pgcmd+['tee','-a',str(hba)],input=b'local replication all trust\n',stdout=subprocess.DEVNULL,check=True)
            subprocess.run(self.pgcmd+[self.pgctl,'-D',str(self.data),'reload'],capture_output=True,check=True)
            subprocess.run(self.pgcmd+[backup,'-c','fast','-h',str(self.data),'-p',str(self.port),'-D',str(standby),'-R','-X','stream'],capture_output=True,check=True)
            subprocess.run(self.pgcmd+['tee','-a',str(standby/'postgresql.conf')],input=b'\nport=28433\n',stdout=subprocess.DEVNULL,check=True)
            subprocess.run(self.pgcmd+[self.pgctl,'-D',str(standby),'-l',str(standby/'server.log'),'-w','start'],capture_output=True,check=True)
            started = True
            job = self.make_job('a3ha',1)
            job['mode'] = 'pg_auto_failover'
            second = copy.deepcopy(job['candidates'][0])
            second.update(hostId='node2',memberId='data2',port=28433)
            job['candidates'].append(second)
            self.play(job)
            self.play(job, phases=('preflight','verify'))
            def blocked(project, candidates):
                negative = self.make_job(project,1)
                negative.update(mode='pg_auto_failover',candidates=copy.deepcopy(candidates))
                self.play(negative, success=False)
                self.assertEqual('0',self.sql("SELECT count(*) FROM pg_roles WHERE rolname='"+negative['accounts'][0]['name']+"'"))
                self.assertEqual('0',self.sql("SELECT count(*) FROM pg_database WHERE datname='"+negative['databases'][0]['name']+"'"))
            self.sql("ALTER SYSTEM SET default_transaction_read_only='on'")
            self.sql('SELECT pg_reload_conf()')
            try:
                blocked('a3hazero',job['candidates'])
            finally:
                self.sql('ALTER SYSTEM RESET default_transaction_read_only')
                self.sql('SELECT pg_reload_conf()')
            missing = copy.deepcopy(job)
            missing['candidates'][1]['port'] = 28434
            blocked('a3hamissing',missing['candidates'])
            subprocess.run(self.pgcmd+[self.pgctl,'-D',str(standby),'-w','promote'],capture_output=True,check=True)
            blocked('a3hatwo',job['candidates'])
        finally:
            if started:
                subprocess.run(self.pgcmd+[self.pgctl,'-D',str(standby),'-m','immediate','-w','stop'],capture_output=True,check=True)
            subprocess.run(self.pgcmd+['tee',str(hba)],input=original,stdout=subprocess.DEVNULL,check=True)
            subprocess.run(self.pgcmd+[self.pgctl,'-D',str(self.data),'reload'],capture_output=True,check=True)
            if standby.parent != self.runtime or standby.is_symlink():
                raise RuntimeError('A3_CLEANUP_PATH_INVALID')
            subprocess.run(['sudo','-n','rm','-rf','--',str(standby)],check=True)

    def test_07_full_core_entrypoints(self):
        project = self.runtime/('a3entry-'+secrets.token_hex(6))
        shutil.copytree(ROOT/'examples/valid/application-providers',project)
        group_file = project/'inventory/group_vars/all/platform-installer.yml'
        group = json.loads(group_file.read_text())
        group['platform_desired_state']['serviceDeployments']['postgres-sdku']['configuration']['port'] = self.port
        deployment = group['platform_desired_state']['applicationLibraryDeployments']['sdku']
        deployment['resources']['application-database']['parameters']['name'] = 'a3entry_db'
        for slot, name, ref in [('gateway','a3entry_gateway','gateway-password'),('manager','a3entry_manager','manager-password')]:
            deployment['applications'][slot]['overrides']['parameters']['postgres'] = {'user':name,'password_ref':ref}
        group_file.write_text(json.dumps(group))
        inventory = json.loads((project/'inventory/hosts.yml').read_text())
        for index, name in enumerate(('node1','node2'),1):
            inventory['all']['hosts'][name].update(ansible_connection='local',ansible_host='127.0.0.'+str(index),platform_postgresql_user='postgres')
        (project/'inventory/hosts.yml').write_text(json.dumps(inventory))
        protected_vars = self.runtime/'entry-vars.json'
        protected_vars.write_text(json.dumps({'platform_project_root':str(project),
            'platform_service_catalog_path':str(ROOT/'examples/catalog/service-catalog.yml'),
            'platform_postgresql_application_socket':str(self.data),
            'platform_postgresql_application_secret_root':str(self.secret_root),
            'platform_postgresql_secret_files':self.passwords}))
        protected_vars.chmod(0o600)
        playbooks = ROOT/'ansible-core/playbooks'
        # Materialize only this fixture's public CA at the actual Core-projected paths.
        prepare = {'hosts':'localhost','gather_facts':False,'tasks':[
            {'ansible.builtin.file':{'path':'{{ item.pkiPlans[0].targetDirectory }}','state':'directory','mode':'0755'},
             'become':True,'loop':'{{ application_provider_inputs.jobs | map(attribute="candidates") | flatten }}'},
            {'ansible.builtin.copy':{'src':str(self.data/'ca-chain.pem'),'dest':'{{ item.pkiPlans[0].targetDirectory }}/ca-chain.pem','mode':'0644','remote_src':True},
             'become':True,'loop':'{{ application_provider_inputs.jobs | map(attribute="candidates") | flatten }}'}]}
        wrapper = self.runtime/'entry.yml'
        wrapper.write_text(yaml.safe_dump([
            {'import_playbook':str(playbooks/'application-libraries-providers-resolve.yml')},prepare,
            {'import_playbook':str(playbooks/'application-libraries-providers-apply.yml')},
            {'import_playbook':str(playbooks/'application-libraries-providers-verify.yml')}]))
        pki_root = Path('/etc/platform-installer/pki')/project.name
        try:
            result = subprocess.run(['ansible-playbook','-i',str(project/'inventory/hosts.yml'),str(wrapper),'-e','@'+str(protected_vars)],
                env=dict(self.env,ANSIBLE_CONFIG=str(project/'ansible.cfg')),capture_output=True,timeout=600)
            log = self.runtime/'entry.log'
            log.write_bytes(result.stdout+result.stderr); log.chmod(0o600)
            if result.returncode:
                preserved=Path('/tmp/a3-entry-last-protected.log')
                preserved.write_bytes(result.stdout+result.stderr); preserved.chmod(0o600)
            self.assertEqual(0,result.returncode,'A3_ENTRYPOINT_RESULT protected log: '+str(log))
            self.assertEqual('2',self.sql("SELECT count(*) FROM pg_roles WHERE rolname IN ('a3entry_gateway','a3entry_manager')"))
            for file in self.passwords.values():
                self.assertNotIn(Path(file).read_bytes(),result.stdout+result.stderr)
        finally:
            if pki_root.parent != Path('/etc/platform-installer/pki') or not pki_root.name.startswith('a3entry-'):
                raise RuntimeError('A3_CLEANUP_PATH_INVALID')
            subprocess.run(['sudo','-n','rm','-rf','--',str(pki_root)],check=True)

    def test_08_tls_probe_deadline(self):
        stop = threading.Event()
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0)); listener.listen(1)
            port = listener.getsockname()[1]
            def stall():
                connection, _ = listener.accept()
                with connection:
                    connection.recv(8)  # PostgreSQL SSLRequest
                    connection.sendall(b'S')
                    stop.wait(15)
            thread = threading.Thread(target=stall,daemon=True)
            thread.start()
            try:
                result = subprocess.run(self.pgcmd+['timeout','--kill-after=2s','10s','openssl','s_client',
                    '-starttls','postgres','-connect','127.0.0.1:'+str(port),'-CAfile',str(self.data/'ca-chain.pem'),
                    '-verify_return_error','-verify_ip','127.0.0.1'],input=b'',capture_output=True,timeout=15)
                self.assertEqual(124,result.returncode)
            finally:
                stop.set(); thread.join(timeout=3)


if __name__ == '__main__':
    unittest.main(verbosity=2)

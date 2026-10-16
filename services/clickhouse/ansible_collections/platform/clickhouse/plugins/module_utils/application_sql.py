"""Private native-client execution for library and logical instance scopes."""
import contextlib
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
import time
from xml.sax.saxutils import escape


class ProviderFailure(ValueError):
    pass


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z_][a-z0-9_-]{0,62}', value) or value in {'default', 'system', 'information_schema', 'INFORMATION_SCHEMA'}:
        raise ProviderFailure('CLICKHOUSE_APPLICATION_IDENTIFIER_INVALID')
    return '`' + value + '`'


def literal(value):
    return "'" + value.replace('\\', '\\\\').replace("'", "\\'") + "'"


class NativeClient:
    def __init__(self, target, directory, password, username='default', timeout=60):
        descriptor, self.path = tempfile.mkstemp(prefix='.application-client-', suffix='.xml', dir=directory)
        self.timeout = timeout
        try:
            pki = directory + '/pki/'
            content = '<clickhouse><host>%s</host><port>%s</port><secure>true</secure><user>%s</user><password>%s</password><openSSL><client><caConfig>%s</caConfig><certificateFile>%s</certificateFile><privateKeyFile>%s</privateKeyFile><loadDefaultCAFile>false</loadDefaultCAFile><verificationMode>strict</verificationMode><extendedVerification>true</extendedVerification><invalidCertificateHandler><name>RejectCertificateHandler</name></invalidCertificateHandler></client></openSSL></clickhouse>' % (
                escape(target['address']), int(target['port']), escape(username), escape(password),
                escape(pki + 'ca-chain.pem'), escape(pki + 'certificate.pem'), escape(pki + 'private-key.pem'))
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                stream.write(content)
        except Exception:
            os.unlink(self.path)
            raise

    def close(self):
        os.unlink(self.path)

    def query(self, sql):
        result = subprocess.run(['clickhouse-client', '--config-file', self.path, '--multiquery'], input=sql,
                                text=True, capture_output=True, timeout=self.timeout)
        if result.returncode:
            code = re.search(r'\bCode:\s*(\d{1,6})\b', result.stderr)
            raise ProviderFailure('CLICKHOUSE_APPLICATION_QUERY_FAILED' + ('_' + code.group(1) if code else ''))
        if len(result.stdout) > 1048576:
            raise ProviderFailure('CLICKHOUSE_APPLICATION_RESPONSE_INVALID')
        return result.stdout


def private_file(descriptor):
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_nlink != 1 or info.st_size > 1048576:
        raise ProviderFailure('CLICKHOUSE_APPLICATION_PATH_UNSAFE')


@contextlib.contextmanager
def custody(directory, timeout):
    info = os.lstat(directory)
    if os.path.realpath(directory) != os.path.abspath(directory) or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ProviderFailure('CLICKHOUSE_APPLICATION_PATH_UNSAFE')
    descriptor = os.open(directory + '/.application-objects.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        private_file(descriptor)
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ProviderFailure('CLICKHOUSE_APPLICATION_LOCK_TIMEOUT')
                time.sleep(0.05)
        path = directory + '/application-objects.json'
        try:
            witness_descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            witness = {}
        else:
            with os.fdopen(witness_descriptor, 'r', encoding='utf-8') as stream:
                private_file(stream.fileno())
                witness = json.load(stream)
        if not isinstance(witness, dict):
            raise ProviderFailure('CLICKHOUSE_APPLICATION_WITNESS_INVALID')
        yield witness
    finally:
        os.close(descriptor)


def publish(directory, witness):
    descriptor, path = tempfile.mkstemp(prefix='.application-objects-', dir=directory)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(witness, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(path, directory + '/application-objects.json')
    finally:
        if os.path.exists(path):
            os.unlink(path)


def state(client, databases, accounts):
    sql = ''
    if databases:
        sql += "SELECT 'database' AS kind, name, toString(uuid) AS id FROM system.databases WHERE name IN (%s) FORMAT JSONEachRow;\n" % ','.join(literal(item['name']) for item in databases)
    if accounts:
        names = ','.join(literal(item['name']) for item in accounts)
        sql += "SELECT 'user' AS kind, name, toString(id) AS id FROM system.users WHERE name IN (%s) FORMAT JSONEachRow;\n" % names
        sql += "SELECT 'grant' AS kind, user_name AS name, access_type AS privilege, database, table, column, is_partial_revoke, grant_option FROM system.grants WHERE user_name IN (%s) FORMAT JSONEachRow;\n" % names
        sql += "SELECT 'role' AS kind, user_name AS name FROM system.role_grants WHERE user_name IN (%s) FORMAT JSONEachRow;\n" % names
        tables = {(database, table) for account in accounts for database, table, _ in required_grants(account) if table != '*'}
        if tables:
            pairs = ','.join('(%s,%s)' % (literal(database), literal(table)) for database, table in sorted(tables))
            sql += "SELECT 'table' AS kind, database, name FROM system.tables WHERE (database, name) IN (%s) FORMAT JSONEachRow;\n" % pairs
    return [json.loads(line) for line in client.query(sql).splitlines() if line.strip()] if sql else []


def required_grants(account):
    values = set()
    for grant in account.get('grants', []):
        identifier(grant['database'])
        if grant['table'] != '*':
            identifier(grant['table'])
        if not set(grant['privileges']) <= {'SELECT', 'INSERT'}:
            raise ProviderFailure('CLICKHOUSE_APPLICATION_GRANTS_INVALID')
        values.update((grant['database'], grant['table'], privilege) for privilege in grant['privileges'])
    return values


def managed_grant_delta(account, rows, databases):
    """Reconcile only direct SELECT/INSERT on this account's witnessed library DBs.

    Custody and UUID/marker checks remain the caller's prerequisite. Anything
    outside that limited authority remains a conflict, not a cleanup candidate.
    """
    grants = [row for row in rows if row['kind'] == 'grant' and row['name'] == account['name']]
    if (any(row['column'] or row['is_partial_revoke'] or row['grant_option'] for row in grants)
            or any(row['kind'] == 'role' and row['name'] == account['name'] for row in rows)):
        raise ProviderFailure('CLICKHOUSE_APPLICATION_GRANTS_DRIFT')
    prefix = account['marker'].split(':account:', 1)[0] + ':clickhouse.database:'
    owned = {db['name'] for db in databases if db['mode'] == 'managed' and db['marker'].startswith(prefix)}
    current = {(row['database'], row['table'] or '*', row['privilege']) for row in grants}
    expected = required_grants(account)
    removed = current - expected
    for database, table, privilege in removed:
        if database not in owned or privilege not in {'SELECT', 'INSERT'}:
            raise ProviderFailure('CLICKHOUSE_APPLICATION_GRANTS_DRIFT')
        if table != '*':
            identifier(table)
    return expected - current, removed


def user_batch(account, password, missing, create, clustered, revoked=()):
    name = identifier(account['name'])
    cluster = ' ON CLUSTER default' if clustered else ''
    statements = []
    if create:
        verifier = hashlib.sha256(password.encode()).hexdigest()
        statements.append("CREATE USER %s%s IDENTIFIED WITH sha256_hash BY '%s' DEFAULT ROLE NONE;" % (name, cluster, verifier))
    for database, table, privilege in sorted(revoked):
        if privilege not in {'SELECT', 'INSERT'}:
            raise ProviderFailure('CLICKHOUSE_APPLICATION_GRANTS_INVALID')
        scope = identifier(database) + '.' + ('*' if table == '*' else identifier(table))
        statements.append('REVOKE%s %s ON %s FROM %s;' % (cluster, privilege, scope, name))
    for database, table, privilege in sorted(missing):
        if privilege not in {'SELECT', 'INSERT'}:
            raise ProviderFailure('CLICKHOUSE_APPLICATION_GRANTS_INVALID')
        scope = identifier(database) + '.' + ('*' if table == '*' else identifier(table))
        statements.append('GRANT%s %s ON %s TO %s;' % (cluster, privilege, scope, name))
    return '\n'.join(statements)


def verify_login(client, account, preflight=False):
    expected = required_grants(account)
    sql = 'SELECT 1;\n'
    if not preflight:
        for database, table, privilege in sorted(expected):
            sql += 'CHECK GRANT %s ON %s.%s;\n' % (privilege, identifier(database), '*' if table == '*' else identifier(table))
    if client.query(sql).split() != ['1'] * (1 if preflight else len(expected) + 1):
        raise ProviderFailure('CLICKHOUSE_APPLICATION_LOGIN_OR_GRANTS_FAILED')

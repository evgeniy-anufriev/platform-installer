"""Target-free provider hook projection. Ansible remains the variable resolver."""
import hashlib
import re

try:
    from .application_libraries import resolve_connection, finding
except ImportError:
    from application_libraries import resolve_connection, finding

NAME = re.compile(r'^[a-z_][a-z0-9_]{0,62}$')
USER = re.compile(r'^[a-z_][a-z0-9_-]{0,62}$')
GRANTS = {'schema': {'USAGE'}, 'table': {'SELECT', 'INSERT', 'UPDATE', 'DELETE'},
          'sequence': {'USAGE', 'SELECT', 'UPDATE'}}


def normalize_redis_grants(value, sentinel=False):
    """Typed ACL tokens only; no categories, raw ACL rules or global defaults."""
    allowed = {'commands'} if sentinel else {'commands', 'keys', 'channels'}
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError('APPLICATION_PROVIDER_GRANTS_INVALID')
    result = {}
    for key in allowed:
        values = value.get(key, [])
        if not isinstance(values, list) or len(values) > 256 or any(not isinstance(item, str) or not item or len(item) > 256 for item in values):
            raise ValueError('APPLICATION_PROVIDER_GRANTS_INVALID')
        if key == 'commands':
            if not values or any(not re.fullmatch(r'[a-z][a-z0-9]*(?:\|[a-z][a-z0-9-]*)?', item) for item in values):
                raise ValueError('APPLICATION_PROVIDER_GRANTS_INVALID')
            # Only discovery, never Sentinel administration in application hooks.
            if sentinel and not set(values) <= {'ping', 'auth', 'hello', 'sentinel|get-master-addr-by-name'}:
                raise ValueError('APPLICATION_PROVIDER_GRANTS_INVALID')
            if not sentinel and any(item.split('|')[0] in {'acl', 'config', 'flushall', 'flushdb', 'shutdown', 'module', 'debug', 'replicaof', 'slaveof', 'sentinel'} for item in values):
                raise ValueError('APPLICATION_PROVIDER_GRANTS_INVALID')
        elif any(any(char.isspace() or ord(char) < 32 for char in item) or item[0] in {'~', '&', '+', '-', '#', '>', '<', '%'} for item in values):
            raise ValueError('APPLICATION_PROVIDER_GRANTS_INVALID')
        result[key] = sorted(set(values))
    return result


def normalize_clickhouse_grants(values, databases, provider_id):
    if not isinstance(values, list) or len(values) > 256:
        raise ValueError('APPLICATION_PROVIDER_GRANTS_INVALID')
    merged = {}
    for value in values:
        if not isinstance(value, dict) or set(value) != {'databaseRef', 'tables', 'privileges'}:
            raise ValueError('APPLICATION_PROVIDER_GRANTS_INVALID')
        database = databases.get(value['databaseRef'])
        tables, privileges = value['tables'], value['privileges']
        if (not database or database['providerId'] != provider_id or not isinstance(tables, list) or not tables or len(tables) > 256
                or not isinstance(privileges, list) or not privileges or any(not isinstance(item, str) for item in privileges)
                or not set(privileges) <= {'SELECT', 'INSERT'}):
            raise ValueError('APPLICATION_PROVIDER_GRANTS_INVALID')
        for table in tables:
            name = '*' if table == '*' else identifier(table)
            merged.setdefault((database['name'], name), set()).update(privileges)
    return [dict(database=key[0], table=key[1], privileges=sorted(value)) for key, value in sorted(merged.items())]


def identifier(value, username=False):
    if (not isinstance(value, str) or not (USER if username else NAME).fullmatch(value)
            or value.startswith('pg_') or value in {'postgres', 'template0', 'template1', 'public'}):
        raise ValueError('APPLICATION_PROVIDER_IDENTIFIER_INVALID')
    return value


def marker(project, provider, library, kind, identity):
    return 'platform.application/v1:' + ':'.join((project, provider, library, kind, identity))


def normalize_grants(values):
    result = []
    if not isinstance(values, list) or len(values) > 256:
        raise ValueError('APPLICATION_PROVIDER_GRANTS_INVALID')
    for value in values:
        if not isinstance(value, dict) or set(value) - {'schema', 'tables', 'sequences', 'privileges'}:
            raise ValueError('APPLICATION_PROVIDER_GRANTS_INVALID')
        schema = identifier(value.get('schema'))
        if 'tables' in value and 'sequences' in value:
            raise ValueError('APPLICATION_PROVIDER_GRANTS_INVALID')
        kind = 'table' if 'tables' in value else 'sequence' if 'sequences' in value else 'schema'
        privileges = value.get('privileges')
        if (not isinstance(privileges, list) or not privileges or
                any(not isinstance(p, str) for p in privileges) or not set(privileges) <= GRANTS[kind]):
            raise ValueError('APPLICATION_PROVIDER_GRANTS_INVALID')
        objects = value.get('tables' if kind == 'table' else 'sequences', [schema])
        if not isinstance(objects, list) or not objects or len(objects) > 256:
            raise ValueError('APPLICATION_PROVIDER_GRANTS_INVALID')
        for name in objects:
            result.append({'kind': kind, 'schema': schema, 'name': identifier(name),
                           'privileges': sorted(set(privileges))})
    merged = {}
    for grant in result:
        key = (grant['kind'], grant['schema'], grant['name'])
        merged.setdefault(key, set()).update(grant['privileges'])
    return [dict(kind=k[0], schema=k[1], name=k[2], privileges=sorted(v)) for k, v in sorted(merged.items())]


def normalize_database_access(values, databases, provider_id, owner):
    """Explicit database-wide policy; never infer creator roles from membership."""
    if not isinstance(values, list) or len(values) > 256:
        raise ValueError('APPLICATION_PROVIDER_GRANTS_INVALID')
    result, seen = [], set()
    for value in values:
        if not isinstance(value, dict) or set(value) - {'databaseRef', 'privileges', 'additionalCreatorRoles'}:
            raise ValueError('APPLICATION_PROVIDER_GRANTS_INVALID')
        database = databases.get(value.get('databaseRef'))
        privileges, creators = value.get('privileges'), value.get('additionalCreatorRoles', [])
        if (not database or database['providerId'] != provider_id or database['mode'] != 'managed'
                or database['name'] in seen or not isinstance(privileges, list) or not privileges
                or len(privileges) > 4 or any(not isinstance(p, str) for p in privileges)
                or len(set(privileges)) != len(privileges) or not set(privileges) <= GRANTS['table']
                or not isinstance(creators, list) or len(creators) > 256):
            raise ValueError('APPLICATION_PROVIDER_GRANTS_INVALID')
        creators = [identifier(role, True) for role in creators]
        if len(set(creators)) != len(creators):
            raise ValueError('APPLICATION_PROVIDER_GRANTS_INVALID')
        seen.add(database['name'])
        result.append(dict(database=database['name'], privileges=sorted(privileges),
                           creatorRoles=sorted(set([owner] + creators))))
    return sorted(result, key=lambda row: row['database'])


def project_providers(rows, snapshot, configuration, desired, catalog):
    """Discovery per provider; mutation batches per library and logical instance."""
    jobs, findings, names, logical = {}, [], {}, {}
    applications = snapshot.get('applicationLibraries', {})
    if applications.get('status') != 'PASS':
        return {'status': 'BLOCKED', 'jobs': [], 'findings': [finding('APPLICATION_PROVIDER_INPUT_INVALID', 'applicationLibraryDeployments')]}
    topology = snapshot.get('topology', {}).get('resolved', {}).get('serviceDeployments', {})
    materialized = dict(desired, serviceDeployments={key: dict(value, members=topology.get(key, {}).get('members', value.get('members', {})))
                                                 for key, value in desired.get('serviceDeployments', {}).items()})
    project_id = snapshot['project']['id']

    def provider(ref):
        deployment = materialized['serviceDeployments'][ref]
        definition = catalog['definitions'][deployment['serviceType']]
        service_type = deployment['serviceType']
        modes = {'postgresql': {'standalone', 'pg_auto_failover'}, 'redis': {'standalone', 'sentinel-ha'},
                 'clickhouse': {'standalone', 'raft-ha'}}
        if deployment['mode'] not in modes.get(service_type, set()):
            raise ValueError('APPLICATION_PROVIDER_MODE_UNSUPPORTED')
        capabilities = {'postgresql': {'service.postgresql.database', 'service.postgresql.schema', 'service.postgresql.account'},
                        'redis': {'service.redis.account'}, 'clickhouse': {'service.clickhouse.database', 'service.clickhouse.account'}}
        if not capabilities[service_type] <= set(definition.get('capabilities', [])):
            raise ValueError('APPLICATION_PROVIDER_CAPABILITY_UNSUPPORTED')
        if ref not in jobs:
            connection = resolve_connection(ref, {'purpose': 'native' if service_type == 'clickhouse' else 'client'}, None, materialized, configuration, catalog, snapshot['hosts'])
            targets = connection['targets']
            if service_type == 'postgresql' and len(targets) != (1 if deployment['mode'] == 'standalone' else 2):
                raise ValueError('APPLICATION_PROVIDER_MEMBERS_INVALID')
            jobs[ref] = {'providerId': ref, 'projectId': project_id, 'mode': deployment['mode'],
                         'serviceType': service_type, 'candidates': targets, 'libraries': [], 'databases': [], 'accounts': []}
        return jobs[ref]

    def claim(key, owner, mode):
        previous = names.setdefault(key, (owner, mode))
        if previous != (owner, mode) and not (mode == previous[1] == 'existing'):
            raise ValueError('APPLICATION_PROVIDER_NAME_CONFLICT')

    try:
        for row in rows:
            key = (row['libraryId'], row['instanceId'])
            identity = {k: row.get(k) for k in ('resources', 'bindings', 'connectionDefaults')}
            identity['accounts'] = row['settings'].get('accounts', {})
            if key in logical and logical[key] != identity:
                raise ValueError('APPLICATION_PROVIDER_HOST_CONFLICT')
            logical[key] = identity
        for library_id, library in sorted(applications['libraries'].items()):
            library_rows = [row for row in rows if row['libraryId'] == library_id]
            row = library_rows[0]
            if any({k: other.get(k) for k in ('resources', 'bindings', 'connectionDefaults')} !=
                   {k: row.get(k) for k in ('resources', 'bindings', 'connectionDefaults')} for other in library_rows):
                raise ValueError('APPLICATION_PROVIDER_HOST_CONFLICT')
            databases, schemas = {}, []
            for resource_id, resource in sorted(library.get('resources', {}).items()):
                if resource['kind'] not in {'postgresql.database', 'postgresql.schema', 'clickhouse.database'}:
                    raise ValueError('APPLICATION_PROVIDER_CAPABILITY_UNSUPPORTED')
                ref = row['bindings'].get(resource['binding'], {}).get('deploymentRef')
                job = provider(ref)
                if resource['kind'].split('.')[0] != job['serviceType']:
                    raise ValueError('APPLICATION_PROVIDER_RESOURCE_INVALID')
                if set(resource['parameters']) != {'name'}:
                    raise ValueError('APPLICATION_PROVIDER_RESOURCE_INVALID')
                name, mode = identifier(resource['parameters']['name']), resource.get('mode', 'managed')
                value = dict(resourceId=resource_id, name=name, mode=mode,
                             marker=marker(project_id, ref, library_id, resource['kind'], resource_id))
                if resource['kind'] in {'postgresql.database', 'clickhouse.database'}:
                    owner = 'pla_' + hashlib.sha256((project_id + ':' + ref + ':' + library_id).encode()).hexdigest()[:24]
                    value.update(providerId=ref, libraryId=library_id, owner=owner, schemas=[], accounts=[],
                                 ownerMarker=marker(project_id, ref, library_id, 'owner', library_id))
                    claim((ref, 'database', name), (library_id, resource_id), mode)
                    databases[resource_id] = value
                    job['databases'].append(value)
                    if job['serviceType'] == 'postgresql' and mode == 'managed' and not any(o['name'] == owner for o in job['libraries']):
                        job['libraries'].append({'name': owner, 'marker': value['ownerMarker']})
                else:
                    schemas.append((ref, resource, value))
            for ref, source, schema in schemas:
                database = databases.get(source.get('databaseRef'))
                if not database or database['providerId'] != ref or (schema['mode'] == 'managed' and database['mode'] != 'managed'):
                    raise ValueError('APPLICATION_PROVIDER_DATABASE_REF_INVALID')
                claim((ref, database['name'], schema['name']), (library_id, schema['resourceId']), schema['mode'])
                database['schemas'].append(schema)
            for instance_id, instance in sorted(library.get('instances', {}).items()):
                for account_id, account in sorted(instance.get('credentialRequirements', {}).items()):
                    connection = instance['connections'].get(account_id, {})
                    service_type = connection.get('serviceType')
                    if service_type not in {'postgresql', 'redis', 'clickhouse'}:
                        raise ValueError('APPLICATION_PROVIDER_CAPABILITY_UNSUPPORTED')
                    ref = connection['deploymentRef']
                    job = provider(ref)
                    database = databases.get(account.get('databaseRef'))
                    bulk_access = 'databaseAccess' in account
                    if bulk_access and (service_type != 'postgresql' or account['mode'] != 'managed'
                                        or 'service.postgresql.database-access' not in catalog['definitions']['postgresql'].get('capabilities', [])):
                        raise ValueError('APPLICATION_PROVIDER_CAPABILITY_UNSUPPORTED')
                    if not bulk_access and service_type != 'redis' and (not database or database['providerId'] != ref or (account['mode'] == 'managed' and database['mode'] != 'managed')):
                        raise ValueError('APPLICATION_PROVIDER_DATABASE_REF_INVALID')
                    credentials = account['credentials']
                    if set(credentials) != {'username', 'password'} or credentials['username']['source']['kind'] != 'literal':
                        raise ValueError('APPLICATION_PROVIDER_CREDENTIAL_INVALID')
                    if credentials['password']['source']['kind'] not in {'runtime_secret_ref', 'vault_ref'}:
                        raise ValueError('APPLICATION_PROVIDER_CREDENTIAL_SOURCE_DEFERRED')
                    username = identifier(credentials['username']['source']['value'], True)
                    admin = configuration['services'][ref]['configuration'].get('adminSuperuser', {}).get('value', {}).get('username')
                    if username in {admin, 'default', 'autoctl_node', 'pgautofailover_replicator'}:
                        raise ValueError('APPLICATION_PROVIDER_IDENTIFIER_INVALID')
                    listener = connection.get('connectionRef', 'client')
                    if service_type == 'redis':
                        if listener == 'sentinel' and 'service.redis.sentinel.account' not in catalog['definitions']['redis'].get('capabilities', []):
                            raise ValueError('APPLICATION_PROVIDER_CAPABILITY_UNSUPPORTED')
                        grants = normalize_redis_grants(account.get('grants', {}), listener == 'sentinel')
                        if 'databaseRef' in account:
                            raise ValueError('APPLICATION_PROVIDER_DATABASE_REF_INVALID')
                    elif service_type == 'clickhouse':
                        grants = normalize_clickhouse_grants(account.get('grants', []), databases, ref)
                        if account['mode'] == 'managed' and any(databases[g['databaseRef']]['mode'] != 'managed' for g in account.get('grants', [])):
                            raise ValueError('APPLICATION_PROVIDER_GRANTS_INVALID')
                    elif bulk_access:
                        if 'grants' in account or 'databaseRef' in account:
                            raise ValueError('APPLICATION_PROVIDER_GRANTS_INVALID')
                        owner = 'pla_' + hashlib.sha256((project_id + ':' + ref + ':' + library_id).encode()).hexdigest()[:24]
                        access = normalize_database_access(account['databaseAccess'], databases, ref, owner)
                        grants = []
                        database = next((db for db in databases.values() if access and db['name'] == access[0]['database']), None)
                    else:
                        grants = normalize_grants(account.get('grants', []))
                        schemas_by_name = {s['name']: s for s in database['schemas']}
                        if any(g['schema'] not in schemas_by_name or
                               (account['mode'] == 'managed' and schemas_by_name[g['schema']]['mode'] != 'managed') for g in grants):
                            raise ValueError('APPLICATION_PROVIDER_GRANTS_INVALID')
                    claim((ref, listener if service_type == 'redis' else 'account', username), (library_id, instance_id, account_id), account['mode'])
                    value = dict(name=username, mode=account['mode'], instanceId=instance_id, accountId=account_id,
                                 database=database['name'] if database else None, libraryId=library_id,
                                 listener=listener, candidates=connection.get('targets', job['candidates']),
                                 passwordRef=(credentials['password']['source']['ref'] if credentials['password']['source']['kind'] == 'runtime_secret_ref' else 'pla-vault-'+hashlib.sha256(repr(sorted(credentials['password']['source'].items())).encode()).hexdigest()[:32]), grants=grants,
                                 marker=marker(project_id, ref, library_id, 'account', instance_id + '/' + account_id))
                    if bulk_access:
                        value['databaseAccess'] = access
                        value['database'] = database['name'] if database else 'postgres'
                    job['accounts'].append(value)
                    if database:
                        database['accounts'].append(value)
    except (KeyError, TypeError, ValueError) as error:
        code = str(error)
        if not code.startswith('APPLICATION_PROVIDER_'):
            code = 'APPLICATION_PROVIDER_INPUT_INVALID'
        findings.append(finding(code, 'applicationLibraryDeployments'))
    providers = [] if findings else [jobs[k] for k in sorted(jobs)]
    library_jobs, instance_jobs = split_provider_jobs(providers)
    return {'status': 'BLOCKED' if findings else 'PASS', 'jobs': providers,
            'libraryJobs': library_jobs, 'instanceJobs': instance_jobs, 'findings': findings}


def split_provider_jobs(providers):
    """Execution boundaries are a library resource batch and one instance hook."""
    library_jobs, instance_jobs = [], []
    for job in providers:
        for library_id in sorted({db['libraryId'] for db in job['databases']}):
            databases = [dict(db, accounts=[]) for db in job['databases'] if db['libraryId'] == library_id]
            owners = {db['owner'] for db in databases if db['mode'] == 'managed'}
            library_jobs.append(dict(job, libraryId=library_id, databases=databases, accounts=[],
                                     libraries=[owner for owner in job['libraries'] if owner['name'] in owners]))
        for library_id, instance_id in sorted({(a['libraryId'], a['instanceId']) for a in job['accounts']}):
            accounts = [a for a in job['accounts'] if (a['libraryId'], a['instanceId']) == (library_id, instance_id)]
            database_names = {a['database'] for a in accounts}
            if job.get('serviceType') == 'clickhouse':
                database_names.update(grant['database'] for account in accounts for grant in account['grants'])
            bulk_accounts = [a for a in accounts if 'databaseAccess' in a]
            reconcile_accounts = bulk_accounts + ([a for a in accounts if a['mode'] == 'managed']
                                                  if job.get('serviceType') == 'clickhouse' else [])
            databases = [dict(db, accounts=[a for a in accounts if a['database'] == db['name'] or
                                           (a in bulk_accounts and db['libraryId'] == library_id and db['mode'] == 'managed')])
                         for db in job['databases'] if db['name'] in database_names or
                         (reconcile_accounts and db['libraryId'] == library_id and db['mode'] == 'managed')]
            login_accounts = [dict(a, database=entry['database']) for a in accounts
                              for entry in (a.get('databaseAccess') or [{'database': a['database']}])]
            instance_jobs.append(dict(job, libraryId=library_id, instanceId=instance_id, libraries=[],
                                      databases=databases, accounts=accounts, loginAccounts=login_accounts))
    return library_jobs, instance_jobs

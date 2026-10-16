#!/usr/bin/python
"""One library resource batch or logical instance account/grant batch."""
import json
from subprocess import SubprocessError
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.platform.clickhouse.plugins.module_utils.application_sql import (
    NativeClient, ProviderFailure, custody, publish, state, identifier,
    required_grants, user_batch, verify_login, managed_grant_delta)

DOCUMENTATION = r'''
module: application_scope
short_description: Execute one library resource or application account scope
description:
  - Uses native TLS, private ephemeral client configuration and an ownership witness.
  - HA accounts and grants use one initiating ON CLUSTER default batch.
options:
  job: {type: dict, required: true}
  directory: {type: path, required: true}
  admin_password: {type: str, required: true}
  passwords: {type: dict, default: {}}
  phase: {type: str, choices: [preflight, resources, accounts, verify], required: true}
  lock_timeout: {type: int, default: 15}
  query_timeout: {type: int, default: 60}
author: Platform Installer
'''


def identity(rows, kind, name):
    values = [row['id'] for row in rows if row['kind'] == kind and row['name'] == name]
    if len(values) > 1:
        raise ProviderFailure('CLICKHOUSE_APPLICATION_IDENTITY_INVALID')
    return values[0] if values else None


def check_owner(witness, key, marker, actual, mode, phase):
    record = witness.get(key)
    if record is not None and (not isinstance(record, dict) or set(record) != {'marker', 'ids'}
                               or not isinstance(record['ids'], dict)):
        raise ProviderFailure('CLICKHOUSE_APPLICATION_WITNESS_INVALID')
    existing = {member: value for member, value in actual.items() if value is not None}
    if mode == 'managed':
        if existing and (not isinstance(record, dict) or record.get('marker') != marker or record.get('ids') != existing):
            raise ProviderFailure('CLICKHOUSE_APPLICATION_OWNERSHIP_UNKNOWN')
        if record and (record.get('marker') != marker or record.get('ids') != existing):
            raise ProviderFailure('CLICKHOUSE_APPLICATION_OWNERSHIP_DRIFT')
    if (mode == 'existing' or phase == 'verify') and len(existing) != len(actual):
        raise ProviderFailure('CLICKHOUSE_APPLICATION_OBJECT_MISSING')
    return existing


def main():
    module = AnsibleModule(argument_spec={
        'job': {'type': 'dict', 'required': True}, 'directory': {'type': 'path', 'required': True},
        'admin_password': {'type': 'str', 'required': True, 'no_log': True},
        'passwords': {'type': 'dict', 'default': {}, 'no_log': True},
        'phase': {'choices': ['preflight', 'resources', 'accounts', 'verify'], 'required': True},
        'lock_timeout': {'type': 'int', 'default': 15}, 'query_timeout': {'type': 'int', 'default': 60}})
    args, clients, changed = module.params, [], False
    try:
        job, phase, directory = args['job'], args['phase'], args['directory']
        if not 1 <= args['lock_timeout'] <= 120 or not 1 <= args['query_timeout'] <= 120:
            raise ProviderFailure('CLICKHOUSE_APPLICATION_INPUT_INVALID')
        if any(not isinstance(password, str) or not 1 <= len(password) <= 4096
               for password in [args['admin_password']] + list(args['passwords'].values())):
            raise ProviderFailure('CLICKHOUSE_APPLICATION_INPUT_INVALID')
        if job['serviceType'] != 'clickhouse' or job['mode'] not in {'standalone', 'raft-ha'}:
            raise ProviderFailure('CLICKHOUSE_APPLICATION_INPUT_INVALID')
        targets = sorted(job['candidates'], key=lambda target: (target['hostId'], target['memberId']))
        if len(targets) != (3 if job['mode'] == 'raft-ha' else 1) or len({item['memberId'] for item in targets}) != len(targets):
            raise ProviderFailure('CLICKHOUSE_APPLICATION_MEMBERS_INVALID')
        databases, accounts = job['databases'], job['accounts']
        if len(databases) > 128 or len(accounts) > 128 or (phase == 'resources' and accounts):
            raise ProviderFailure('CLICKHOUSE_APPLICATION_INPUT_INVALID')
        for value in databases + accounts:
            identifier(value['name'])
            if value['mode'] not in {'managed', 'existing'} or not isinstance(value['marker'], str) or not value['marker'].startswith('platform.application/v1:'):
                raise ProviderFailure('CLICKHOUSE_APPLICATION_INPUT_INVALID')
        with custody(directory, args['lock_timeout']) as witness:
            original_witness = dict(witness)
            for target in targets:
                clients.append(NativeClient(target, directory, args['admin_password'], timeout=args['query_timeout']))
            if job['mode'] == 'raft-ha':
                topology = clients[0].query("SELECT host_name AS address, port FROM system.clusters WHERE cluster = 'default' FORMAT JSONEachRow;")
                resolved = {(item['address'], int(item['port'])) for item in map(json.loads, topology.splitlines())}
                if resolved != {(target['address'], int(target['port'])) for target in targets}:
                    raise ProviderFailure('CLICKHOUSE_APPLICATION_CLUSTER_INVALID')
            observed = {target['memberId']: state(client, databases, accounts) for target, client in zip(targets, clients)}
            resource_sql = {target['memberId']: [] for target in targets}
            for database in databases:
                actual = {member: identity(rows, 'database', database['name']) for member, rows in observed.items()}
                check_owner(witness, 'database/' + database['name'], database['marker'], actual, database['mode'], phase)
                if phase == 'accounts' and any(value is None for value in actual.values()):
                    raise ProviderFailure('CLICKHOUSE_APPLICATION_DATABASE_MISSING')
                for target in targets:
                    if actual[target['memberId']] is None and phase == 'resources' and database['mode'] == 'managed':
                        resource_sql[target['memberId']].append('CREATE DATABASE ' + identifier(database['name']) + ';')
            for target, client in zip(targets, clients):
                statements = resource_sql[target['memberId']]
                if statements:
                    client.query('\n'.join(statements))
                    changed = True
            account_sql = []
            for account in accounts:
                actual = {member: identity(rows, 'user', account['name']) for member, rows in observed.items()}
                existing = check_owner(witness, 'user/' + account['name'], account['marker'], actual, account['mode'], phase)
                if existing and len(existing) != len(targets):
                    raise ProviderFailure('CLICKHOUSE_APPLICATION_PARTIAL_ACCOUNT')
                expected = required_grants(account)
                missing_union, removed_union = set(), set()
                for target, client in zip(targets, clients):
                    rows = observed[target['memberId']]
                    grants = [row for row in rows if row['kind'] == 'grant' and row['name'] == account['name']]
                    current = {(row['database'], row['table'] or '*', row['privilege']) for row in grants}
                    missing = expected - current
                    if account['mode'] == 'managed':
                        missing, removed = managed_grant_delta(account, rows, databases)
                        if phase == 'verify' and removed:
                            raise ProviderFailure('CLICKHOUSE_APPLICATION_GRANTS_DRIFT')
                        removed_union.update(removed)
                    if phase == 'verify' and missing and account['mode'] == 'managed':
                        raise ProviderFailure('CLICKHOUSE_APPLICATION_GRANTS_MISSING')
                    missing_union.update(missing)
                    # Specific table grants require application migrations first.
                    for database, table, _ in expected:
                        if table != '*':
                            if (database, table) not in {(row['database'], row['name']) for row in rows if row['kind'] == 'table'}:
                                raise ProviderFailure('CLICKHOUSE_APPLICATION_MIGRATION_REQUIRED')
                    if existing:
                        user_client = NativeClient(target, directory, args['passwords'][account['passwordRef']], account['name'], args['query_timeout'])
                        try:
                            verify_login(user_client, account, account['mode'] == 'managed' and
                                         (phase == 'preflight' or (phase == 'accounts' and bool(missing))))
                        finally:
                            user_client.close()
                if phase == 'accounts' and account['mode'] == 'managed':
                    account_sql.append(user_batch(account, args['passwords'][account['passwordRef']], missing_union, not existing, job['mode'] == 'raft-ha', removed_union))
            if any(account_sql):
                clients[0].query('SET distributed_ddl_task_timeout = 30;\n' + '\n'.join(account_sql))
                changed = True
            # Observed identities/grants and authenticated probes already prove
            # an unchanged scope. Reread only after an actual native mutation.
            if phase in {'resources', 'accounts'} and changed:
                final = {target['memberId']: state(client, databases, accounts) for target, client in zip(targets, clients)}
                for value, kind in [(value, 'database') for value in databases] + [(value, 'user') for value in accounts]:
                    ids = {member: identity(rows, kind, value['name']) for member, rows in final.items()}
                    if any(value is None for value in ids.values()):
                        raise ProviderFailure('CLICKHOUSE_APPLICATION_OBJECT_MISSING')
                    original = {member: identity(rows, kind, value['name']) for member, rows in observed.items()}
                    if any(identifier is not None and ids[member] != identifier for member, identifier in original.items()):
                        raise ProviderFailure('CLICKHOUSE_APPLICATION_OWNERSHIP_DRIFT')
                    if value['mode'] == 'managed':
                        witness[kind + '/' + value['name']] = {'marker': value['marker'], 'ids': ids}
                for account in accounts:
                    if account['mode'] == 'managed':
                        for rows in final.values():
                            missing, removed = managed_grant_delta(account, rows, databases)
                            if missing or removed:
                                raise ProviderFailure('CLICKHOUSE_APPLICATION_GRANTS_DRIFT')
                    for target in targets:
                        user_client = NativeClient(target, directory, args['passwords'][account['passwordRef']], account['name'], args['query_timeout'])
                        try:
                            verify_login(user_client, account)
                        finally:
                            user_client.close()
                if witness != original_witness:
                    publish(directory, witness)
        module.exit_json(changed=changed)
    except ProviderFailure as error:
        module.fail_json(msg=str(error))
    except (ValueError, OSError, TypeError, KeyError, SubprocessError):
        module.fail_json(msg='CLICKHOUSE_APPLICATION_SCOPE_FAILED')
    finally:
        for client in clients:
            client.close()

if __name__ == '__main__':
    main()

"""Trusted SQL quoting and protected controller credential-file validation."""
import os
import re
from ansible_collections.platform.core.plugins.module_utils.application_credentials import protected_secret_files
import hashlib
from ansible.errors import AnsibleFilterError


def sql_literal(value):
    text = str(value)
    if '\x00' in text:
        raise AnsibleFilterError('APPLICATION_PROVIDER_VALUE_INVALID')
    return "'" + text.replace("'", "''") + "'"


def sql_identifier(value):
    text = str(value)
    if '\x00' in text:
        raise AnsibleFilterError('APPLICATION_PROVIDER_IDENTIFIER_INVALID')
    return '"' + text.replace('"', '""') + '"'


def validate_job(job):
    """Manual inventory uses the same bounded resolved inputs, never arbitrary SQL."""
    try:
        safe = re.compile(r'^[A-Za-z0-9_][A-Za-z0-9_.:/-]*$')
        for key in ('providerId', 'projectId'):
            if not safe.fullmatch(job[key]):
                raise ValueError()
        if job['mode'] not in ('standalone', 'pg_auto_failover') or not job['candidates']:
            raise ValueError()
        for candidate in job['candidates']:
            if not isinstance(candidate['port'], int) or not 1 <= candidate['port'] <= 65535:
                raise ValueError()
        for value in job['libraries'] + job['databases'] + job['accounts'] + [s for d in job['databases'] for s in d['schemas']]:
            if not re.fullmatch(r'[a-z_][a-z0-9_-]{0,62}', value['name']):
                raise ValueError()
            if not value['marker'].startswith('platform.application/v1:') or not safe.fullmatch(value['marker']):
                raise ValueError()
        owners = {}
        for database in job['databases']:
            restore = database.get('restoreOnCreate')
            if restore is not None and (database['mode'] != 'managed' or restore.get('format') != 'pg_custom'
                    or not re.fullmatch(r'[a-f0-9]{64}', restore.get('sha256', ''))
                    or not isinstance(database.get('restorePath'), str) or not database['restorePath']):
                raise ValueError()
            prefix = 'platform.application/v1:' + ':'.join((job['projectId'],job['providerId'],database['libraryId'])) + ':'
            owner = 'pla_' + hashlib.sha256(':'.join((job['projectId'],job['providerId'],database['libraryId'])).encode()).hexdigest()[:24]
            if database['owner'] != owner or database['ownerMarker'] != prefix+'owner:'+database['libraryId'] or database['marker'] != prefix+'postgresql.database:'+database['resourceId']:
                raise ValueError()
            owners[owner] = database['ownerMarker']
            for schema in database['schemas']:
                if schema['marker'] != prefix+'postgresql.schema:'+schema['resourceId']:
                    raise ValueError()
        for owner in job['libraries']:
            # Owner-only native phase remains valid for separate-request comparison.
            parts=owner['marker'].split(':')
            if len(parts) != 6 or parts[:3] != ['platform.application/v1',job['projectId'],job['providerId']] or parts[4] != 'owner' or parts[3] != parts[5]:
                raise ValueError()
            expected='pla_'+hashlib.sha256(':'.join(parts[1:4]).encode()).hexdigest()[:24]
            if owner['name'] != expected:
                raise ValueError()
        for account in job['accounts']:
            expected='platform.application/v1:'+':'.join((job['projectId'],job['providerId'],account['libraryId'],'account',account['instanceId']+'/'+account['accountId']))
            if account['marker'] != expected:
                raise ValueError()
        allowed = {'schema': {'USAGE'}, 'table': {'SELECT', 'INSERT', 'UPDATE', 'DELETE'},
                   'sequence': {'USAGE', 'SELECT', 'UPDATE'}}
        for account in job['accounts']:
            for grant in account['grants']:
                if (grant['kind'] not in allowed or not set(grant['privileges']) <= allowed[grant['kind']] or
                        not grant['privileges'] or not re.fullmatch(r'[a-z_][a-z0-9_]{0,62}', grant['schema']) or
                        not re.fullmatch(r'[a-z_][a-z0-9_]{0,62}', grant['name'])):
                    raise ValueError()
        return True
    except (TypeError, KeyError, ValueError):
        raise AnsibleFilterError('APPLICATION_PROVIDER_INPUT_INVALID')


class FilterModule:
    def filters(self):
        return {'application_sql_literal': sql_literal, 'application_sql_identifier': sql_identifier,
                'application_protected_secret_files': protected_secret_files,
                'application_validate_provider_job': validate_job}

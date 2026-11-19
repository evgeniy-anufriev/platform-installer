"""Resolve and reconcile managed KV documents and AppRole with private inputs."""
import re
import json
import secrets
import string
from urllib.error import HTTPError
from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleFilterError
from ansible.module_utils.urls import open_url
from ansible_collections.platform.core.plugins.module_utils.application_credentials import protected_secret_files
from ansible_collections.platform.vault.plugins.filter.application_provider import delta, cas_conflict, role_changed


class VaultOperationError(ValueError):
    def __init__(self, code, status, category='http'):
        super().__init__(code)
        self.status = status
        self.category = category


def reconcile_documents(documents, provider_id, states, values, request):
    changed = False
    for document in documents:
        key = provider_id + ':' + document['mount'] + '/' + document['document']
        state = states[key]
        change = delta(state, values[key], document['owner'])
        resource = document['mount'] + '/data/' + document['document']
        if not change['changed']:
            if not state.get('reused'):
                continue
            state = request('GET', resource)
            if state['status'] not in (200, 404):
                raise ValueError('APPLICATION_VAULT_DOCUMENT_READ_FAILED')
            change = delta(state, values[key], document['owner'])
        if not change['changed']:
            continue
        response = request(change['method'], resource, change['body'])
        if cas_conflict(response):
            state = request('GET', resource)
            if state['status'] not in (200, 404):
                raise ValueError('APPLICATION_VAULT_DOCUMENT_READ_FAILED')
            change = delta(state, values[key], document['owner'])
            if not change['changed']:
                continue
            response = request(change['method'], resource, change['body'])
        if response['status'] != 200:
            code = ('APPLICATION_VAULT_DOCUMENT_CAS_CONFLICT' if cas_conflict(response)
                    else 'APPLICATION_VAULT_DOCUMENT_WRITE_FAILED')
            raise VaultOperationError(code, response['status'])
        changed = True
    return changed


def reconcile_identity(identity, owner, policy, role, current, request):
    before_policy, before_role = current
    if (before_policy['status'] not in (200, 404) or before_role['status'] not in (200, 404) or
            (before_policy['status'] == 200 and not before_policy['json']['data']['policy'].startswith('# ' + owner + '\n')) or
            (before_role['status'] == 200 and (before_policy['status'] != 200 or
             before_role['json']['data']['token_policies'] != [identity]))):
        raise ValueError('APPLICATION_VAULT_IDENTITY_OWNERSHIP_INVALID')
    changed = False
    if before_policy['status'] == 404 or before_policy['json']['data']['policy'] != policy:
        response = request('PUT', 'sys/policies/acl/' + identity, dict(policy=policy))
        if response['status'] not in (200, 204):
            raise VaultOperationError('APPLICATION_VAULT_IDENTITY_WRITE_FAILED', response['status'])
        changed = True
    if role_changed(before_role, role):
        response = request('POST', 'auth/approle/role/' + identity, role)
        if response['status'] not in (200, 204):
            raise VaultOperationError('APPLICATION_VAULT_IDENTITY_WRITE_FAILED', response['status'])
        changed = True
    response = request('GET', 'auth/approle/role/' + identity + '/role-id')
    if response['status'] != 200:
        raise ValueError('APPLICATION_VAULT_IDENTITY_READ_FAILED')
    role_id = response['json']['data']['role_id']
    if not isinstance(role_id, str) or not 1 <= len(role_id) <= 4096:
        raise ValueError('APPLICATION_VAULT_IDENTITY_READ_FAILED')
    return dict(changed=changed, role_id=role_id)


def generated_password():
    # Fixed 15-character baseline; guarantee each required character class.
    chars = [secrets.choice(string.ascii_lowercase),
             secrets.choice(string.ascii_uppercase),
             secrets.choice(string.digits), '!']
    alphabet = string.ascii_letters + string.digits + '!'
    chars.extend(secrets.choice(alphabet) for _ in range(11))
    secrets.SystemRandom().shuffle(chars)
    return ''.join(chars)


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        values = task_vars or {}
        args = self._task.args
        try:
            if args.get('operation') in ('documents', 'identity'):
                if getattr(self._task, 'check_mode', False):
                    return dict(changed=False, skipped=True)
                protected_secret_files({}, [], args['secret_root'])
                provider = args['provider']

                def request(method, resource, body=None):
                    headers = {'X-Vault-Token': provider['token']}
                    if body is not None:
                        headers['Content-Type'] = ('application/merge-patch+json' if method == 'PATCH'
                                                   else 'application/json')
                    try:
                        response = open_url(provider['url'] + '/v1/' + resource, method=method,
                            headers=headers, data=json.dumps(body).encode() if body is not None else None,
                            validate_certs=True, follow_redirects='none', timeout=10,
                            ca_path=args['secret_root'] + '/vault-' + args['provider_id'] + '-ca.pem')
                    except HTTPError as error:
                        response = error
                    except Exception as error:
                        message = str(error).lower()
                        category = ('tls' if 'certificate' in message or 'ssl' in message else
                                    'timeout' if 'timeout' in message or 'timed out' in message else 'transport')
                        raise VaultOperationError('APPLICATION_VAULT_REQUEST_FAILED', -1, category) from None
                    with response:
                        raw = response.read(16 * 1024 * 1024 + 1)
                        if len(raw) > 16 * 1024 * 1024:
                            raise ValueError()
                        return dict(status=response.code, json=json.loads(raw) if raw else {})

                if args['operation'] == 'documents':
                    return dict(changed=reconcile_documents(args['documents'], args['provider_id'],
                        args['states'], args['values'], request))
                return reconcile_identity(args['identity'], args['owner'], args['policy'], args['role'],
                                          args['current'], request)
            document, provider = args['document'], args['provider']
            mount = provider['mounts'].get(document['mount']+'/', {})
            if mount.get('type') != 'kv' or str(mount.get('options', {}).get('version')) != '2':
                raise ValueError()
            fields, generated = {}, {}
            for field, descriptor in document['fields'].items():
                source = descriptor['source']
                if field == '_platform_owner':
                    raise ValueError()
                if source['kind'] == 'literal':
                    value = source['value']
                elif source['kind'] == 'runtime_secret_ref':
                    protected_secret_files(args['secret_files'], [source['ref']], args['secret_root'])
                    with open(args['secret_files'][source['ref']], encoding='utf-8') as stream:
                        value = stream.read(4097)
                elif source['kind'] == 'generated':
                    ref = descriptor['passwordRef']
                    profile = source.get('profile', 'password')
                    if profile not in ('password', 'client_secret'):
                        return dict(failed=True, msg='APPLICATION_GENERATED_PROFILE_INVALID')
                    shared_field = (document.get('document', '').endswith('/shared') and
                                    re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]{0,127}', field))
                    if (field != 'password' and not shared_field) or not re.fullmatch(r'pla-generated-[0-9a-f]{40}', ref):
                        raise ValueError()
                    protected_secret_files({}, [], args['secret_root'])
                    current = args['current']
                    if current['status'] == 200:
                        data = current['json']['data']
                        if (data['data'].get('_platform_owner') != document['owner'] or
                                data['metadata'].get('deletion_time') or data['metadata'].get('destroyed')):
                            raise ValueError()
                        value = data['data'].get(field)
                    elif current['status'] == 404 and not current.get('json', {}).get('data'):
                        value = None
                    else:
                        raise ValueError()
                    # Keep the password already provisioned into the account during
                    # this invocation when deferred delivery re-reads a missing KV.
                    if ref in args['secret_files']:
                        protected_secret_files(args['secret_files'], [ref], args['secret_root'])
                        with open(args['secret_files'][ref], encoding='utf-8') as stream:
                            value = stream.read(4097)
                    if value is None:
                        value = (''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
                                 if profile == 'client_secret' else generated_password())
                    generated[ref] = value
                else:
                    raise ValueError()
                if not isinstance(value, str) or not 1 <= len(value.encode()) <= 4096 or '\x00' in value:
                    raise ValueError()
                fields[field] = value
            return dict(changed=False, fields=fields, generated=generated)
        except (ValueError, AnsibleFilterError) as error:
            code = str(error)
            if isinstance(error, VaultOperationError):
                return dict(failed=True, msg='%s (HTTP %s, %s)' % (code, error.status, error.category),
                            http_status=error.status, category=error.category)
            return dict(failed=True, msg=code if code.startswith('APPLICATION_VAULT_') and re.fullmatch(r'[A-Z_]+', code)
                        else 'APPLICATION_VAULT_DOCUMENT_SOURCE_INVALID')
        except Exception:
            return dict(failed=True, msg='APPLICATION_VAULT_DOCUMENT_SOURCE_INVALID')

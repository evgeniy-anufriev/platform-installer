"""Resolve one managed document through existing private inputs and builtin uri."""
import re
import secrets
import string
from ansible.plugins.action import ActionBase
from ansible_collections.platform.core.plugins.module_utils.application_credentials import protected_secret_files


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
                    if field != 'password' or not re.fullmatch(r'pla-generated-[0-9a-f]{40}', ref):
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
                        value = generated_password()
                    generated[ref] = value
                else:
                    raise ValueError()
                if not isinstance(value, str) or not 1 <= len(value.encode()) <= 4096 or '\x00' in value:
                    raise ValueError()
                fields[field] = value
            return dict(changed=False, fields=fields, generated=generated)
        except Exception:
            return dict(failed=True, msg='APPLICATION_VAULT_DOCUMENT_SOURCE_INVALID')

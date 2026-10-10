"""Resolve one managed document through existing private inputs and builtin uri."""
from ansible.plugins.action import ActionBase
from ansible_collections.platform.core.plugins.module_utils.application_credentials import protected_secret_files


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
            fields = {}
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
                else:
                    raise ValueError()
                if not isinstance(value, str) or not 1 <= len(value.encode()) <= 4096 or '\x00' in value:
                    raise ValueError()
                fields[field] = value
            return dict(changed=False, fields=fields)
        except Exception:
            return dict(failed=True, msg='APPLICATION_VAULT_DOCUMENT_SOURCE_INVALID')

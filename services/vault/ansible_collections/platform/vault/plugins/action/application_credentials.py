"""Existing Vault runtime inputs and protected standalone bootstrap custody."""
import os
import re
from ansible.plugins.action import ActionBase
from ansible_collections.platform.core.plugins.module_utils.application_credentials import protected_secret_files


class ActionModule(ActionBase):
    TRANSFERS_FILES = False
    _requires_connection = False

    def run(self, tmp=None, task_vars=None):
        values = task_vars or {}
        try:
            args = self._task.args
            ref = args['provider_id']
            protected_secret_files({}, [], values.get('platform_application_secret_root', ''))
            inputs = [i for i in values.get('platform_runtime_secret_inputs', [])
                      if i.get('purpose') == 'SERVICE_ADMIN_TOKEN' and (i.get('serviceDeployment') == ref or (i.get('serviceDeployment') is None and args.get('single_provider', False)))]
            if inputs:
                if (len(inputs) != 1 or not isinstance(inputs[0].get('value'), str)
                        or not re.fullmatch(r'si-[a-f0-9]{40}', inputs[0].get('requirementRef', ''))
                        or set(inputs[0]) - {'purpose', 'requirementRef', 'value', 'serviceDeployment'}):
                    raise ValueError()
                token = inputs[0]['value']
            else:
                token = values.get('platform_vault_admin_token', '')
                if not token:
                    directory = values.get('platform_vault_bootstrap_output_dir', '')
                    if not directory or not os.path.isabs(directory):
                        raise ValueError()
                    path = os.path.join(directory, 'admin-token')
                    protected_secret_files({'token': path}, ['token'], directory)
                    with open(path, encoding='utf-8') as stream:
                        token = stream.read(4097).strip()
            if not isinstance(token, str):
                raise ValueError()
            if not 1 <= len(token.encode()) <= 4096 or '\n' in token or '\r' in token:
                raise ValueError()
            return dict(changed=False, token=token)
        except Exception:
            return dict(failed=True, msg='APPLICATION_VAULT_ADMIN_CREDENTIAL_INVALID')

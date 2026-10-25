"""Resolve one account callback invocation; no product API or credential values."""
import hashlib
from ansible.plugins.action import ActionBase
from ansible_collections.platform.core.plugins.module_utils.application_scripts import _argument
from ansible_collections.platform.core.plugins.module_utils.application_connections import script_secret_source, script_secret_reference
from ansible_collections.platform.core.plugins.module_utils.application_libraries import checked_file


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        values = task_vars or {}
        try:
            batch = self._task.args['batch']
            snapshot = values['hostvars']['localhost']['application_snapshot']['snapshot']
            owner = batch['providerLibraryId']
            app_id = batch['providerInstanceId']
            library = snapshot['applicationLibraries']['libraries'][owner]
            instance = library['instances'][app_id]
            callback = next(item for item in instance['scripts'] if item['phase'] == 'account_apply'
                            and item['id'] == batch['connection']['accountProvisioner']['apply_script'])
            runtime = values['hostvars']['localhost']['application_runtime_inputs']
            jobs = runtime.get('scriptContexts', runtime['jobs'])
            job = min((item for item in jobs if item['libraryId'] == owner and item['instanceId'] == app_id), key=lambda item: item['hostId'])
            requests = []
            for account in batch['accounts']:
                source = account['passwordSource']
                password_ref = source['ref'] if source['kind'] == 'runtime_secret_ref' else 'pla-vault-' + hashlib.sha256(repr(sorted(source.items())).encode()).hexdigest()[:32]
                requests.append(dict(account, passwordRef=password_ref))
            context = dict(job, accountBatch=[{key: value for key, value in item.items() if key not in ('passwordSource', 'passwordRef')} for item in requests])
            secret_inputs = {}
            for key, source in callback.get('secretInputs', {}).items():
                value = script_secret_source(source, library, instance)
                if source['valueFrom'] == 'account_batch':
                    secret_inputs[key] = batch['id']
                elif value is None and source.get('optional', False):
                    continue
                else:
                    secret_inputs[key] = script_secret_reference(value)
            hosts = {key: {'ansible_host': value['ansibleHost']} for key, value in snapshot['hosts'].items()}
            script = dict(id=callback['id'], phase='account_apply', scope='instance',
                          path=checked_file(self._task.args['project_root'], job['applicationPackagePath'] + '/' + callback['source']),
                          argv=[_argument(arg, context, library, hosts, values['platform_desired_state']) for arg in callback.get('argv', [])],
                          secretInputs=secret_inputs, runOn=callback.get('run_on', 'target'))
            return dict(changed=False, script=script, requests=requests, accounts=context['accountBatch'], targetHostId=job['hostId'])
        except (ValueError, KeyError, TypeError, StopIteration, OSError):
            return dict(changed=False, failed=True, msg='APPLICATION_ACCOUNT_CALLBACK_INVALID')

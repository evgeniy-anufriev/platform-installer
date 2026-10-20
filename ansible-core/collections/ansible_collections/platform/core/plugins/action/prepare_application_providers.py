"""Resolve provider-only hooks without image authority or target contacts."""
from ansible.plugins.action import ActionBase
from ansible_collections.platform.core.plugins.module_utils.application_providers import project_providers



class ActionModule(ActionBase):
    TRANSFERS_FILES = False
    _requires_connection = False

    def run(self, tmp=None, task_vars=None):
        values = task_vars or {}
        try:
            args = self._task.args
            prepared = args['snapshot_result']
            snapshot, configuration = prepared['snapshot'], prepared['execution_configuration']
            catalog = self._loader.load_from_file(args['service_catalog_path'])
            result = project_providers(values['platform_application_rows'], snapshot, configuration,
                                       values['platform_desired_state'], catalog)
            if result['status'] == 'PASS':
                for job in result['jobs'] + result['libraryJobs'] + result['instanceJobs']:
                    settings = configuration['services'][job['providerId']]['configuration']
                    if job['serviceType'] == 'clickhouse':
                        credential = settings.get('defaultCredential', {})
                        if credential.get('state') != 'RESOLVED' or not credential.get('value', {}).get('passwordSecretRef'):
                            raise ValueError('APPLICATION_PROVIDER_ADMIN_CREDENTIAL_REQUIRED')
                        job['adminPasswordRef'] = credential['value']['passwordSecretRef']
                    if job['serviceType'] in {'redis', 'clickhouse'}:
                        for account in job['accounts']:
                            setting = ('sentinelCredential' if account['listener'] == 'sentinel' else 'redisCredential') if job['serviceType'] == 'redis' else 'defaultCredential'
                            credential = settings.get(setting, {})
                            if credential.get('state') != 'RESOLVED' or not credential.get('value', {}).get('passwordSecretRef'):
                                raise ValueError('APPLICATION_PROVIDER_ADMIN_CREDENTIAL_REQUIRED')
                            account['adminPasswordRef'] = credential['value']['passwordSecretRef']
                    for candidate in job['candidates'] + job.get('adminCandidates', []):
                        plans = [p for p in prepared['pki_materialization'].get('materializationPlans', [])
                                 if p['hostId'] == candidate['hostId'] and p['tlsProfileId'] == candidate.get('tlsProfileRef')]
                        if job['serviceType'] == 'kafka':
                            request_ids = {r['id'] for r in prepared['pki_materialization'].get('requests', [])
                                           if any(c.get('deploymentId') == job['providerId'] and c.get('memberId') == candidate['memberId']
                                                  for c in r.get('consumers', []))}
                            plans = [p for p in plans if p['requestId'] in request_ids]
                            if candidate['tls'] and len(plans) != 1:
                                raise ValueError('APPLICATION_PROVIDER_PKI_PLAN_REQUIRED')
                        candidate['pkiPlans'] = plans
                        if (job['accounts'] or job['serviceType'] == 'clickhouse') and len(plans) != 1:
                            raise ValueError('APPLICATION_PROVIDER_PKI_PLAN_REQUIRED')
            return dict(result, changed=False)
        except (KeyError, TypeError, ValueError, OSError):
            return {'changed': False, 'status': 'BLOCKED', 'jobs': [],
                    'findings': [{'code': 'APPLICATION_PROVIDER_INPUT_INVALID', 'field': 'applicationLibraryDeployments'}]}

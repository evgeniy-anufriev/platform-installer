"""Standalone authority assembly without enabling the Installer planner."""
import os
from ansible.plugins.action import ActionBase
from ansible_collections.platform.core.plugins.module_utils.application_post_install import script_queue
from ansible_collections.platform.core.plugins.module_utils.application_runtime import prepare_runtime, resolve_image_lock, provider_script_contexts
from ansible_collections.platform.core.plugins.module_utils.schema_validation import SchemaValidator
from ansible_collections.platform.core.plugins.module_utils.application_integrations import prepare_integrations
from ansible_collections.platform.core.plugins.module_utils.application_selection import integration_consumers


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        values = task_vars or {}
        try:
            args = self._task.args
            root = os.path.realpath(args["project_root"])
            if args.get('scripts_only', False):
                from ansible_collections.platform.core.plugins.module_utils.application_libraries import invocation_package_loader
                from ansible_collections.platform.core.plugins.module_utils.application_scripts import prepare_script_jobs
                snapshot = args['snapshot']
                loader = invocation_package_loader(root, self._loader.load_from_file, SchemaValidator(args['contracts_root']))
                contexts = provider_script_contexts(root, snapshot, values['platform_application_rows'], loader, include_selected=True)
                prepare_script_jobs(root, snapshot, values['platform_desired_state'], values['platform_application_rows'], contexts, phase='post_install')
                queue = script_queue(contexts, snapshot['applicationExecutionScope']['libraryOrder'])
                return dict(changed=False, status='PASS', jobs=[], scriptContexts=contexts, postInstallScripts=queue)
            manifest_path = os.path.join(root, "project.yml")
            manifest = self._loader.load_from_file(manifest_path) if os.path.isfile(manifest_path) else {}
            native_lock = values.get("platform_artifact_lock")
            manifest_lock = (manifest or {}).get("artifactLock")
            resolve_image_lock(native_lock, manifest_lock, values.get('platform_prepared_application_images'))
            if values.get('platform_prepared_application_images') is not None:
                native_lock = dict(native_lock or manifest_lock or {}, **{
                    'x-container-images': values['platform_prepared_application_images']})
            snapshot = args["snapshot"]
            contexts = []
            jobs = prepare_runtime(root, snapshot, values["platform_application_rows"],
                                   values["platform_desired_state"], native_lock or manifest_lock or {},
                                   SchemaValidator(args["contracts_root"]), self._loader.load_from_file, contexts)
            for job in jobs:
                job["projectId"] = snapshot["project"]["id"]
                job['integrationConsumers'] = integration_consumers(snapshot, job['libraryId'], values['platform_desired_state'])
                row = next(row for row in values['platform_application_rows']
                           if (row['libraryId'], row['instanceId'], row['hostId']) ==
                           (job['libraryId'], job['instanceId'], job['hostId']))
                profiles = {binding['profileRef'] for binding in row.get('bindings', {}).values() if 'profileRef' in binding}
                plans = values['application_snapshot']['pki_materialization']['materializationPlans']
                job['pkiPlans'] = [plan for plan in plans if plan['hostId'] == job['hostId'] and plan['tlsProfileId'] in profiles]
                if len(job['pkiPlans']) != len(profiles) or len(profiles) > 1:
                    raise ValueError('APPLICATION_PKI_PROFILE_AMBIGUOUS')
                if job.get('agentTemplate'):
                    vault = values['application_vault_inputs']
                    matches = [x for x in vault['instanceJobs'] if x['instanceId'] == job['instanceId'] and x['libraryId'] == job['libraryId']]
                    if len(matches) != 1:
                        raise ValueError('APPLICATION_VAULT_INSTANCE_REQUIRED')
                    instance = matches[0]
                    provider = next(x for x in vault['providers'] if x['providerId'] == instance['providerId'])
                    job['vault'] = dict(endpoint_url=provider['url'], ca_container_path='/opt/vault/ca.pem',
                                        auth_mount='auth/approle', role_id_container_path='/opt/vault/role-id',
                                        env_templates=instance['envTemplates'], readFields=instance['readFields'], providerId=instance['providerId'])
            return {"changed": False, "jobs": jobs, "scriptContexts": jobs + contexts,
                    "postInstallScripts": script_queue(jobs, values.get("platform_application_execution_scope", {}).get("libraryOrder", sorted(snapshot["applicationLibraries"]["libraries"]))),
                    "integrationScripts": [dict(script, libraryId=job['libraryId'], instanceId=job['instanceId'], hostId=job['hostId'])
                        for job in jobs + contexts for script in job.get('scripts', []) if script['phase'] == 'integration_apply'],
                    "integrations": prepare_integrations(snapshot, jobs), "status": "PASS"}
        except (ValueError, KeyError, TypeError, OSError) as error:
            code = str(error)
            if not code.startswith("APPLICATION_") or not code.replace("_", "").isalnum():
                code = "APPLICATION_RUNTIME_INPUT_INVALID"
            return {"changed": False, "jobs": [], "status": "BLOCKED", "code": code}

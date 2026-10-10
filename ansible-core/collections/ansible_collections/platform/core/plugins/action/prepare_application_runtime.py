"""Standalone authority assembly without enabling the Installer planner."""
import os
from ansible.plugins.action import ActionBase
from ansible_collections.platform.core.plugins.module_utils.application_runtime import prepare_runtime
from ansible_collections.platform.core.plugins.module_utils.schema_validation import SchemaValidator


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        values = task_vars or {}
        try:
            args = self._task.args
            root = os.path.realpath(args["project_root"])
            manifest_path = os.path.join(root, "project.yml")
            manifest = self._loader.load_from_file(manifest_path) if os.path.isfile(manifest_path) else {}
            native_lock = values.get("platform_artifact_lock")
            manifest_lock = (manifest or {}).get("artifactLock")
            if native_lock is not None and manifest_lock is not None and native_lock != manifest_lock:
                raise ValueError("APPLICATION_ARTIFACT_LOCK_CONFLICT")
            snapshot = args["snapshot"]
            jobs = prepare_runtime(root, snapshot, values["platform_application_rows"],
                                   values["platform_desired_state"], native_lock or manifest_lock or {},
                                   SchemaValidator(args["contracts_root"]), self._loader.load_from_file)
            for job in jobs:
                job["projectId"] = snapshot["project"]["id"]
                if job.get('agentTemplate'):
                    vault = values['application_vault_inputs']
                    matches = [x for x in vault['instanceJobs'] if x['instanceId'] == job['instanceId'] and x['libraryId'] == job['libraryId']]
                    if len(matches) != 1:
                        raise ValueError('APPLICATION_VAULT_INSTANCE_REQUIRED')
                    instance = matches[0]
                    provider = next(x for x in vault['providers'] if x['providerId'] == instance['providerId'])
                    shared = [p for x in vault['libraryJobs'] if x['libraryId'] == job['libraryId'] for d in x['documents'] for f in d['fields'].values() for p in f.get('pkiPlans', []) if p['hostId'] == job['hostId']]
                    job['vault'] = dict(endpoint_url=provider['url'], ca_container_path='/opt/vault/ca.pem',
                                        auth_mount='auth/approle', role_id_container_path='/opt/vault/role-id',
                                        env_templates=instance['envTemplates'], readFields=instance['readFields'], providerId=instance['providerId'], pkiPlans=shared)
            return {"changed": False, "jobs": jobs, "status": "PASS"}
        except (ValueError, KeyError, TypeError, OSError) as error:
            code = str(error)
            if not code.startswith("APPLICATION_") or not code.replace("_", "").isalnum():
                code = "APPLICATION_RUNTIME_INPUT_INVALID"
            return {"changed": False, "jobs": [], "status": "BLOCKED", "code": code}

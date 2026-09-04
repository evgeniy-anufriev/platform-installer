from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleError

from ansible_collections.platform.core.plugins.module_utils.deployment_plan import build_deployment_plan


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        del tmp, task_vars
        try:
            result = build_deployment_plan(self._task.args.get("snapshot"), self._task.args.get("service_catalog"), self._task.args.get("runtime_release"), self._task.args.get("created_at", "1970-01-01T00:00:00Z"))
            return {"changed": False, "deployment_plan": result["deploymentPlan"], "execution_manifest_digest": result["executionManifestDigest"]}
        except (TypeError, ValueError, KeyError) as error:
            raise AnsibleError("DEPLOYMENT_PLAN_INPUT_INVALID: %s" % error)

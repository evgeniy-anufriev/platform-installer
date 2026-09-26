from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleError

from ansible_collections.platform.core.plugins.module_utils.deployment_plan import build_runtime_secret_descriptors


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        del tmp, task_vars
        snapshot, catalog = self._task.args.get("snapshot"), self._task.args.get("service_catalog")
        if not isinstance(snapshot, dict) or not isinstance(catalog, dict):
            raise AnsibleError("RUNTIME_SECRET_DESCRIPTORS_INPUT_INVALID")
        result = build_runtime_secret_descriptors(snapshot, catalog,
                                                  self._task.args.get("pki_materialization"))
        return {"changed": False, "runtime_secret_descriptors": result}

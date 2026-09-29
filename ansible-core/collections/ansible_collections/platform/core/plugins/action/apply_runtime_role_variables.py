"""Transfer the trusted current-host projection without scalar templating."""
import copy
import re

from ansible.plugins.action import ActionBase


class ActionModule(ActionBase):
    TRANSFERS_FILES = False
    _requires_connection = False

    def run(self, tmp=None, task_vars=None):
        del tmp
        task_vars = task_vars or {}
        hosts = task_vars.get("platform_execution_role_variables_by_host")
        host = task_vars.get("inventory_hostname")
        values = hosts.get(host) if isinstance(hosts, dict) and isinstance(host, str) else None
        if (self._task.args or not isinstance(values, dict) or
                any(not isinstance(name, str) or
                    re.fullmatch(r"platform_[A-Za-z0-9_]+", name) is None for name in values)):
            return {"changed": False, "failed": True, "_ansible_no_log": True,
                    "msg": "EXECUTION_ROLE_VARIABLES_INVALID"}
        # No service rules, value normalization, target calls, or file writes.
        return {"changed": False, "ansible_facts": copy.deepcopy(values),
                "_ansible_facts_cacheable": False, "_ansible_no_log": True}

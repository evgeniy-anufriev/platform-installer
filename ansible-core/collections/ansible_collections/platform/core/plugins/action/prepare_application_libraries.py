"""Validate local package closure before Ansible loads/expands its defaults."""
import os

from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleError
from ansible_collections.platform.core.plugins.module_utils.application_libraries import prepare, finding


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        task_vars = task_vars or {}
        args = self._task.args
        root = os.path.realpath(args["project_root"])
        memberships = {host: task_vars["hostvars"][host].get("platform_application_libraries", {})
                       for host in task_vars.get("groups", {}).get("platform_targets", [])}
        try:
            result = prepare(root, task_vars.get("platform_desired_state", {}), memberships,
                             task_vars.get("platform_desired_state_contract"),
                             lambda path: self._loader.load_from_file(path), args["contracts_root"])
            common = {}
            for job in result['jobs']:
                key = (job['libraryId'], job['hostId'])
                if key not in common:
                    variables = dict(task_vars)
                    variables.update(task_vars['hostvars'].raw_get(job['hostId']))
                    for name in list(variables):
                        if name.startswith(('application_', '_application_')) or name in ('hostvars', 'vars', 'ansible_facts', 'library_runtime'):
                            variables.pop(name)
                    variables['library_instance_id'] = job['libraryId']
                    templar = self._templar.copy_with_new_env(available_variables=variables)
                    common[key] = (
                        templar.template(job['library']['definition'].get('defaults', {})),
                        templar.template(job['deployment'].get('overrides', {})))
                job['commonDefaults'], job['commonOverrides'] = common[key]
        except (ValueError, OSError, KeyError, TypeError, AnsibleError):
            result = {"jobs": [], "findings": [finding("APPLICATION_INPUT_INVALID", "applicationLibraryDeployments")]}
        return dict(result, changed=False)

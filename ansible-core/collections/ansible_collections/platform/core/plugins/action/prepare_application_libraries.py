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
        if args.get('shared_defaults') or args.get('resource_defaults') or args.get('provided_connections'):
            try:
                variables = dict(task_vars)
                variables.update(task_vars['hostvars'].raw_get(args['host_id']))
                for name in list(variables):
                    if name.startswith(('application_', '_application_', '_library_')) or name in ('hostvars', 'vars', 'ansible_facts', 'library_runtime', 'library_resources', 'platform_application_rows', 'platform_application_findings'):
                        variables.pop(name)
                variables['library_instance_id'] = args['library_id']
                if args.get('shared_defaults'):
                    variables['library_resources'] = task_vars['library_resources']
                templar = self._templar.copy_with_new_env(available_variables=variables)
                field = ('provided_connections' if args.get('provided_connections') else
                         'resource_defaults' if args.get('resource_defaults') else 'defaults')
                defaults = self._loader.load_from_file(args['defaults_path'])['platform_library_definition'].get(field, {})
                overrides = task_vars['platform_desired_state']['applicationLibraryDeployments'][args['library_id']].get(
                    field if field != 'defaults' else 'overrides', {})
                return dict(defaults=templar.template(defaults), overrides=templar.template(overrides), changed=False)
            except (ValueError, OSError, KeyError, TypeError, AnsibleError):
                return dict(defaults={}, overrides={}, findings=[finding('APPLICATION_INPUT_INVALID', 'applicationLibraryDeployments')], changed=False)
        root = os.path.realpath(args["project_root"])
        memberships = {host: task_vars["hostvars"][host].get("platform_application_libraries", {})
                       for host in task_vars.get("groups", {}).get("platform_targets", [])}
        try:
            result = prepare(root, task_vars.get("platform_desired_state", {}), memberships,
                             task_vars.get("platform_desired_state_contract"),
                             lambda path: self._loader.load_from_file(path), args["contracts_root"])
        except (ValueError, OSError, KeyError, TypeError, AnsibleError):
            result = {"jobs": [], "findings": [finding("APPLICATION_INPUT_INVALID", "applicationLibraryDeployments")]}
        return dict(result, changed=False)

"""Validate local package closure before Ansible loads/expands its defaults."""
import os

from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleError
from ansible.utils.vars import merge_hash
from ansible_collections.platform.core.plugins.module_utils.application_libraries import prepare, finding
from ansible_collections.platform.core.plugins.module_utils.project_snapshot_output import snapshot_input_message


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        task_vars = task_vars or {}
        args = self._task.args
        if args.get('diagnose_failure'):
            failure = task_vars.get('ansible_failed_result', {})
            message = failure.get('msg', '')
            context = {'libraryId': args.get('library_id'), 'slotId': args.get('slot_id'), 'hostId': args.get('host_id')}
            field = 'applicationLibraryDeployments.%s.applications.%s.placements.%s' % (
                args['library_id'], args['slot_id'], args['host_id'])
            diagnostic = finding('APPLICATION_INPUT_INVALID', field)
            previous = failure.get('finding', {})
            diagnostic['safeMessage'] = (previous['safeMessage']
                if previous.get('code') == 'APPLICATION_INPUT_INVALID' and previous.get('safeMessage') else
                snapshot_input_message(args.get('stage', 'application-settings'), AnsibleError(message), context))
            return dict(changed=False, finding=diagnostic)
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
                defaults, overrides = templar.template(defaults), templar.template(overrides)
                if field == 'resource_defaults':
                    merged = merge_hash(defaults, overrides, recursive=True, list_merge='replace')
                    return dict(resource_defaults=merged, changed=False)
                return dict(defaults=defaults, overrides=overrides, changed=False)
            except (ValueError, OSError, KeyError, TypeError, AnsibleError) as error:
                context = {'libraryId': args.get('library_id'), 'hostId': args.get('host_id'),
                           'slotId': task_vars.get('application_job', {}).get('slotId')}
                diagnostic = finding('APPLICATION_INPUT_INVALID', 'applicationLibraryDeployments')
                diagnostic['safeMessage'] = snapshot_input_message('library-defaults', error, context)
                return dict(failed=True, finding=diagnostic, changed=False)
        root = os.path.realpath(args["project_root"])
        memberships = {host: task_vars["hostvars"][host].get("platform_application_libraries", {})
                       for host in task_vars.get("groups", {}).get("platform_targets", [])}
        try:
            result = prepare(root, task_vars.get("platform_desired_state", {}), memberships,
                             task_vars.get("platform_desired_state_contract"),
                             lambda path: self._loader.load_from_file(path), args["contracts_root"])
        except (ValueError, OSError, KeyError, TypeError, AnsibleError):
            result = {"jobs": [], "findings": [finding("APPLICATION_INPUT_INVALID", "applicationLibraryDeployments")]}
        literal_addresses = {}
        for job in result['jobs']:
            if job['skipConnectionTopology']:
                host = job['hostId']
                if host not in literal_addresses:
                    address = task_vars['hostvars'].raw_get(host).get('ansible_host')
                    literal_addresses[host] = isinstance(address, str) and not any(
                        marker in address for marker in ('{', '}', '#jinja2'))
                job['skipConnectionTopology'] = literal_addresses[host]
            if job['connections'] is not None:
                continue
            context = {key: job[key] for key in ('libraryId', 'slotId', 'hostId')}
            diagnostic = finding('APPLICATION_INPUT_INVALID',
                'applicationLibraryDeployments.%s.applications.%s.placements.%s' %
                (job['libraryId'], job['slotId'], job['hostId']))
            diagnostic['safeMessage'] = snapshot_input_message(
                'application-settings', AnsibleError('Unknown library connection'), context)
            result['findings'].append(diagnostic)
        return dict(result, changed=False)

"""Validate local package closure before Ansible loads/expands its defaults."""
import os

from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleError
from ansible.template import AnsibleNativeEnvironment
from ansible.utils.vars import merge_hash
from ansible_collections.platform.core.plugins.module_utils.application_libraries import prepare, finding, account_policies
from ansible_collections.platform.core.plugins.module_utils.project_snapshot_output import snapshot_input_message


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        task_vars = task_vars or {}
        args = self._task.args
        if args.get('resolved_row'):
            return self._resolved_row(args, task_vars)
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
        if args.get('application_defaults'):
            try:
                definition = self._loader.load_from_file(args['defaults_path'])['platform_application_definition']
                defaults = definition['defaults']
                templar = self._templar.copy_with_new_env(
                    environment_class=AnsibleNativeEnvironment, available_variables=task_vars)
                return dict(defaults=templar.template(defaults), identity_names=definition.get('identity_environment', []), changed=False)
            except (ValueError, OSError, KeyError, TypeError, AnsibleError) as error:
                job = task_vars.get('application_job', {})
                context = {key: job.get(key) for key in ('libraryId', 'slotId', 'hostId')}
                diagnostic = finding('APPLICATION_INPUT_INVALID', 'applicationLibraryDeployments')
                diagnostic['safeMessage'] = snapshot_input_message('application-settings', error, context)
                return dict(failed=True, finding=diagnostic, changed=False)
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
                templar = self._templar.copy_with_new_env(
                    environment_class=AnsibleNativeEnvironment, available_variables=variables)
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

    def _resolved_row(self, args, task_vars):
        """Assemble typed facts without templating the complete package namespace.

        Library resources/shared defaults were rendered in the isolated host
        context, and application defaults/inheritance in the placement context.
        Keep Ansible's native merge_hash and the existing account policy helper.
        Only the selected package metadata below still needs native templating.
        """
        job = task_vars['application_job']
        deployment = job['deployment']
        library = task_vars[args['library_namespace']]['platform_library_definition']
        shared = task_vars['_application_shared']
        resource_defaults = task_vars['_application_resource_defaults']
        defaults = task_vars['_application_defaults']
        inherit = job['slot'].get('inherit_defaults', True)
        inherited = merge_hash(shared['defaults'] if inherit else {}, defaults['defaults'], recursive=True, list_merge='replace')
        if task_vars['_application_library_endpoint']:
            inherited = merge_hash(inherited, {'endpoint': task_vars['_application_library_endpoint']}, recursive=True, list_merge='replace')
        inherited = merge_hash(inherited, job['slot'].get('overrides', {}), recursive=True, list_merge='replace')
        inherited = merge_hash(inherited, shared['overrides'] if inherit else {}, recursive=True, list_merge='replace')
        variables = dict(task_vars, application_inherited=inherited)
        templar = self._templar.copy_with_new_env(environment_class=AnsibleNativeEnvironment, available_variables=variables)
        metadata = templar.template({
            name: library[name] for name in (
                'runtime_directory', 'connections', 'shared_secrets', 'connection_defaults') if name in library
        })
        instance = job['instance']
        settings = merge_hash(inherited, instance.get('overrides', {}), recursive=True, list_merge='replace')
        if 'accounts' in instance:
            settings = merge_hash(settings, {'accounts': instance['accounts']}, recursive=True, list_merge='replace')
        settings = merge_hash(settings, job['hostOverride'], recursive=True, list_merge='replace')
        settings = account_policies(settings, [defaults['defaults'], job['slot'].get('overrides', {}),
            instance.get('overrides', {}), {'accounts': instance.get('accounts', {})}, job['hostOverride']])
        exports = {} if job['skipConnectionTopology'] else next(
            row['providedConnections'] for row in task_vars['platform_application_connection_rows']
            if row['libraryId'] == job['libraryId'])
        row = {
            'libraryId': job['libraryId'], 'libraryRef': deployment['libraryRef'], 'slotId': job['slotId'],
            'startupPriority': job['slot'].get('start_priority', 100),
            'instanceId': task_vars['application_instance_id'],
            'instanceIdStrategy': job['library']['definition'].get('instance_id_strategy', 'qualified'),
            'applicationName': task_vars['application_name'], 'applicationVersion': job['application']['version'],
            'hostId': job['hostId'], 'runtimeRef': deployment['runtimeRef'],
            'runtimeDirectory': deployment.get('runtime_directory') or metadata.get('runtime_directory', '~/' + job['libraryId']),
            'libraryConnections': metadata.get('connections', {}), 'providedConnections': exports,
            'bindings': deployment.get('bindings', {}),
            'vaultRef': {'binding': 'secrets'} if 'secrets' in deployment.get('bindings', {}) else deployment.get('vault_ref', {}),
            'registryCredentials': deployment.get('registry_credentials', {}),
            'resources': task_vars['_application_resources'], 'resourceDefaults': resource_defaults,
            'sharedSecrets': dict(metadata.get('shared_secrets', {}), **deployment.get('shared_secrets', {})),
            'connectionDefaults': merge_hash(metadata.get('connection_defaults', {}), deployment.get('connection_defaults', {}),
                                              recursive=True, list_merge='replace'),
            'connections': task_vars['_application_connections'], 'identityNames': defaults['identity_names'],
            'packageIdentity': {'application': job['application']['digest'], 'library': job['library']['digest']},
            'libraryScripts': job['library'].get('scripts', []), 'applicationScripts': job['application'].get('scripts', []),
            'commonDefaults': merge_hash(shared['defaults'], shared['overrides'], recursive=True, list_merge='replace'),
            'inherited': {name: inherited.get(name, {}) for name in ('environment', 'parameters')},
            'settings': settings,
        }
        return dict(changed=False, row=row, inherited=inherited)

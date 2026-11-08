"""Validate local package closure before Ansible loads/expands its defaults."""
import os
import copy
import json

from jinja2 import Environment, nodes

from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleError
from ansible.template import AnsibleNativeEnvironment, Templar
from ansible.utils.vars import merge_hash
from ansible.utils.unsafe_proxy import wrap_var
from ansible_collections.platform.core.plugins.module_utils.application_libraries import prepare, finding, account_policies
from ansible_collections.platform.core.plugins.module_utils.project_snapshot_output import snapshot_input_message
from ansible_collections.platform.core.plugins.module_utils.project_resolution import pure_templates


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def _native_templar(self, variables):
        # copy_with_new_env retains globals bound to the source Templar. Start
        # with the intended scope so lookup/template cannot deepcopy another
        # placement's internal jobs/results through those bound methods.
        return Templar(loader=self._loader, variables=variables).copy_with_new_env(
            environment_class=AnsibleNativeEnvironment)

    @staticmethod
    def _placement_variables(task_vars):
        payloads = {'_application_inputs', '_project_resolution_cache', '_application_resolved',
                    '_library_resolved_defaults', 'platform_project_resolution',
                    'platform_image_snapshot', 'platform_application_rows',
                    'application_group', '_application_group_result'}
        memo = {}

        def scoped(values):
            if id(values) in memo:
                return memo[id(values)]
            result = {}
            memo[id(values)] = result
            for key, value in values.items():
                if key in payloads or key.startswith(('_application_resolved_row_', '_application_resolved_group_')):
                    continue
                result[key] = scoped(value) if key in ('vars', 'ansible_facts') and isinstance(value, dict) else value
            return result

        return scoped(task_vars)

    def run(self, tmp=None, task_vars=None):
        task_vars = task_vars or {}
        args = self._task.args
        if args.get('placements'):
            rows, findings, contexts = [], [], {}
            metrics = dict(instances=0, placements=0, libraryContexts=0, rendered=0, reused=0)
            for group in task_vars['_application_inputs']['placement_groups']:
                result = self._placement_group(dict(task_vars, application_group=group, _library_resolved_defaults=contexts))
                rows.extend(result['rows'])
                findings.extend(result['findings'])
                contexts = result['library_contexts']
                metrics['instances'] += 1
                for key, value in result['metrics'].items():
                    metrics[key] += value
            return dict(changed=False, rows=rows, findings=findings, library_contexts=contexts, metrics=metrics)
        if args.get('placement_group'):
            return self._placement_group(task_vars)
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
        if args.get('placement') or args.get('application_defaults') or args.get('application_parameters'):
            try:
                return self._application_values(args, task_vars)
            except (ValueError, OSError, KeyError, TypeError, AnsibleError) as error:
                job = task_vars.get('application_job', {})
                context = {key: job.get(key) for key in ('libraryId', 'slotId', 'hostId')}
                diagnostic = finding('APPLICATION_INPUT_INVALID', 'applicationLibraryDeployments')
                diagnostic['safeMessage'] = snapshot_input_message('application-settings', error, context)
                return dict(failed=True, finding=diagnostic, changed=False)
        if args.get('shared_defaults') or args.get('resource_defaults') or args.get('provided_connections'):
            try:
                return self._library_values(args, task_vars)
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
        groups = []
        for job in result['jobs']:
            if job['connections'] is None:
                continue
            if not groups or (groups[-1][0]['libraryId'], groups[-1][0]['slotId']) != (job['libraryId'], job['slotId']):
                groups.append([])
            groups[-1].append(job)
        return dict(result, placement_groups=groups, changed=False)

    def _application_values(self, args, task_vars, memo=None):
        defaults_path = args.get('defaults_path') or task_vars['application_job']['application']['defaultsPath']
        definition = self._loader.load_from_file(defaults_path)['platform_application_definition']
        defaults = definition['defaults']
        variables = self._placement_variables(task_vars)
        if args.get('placement') or args.get('application_parameters'):
            job = task_vars['application_job']
            shared = task_vars['_application_shared']
            inherit = job['slot'].get('inherit_defaults', True)
            layers = [shared['defaults'].get('parameters', {}) if inherit else {},
                      defaults.get('parameters', {}), job['slot'].get('overrides', {}).get('parameters', {}),
                      shared['overrides'].get('parameters', {}) if inherit else {},
                      job['instance'].get('overrides', {}).get('parameters', {}),
                      job['hostOverride'].get('parameters', {})]
            seed = {}
            for layer in layers:
                seed = merge_hash(seed, layer, recursive=True, list_merge='replace')
            # Match the provisional set_fact context before resolving
            # typed parameters. Do not render unrelated ENV here.
            self._bind_context(variables, {'application_parameters': wrap_var(seed)})
            templar = self._native_templar(variables)
            layers[1] = self._render_common(defaults.get('parameters', {}), templar, variables, memo)
            parameters = {}
            for layer in layers:
                parameters = merge_hash(parameters, layer, recursive=True, list_merge='replace')
            if not args.get('placement'):
                return dict(parameters=parameters, changed=False)
            self._bind_context(variables, {'application_parameters': wrap_var(parameters)})
        templar = self._native_templar(variables)
        rendered = dict(defaults=self._render_common(defaults, templar, variables, memo), identity_names=definition.get('identity_environment', []), changed=False)
        if not args.get('placement'):
            return rendered
        variables['_application_defaults'] = rendered
        result = self._resolved_row(args, variables)
        result['parameters'] = parameters
        return result

    def _library_values(self, args, task_vars):
        variables = dict(task_vars)
        variables.update(task_vars['hostvars'].raw_get(args['host_id']))
        variables = self._placement_variables(variables)
        for name in list(variables):
            if name.startswith(('application_', '_application_', '_library_')) or name in ('hostvars', 'vars', 'ansible_facts', 'library_runtime', 'library_resources', 'platform_application_rows', 'platform_application_findings'):
                variables.pop(name)
        variables['library_instance_id'] = args['library_id']
        if args.get('shared_defaults'):
            variables['library_resources'] = task_vars['library_resources']
        templar = self._native_templar(variables)
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

    @staticmethod
    def _bind_context(variables, values):
        variables.update(values)
        for namespace in ('vars', 'ansible_facts'):
            if isinstance(variables.get(namespace), dict) and variables[namespace] is not variables:
                variables[namespace].update({k: v for k, v in values.items() if namespace == 'vars' or k != 'application_job'})

    @staticmethod
    def _literal_input(value):
        """A bounded proof for already typed data, not a Jinja dependency resolver."""
        unsafe = bool(getattr(value, '__UNSAFE__', False))
        if isinstance(value, str):
            if any(marker in value for marker in ('{{', '{%', '{#', '#jinja2')):
                raise ValueError('Unresolved dependency')
            return ['string', unsafe, value]
        if value is None or type(value) in (bool, int, float):
            return [type(value).__name__, unsafe, value]
        if isinstance(value, list):
            return ['list', unsafe, [ActionModule._literal_input(v) for v in value]]
        if isinstance(value, dict):
            # Preserve insertion order: native dict2items/join may observe it.
            return ['dict', unsafe, [[ActionModule._literal_input(k), ActionModule._literal_input(v)]
                                     for k, v in value.items()]]
        raise ValueError('Unknown dependency type')

    def _render_common(self, value, templar, variables, memo):
        if memo is None or hasattr(value, '__UNSAFE__'):
            return templar.template(value)
        if isinstance(value, dict):
            return {key: self._render_common(item, templar, variables, memo) for key, item in value.items()}
        if isinstance(value, list):
            return [self._render_common(item, templar, variables, memo) for item in value]
        if not isinstance(value, str) or not templar.is_possibly_template(value):
            return templar.template(value)
        allowed = {'application_instance_id', 'application_name', 'library_instance_id',
                   'application_parameters', 'application_connections', 'application_databases',
                   'application_topics', 'application_placements', 'platform_name_prefix',
                   'platform_data_root_directory'}
        if value not in memo['expressions']:
            names = None
            if '#jinja2' not in value and pure_templates(value):
                tree = Environment().parse(value)
                used = {node.name for node in tree.find_all(nodes.Name)}
                methods = any(any(callable(getattr(kind, node.attr, None)) for kind in (str, dict, list, tuple, int, float))
                              for node in tree.find_all(nodes.Getattr))
                # Even a familiar short filter name can be overridden by a
                # project plugin. Keep filters/tests on the fresh native path.
                if used <= allowed and not methods and not any(tree.find_all((nodes.For, nodes.Assign, nodes.Filter, nodes.Test))):
                    names = sorted(used)
            memo['expressions'][value] = names
        names = memo['expressions'][value]
        key = None
        if names is not None:
            try:
                key = (value, json.dumps([self._literal_input(variables[name]) for name in names], ensure_ascii=False))
            except (KeyError, TypeError, ValueError, RecursionError):
                pass  # Unknown/transitive/dynamic inputs retain fresh native rendering.
        if key is not None and key in memo['values']:
            memo['reused'] += 1
            return copy.deepcopy(memo['values'][key])
        result = templar.template(value)
        memo['rendered'] += 1
        if key is not None:
            try:
                self._literal_input(result)
                memo['values'][key] = copy.deepcopy(result)
            except (TypeError, ValueError, RecursionError):
                pass
        return result

    def _library_context(self, job, variables, contexts):
        key = job['libraryId'] + '/' + job['hostId']
        if key not in contexts:
            args = dict(library_id=job['libraryId'], host_id=job['hostId'], defaults_path=job['library']['defaultsPath'])
            defaults = self._library_values(dict(args, resource_defaults=True), variables)['resource_defaults']
            sections = {'kafka.topic': ('kafka', 'topics'), 'postgresql.database': ('postgresql', 'databases'),
                        'clickhouse.database': ('clickhouse', 'databases'), 'redis.key': ('redis', 'keys')}
            resources = {}
            for name, resource in self._native_templar(variables).template(job['deployment'].get('resources', {})).items():
                section = sections.get(resource['kind'])
                base = defaults.get(section[0], {}).get(section[1], {}).get(name, {}) if section else {}
                resources[name] = dict(resource, parameters=merge_hash(base, resource['parameters'], recursive=True, list_merge='replace'))
            shared = self._library_values(dict(args, shared_defaults=True), dict(variables, library_resources=resources))
            contexts[key] = dict(resourceDefaults=defaults, resources=resources, shared=shared)
        return copy.deepcopy(contexts[key])

    def _placement_group(self, task_vars):
        contexts = dict(task_vars.get('_library_resolved_defaults', {}))
        initial_contexts = len(contexts)
        rows, findings = [], []
        memo = dict(values={}, expressions={}, rendered=0, reused=0)
        for source_job in task_vars['application_group']:
            stage = 'library-defaults'
            job = copy.deepcopy(source_job)
            try:
                variables = copy.deepcopy(self._placement_variables(task_vars))
                for space in (variables, variables.get('vars'), variables.get('ansible_facts')):
                    if isinstance(space, dict):
                        for name in list(space):
                            if name.startswith(('application_', '_application_')):
                                space.pop(name)
                bindings = dict(application_job=job, application_name=job['application']['name'],
                    application_instance_id=job['instanceId'], library_instance_id=job['libraryId'],
                    application_placements=task_vars['_application_connection_inputs']['placements'].get(
                        job['libraryId'], {}).get(job['slotId'], []), application_connections={},
                    application_topics={}, application_databases={}, _application_connections=job['connections'])
                self._bind_context(variables, bindings)
                local = self._library_context(job, variables, contexts)
                bindings.update(_application_resources=local['resources'], library_resources=local['resources'],
                    _application_resource_defaults=local['resourceDefaults'], _application_shared=local['shared'])
                endpoint = job['deployment'].get('bindings', {}).get('endpoint', {}).get('endpointGroupRef',
                    task_vars['platform_desired_state'].get('x-applicationLibraryEndpointGroups', {}).get(job['libraryId'], ''))
                bindings['_application_library_endpoint'] = {'endpoint_group': endpoint} if endpoint else {}
                stage = 'application-settings'
                for name, connection in job['connections'].items():
                    ref = job['deployment'].get('bindings', {}).get(connection.get('library_binding'), {}).get('providedConnectionRef')
                    if ref is not None:
                        bindings['application_connections'][name] = task_vars['platform_application_provided_connections'].get(
                            ref['libraryId'], {}).get(ref['name'], {})
                self._bind_context(variables, bindings)
                topic_bindings = {}
                for layer in (local['shared']['defaults'] if job['slot'].get('inherit_defaults', True) else {},
                              job['application']['definition'].get('defaults', {}), job['slot'].get('overrides', {}),
                              local['shared']['overrides'] if job['slot'].get('inherit_defaults', True) else {},
                              job['instance'].get('overrides', {}), job['hostOverride']):
                    topic_bindings = merge_hash(topic_bindings, layer.get('topicBindings', {}), recursive=True, list_merge='replace')
                topic_bindings = self._native_templar(variables).template(topic_bindings)
                for name, connection in job['connections'].items():
                    binding = connection.get('library_binding')
                    for resource_id, resource in local['resources'].items():
                        kind = resource['kind']
                        if binding is None or kind not in ('kafka.topic', 'postgresql.database', 'clickhouse.database'):
                            continue
                        selected = (kind != 'kafka.topic' and resource['binding'] == binding) or (
                            resource['binding'] in job['deployment'].get('bindings', {}) and binding in job['deployment']['bindings']
                            and job['deployment']['bindings'][resource['binding']].get('deploymentRef', '') ==
                            job['deployment']['bindings'][binding].get('deploymentRef', ''))
                        if selected:
                            target = bindings['application_topics' if kind == 'kafka.topic' else 'application_databases']
                            target.setdefault(name, {})[resource_id] = dict(resourceId=resource_id, name=resource['parameters']['name'])
                for name, roles in topic_bindings.items():
                    if not isinstance(roles, dict):
                        continue
                    for role, resource_id in roles.items():
                        resource = local['resources'][resource_id]
                        declared = job['deployment']['bindings']
                        if (resource['kind'] != 'kafka.topic' or not resource['parameters'].get('name') or
                                declared[resource['binding']]['deploymentRef'] != declared[job['connections'][name]['library_binding']]['deploymentRef']):
                            raise ValueError('Invalid Kafka topic role')
                        bindings['application_topics'].setdefault(name, {})[role] = dict(resourceId=resource_id, name=resource['parameters']['name'])
                # Match current set_fact/loop namespaces without leaking another host's context.
                self._bind_context(variables, bindings)
                namespace = self._native_templar(variables).template(
                    "_library_package_{{ [application_job.libraryId, application_job.hostId] | to_json | hash('sha256') }}")
                resolved = self._application_values(dict(placement=True, library_namespace=namespace), variables, memo)
                rows.append(resolved['row'])
            except (ValueError, OSError, KeyError, TypeError, AnsibleError) as error:
                diagnostic = finding('APPLICATION_INPUT_INVALID',
                    'applicationLibraryDeployments.%s.applications.%s.placements.%s' % (job['libraryId'], job['slotId'], job['hostId']))
                diagnostic['safeMessage'] = snapshot_input_message(stage, error, {k: job[k] for k in ('libraryId', 'slotId', 'hostId')})
                findings.append(diagnostic)
        return dict(changed=False, rows=rows, findings=findings, library_contexts=contexts,
                    metrics=dict(placements=len(task_vars['application_group']), libraryContexts=len(contexts)-initial_contexts,
                                 rendered=memo['rendered'], reused=memo['reused']))

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
        variables = self._placement_variables(dict(task_vars, application_inherited=inherited))
        templar = self._native_templar(variables)
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

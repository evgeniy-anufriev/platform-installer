"""Validate Core-owned values from the native Compose JSON projection."""
import json
from posixpath import commonpath, dirname, isabs
import re
from pathlib import Path

from ansible.errors import AnsibleFilterError
from ansible.parsing.dataloader import DataLoader
from ansible.plugins.loader import filter_loader, test_loader
from jinja2 import Environment, TemplateError, nodes
from ansible_collections.platform.core.plugins.module_utils.application_libraries import account_policies
from ansible_collections.platform.core.plugins.module_utils.application_runtime import validate_compose, validate_config_contents, selected_archive, pinned_registry_reference, agent_config, validate_agent


def selected_archive_path(root, source, offline):
    return selected_archive(root, source, offline, DataLoader().load_from_file)


def parent_paths(paths):
    result = set()
    for path in paths:
        current = ''
        for part in path.split('/'):
            if part:
                current += '/' + part
                result.add(current)
    return sorted(result)


def application_runtime_root(directory, home):
    return home + directory[1:] if directory == '~' or directory.startswith('~/') else directory


def preflight_library_roots(jobs, discoveries):
    homes = {item['account']: item['home'] for item in discoveries.values()}
    roots = {}
    for job in jobs:
        path = application_runtime_root(job['placement']['runtimeDirectory'], homes[job['account']])
        roots[job['libraryId'], path] = dict(libraryId=job['libraryId'], libraryPath=path)
    by_path = {}
    for library, path in roots:
        if path in by_path and by_path[path] != library:
            raise AnsibleFilterError('APPLICATION_LIBRARY_PATH_OVERLAP')
        by_path[path] = library
    for path, library in by_path.items():
        parent = dirname(path)
        while parent and parent != '/':
            if parent in by_path and by_path[parent] != library:
                raise AnsibleFilterError('APPLICATION_LIBRARY_PATH_OVERLAP')
            parent = dirname(parent)
    return list(roots.values())


def preflight_template_contexts(jobs, libraries):
    contexts = []
    for job in jobs:
        library = libraries[job['libraryId']]
        instance = library['instances'][job['instanceId']]
        contexts.append(dict(
            identity_environment=instance['identityEnvironment'],
            connections=instance['connections'],
            topics=instance.get('topics', {}),
            library_connections=library.get('connections') or instance['connections'],
        ))
    return contexts


def shared_render_literal(value):
    if isinstance(value, str):
        return not any(marker in value for marker in ('{{', '{%', '{#', '#jinja2'))
    if isinstance(value, dict):
        return all(shared_render_literal(key) and shared_render_literal(item) for key, item in value.items())
    if isinstance(value, (tuple, list)):
        return all(shared_render_literal(item) for item in value)
    return value is None or type(value) in (bool, int, float)


def template_inputs(body, bound=()):
    """Track names read before assignment in the supported Jinja scopes."""
    bound = set(bound)
    inputs = set()

    def names(node):
        return {node.name} if isinstance(node, nodes.Name) else {item.name for item in node.find_all(nodes.Name)}

    for statement in body:
        if isinstance(statement, nodes.Assign) and isinstance(statement.target, nodes.Name):
            inputs.update(names(statement.node) - bound)
            bound.add(statement.target.name)
        elif isinstance(statement, nodes.Output):
            inputs.update(names(statement) - bound)
        elif isinstance(statement, nodes.If):
            inputs.update(names(statement.test) - bound)
            inputs.update(template_inputs(statement.body, bound))
            inputs.update(template_inputs(statement.elif_, bound))
            inputs.update(template_inputs(statement.else_, bound))
        elif isinstance(statement, nodes.For) and not statement.recursive:
            inputs.update(names(statement.iter) - bound)
            loop_bound = bound | names(statement.target)
            if statement.test is not None:
                inputs.update(names(statement.test) - loop_bound)
            inputs.update(template_inputs(statement.body, loop_bound | {'loop'}))
            inputs.update(template_inputs(statement.else_, bound))
        else:
            raise ValueError('Unsupported shared template statement')
    return inputs


def shared_base_template(text, literal_peers):
    """Recognize the closed subset used by shared library templates."""
    if '#jinja2' in text:
        return False
    env = Environment()
    filters = {'combine', 'default', 'join', 'list', 'reject', 'sort', 'string', 'to_json'}
    try:
        tree = env.parse(text)
        names = template_inputs(tree.body)
    except (TemplateError, ValueError, RecursionError):
        return False
    if names - {'library_runtime', 'inventory_hostname', 'groups', 'hostvars'}:
        return False
    if any(tree.find_all(nodes.Test)):
        return False
    if any(item.attr.startswith('_') for item in tree.find_all(nodes.Getattr)):
        return False
    if any(item.name not in filters or (item.name == 'reject' and (
            len(item.args) != 2 or not isinstance(item.args[0], nodes.Const) or
            item.args[0].value != 'equalto')) for item in tree.find_all(nodes.Filter)):
        return False
    for name in {item.name for item in tree.find_all(nodes.Filter)}:
        if not builtin_jinja_plugin(filter_loader, name, env.filters):
            return False
        if name == 'reject' and not builtin_jinja_plugin(test_loader, 'equalto', env.tests):
            return False
    assignments = list(tree.find_all(nodes.Assign))
    writes = [item.name for item in tree.find_all(nodes.Name) if item.ctx == 'store']
    locals_ = {item.target.name: item.node for item in assignments
               if isinstance(item.target, nodes.Name) and writes.count(item.target.name) == 1}
    if any(name in writes for name in ('hostvars', 'library_runtime', 'groups', 'inventory_hostname')):
        return False
    for call in tree.find_all(nodes.Call):
        method = call.node
        if not isinstance(method, nodes.Getattr) or call.kwargs or call.dyn_args or call.dyn_kwargs:
            return False
        receiver = method.node
        value = locals_.get(receiver.name) if isinstance(receiver, nodes.Name) else receiver
        copied_dict = (isinstance(value, nodes.Filter) and value.name == 'combine' and
                       len(value.args) == 1 and isinstance(value.args[0], nodes.Dict))
        if method.attr == 'items' and (isinstance(value, nodes.Dict) or copied_dict) and not call.args:
            continue
        if method.attr in ('append', 'index') and len(call.args) == 1 and (
                isinstance(value, nodes.List) or isinstance(value, nodes.Filter) and value.name in ('sort', 'list')):
            continue
        if method.attr == 'update' and len(call.args) == 1 and copied_dict:
            continue
        return False
    if 'hostvars' not in names:
        return True
    if not literal_peers:
        return False

    def peer_index(item):
        return isinstance(item, nodes.Getitem) and isinstance(item.node, nodes.Name) and item.node.name == 'hostvars'

    aliases = {name for name, item in locals_.items() if peer_index(item)}
    allowed = {id(item.node) for item in locals_.values() if peer_index(item)}
    allowed_aliases = set()
    for item in tree.find_all(nodes.Getattr):
        if item.attr in ('ansible_host', 'platform_host'):
            if peer_index(item.node):
                allowed.add(id(item.node.node))
            if isinstance(item.node, nodes.Name) and item.node.name in aliases:
                allowed_aliases.add(id(item.node))
    return all((item.name != 'hostvars' or id(item) in allowed) and
               (item.name not in aliases or item.ctx == 'store' or id(item) in allowed_aliases)
               for item in tree.find_all(nodes.Name))


def builtin_jinja_plugin(loader, name, jinja_defaults):
    try:
        active = loader.get(name)
    except KeyError:
        active = None
    if active is None:
        return name in jinja_defaults
    builtin = loader.get('ansible.builtin.' + name)
    return builtin is not None and active.j2_function is builtin.j2_function


def preflight_shared_templates(jobs, hostvars):
    # Only raw literal inventory values can be shared across placements.
    literal_peers = hasattr(hostvars, 'raw_get') and all(
        shared_render_literal(peer.get(field))
        for peer in map(hostvars.raw_get, hostvars) for field in ('ansible_host', 'platform_host'))
    templates = {}
    for path in {job['baseTemplate'] for job in jobs}:
        try:
            templates[path] = shared_base_template(Path(path).read_text(encoding='utf-8'), literal_peers)
        except (OSError, UnicodeError):
            templates[path] = False  # Let the native lookup report the failure.
    return dict(base=templates, env=literal_peers)


def preflight_host_inputs(jobs, libraries, hostvars):
    shared = preflight_shared_templates(jobs, hostvars)
    hosts, base_keys, env_keys = {}, {}, {}
    for index, (job, context) in enumerate(zip(jobs, preflight_template_contexts(jobs, libraries))):
        host, library = job['hostId'], job['libraryId']
        base_key = env_key = ''
        if shared['base'][job['baseTemplate']]:
            library_runtime = dict(defaults=job.get('commonDefaults', {}), library_id=library,
                                   host_id=host, connections=context['library_connections'])
            try:
                inputs = json.dumps([job['baseTemplate'], library_runtime], ensure_ascii=False)
            except (TypeError, ValueError, RecursionError):
                pass  # Unusual native values retain the ordinary template lookup.
            else:
                if inputs not in base_keys:
                    base_keys[inputs] = f'base-{len(base_keys)}' if shared_render_literal(inputs) else ''
                base_key = base_keys[inputs]
        if shared['env']:
            env_key = env_keys.setdefault((library, job['envSource']), f'env-{len(env_keys)}')
        hosts.setdefault(host, []).append(dict(
            index=index, account=job['account'], libraryId=library,
            projectId=job['projectId'], instanceId=job['instanceId'], placement={
                key: job['placement'][key] for key in ('runtimeDirectory', 'runtimePath', 'containerName')},
            baseFilename=job['baseFilename'], configs=[{'destination': row['destination']} for row in job['configs']],
            directoryConfigs=[{'destination': row['destination']} for row in job['directoryConfigs']],
            archiveConfigs=[{'destination': row['destination']} for row in job['archiveConfigs']],
            template_context=context, base_key=base_key, env_key=env_key,
        ))
    return hosts


def preflight_source_jobs(hostvars, indices):
    # The registered Core output is already calculated. Index it before Ansible
    # templates the selected job, so resolving one job does not walk every row.
    jobs = hostvars.raw_get('localhost')['application_runtime_inputs']['jobs']
    return [jobs[index] for index in indices]


def preflight_paths(job, root, home):
    if (not re.fullmatch(r'/[a-zA-Z0-9_./-]+', home) or
            not re.fullmatch(r'/[a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)*', root) or
            {'.', '..'}.intersection(root.split('/')) or root == home):
        raise AnsibleFilterError('APPLICATION_RUNTIME_ROOT_INVALID')
    instance = root + '/' + job['placement']['runtimePath']
    config_root = instance + '/config/'
    files = [config_root + item['destination'] for item in job['configs']]
    directories = [config_root + item['destination']
                   for item in job['directoryConfigs'] + job['archiveConfigs']]
    return dict(parents=parent_paths([root, instance + '/config'] +
                                    [dirname(path) for path in files + directories]),
                markers=[root + '/.owner.json', instance + '/.owner.json'],
                files=[root + '/.env', root + '/' + job['baseFilename'], instance + '/compose.yml'] + files,
                directories=directories)


def preflight_observation_inputs(jobs, discoveries):
    accounts = {item['account']: item for item in discoveries.values()}
    checks = []
    for job in jobs:
        account = accounts[job['account']]
        root = application_runtime_root(job['placement']['runtimeDirectory'], account['home'])
        checks.append(dict(preflight_paths(job, root, account['home']), root=root,
                           instance_path=root + '/' + job['placement']['runtimePath'], uid=account['uid'],
                           project=job['projectId'], library=job['libraryId'], instance=job['instanceId']))
    return checks


def preflight_validate_observations(checks, host, observed):
    states, markers = observed['paths'], observed['markers']
    for check in checks:
        root, uid = check['root'], str(check['uid'])
        for path in check['parents']:
            state = states[path]
            if state.get('islnk') or (state['exists'] and
                    (not state['isdir'] or (path.startswith(root) and str(state['uid']) != uid))):
                raise AnsibleFilterError('APPLICATION_RUNTIME_PATH_OWNERSHIP_INVALID')
        for path in check['markers']:
            state, parent = states[path], dirname(path)
            expected = dict(project=check['project'], library=check['library'], host=host)
            if parent != root:
                expected['instance'] = check['instance']
            if ((states[parent]['exists'] and not state.get('isreg')) or state.get('islnk') or
                    (state['exists'] and any(markers.get(path, {}).get(key) != value
                                             for key, value in expected.items()))):
                raise AnsibleFilterError('APPLICATION_DIRECTORY_OWNERSHIP_INVALID')
        files, directories = set(check['files']), set(check['directories'])
        for path in files | directories:
            state = states[path]
            if state.get('islnk') or (state['exists'] and (
                    not state['isdir' if path in directories else 'isreg'] or
                    str(state['uid']) != uid or path in files & directories)):
                raise AnsibleFilterError('APPLICATION_RUNTIME_FILE_OWNERSHIP_INVALID')
    return True


def bind_sources_changed(sources, changed_paths):
    for source in sources:
        if not isabs(source):
            continue
        for changed in changed_paths:
            if isabs(changed) and commonpath((source, changed)) in (source, changed):
                return True
    return False


def application_owned_container(output, job, host):
    labels = json.loads(output)[0]['Config'].get('Labels') or {}
    return owned_labels(labels, job, host)


def owned_labels(labels, job, host):
    return all(labels.get('platform.installer.' + key) == expected for key, expected in (
        ('project', job['projectId']), ('library', job['libraryId']),
        ('instance', job['instanceId']), ('host', host)))


def preflight_ports(jobs, discoveries, host):
    containers = {entry['account']: {row[0].lstrip('/'): row[1:]
                  for row in map(json.loads, entry.get('containerDetails', []))}
                  for entry in discoveries.values()}
    pending = {}
    for job in jobs:
        name = job['placement']['containerName']
        detail = containers[job['account']].get(name)
        owned = set()
        if detail is not None:
            labels, running, bindings = detail
            if not owned_labels(labels or {}, job, host):
                raise AnsibleFilterError('APPLICATION_CONTAINER_OWNERSHIP_INVALID: ' + name)
            if running:
                owned = {str(row['HostPort']) for rows in (bindings or {}).values() for row in (rows or [])}
        for port in job['settings'].get('ports', {}).values():
            published = str(port['published'])
            if published not in owned:
                pending.setdefault(published, []).append(name)
    return pending


class FilterModule(object):
    def filters(self):
        return {"application_agent_config": agent_config, "application_validate_agent": validate_agent, "application_validate_compose": validate_compose, "application_parent_paths": parent_paths,
                "application_runtime_root": application_runtime_root, "application_preflight_paths": preflight_paths,
                "application_preflight_library_roots": preflight_library_roots,
                "application_preflight_template_contexts": preflight_template_contexts,
                "application_preflight_shared_templates": preflight_shared_templates,
                "application_preflight_host_inputs": preflight_host_inputs,
                "application_preflight_ports": preflight_ports,
                "application_preflight_source_jobs": preflight_source_jobs,
                "application_preflight_observation_inputs": preflight_observation_inputs,
                "application_preflight_validate_observations": preflight_validate_observations,
                "application_bind_sources_changed": bind_sources_changed,
                "application_validate_configs": validate_config_contents, "application_account_policies": account_policies,
                "application_selected_archive": selected_archive_path,
                "application_pinned_registry_reference": pinned_registry_reference,
                "application_owned_container": application_owned_container}

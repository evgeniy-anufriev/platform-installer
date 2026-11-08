"""Private desired-only result reuse; never a source of desired state."""
import copy
import hashlib
import json
import os
import tempfile

from jinja2 import Environment, nodes
import yaml

from .project_snapshot import project_documents
from .project_validation import canonical_digest
from .application_runtime import resolve_image_lock

VERSION = 'platform.installer/private-project-resolution/v1alpha2'
FIELDS = ('snapshot', 'pki_materialization', 'application_image_lock',
          'execution_configuration', 'execution_connections')
# Eligibility only: unsupported expressions still resolve normally in Ansible.
# In particular no lookup implementation or alternate precedence exists here.
PURE_FILTERS = frozenset(('default', 'd', 'combine', 'dict2items', 'items2dict',
    'sort', 'unique', 'list', 'join', 'replace', 'regex_replace', 'int', 'float',
    'bool', 'string', 'lower', 'upper', 'length', 'first', 'last', 'split', 'trim',
    'basename', 'dirname', 'quote', 'urlencode', 'hash', 'b64encode', 'b64decode',
    'ternary', 'to_json', 'to_nice_json', 'from_json', 'to_yaml', 'from_yaml',
    'map', 'selectattr', 'rejectattr', 'select', 'reject', 'extract', 'flatten',
    'zip', 'dictsort', 'regex_search', 'regex_findall', 'urlsplit', 'mandatory'))
PURE_TESTS = frozenset(('defined', 'undefined', 'none', 'string', 'number',
    'mapping', 'sequence', 'iterable', 'boolean', 'true', 'false', 'equalto',
    'eq', 'ne', 'in', 'match', 'search', 'gt', 'ge', 'lt', 'le'))
CONTEXT_NAMES = frozenset(('vars', 'environment', 'inventory_dir', 'playbook_dir',
    'inventory_file', 'role_path', 'ansible_search_path', 'ansible_inventory_sources',
    'ansible_env', 'ansible_facts', 'ansible_date_time'))
# Only these resolver-owned data contexts may participate in project-local
# lookups. Unknown globals retain the ordinary fresh Ansible path.
DATA_NAMES = frozenset(('application_job', 'application_connections',
    'application_databases', 'application_topics', 'application_parameters',
    'application_placements', 'application_instance_id', 'library_instance_id', 'library_resources',
    '_application_shared', '_application_library_endpoint', 'hostvars', 'groups', 'inventory_hostname', 'platform_desired_state',
    'platform_application_provided_connections', 'platform_project_root',
    'platform_name_prefix', 'platform_data_root_directory'))


def _local_lookup(call, project, source, documents, visiting):
    if (not isinstance(call.node, nodes.Name) or call.node.name != 'lookup'
            or len(call.args) != 2 or call.dyn_args or call.dyn_kwargs
            or not isinstance(call.args[0], nodes.Const)
            or call.args[0].value not in ('ansible.builtin.file', 'ansible.builtin.template')
            or any(item.key != 'convert_data' or not isinstance(item.value, nodes.Const)
                   or item.value.value is not False for item in call.kwargs)):
        return False
    path = call.args[1]
    if not isinstance(path, nodes.Concat) or len(path.nodes) != 2:
        return False
    base, suffix = path.nodes
    if (not isinstance(suffix, nodes.Const) or not isinstance(suffix.value, str)
            or not suffix.value.startswith('/')):
        return False
    if isinstance(base, nodes.Name) and base.name == 'platform_project_root':
        base_path = project
    elif (isinstance(base, nodes.Filter) and base.name == 'dirname' and not base.args
          and not base.kwargs and not base.dyn_args and not base.dyn_kwargs
          and isinstance(base.node, nodes.Getattr) and base.node.attr == 'defaultsPath'
          and isinstance(base.node.node, nodes.Getattr) and base.node.node.attr == 'application'
          and isinstance(base.node.node.node, nodes.Name) and base.node.node.node.name == 'application_job'
          and os.path.relpath(source, project).replace(os.sep, '/').startswith('application-packages/')
          and '/roles/' in source.replace(os.sep, '/') and source.endswith('/defaults/main.yml')):
        base_path = os.path.dirname(source)
    else:
        return False
    # Walk before normalization too: link/../file must not hide a symlink.
    current = base_path
    for part in suffix.value.split('/'):
        current = os.path.abspath(os.path.join(current, part))
        if (os.path.commonpath((project, current)) != project
                or os.path.islink(current) or not os.path.exists(current)):
            return False
    target = current
    relative = os.path.relpath(target, project)
    if relative.replace(os.sep, '/') not in documents or target in visiting:
        return False
    with open(target, encoding='utf-8') as stream:
        return pure_templates(stream.read(), project, target, documents, visiting | {target})


def pure_templates(text, project=None, source=None, documents=(), visiting=frozenset()):
    try:
        tree = Environment().parse(text)
    except Exception:
        return False
    assignments = list(tree.find_all(nodes.Assign))
    locals_ = {node.name for item in assignments
               for node in ([item.target] if isinstance(item.target, nodes.Name) else [])}
    loop_names = {node.name for item in tree.find_all(nodes.For)
                  for node in ([item.target] if isinstance(item.target, nodes.Name)
                               else item.target.find_all(nodes.Name))}
    locals_.update(loop_names)
    if project is not None and locals_ & (DATA_NAMES | {'lookup'}):
        return False
    unique = {name for name in locals_ - loop_names if sum(
        isinstance(item.target, nodes.Name) and item.target.name == name for item in assignments) == 1}
    lists = {item.target.name for item in assignments
             if isinstance(item.target, nodes.Name) and (isinstance(item.node, nodes.List)
                 or isinstance(item.node, nodes.Filter) and item.node.name in ('sort', 'list'))}
    lists &= unique
    dictionaries = {item.target.name for item in assignments
                    if isinstance(item.target, nodes.Name) and isinstance(item.node, nodes.Dict)}
    dictionaries &= unique
    path_nodes = set()
    for call in tree.find_all(nodes.Call):
        if project is None:
            return False
        method = call.node
        if (isinstance(method, nodes.Getattr) and not call.kwargs
                and not call.dyn_args and not call.dyn_kwargs):
            receiver = method.node
            while isinstance(receiver, (nodes.Getattr, nodes.Filter)):
                receiver = receiver.node
            if (method.attr == 'get' and isinstance(receiver, nodes.Name)
                    and receiver.name == '_application_shared'
                    and 1 <= len(call.args) <= 2):
                continue
            if (method.attr in ('append', 'index') and isinstance(method.node, nodes.Name)
                    and method.node.name in lists and len(call.args) == 1):
                continue
            if (method.attr == 'update' and isinstance(method.node, nodes.Name)
                    and method.node.name in dictionaries and len(call.args) == 1
                    and isinstance(call.args[0], nodes.Dict)):
                continue
        if not _local_lookup(call, project, source, documents, visiting):
            return False
        path_nodes.update(id(node) for node in call.args[1].find_all(nodes.Node))
    # A path hashed/trimmed into a scalar would evade the final absolute-path
    # check. Permit path-bearing contexts only at proved package lookup sites
    # or at the documented desired-data leaves used by application templates.
    data_nodes = set(path_nodes)
    for item in tree.find_all(nodes.Getattr):
        fields, base = [], item
        while isinstance(base, nodes.Getattr):
            fields.insert(0, base.attr)
            base = base.node
        if isinstance(base, nodes.Name) and base.name == 'application_job' and (
                fields[0] in ('hostId', 'slotId', 'libraryId', 'slot', 'instance', 'hostOverride')
                or fields[:2] in (['application', 'definition'], ['application', 'name'], ['application', 'version'])):
            data_nodes.add(id(base))
        if (item.attr == 'ansible_host' and isinstance(item.node, nodes.Getitem)
                and isinstance(item.node.node, nodes.Name) and item.node.node.name == 'hostvars'):
            data_nodes.add(id(item.node.node))
    if any(item.name in ('platform_project_root', 'application_job', 'hostvars')
           and id(item) not in data_nodes for item in tree.find_all(nodes.Name)):
        return False
    if project is not None and any(item.name not in DATA_NAMES | locals_ | {'lookup'}
                                   for item in tree.find_all(nodes.Name)):
        return False
    for kind in (nodes.Include, nodes.Import, nodes.FromImport, nodes.Extends):
        if any(tree.find_all(kind)):
            return False
    if any(item.name not in PURE_FILTERS for item in tree.find_all(nodes.Filter)):
        return False
    if any(item.name not in PURE_TESTS for item in tree.find_all(nodes.Test)):
        return False
    for item in tree.find_all(nodes.Filter):
        if item.name in ('map', 'select', 'reject') and item.args:
            allowed = PURE_FILTERS if item.name == 'map' else PURE_TESTS
            if not isinstance(item.args[0], nodes.Const) or item.args[0].value not in allowed:
                return False
        if item.name in ('selectattr', 'rejectattr') and len(item.args) > 1:
            if not isinstance(item.args[1], nodes.Const) or item.args[1].value not in PURE_TESTS:
                return False
    if any(item.name in CONTEXT_NAMES for item in tree.find_all(nodes.Name)):
        return False
    if any(item.name.startswith(('platform_execution_', 'platform_plan_', 'platform_runtime_'))
           and not (project is None and item.name == 'platform_execution_service_deployment')
           for item in tree.find_all(nodes.Name)):
        return False
    if project is None and any(item.name == 'platform_project_root' for item in tree.find_all(nodes.Name)):
        return False
    if any(item.attr in CONTEXT_NAMES or item.attr.startswith(('_', 'platform_execution_', 'platform_plan_', 'platform_runtime_'))
           for item in tree.find_all(nodes.Getattr)):
        return False
    if any(isinstance(item.value, str) and (item.value in CONTEXT_NAMES or item.value.startswith(('__', 'platform_execution_', 'platform_plan_', 'platform_runtime_')))
           for item in tree.find_all(nodes.Const)):
        return False
    return True


def identity(project, runtime, owned=()):
    documents, revision = project_documents(project, owned)
    inputs = [[item['logicalPath'], item['digest']] for item in documents]
    inventory = os.path.join(project, 'inventory/hosts.yml')
    return dict(version=VERSION, revision=revision, runtime=copy.deepcopy(runtime),
                inputDigest=canonical_digest(inputs), owned=sorted(owned),
                inventoryExecutable=os.path.isfile(inventory) and bool(os.stat(inventory).st_mode & 0o111)), documents


def _pure_document(text, **context):
    # Inspect actual YAML scalar values: doubled YAML quotes are not Jinja
    # escapes. This parses eligibility only, not Ansible precedence or values.
    try:
        pending = [yaml.safe_load(text)]
    except yaml.YAMLError:
        return False
    if (context.get('source') or '').endswith('/inventory/hosts.yml') and (
            not isinstance(pending[0], dict) or 'plugin' in pending[0]):
        return False
    visited = set()
    while pending:
        value = pending.pop()
        if isinstance(value, str):
            if not pure_templates(value, **context):
                return False
        elif isinstance(value, (dict, list)):
            if id(value) in visited:
                continue
            visited.add(id(value))
            pending.extend(value if isinstance(value, list) else list(value) + list(value.values()))
        elif value is not None and not isinstance(value, (bool, int, float)):
            return False
    return True


def reusable(project, documents, result, defaults_root):
    # Captured staging paths cannot be transplanted into a different request.
    if os.path.realpath(project) in json.dumps(result, ensure_ascii=False):
        return False
    closure = {item['logicalPath'] for item in documents}
    for document in documents:
        name = document['logicalPath']
        if not name.endswith(('.yml', '.yaml', '.json', '.cfg')):
            continue
        # Mounted configuration/templates are rendered during Apply, not resolve.
        if '/assets/' in name:
            continue
        if name == 'inventory/hosts.yml' and os.stat(os.path.join(project, name)).st_mode & 0o111:
            return False
        with open(os.path.join(project, name), encoding='utf-8') as stream:
            text = stream.read()
            context = dict(project=project, source=os.path.join(project, name), documents=closure)
            if not (_pure_document(text, **context) if name.endswith(('.yml', '.yaml', '.json'))
                    else pure_templates(text, **context)):
                return False
    # Service defaults are immutable bundle inputs, but may contain environment
    # lookups; such a runtime is ineligible for cross-request reuse as well.
    for directory, dirs, files in os.walk(defaults_root):
        dirs[:] = sorted(d for d in dirs if d not in ('_vendor', 'tests'))
        if os.path.basename(directory) != 'defaults':
            continue
        for name in sorted(files):
            if name.endswith(('.yml', '.yaml')):
                with open(os.path.join(directory, name), encoding='utf-8') as stream:
                    if not _pure_document(stream.read()):
                        return False
    return True


def read(path, expected):
    if not path or not os.path.isfile(path):
        return None
    with open(path, encoding='utf-8') as stream:
        envelope = json.load(stream)
    if not isinstance(envelope, dict):
        raise ValueError('PROJECT_RESOLUTION_INVALID')
    if envelope.get('version') != VERSION:
        return None
    if envelope.get('digest') != canonical_digest(envelope.get('result')):
        raise ValueError('PROJECT_RESOLUTION_INVALID')
    if envelope.get('identity') != expected:
        return None
    result = envelope['result']
    if not isinstance(result, dict) or any(not isinstance(result.get(k), dict) for k in FIELDS):
        raise ValueError('PROJECT_RESOLUTION_INVALID')
    if any(not isinstance(result.get(key, []), list) for key in ('application_rows', 'application_findings', 'application_pki_bindings')):
        raise ValueError('PROJECT_RESOLUTION_INVALID')
    if result['snapshot'].get('projectRevision') != expected['revision']:
        raise ValueError('PROJECT_RESOLUTION_INVALID')
    return result


def atomic_json(path, value):
    if not path:
        return
    directory = os.path.dirname(path)
    os.makedirs(directory, mode=0o700, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.resolution-', dir=directory)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write(path, expected, result):
    result = {key: copy.deepcopy(result[key]) for key in (*FIELDS, 'application_rows', 'application_findings', 'application_pki_bindings') if key in result}
    atomic_json(path, dict(version=VERSION, identity=expected, result=result,
                           digest=canonical_digest(result)))


def enrich(result, prepared):
    result = copy.deepcopy(result)
    if prepared is not None:
        native = {'x-container-images': result['application_image_lock']}
        result['application_image_lock'] = resolve_image_lock(native, native, prepared)
    result['changed'] = False
    return result


def scope_name(project, runtime):
    del runtime
    path = os.path.join(project, 'project.yml')
    project_id = os.path.realpath(project)
    if os.path.isfile(path):
        with open(path, encoding='utf-8') as stream:
            import yaml
            try:
                manifest = yaml.safe_load(stream)
            except yaml.YAMLError:
                raise ValueError('PROJECT_RESOLUTION_INVALID') from None
        if not isinstance(manifest, dict) or not isinstance(manifest.get('metadata', {}), dict):
            raise ValueError('PROJECT_RESOLUTION_INVALID')
        project_id = manifest.get('metadata', {}).get('id', project_id)
    return hashlib.sha256(json.dumps([project_id],
                                    sort_keys=True).encode()).hexdigest() + '.json'

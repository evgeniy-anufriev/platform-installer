"""Private desired-only result reuse; never a source of desired state."""
import copy
import hashlib
import json
import os
import tempfile

from jinja2 import Environment, nodes

from .project_snapshot import project_documents
from .project_validation import canonical_digest
from .application_runtime import resolve_image_lock

VERSION = 'platform.installer/private-project-resolution/v1alpha1'
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
    'zip', 'dictsort', 'regex_search', 'regex_findall'))
PURE_TESTS = frozenset(('defined', 'undefined', 'none', 'string', 'number',
    'mapping', 'sequence', 'iterable', 'boolean', 'true', 'false', 'equalto',
    'eq', 'ne', 'in', 'match', 'search', 'gt', 'ge', 'lt', 'le'))
CONTEXT_NAMES = frozenset(('vars', 'environment', 'inventory_dir', 'playbook_dir',
    'role_path', 'ansible_env', 'ansible_facts', 'ansible_date_time'))


def pure_templates(text):
    try:
        tree = Environment().parse(text)
    except Exception:
        return False
    if any(tree.find_all(nodes.Call)):
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
    if any(item.attr in CONTEXT_NAMES or item.attr.startswith('_')
           for item in tree.find_all(nodes.Getattr)):
        return False
    if any(isinstance(item.value, str) and (item.value in CONTEXT_NAMES or item.value.startswith('__'))
           for item in tree.find_all(nodes.Const)):
        return False
    return True


def identity(project, runtime, owned=()):
    documents, revision = project_documents(project, owned)
    inputs = [[item['logicalPath'], item['digest']] for item in documents]
    return dict(version=VERSION, revision=revision, runtime=copy.deepcopy(runtime),
                inputDigest=canonical_digest(inputs), owned=sorted(owned)), documents


def reusable(project, documents, result, defaults_root):
    # Captured staging paths cannot be transplanted into a different request.
    if os.path.realpath(project) in json.dumps(result, ensure_ascii=True):
        return False
    for document in documents:
        name = document['logicalPath']
        if not name.endswith(('.yml', '.yaml', '.json', '.cfg')):
            continue
        # Mounted configuration/templates are rendered during Apply, not resolve.
        if '/assets/' in name:
            continue
        with open(os.path.join(project, name), encoding='utf-8') as stream:
            if not pure_templates(stream.read()):
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
                    if not pure_templates(stream.read()):
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
    if not isinstance(result.get('application_rows', []), list):
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
    result = {key: copy.deepcopy(result[key]) for key in (*FIELDS, 'application_rows') if key in result}
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

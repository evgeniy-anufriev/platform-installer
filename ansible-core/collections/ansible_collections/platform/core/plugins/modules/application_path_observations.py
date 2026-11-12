#!/usr/bin/python
"""Observe exact placement paths on one target without following symlinks."""
import json
import os
import stat

from ansible.module_utils.basic import AnsibleModule

MAX_PATHS = 32768
MAX_MARKER_BYTES = 16384
IDENTITY_FIELDS = ('project', 'library', 'host', 'instance')


def marker_identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def read_marker(parent, name, observed):
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    with os.fdopen(descriptor, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or marker_identity(before) != marker_identity(observed):
            raise ValueError
        raw = stream.read(MAX_MARKER_BYTES + 1)
        after = os.fstat(stream.fileno())
        if (len(raw) > MAX_MARKER_BYTES or len(raw) != before.st_size or
                marker_identity(before) != marker_identity(after)):
            raise ValueError
    marker = json.loads(raw)
    if not isinstance(marker, dict):
        raise ValueError
    fields = {key: marker[key] for key in IDENTITY_FIELDS if key in marker}
    if any(not isinstance(value, str) for value in fields.values()):
        raise ValueError
    return fields


def observe(path, marker=False):
    parts = path.split('/')[1:]
    flags = os.O_PATH | os.O_DIRECTORY | os.O_NOFOLLOW
    parent = os.open('/', flags)
    try:
        for component in parts[:-1]:
            child = os.open(component, flags, dir_fd=parent)
            os.close(parent)
            parent = child
        info = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return {'exists': False}, None
    else:
        result = dict(exists=True, uid=info.st_uid, isdir=stat.S_ISDIR(info.st_mode),
                      isreg=stat.S_ISREG(info.st_mode), islnk=stat.S_ISLNK(info.st_mode))
        return result, read_marker(parent, parts[-1], info) if marker and result['isreg'] else None
    finally:
        os.close(parent)


def observations(paths, markers):
    all_paths = set(paths) | set(markers)
    if len(all_paths) > MAX_PATHS:
        raise ValueError
    for path in all_paths:
        if (not path.startswith('/') or len(os.fsencode(path)) > 4096 or
                any(part in ('', '.', '..') for part in path.split('/')[1:]) or '\x00' in path):
            raise ValueError
    marker_paths = set(markers)
    if any(not path.endswith('/.owner.json') for path in marker_paths):
        raise ValueError
    states, identities = {}, {}
    for path in sorted(all_paths):
        states[path], identity = observe(path, path in marker_paths)
        if identity is not None:
            identities[path] = identity
    return states, identities


def main():
    module = AnsibleModule(argument_spec=dict(
        paths=dict(type='list', elements='str', required=True),
        markers=dict(type='list', elements='str', required=True)),
        supports_check_mode=True)
    try:
        states, identities = observations(module.params['paths'], module.params['markers'])
    except (OSError, ValueError):
        module.fail_json(msg='APPLICATION_RUNTIME_PATH_OBSERVATION_INVALID')
    module.exit_json(changed=False, paths=states, markers=identities)


if __name__ == '__main__':
    main()

#!/usr/bin/python
"""Bounded batch writes of already-rendered HAProxy fragments, never deletion."""
import os
import stat
import uuid
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.platform.haproxy.plugins.module_utils.managed_graph import (
    ArchiveError, NAME, MAX_FILE, MAX_FILES, MAX_TOTAL, require,
    open_directory_path, read_regular)

DOCUMENTATION = r'''
module: fragment_batch
short_description: Compare or atomically write a bounded batch of HAProxy fragments
options:
  directory:
    type: path
    required: true
  files:
    type: list
    elements: dict
    required: true
  operation:
    type: str
    choices: [inspect, write]
    default: inspect
'''


def reconcile(directory, files, write=False):
    require(isinstance(files, list) and 0 < len(files) <= MAX_FILES, 'HAPROXY_FRAGMENT_BATCH_INVALID')
    payload = {}
    for item in files:
        name, content = item.get('name'), item.get('content')
        require(isinstance(name, str) and (name == '10-public.cfg' or NAME.fullmatch(name))
                and name not in payload and isinstance(content, str), 'HAPROXY_FRAGMENT_BATCH_INVALID')
        data = content.encode('utf-8')
        require(0 < len(data) <= MAX_FILE, 'HAPROXY_FRAGMENT_BATCH_INVALID')
        if name != '10-public.cfg':
            require(data.startswith(('# platform-installer-managed-backend/v1 ' + name + '\n').encode()),
                    'HAPROXY_FRAGMENT_OWNER_INVALID')
        payload[name] = data
    require(sum(map(len, payload.values())) <= MAX_TOTAL, 'HAPROXY_FRAGMENT_BATCH_INVALID')
    fd = open_directory_path(directory)
    try:
        changes = []
        # Validate the complete batch before the first write; reject links/devices.
        for name, data in payload.items():
            try:
                existing, info = read_regular(fd, name)
                same = existing == data and stat.S_IMODE(info.st_mode) == 0o640 and info.st_gid == 0
            except FileNotFoundError:
                same = False
            if not same:
                changes.append(name)
        if write:
            for name in changes:
                temp = '.fragment-' + uuid.uuid4().hex
                out = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
                try:
                    with os.fdopen(out, 'wb', closefd=False) as stream:
                        stream.write(payload[name])
                        stream.flush()
                    os.fchown(out, 0, 0)
                    os.fchmod(out, 0o640)
                    os.fsync(out)
                    os.replace(temp, name, src_dir_fd=fd, dst_dir_fd=fd)
                finally:
                    os.close(out)
                    try:
                        os.unlink(temp, dir_fd=fd)
                    except FileNotFoundError:
                        pass
            os.fsync(fd)
        return dict(changed=bool(changes) if write else False, matches=not changes, changedFiles=changes)
    finally:
        os.close(fd)


def main():
    module = AnsibleModule(argument_spec=dict(directory=dict(type='path', required=True),
        files=dict(type='list', elements='dict', required=True),
        operation=dict(type='str', choices=['inspect', 'write'], default='inspect')), supports_check_mode=True)
    try:
        result = reconcile(module.params['directory'], module.params['files'],
                           module.params['operation'] == 'write' and not module.check_mode)
        if module.check_mode and module.params['operation'] == 'write':
            result['changed'] = not result['matches']
        module.exit_json(**result)
    except (ArchiveError, OSError, ValueError, TypeError, AttributeError) as error:
        module.fail_json(msg=str(error) if isinstance(error, ArchiveError) else 'HAPROXY_FRAGMENT_BATCH_FAILED')


if __name__ == '__main__':
    main()

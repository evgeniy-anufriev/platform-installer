#!/usr/bin/python
"""Explicit Vault-only Raft clear; never remove the identity-bound member root."""
import ctypes
from contextlib import ExitStack
import json
import os
import pwd
import re
import stat
import subprocess

DOCUMENTATION = r'''
module: clear_member
short_description: Inspect or explicitly clear an owned stopped Vault member
description: Clears Raft contents only, keeping the member root and identity marker.
options:
  deployment_id: {type: str, required: true}
  member_id: {type: str, required: true}
  data_directory: {type: str, required: true}
  confirmation: {type: str, required: true}
  inspect_only: {type: bool, default: false}
  data_root_directory: {type: str, default: ''}
  data_root_owner: {type: str, default: ''}
author: Platform Installer
'''
EXAMPLES = r'''
- platform.vault.clear_member:
    deployment_id: vault-ha
    member_id: vault-1
    data_directory: /var/lib/vault-ha
    confirmation: vault-ha
    inspect_only: true
'''
RETURN = r'''
changed: {description: Whether Raft contents were removed, type: bool, returned: always}
'''

CONFIG_ROOT = '/etc'
UNIT_ROOT = '/etc/systemd/system'
IDENTIFIER = re.compile(r'[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*\Z')


class ClearFailure(Exception):
    """Only fixed safe codes cross the Ansible boundary."""


def require(condition, code):
    if not condition:
        raise ClearFailure(code)


def private_mount_namespace():
    # Prevent external mount propagation after the complete mountinfo check.
    libc = ctypes.CDLL(None, use_errno=True)
    libc.unshare.argtypes = [ctypes.c_int]
    libc.unshare.restype = ctypes.c_int
    libc.mount.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p,
                           ctypes.c_ulong, ctypes.c_void_p]
    libc.mount.restype = ctypes.c_int
    require(libc.unshare(0x00020000) == 0, 'VAULT_CLEAR_MOUNT_ISOLATION_UNAVAILABLE')
    require(libc.mount(None, b'/', None, (1 << 18) | (1 << 14), None) == 0,
            'VAULT_CLEAR_MOUNT_ISOLATION_UNAVAILABLE')  # MS_PRIVATE | MS_REC


def owned_directory(stack, path, service_uid=None, service_owned_ancestors=False,
                    data_root=None):
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    stack.callback(os.close, fd)
    components = path.strip('/').split('/')
    for index, component in enumerate(components):
        require(component not in ('', '.', '..'), 'VAULT_CLEAR_PATH_UNSAFE')
        fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                     dir_fd=fd)
        stack.callback(os.close, fd)
        metadata = os.fstat(fd)
        if index == len(components) - 1 and service_uid is not None:
            require(metadata.st_uid == service_uid and
                    stat.S_IMODE(metadata.st_mode) == 0o700,
                    'VAULT_CLEAR_PATH_UNSAFE')
        else:
            allowed_owners = (0, service_uid) if service_owned_ancestors else (0,)
            if (data_root is not None and
                    '/' + '/'.join(components[:index + 1]) == data_root[0]):
                allowed_owners = allowed_owners + (data_root[1],)
            require(metadata.st_uid in allowed_owners and metadata.st_mode & 0o022 == 0,
                    'VAULT_CLEAR_PATH_UNSAFE')
    return fd


def read_owned_file(directory, name, uid, limit, private=False):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    try:
        metadata = os.fstat(fd)
        require(stat.S_ISREG(metadata.st_mode) and metadata.st_uid == uid and
                metadata.st_nlink == 1 and metadata.st_size <= limit and
                (stat.S_IMODE(metadata.st_mode) == 0o600 if private
                 else metadata.st_mode & 0o022 == 0), 'VAULT_CLEAR_FILE_UNSAFE')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            data = stream.read(limit + 1)
        require(len(data) <= limit, 'VAULT_CLEAR_FILE_UNSAFE')
        return data.decode('utf-8')
    finally:
        os.close(fd)


def reject_submounts(path):
    with open('/proc/self/mountinfo', 'rb') as stream:
        data = stream.read(8 * 1024 * 1024 + 1)
    require(len(data) <= 8 * 1024 * 1024, 'VAULT_CLEAR_MOUNT_EVIDENCE_INVALID')
    for line in data.decode('utf-8').splitlines():
        fields = line.split()
        require(len(fields) >= 10 and '-' in fields,
                'VAULT_CLEAR_MOUNT_EVIDENCE_INVALID')
        mountpoint = re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), fields[4])
        require(mountpoint != path and not mountpoint.startswith(path + '/'),
                'VAULT_CLEAR_MOUNT_IN_USE')


def unit_properties(unit):
    result = subprocess.run(
        ['/usr/bin/systemctl', 'show', unit + '.service',
         '--property=ActiveState,MainPID,FragmentPath,User,ExecStart'],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15, check=True)
    require(len(result.stdout) <= 65536, 'VAULT_CLEAR_UNIT_INVALID')
    return dict(line.split('=', 1) for line in result.stdout.decode('utf-8').splitlines()
                if '=' in line)


def require_no_process(config):
    for name in os.listdir('/proc'):
        if not name.isdigit():
            continue
        try:
            with open('/proc/' + name + '/cmdline', 'rb') as stream:
                data = stream.read(65537)
        except FileNotFoundError:
            continue
        args = data.split(b'\0')
        # argv[0] is caller-controlled. Any exact config argument is sufficient
        # to block clear, including a process outside the managed service unit.
        require(len(data) <= 65536 and ('-config=' + config).encode() not in args
                and not any(args[i:i + 2] == [b'-config', config.encode()]
                            for i in range(len(args))), 'VAULT_CLEAR_MEMBER_RUNNING')


def mount_identity(fd):
    with open('/proc/self/fdinfo/' + str(fd), 'rb') as stream:
        info = stream.read(4097)
    require(len(info) <= 4096, 'VAULT_CLEAR_MOUNT_EVIDENCE_INVALID')
    values = [line.split(b':', 1)[1].strip() for line in info.splitlines()
              if line.startswith(b'mnt_id:')]
    require(len(values) == 1 and values[0].isdigit() and len(values[0]) <= 20,
            'VAULT_CLEAR_MOUNT_EVIDENCE_INVALID')
    return int(values[0])


def remove_raft_child(parent, name, member_mount, depth=0):
    """Vault-only fd traversal: no descent into an unchecked mount object."""
    require(depth < 128, 'VAULT_CLEAR_DEPTH_LIMIT')
    metadata = os.stat(name, dir_fd=parent, follow_symlinks=False)
    if not stat.S_ISDIR(metadata.st_mode):
        # unlink does not follow symlinks or remove file bind-mount contents.
        os.unlink(name, dir_fd=parent)
        return
    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    try:
        opened = os.fstat(child)
        require((metadata.st_dev, metadata.st_ino) == (opened.st_dev, opened.st_ino),
                'VAULT_CLEAR_SOURCE_CHANGED')
        # st_dev cannot distinguish same-filesystem bind mounts. Check the
        # actual opened directory's Linux mount identity before listing it.
        require(mount_identity(child) == member_mount, 'VAULT_CLEAR_MOUNT_IN_USE')
        for entry in sorted(os.listdir(child)):
            remove_raft_child(child, entry, member_mount, depth + 1)
        current = os.stat(name, dir_fd=parent, follow_symlinks=False)
        require((current.st_dev, current.st_ino) == (opened.st_dev, opened.st_ino),
                'VAULT_CLEAR_SOURCE_CHANGED')
        os.rmdir(name, dir_fd=parent)
    finally:
        os.close(child)


def same_source(fd, path):
    current = os.stat(path, follow_symlinks=False)
    held = os.fstat(fd)
    require((current.st_dev, current.st_ino) == (held.st_dev, held.st_ino) and
            stat.S_ISDIR(current.st_mode), 'VAULT_CLEAR_SOURCE_CHANGED')


def clear_member(deployment, member, data_directory, confirmation, inspect_only=False, name_prefix='',
                 data_root_directory='', data_root_owner=''):
    require(isinstance(name_prefix, str) and
            (name_prefix == '' or re.fullmatch(r'[a-z][a-z0-9_]{0,23}', name_prefix) is not None),
            'VAULT_CLEAR_IDENTITY_INVALID')
    service_name = (name_prefix + '-' if name_prefix else '') + 'vault'
    config_root = CONFIG_ROOT + '/' + service_name
    marker_name = '.' + service_name + '-member.json'
    require(all(isinstance(value, str) and len(value) <= 128 and IDENTIFIER.fullmatch(value)
                for value in (deployment, member)), 'VAULT_CLEAR_IDENTITY_INVALID')
    require(confirmation == deployment, 'VAULT_CLEAR_CONFIRMATION_REQUIRED')
    require(isinstance(data_directory, str) and 1 < len(data_directory) <= 255 and
            data_directory.startswith('/') and
            all(component not in ('', '.', '..') for component in data_directory[1:].split('/')),
            'VAULT_CLEAR_PATH_UNSAFE')
    require(os.geteuid() == 0, 'VAULT_CLEAR_ROOT_REQUIRED')
    require(all(function in os.supports_dir_fd for function in
                (os.open, os.stat, os.unlink, os.rmdir)) and os.listdir in os.supports_fd,
            'VAULT_CLEAR_SAFE_DELETE_UNAVAILABLE')
    private_mount_namespace()
    uid = pwd.getpwnam(service_name).pw_uid
    require(re.fullmatch(r'[a-z0-9][a-z0-9-]*', deployment) is not None and
            re.fullmatch(r'.+-[1-9][0-9]*', member) is not None,
            'VAULT_CLEAR_IDENTITY_INVALID')
    unit = service_name + '@' + deployment + '-' + member.rsplit('-', 1)[1]
    require(len(unit + '.service') <= 255, 'VAULT_CLEAR_IDENTITY_INVALID')
    data = data_directory
    data_root = None
    if data_root_directory or data_root_owner:
        require(isinstance(data_root_directory, str) and
                data_root_directory.startswith('/') and
                all(component not in ('', '.', '..')
                    for component in data_root_directory[1:].split('/')) and
                data.startswith(data_root_directory + '/') and
                isinstance(data_root_owner, str) and
                re.fullmatch(r'[a-z_][a-z0-9_-]*', data_root_owner) is not None,
                'VAULT_CLEAR_PATH_UNSAFE')
        root_uid = pwd.getpwnam(data_root_owner).pw_uid
        require(data_root_directory != '/var/lib' or root_uid == 0,
                'VAULT_CLEAR_PATH_UNSAFE')
        data_root = (data_root_directory, root_uid)
    config = config_root + '/' + deployment + '/' + member + '/vault.hcl'
    with ExitStack() as stack:
        directory = owned_directory(stack, data, uid, service_owned_ancestors=True,
                                    data_root=data_root)
        marker = json.loads(read_owned_file(directory, marker_name, uid, 4096, private=True))
        require(marker == {'apiVersion': 'platform.installer/vault-member-marker/v1alpha1',
                           'deploymentId': deployment, 'memberId': member, 'instanceName': unit},
                'VAULT_CLEAR_OWNERSHIP_UNKNOWN')
        configs = owned_directory(stack, os.path.dirname(config), uid)
        hcl = read_owned_file(configs, 'vault.hcl', uid, 65536, private=True)
        require(('  path = "' + data + '"') in hcl.splitlines() and
                ('  node_id = "' + unit + '"') in hcl.splitlines(),
                'VAULT_CLEAR_CONFIG_IDENTITY_INVALID')
        units = owned_directory(stack, UNIT_ROOT)
        text = read_owned_file(units, unit + '.service', 0, 65536)
        start = '/usr/bin/vault server -config=' + config
        require(text.splitlines()[0] == '# ' + service_name + '-managed: ' + deployment + '/' + member
                and text.splitlines().count('ExecStart=' + start) == 1 and
                text.splitlines().count('User=' + service_name) == 1, 'VAULT_CLEAR_UNIT_INVALID')
        properties = unit_properties(unit)
        require(properties.get('FragmentPath') == UNIT_ROOT + '/' + unit + '.service' and
                properties.get('User') == service_name and
                ('argv[]=' + start + ' ;') in properties.get('ExecStart', ''),
                'VAULT_CLEAR_UNIT_INVALID')
        reject_submounts(data)
        same_source(directory, data)
        children = sorted(name for name in os.listdir(directory) if name != marker_name)
        if inspect_only:
            return bool(children)
        require(properties.get('ActiveState') in ('inactive', 'failed') and
                properties.get('MainPID') == '0', 'VAULT_CLEAR_MEMBER_RUNNING')
        require_no_process(config)
        member_mount = mount_identity(directory)
        for name in children:
            same_source(directory, data)
            remove_raft_child(directory, name, member_mount)
        same_source(directory, data)
        require(os.listdir(directory) == [marker_name], 'VAULT_CLEAR_INCOMPLETE')
        os.fsync(directory)
        return bool(children)


def main():
    from ansible.module_utils.basic import AnsibleModule
    module = AnsibleModule(argument_spec={
        'deployment_id': {'type': 'str', 'required': True},
        'member_id': {'type': 'str', 'required': True},
        'data_directory': {'type': 'str', 'required': True},
        'confirmation': {'type': 'str', 'required': True},
        'inspect_only': {'type': 'bool', 'default': False},
        'name_prefix': {'type': 'str', 'default': ''},
        'data_root_directory': {'type': 'str', 'default': ''},
        'data_root_owner': {'type': 'str', 'default': ''},
    }, supports_check_mode=True)
    try:
        predicted = clear_member(module.params['deployment_id'], module.params['member_id'],
                                 module.params['data_directory'], module.params['confirmation'],
                                 module.params['inspect_only'] or module.check_mode,
                                 module.params['name_prefix'],
                                 module.params['data_root_directory'],
                                 module.params['data_root_owner'])
        module.exit_json(changed=predicted if module.check_mode or
                         not module.params['inspect_only'] else False)
    except ClearFailure as error:
        module.fail_json(msg=str(error))
    except Exception:
        # No filesystem names, command output, marker/config contents or traceback.
        module.fail_json(msg='VAULT_CLEAR_FAILED')


if __name__ == '__main__':
    main()

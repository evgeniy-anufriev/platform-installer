#!/usr/bin/python
"""Preserve named users while locking infrastructure ACL writes with app hooks."""
import hashlib
import os
import re
import shlex
import stat
import tempfile

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.platform.redis.plugins.module_utils.application_acl import Client, ACLFailure, member_lock, private_info

DOCUMENTATION = r'''
module: acl_file
short_description: Preserve named ACL users during infrastructure reconciliation
description:
  - Shares the member lock with application hooks and saves only changed native ACL state.
  - Verify is read-only; default-user credential repair requires explicit overwrite_default.
options:
  directory: {type: path, required: true}
  listener: {type: str, choices: [redis, sentinel], required: true}
  phase: {type: str, choices: [prepare, save, verify], required: true}
  password: {type: str, required: true}
  overwrite_default: {type: bool, default: false}
  address: {type: str}
  port: {type: int}
  timeout: {type: int, default: 15}
author: Platform Installer
'''


def checked_lines(content, password, overwrite=False):
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    names, defaults = set(), []
    for line in lines:
        tokens = shlex.split(line)
        if len(tokens) < 3 or tokens[0] != 'user' or tokens[1] in names:
            raise ACLFailure('REDIS_ACL_CONTENT_INVALID')
        names.add(tokens[1])
        if any(token.startswith(('>', '<')) or (token.startswith('#') and not re.fullmatch(r'#[a-f0-9]{64}', token)) for token in tokens[2:]):
            raise ACLFailure('REDIS_ACL_CONTENT_INVALID')
        if tokens[1] == 'default':
            hashes = [token for token in tokens[2:] if token.startswith('#')]
            flags = set(tokens[2:]) - set(hashes)
            if len(hashes) != 1 or flags - {'on', 'sanitize-payload', '~*', '&*', '+@all'} or not {'on', '~*', '&*', '+@all'} <= flags:
                raise ACLFailure('REDIS_ACL_CONTENT_INVALID')
            if not overwrite and hashes != ['#' + hashlib.sha256(password.encode()).hexdigest()]:
                raise ACLFailure('REDIS_ACL_STATE_MIGRATION_REQUIRED')
            defaults.append(line)
    if len(defaults) != 1:
        raise ACLFailure('REDIS_ACL_CONTENT_INVALID')
    return lines


def read_file(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'r', encoding='utf-8') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_nlink != 1 or info.st_size > 1048576:
            raise ACLFailure('REDIS_ACL_PATH_UNSAFE')
        return stream.read(1048577)


def comparable(lines):
    result = []
    for line in lines:
        tokens = shlex.split(line)
        if tokens[1] == 'default':
            # Redis adds this default flag on ACL SAVE; it does not change the
            # credential or unrestricted default-user permission policy.
            tokens = tokens[:2] + sorted(token for token in tokens[2:] if token != 'sanitize-payload')
        result.append(tuple(tokens))
    return sorted(result)


def main():
    module = AnsibleModule(argument_spec={
        'directory': {'type': 'path', 'required': True}, 'listener': {'choices': ['redis', 'sentinel'], 'required': True},
        'phase': {'choices': ['prepare', 'save', 'verify'], 'required': True},
        'password': {'type': 'str', 'no_log': True, 'required': True}, 'overwrite_default': {'type': 'bool', 'default': False},
        'address': {'type': 'str'}, 'port': {'type': 'int'}, 'timeout': {'type': 'int', 'default': 15}})
    args, client, changed = module.params, None, False
    try:
        directory = args['directory']
        with member_lock(directory, args['timeout']):
            path = os.path.join(directory, args['listener'] + '.users.acl')
            exists = os.path.lexists(path)
            content = ''
            if exists:
                private_info(path)
                content = read_file(path)
                checked_lines(content, args['password'], args['phase'] == 'prepare' and args['overwrite_default'])
            elif args['phase'] != 'prepare':
                raise ACLFailure('REDIS_ACL_FILE_INVALID')
            if args['phase'] == 'prepare':
                if not exists or args['overwrite_default']:
                    default = 'user default on #' + hashlib.sha256(args['password'].encode()).hexdigest() + ' ~* &* +@all'
                    for line in content.splitlines():
                        tokens = shlex.split(line)
                        if tokens and tokens[1] == 'default' and '#' + hashlib.sha256(args['password'].encode()).hexdigest() in tokens:
                            default = line
                    retained = [line for line in content.splitlines() if line.strip() and shlex.split(line)[1] != 'default']
                    proposed = '\n'.join([default] + retained) + '\n'
                    if proposed != content:
                        descriptor, temporary = tempfile.mkstemp(prefix='.users-acl-', dir=directory)
                        try:
                            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                                stream.write(proposed)
                                stream.flush()
                                os.fsync(stream.fileno())
                            os.replace(temporary, path)
                        finally:
                            if os.path.exists(temporary):
                                os.unlink(temporary)
                        changed = True
            else:
                client = Client(args['address'], args['port'], directory + '/pki/ca-chain.pem',
                                directory + '/pki/certificate.pem', directory + '/pki/private-key.pem', args['timeout'])
                if client.command('AUTH', 'default', args['password']) != 'OK':
                    raise ACLFailure('REDIS_ACL_LOGIN_FAILED')
                live = client.command('ACL', 'LIST')
                checked_lines('\n'.join(live), args['password'])
                if args['listener'] == 'redis' and client.command('CONFIG', 'GET', 'aclfile') != ['aclfile', path]:
                    raise ACLFailure('REDIS_ACL_CONFIGURATION_INVALID')
                if comparable(checked_lines(content, args['password'])) != comparable(live):
                    if args['phase'] == 'verify':
                        raise ACLFailure('REDIS_ACL_PERSISTENCE_DRIFT')
                    if client.command('ACL', 'SAVE') != 'OK':
                        raise ACLFailure('REDIS_ACL_SAVE_FAILED')
                    private_info(path)
                    saved = checked_lines(read_file(path), args['password'])
                    if comparable(saved) != comparable(live):
                        raise ACLFailure('REDIS_ACL_PERSISTENCE_DRIFT')
                    changed = True
        module.exit_json(changed=changed)
    except ACLFailure as error:
        module.fail_json(msg=str(error))
    except (ValueError, OSError, TypeError, KeyError):
        module.fail_json(msg='REDIS_ACL_OPERATION_FAILED')
    finally:
        if client:
            client.close()


if __name__ == '__main__':
    main()

#!/usr/bin/python
"""Execute one Redis application account scope over authenticated TLS."""
from contextlib import closing
import re

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.platform.redis.plugins.module_utils.application_acl import Client, ensure_account, ACLFailure

DOCUMENTATION = r'''
module: application_account
short_description: Ensure or verify one owned application ACL account
description:
  - Uses authenticated TLS, a member lock and a private ownership witness.
  - Credentials are invocation-only module inputs and never process arguments.
options:
  address: {type: str, required: true}
  port: {type: int, required: true}
  ca: {type: path, required: true}
  certificate: {type: path}
  private_key: {type: path}
  directory: {type: path, required: true}
  admin_password: {type: str, required: true}
  username: {type: str}
  password: {type: str}
  marker: {type: str}
  listener: {type: str, choices: [client, sentinel], required: true}
  grants: {type: dict}
  mode: {type: str, choices: [managed, existing], default: managed}
  verify: {type: bool, default: false}
  preflight: {type: bool, default: false}
  timeout: {type: int, default: 15}
  accounts: {type: list, elements: dict, description: 'Read-only batch for one member and listener.'}
author: Platform Installer
'''


def validate_account(args):
    username, grants = args['username'], args['grants']
    if not re.fullmatch(r'[a-z_][a-z0-9_-]{0,62}', username) or username == 'default':
        raise ACLFailure('REDIS_APPLICATION_INPUT_INVALID')
    permitted = {'commands', 'keys', 'channels'}
    if set(grants) - permitted or not isinstance(grants.get('commands'), list) or not grants['commands']:
        raise ACLFailure('REDIS_APPLICATION_INPUT_INVALID')
    for field, values in grants.items():
        if not isinstance(values, list) or len(values) > 256:
            raise ACLFailure('REDIS_APPLICATION_INPUT_INVALID')
        for value in values:
            if not isinstance(value, str) or not value or len(value) > 256 or any(char.isspace() or ord(char) < 32 for char in value):
                raise ACLFailure('REDIS_APPLICATION_INPUT_INVALID')
            if field == 'commands' and not re.fullmatch(r'[+-]?(?:@[a-z][a-z0-9_-]*|[a-z][a-z0-9]*(?:\|[a-z][a-z0-9-]*)?)', value):
                raise ACLFailure('REDIS_APPLICATION_INPUT_INVALID')


def main():
    account_spec = {
        'username': {'type': 'str', 'required': True},
        'password': {'type': 'str', 'required': True, 'no_log': True},
        'marker': {'type': 'str', 'required': True},
        'grants': {'type': 'dict', 'required': True},
        'mode': {'choices': ['managed', 'existing'], 'default': 'managed'},
    }
    single_spec = {name: dict(spec, required=False) for name, spec in account_spec.items()}
    module = AnsibleModule(argument_spec={
        'address': {'type': 'str', 'required': True}, 'port': {'type': 'int', 'required': True},
        'ca': {'type': 'path', 'required': True}, 'certificate': {'type': 'path'}, 'private_key': {'type': 'path', 'no_log': True},
        'directory': {'type': 'path', 'required': True}, 'admin_password': {'type': 'str', 'required': True, 'no_log': True},
        'listener': {'choices': ['client', 'sentinel'], 'required': True},
        'verify': {'type': 'bool', 'default': False}, 'preflight': {'type': 'bool', 'default': False},
        'timeout': {'type': 'int', 'default': 15},
        'accounts': {'type': 'list', 'elements': 'dict', 'options': account_spec},
        **single_spec}, required_one_of=[('accounts', 'username')],
        required_together=[('username', 'password', 'marker', 'grants')],
        mutually_exclusive=[('accounts', 'username')], supports_check_mode=False)
    args = module.params
    failure_username = None
    try:
        batch = args['accounts']
        if (not 1 <= args['port'] <= 65535 or not 1 <= args['timeout'] <= 120 or
                (batch is not None and (not args['preflight'] or args['verify'] or not 1 <= len(batch) <= 100))):
            raise ACLFailure('REDIS_APPLICATION_INPUT_INVALID')
        accounts = [args] if batch is None else batch
        for account in accounts:
            failure_username = account['username'] if re.fullmatch(r'[a-z_][a-z0-9_-]{0,62}', account['username']) else None
            validate_account(account)
        failure_username = None
        connection = (args['address'], args['port'], args['ca'], args['certificate'], args['private_key'], args['timeout'])
        metadata = None if batch is None else []
        changed = False
        with closing(Client(*connection)) as admin:
            if admin.command('AUTH', 'default', args['admin_password']) != 'OK':
                raise ACLFailure('REDIS_APPLICATION_ADMIN_LOGIN_FAILED')
            for account in accounts:
                failure_username = account['username']
                with closing(Client(*connection)) as user:
                    result = ensure_account(admin, user, args['directory'], account['username'], account['password'],
                                            account['marker'], args['listener'], account['grants'], account['mode'],
                                            args['verify'], args['timeout'], args['preflight'], metadata)
                    changed = changed or result
        module.exit_json(changed=changed)
    except ACLFailure as error:
        module.fail_json(msg=str(error), username=failure_username)
    except (OSError, ValueError, KeyError, TypeError):
        # Neither RESP errors nor private paths/hash values leave the module.
        module.fail_json(msg='REDIS_APPLICATION_ACCOUNT_FAILED', username=failure_username)


if __name__ == '__main__':
    main()

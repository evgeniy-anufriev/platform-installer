#!/usr/bin/python
"""Execute one Redis application account scope over authenticated TLS."""
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
  username: {type: str, required: true}
  password: {type: str, required: true}
  marker: {type: str, required: true}
  listener: {type: str, choices: [client, sentinel], required: true}
  grants: {type: dict, required: true}
  mode: {type: str, choices: [managed, existing], default: managed}
  verify: {type: bool, default: false}
  preflight: {type: bool, default: false}
  timeout: {type: int, default: 15}
author: Platform Installer
'''


def main():
    module = AnsibleModule(argument_spec={
        'address': {'type': 'str', 'required': True}, 'port': {'type': 'int', 'required': True},
        'ca': {'type': 'path', 'required': True}, 'certificate': {'type': 'path'}, 'private_key': {'type': 'path', 'no_log': True},
        'directory': {'type': 'path', 'required': True}, 'admin_password': {'type': 'str', 'required': True, 'no_log': True},
        'username': {'type': 'str', 'required': True}, 'password': {'type': 'str', 'required': True, 'no_log': True},
        'marker': {'type': 'str', 'required': True}, 'listener': {'choices': ['client', 'sentinel'], 'required': True},
        'grants': {'type': 'dict', 'required': True}, 'mode': {'choices': ['managed', 'existing'], 'default': 'managed'},
        'verify': {'type': 'bool', 'default': False}, 'preflight': {'type': 'bool', 'default': False},
        'timeout': {'type': 'int', 'default': 15}}, supports_check_mode=False)
    args, clients = module.params, []
    try:
        username, grants = args['username'], args['grants']
        if not re.fullmatch(r'[a-z_][a-z0-9_-]{0,62}', username) or username == 'default' or not 1 <= args['port'] <= 65535 or not 1 <= args['timeout'] <= 120:
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
        for _ in range(2):
            clients.append(Client(args['address'], args['port'], args['ca'], args['certificate'], args['private_key'], args['timeout']))
        if clients[0].command('AUTH', 'default', args['admin_password']) != 'OK':
            raise ACLFailure('REDIS_APPLICATION_ADMIN_LOGIN_FAILED')
        changed = ensure_account(clients[0], clients[1], args['directory'], username, args['password'], args['marker'],
                                 args['listener'], grants, args['mode'], args['verify'], args['timeout'], args['preflight'])
        module.exit_json(changed=changed)
    except ACLFailure as error:
        module.fail_json(msg=str(error))
    except (OSError, ValueError, KeyError, TypeError):
        # Neither RESP errors nor private paths/hash values leave the module.
        module.fail_json(msg='REDIS_APPLICATION_ACCOUNT_FAILED')
    finally:
        for client in clients:
            client.close()


if __name__ == '__main__':
    main()

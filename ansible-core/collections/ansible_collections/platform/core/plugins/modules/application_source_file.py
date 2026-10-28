#!/usr/bin/python
"""Read a regular source config once; hash exactly the returned binary content."""
import base64
import hashlib
import os
import stat

from ansible.module_utils.basic import AnsibleModule

DOCUMENTATION = r'''
---
module: application_source_file
short_description: Read and hash a regular application source on the Execution Node
description:
  - Returns the same base64 content and SHA-256 used by application preflight.
  - Rejects final-component symlinks, nonregular files and observed mutations.
  - Call with no_log because source content must not enter execution diagnostics.
options:
  path:
    description: Source path already resolved by the application package contract.
    type: path
    required: true
'''


def identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def read_source(path):
    # Core executes on Linux. NONBLOCK lets us reject FIFOs without waiting for
    # a writer; NOFOLLOW prevents a final symlink swap between check and open.
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError('APPLICATION_CONFIG_SOURCE_INVALID')
        with os.fdopen(descriptor, 'rb', closefd=False) as stream:
            raw = stream.read()
        after = os.fstat(descriptor)
        if identity(before) != identity(after) or len(raw) != before.st_size:
            raise ValueError('APPLICATION_CONFIG_SOURCE_INVALID')
        return dict(content=base64.b64encode(raw).decode('ascii'), encoding='base64',
                    sha256=hashlib.sha256(raw).hexdigest())
    finally:
        os.close(descriptor)


def main():
    module = AnsibleModule(argument_spec=dict(path=dict(type='path', required=True, no_log=True)),
                           supports_check_mode=True)
    try:
        result = read_source(module.params['path'])
    except (OSError, ValueError):
        module.fail_json(msg='APPLICATION_CONFIG_SOURCE_INVALID')
    module.exit_json(changed=False, **result)


if __name__ == '__main__':
    main()

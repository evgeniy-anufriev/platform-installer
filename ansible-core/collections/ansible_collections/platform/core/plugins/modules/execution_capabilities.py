#!/usr/bin/python
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: execution_capabilities
short_description: Report the activated Platform Execution runtime capability contract
options:
  runtime_root:
    description: Activated execution runtime directory containing manifest.yaml.
    type: path
    required: true
  bundle_digest:
    description: SHA-256 digest of the verified bundle manifest.
    type: str
    required: true
'''


def main():
    from ansible.module_utils.basic import AnsibleModule
    module = AnsibleModule(argument_spec={
        "runtime_root": {"type": "path", "required": True},
        "bundle_digest": {"type": "str", "required": True},
    }, supports_check_mode=True)
    module.fail_json(msg="execution_capabilities requires its controller-side action plugin")


if __name__ == "__main__":
    main()

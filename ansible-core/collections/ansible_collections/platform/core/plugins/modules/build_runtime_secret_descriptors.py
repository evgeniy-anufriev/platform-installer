DOCUMENTATION = r'''---
module: build_runtime_secret_descriptors
short_description: Build safe target-free runtime-secret prompts
description: This module has a controller-side action plugin.
'''

from ansible.module_utils.basic import AnsibleModule

if __name__ == "__main__":
    AnsibleModule(argument_spec={}).fail_json(msg="build_runtime_secret_descriptors requires its controller-side action plugin")

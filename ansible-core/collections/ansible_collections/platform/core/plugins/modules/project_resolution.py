DOCUMENTATION = r'''---
module: project_resolution
short_description: Reuse a private desired-only controller resolution
description: This module has a controller-side action plugin.
'''

from ansible.module_utils.basic import AnsibleModule

if __name__ == '__main__':
    AnsibleModule(argument_spec={}).fail_json(msg='project_resolution requires its controller-side action plugin')

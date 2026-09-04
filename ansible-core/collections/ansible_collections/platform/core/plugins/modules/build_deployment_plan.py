DOCUMENTATION = r'''---
module: build_deployment_plan
short_description: Build a target-free DeploymentPlan on the controller
description: This module has a controller-side action plugin.
'''

from ansible.module_utils.basic import AnsibleModule

if __name__ == "__main__":
    AnsibleModule(argument_spec={}).fail_json(msg="build_deployment_plan requires its controller-side action plugin")

#!/usr/bin/python
from __future__ import absolute_import, division, print_function

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.platform.core.plugins.module_utils.service_endpoint_resolution import resolve_service_endpoints


def main():
    module = AnsibleModule(
        argument_spec={
            "desired_state": {"type": "dict", "required": True},
            "service_catalog": {"type": "dict", "required": True},
            "inventory_deployments": {"type": "dict", "required": False, "default": {}},
        },
        supports_check_mode=True,
    )
    result = resolve_service_endpoints(
        module.params["desired_state"],
        module.params["service_catalog"],
        inventory_deployments=module.params["inventory_deployments"],
    )
    if result["status"] != "PASS":
        module.fail_json(
            msg="Service endpoint resolution is blocked",
            error_code="SERVICE_ENDPOINT_RESOLUTION_BLOCKED",
            findings=result["findings"],
        )
    module.exit_json(changed=False, resolved_service_endpoints=result)


if __name__ == "__main__":
    main()

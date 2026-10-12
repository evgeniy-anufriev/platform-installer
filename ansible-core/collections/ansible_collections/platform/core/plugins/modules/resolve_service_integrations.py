#!/usr/bin/python
from __future__ import absolute_import, division, print_function

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.platform.core.plugins.module_utils.service_integration_resolution import resolve_service_integrations


def main():
    module = AnsibleModule(argument_spec={
        "endpoint_sources": {"type": "dict", "default": {}},
        "desired_state": {"type": "dict", "required": True},
        "source_service_types": {"type": "list", "elements": "str", "required": True},
        "source_deployment_id": {"type": "str", "required": False},
        "inventory_deployments": {"type": "dict", "required": True},
    }, supports_check_mode=True)
    result = resolve_service_integrations(
        module.params["desired_state"], module.params["source_service_types"],
        module.params.get("source_deployment_id"),
        module.params["inventory_deployments"],
        endpoint_sources=module.params['endpoint_sources'],
    )
    module.exit_json(changed=False, resolved_service_integrations=result)


if __name__ == "__main__":
    main()

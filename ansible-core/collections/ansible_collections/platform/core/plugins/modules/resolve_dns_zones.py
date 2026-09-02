#!/usr/bin/python
from __future__ import absolute_import, division, print_function

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.platform.core.plugins.module_utils.dns_resolution import resolve_dns_zones


def main():
    module = AnsibleModule(argument_spec={
        "desired_state": {"type": "dict", "required": True},
        "service_catalog": {"type": "dict", "required": True},
        "inventory_hosts": {"type": "dict", "required": True},
        "inventory_deployments": {"type": "dict", "required": True},
    }, supports_check_mode=True)
    result = resolve_dns_zones(module.params["desired_state"], module.params["service_catalog"], module.params["inventory_hosts"], module.params["inventory_deployments"])
    if result["status"] != "PASS":
        module.fail_json(msg="DNS resolution is blocked", error_code="DNS_RESOLUTION_BLOCKED", findings=result["findings"])
    module.exit_json(changed=False, resolved_dns_zones=result)


if __name__ == "__main__":
    main()

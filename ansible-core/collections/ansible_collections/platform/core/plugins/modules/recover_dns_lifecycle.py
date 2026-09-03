#!/usr/bin/python
from __future__ import absolute_import, division, print_function

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.platform.core.plugins.module_utils.dns_lifecycle import recover_dns_lifecycle


def main():
    module = AnsibleModule(argument_spec={
        "generated_state": {"type": "dict", "required": False, "default": {}},
        "zones": {"type": "dict", "required": True},
        "recovery": {"type": "dict", "required": True},
    }, supports_check_mode=True)
    result = recover_dns_lifecycle(module.params["generated_state"], module.params["zones"], module.params["recovery"])
    if result["status"] != "PASS":
        module.fail_json(msg="DNS lifecycle recovery is blocked", error_code="BIND_LIFECYCLE_RECOVERY_BLOCKED", findings=result["findings"])
    module.exit_json(changed=False, recovered_dns_lifecycle=result)


if __name__ == "__main__":
    main()

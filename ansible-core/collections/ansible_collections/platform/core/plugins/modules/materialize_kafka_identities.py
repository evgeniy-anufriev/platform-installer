#!/usr/bin/python
from __future__ import absolute_import, division, print_function

import os
import yaml
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.platform.core.plugins.module_utils.managed_kafka_materialization import materialize_ansible_kafka, materialize_managed_kafka


def main():
    module = AnsibleModule(argument_spec={
        "project_path": {"type": "path", "required": False, "default": None},
        "inventory_path": {"type": "path", "required": True},
        "state_path": {"type": "path", "required": False, "default": None},
        "desired_state": {"type": "dict", "required": False, "default": {}},
        "project_id": {"type": "str", "required": False, "default": "ansible-project"},
        "discovery": {"type": "dict", "required": True},
    }, supports_check_mode=False)
    if module.check_mode:
        module.fail_json(msg="Identity materialization is a mutating apply phase")
    try:
        if module.params["desired_state"]:
            if not module.params["state_path"]:
                module.fail_json(msg="Ansible-native identity materialization requires state_path", error_code="PLATFORM_STATE_PATH_REQUIRED")
            result = materialize_ansible_kafka(module.params["desired_state"], module.params["inventory_path"], module.params["state_path"], module.params["discovery"], module.params["project_id"])
        else:
            if not module.params["project_path"]:
                module.fail_json(msg="Legacy identity materialization requires project_path", error_code="PROJECT_PATH_REQUIRED")
            result = materialize_managed_kafka(module.params["project_path"], module.params["inventory_path"], module.params["discovery"])
    except Exception as error:
        module.fail_json(msg="Kafka identity materialization failed", error_code="KAFKA_IDENTITY_MATERIALIZATION_FAILED", safe_details=str(error))
    if result.get("status") != "PASS":
        module.fail_json(msg="Kafka identity materialization is blocked", error_code="KAFKA_IDENTITY_MATERIALIZATION_BLOCKED", findings=result.get("findings", []))
    module.exit_json(changed=result.get("changed", False), materialization=result)


if __name__ == "__main__":
    main()

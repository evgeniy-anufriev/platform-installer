#!/usr/bin/python
from __future__ import absolute_import, division, print_function

import os
import yaml
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.platform.core.plugins.module_utils.managed_kafka_materialization import materialize_managed_kafka


def main():
    module = AnsibleModule(argument_spec={
        "project_path": {"type": "path", "required": True},
        "inventory_path": {"type": "path", "required": True},
        "discovery": {"type": "dict", "required": True},
    }, supports_check_mode=False)
    if module.check_mode:
        module.fail_json(msg="Identity materialization is a mutating apply phase")
    try:
        result = materialize_managed_kafka(module.params["project_path"], module.params["inventory_path"], module.params["discovery"])
    except Exception as error:
        module.fail_json(msg="Kafka identity materialization failed", error_code="KAFKA_IDENTITY_MATERIALIZATION_FAILED", safe_details=str(error))
    if result.get("status") != "PASS":
        module.fail_json(msg="Kafka identity materialization is blocked", error_code="KAFKA_IDENTITY_MATERIALIZATION_BLOCKED", findings=result.get("findings", []))
    module.exit_json(changed=result.get("changed", False), materialization=result)


if __name__ == "__main__":
    main()

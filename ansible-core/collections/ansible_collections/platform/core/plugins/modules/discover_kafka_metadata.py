#!/usr/bin/python
from __future__ import absolute_import, division, print_function
import os
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.platform.core.plugins.module_utils.kafka_discovery import parse_meta_properties

def main():
    module = AnsibleModule(argument_spec={"records": {"type": "list", "required": True, "elements": "dict"}}, supports_check_mode=True)
    output = []
    for item in module.params["records"]:
        path = item["metadataPath"]
        try:
            if not os.path.exists(path):
                output.append(parse_meta_properties(item["deploymentId"], item["memberId"], item["hostId"], path, "", False))
                continue
            with open(path, "r", encoding="utf-8") as source:
                content = source.read()
            output.append(parse_meta_properties(item["deploymentId"], item["memberId"], item["hostId"], path, content))
        except Exception as error:
            output.append(parse_meta_properties(item["deploymentId"], item["memberId"], item["hostId"], path, "", True, str(error)))
    module.exit_json(changed=False, discovery=output)

if __name__ == "__main__":
    main()

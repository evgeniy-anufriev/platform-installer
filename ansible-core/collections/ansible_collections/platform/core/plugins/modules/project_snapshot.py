#!/usr/bin/python
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: project_snapshot
short_description: Query a read-only Platform project snapshot
description:
  - Builds a deterministic controller-only projection from the current Ansible inventory.
  - Does not contact managed hosts or persist project state.
options:
  project_root:
    description: Portable project root. Defaults to the parent of inventory_dir.
    type: path
  service_catalog_path:
    description: Published local service catalog artifact.
    type: path
  installer_owned_paths:
    description: Canonical documents that a future writer may edit.
    type: list
    elements: str
    default: []
author: Platform Installer maintainers
'''

EXAMPLES = r'''
- name: Query project snapshot
  platform.core.project_snapshot:
    service_catalog_path: "{{ platform_service_catalog_path }}"
  register: platform_snapshot
'''

RETURN = r'''
snapshot:
  description: Versioned read-only project projection.
  returned: success
  type: dict
'''


def main():
    from ansible.module_utils.basic import AnsibleModule
    module = AnsibleModule(argument_spec={
        "project_root": {"type": "path"},
        "service_catalog_path": {"type": "path"},
        "installer_owned_paths": {"type": "list", "elements": "str", "default": []},
    }, supports_check_mode=True)
    module.fail_json(msg="project_snapshot requires its controller-side action plugin")


if __name__ == "__main__":
    main()

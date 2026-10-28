#!/usr/bin/python
"""Preflight and archive only proven Platform-owned HAProxy backend fragments.

This intentionally handles one fixed HAProxy layout, not arbitrary filesystem
cleanup. The retained, exact prior Platform candidate proves the old inventory.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import os
import re
import stat
import uuid
import hashlib

from ansible.module_utils.basic import AnsibleModule


DOCUMENTATION = r'''
---
module: archive_managed_backends
short_description: Guard and archive exact owned HAProxy backend fragments
description:
  - Rejects unowned reserved backend files and archives proven stale fragments before publication.
options:
  config_directory:
    type: path
    required: true
    description: Fixed HAProxy configuration root.
  candidate_files:
    type: list
    elements: str
    required: true
    description: Exact candidate backend fragment basenames.
  activation_required:
    type: bool
    required: true
    description: Whether the validated candidate differs from the active graph.
  operation:
    type: str
    choices: [capture, archive]
    default: archive
  previous_inventory:
    type: list
    elements: dict
    description: Exact name/SHA-256 proof from capture before candidate reset.
'''

from ansible_collections.platform.haproxy.plugins.module_utils.managed_graph import (
    ArchiveError, archive, capture_prior_candidate)


def main():
    module = AnsibleModule(argument_spec={
        "config_directory": {"type": "path", "required": True},
        "candidate_files": {"type": "list", "elements": "str", "default": []},
        "activation_required": {"type": "bool", "default": False},
        "operation": {"type": "str", "choices": ["capture", "archive"], "default": "archive"},
        "previous_inventory": {"type": "list", "elements": "dict", "default": []},
        "name_prefix": {"type": "str", "default": ""},
    }, supports_check_mode=False)
    try:
        if module.params["name_prefix"] and not re.fullmatch(r"[a-z][a-z0-9_]{0,23}", module.params["name_prefix"]):
            raise ValueError("HAPROXY_RESOURCE_PREFIX_INVALID")
        if module.params["operation"] == "capture":
            result = {"changed": False, "previousInventory": capture_prior_candidate(
                module.params["config_directory"], module.params["name_prefix"])}
        else:
            result = archive(module.params["config_directory"], module.params["candidate_files"],
                             module.params["activation_required"],
                             module.params["previous_inventory"], module.params["name_prefix"])
        module.exit_json(**result)
    except (ArchiveError, OSError, ValueError) as error:
        # The archive path and file contents are intentionally not included.
        module.fail_json(msg=error.args[0] if isinstance(error, ArchiveError)
                         else "HAPROXY_RESOURCE_PREFIX_INVALID" if isinstance(error, ValueError)
                         else "HAPROXY_ARCHIVE_IO_FAILURE")


if __name__ == "__main__":
    main()

#!/usr/bin/python

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: validate_project
short_description: Validate a Platform desired project without changing targets
description:
  - Validates the portable project, service catalog references, and explicit placements.
  - Writes a versioned machine-readable validation artifact on the controller.
  - Does not inspect or mutate target hosts.
options:
  manifest:
    description: Portable project manifest loaded from project.yml.
    type: dict
    required: true
  topology:
    description: Desired topology loaded from normal Ansible variables.
    type: dict
    required: true
  desired_hosts:
    description: Safe desired host projection containing only platform_host values.
    type: dict
    required: true
  service_catalog:
    description: Service definitions keyed by service type.
    type: dict
    required: true
  inventory_hosts:
    description: Host aliases declared in the active Ansible inventory.
    type: list
    elements: str
    required: true
  artifact_path:
    description: Controller path for the structured validation result.
    type: path
    required: true
  contracts_root:
    description: Local published contracts directory. Network resolution is never used.
    type: path
    required: true
author:
  - Platform Installer maintainers
attributes:
  check_mode:
    support: full
"""

EXAMPLES = r"""
- name: Validate a project on the controller
  platform.core.validate_project:
    manifest: "{{ platform_project_manifest_document }}"
    topology: "{{ platform_project }}"
    desired_hosts: "{{ platform_desired_hosts }}"
    service_catalog: "{{ platform_service_catalog }}"
    inventory_hosts: "{{ groups['platform_targets'] }}"
    artifact_path: /tmp/platform-validation.json
    contracts_root: /workspace/contracts
  delegate_to: localhost
  run_once: true
"""

RETURN = r"""
validation:
  description: Structured validation result.
  returned: always
  type: dict
artifact_path:
  description: Absolute path of the written result artifact.
  returned: always
  type: str
"""

import os

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.platform.core.plugins.module_utils.project_validation import (
    validate_project,
    write_validation_artifact,
)
from ansible_collections.platform.core.plugins.module_utils.schema_validation import (
    SchemaValidationError,
    SchemaValidator,
)


def main():
    module = AnsibleModule(
        argument_spec={
            "manifest": {"type": "dict", "required": True},
            "topology": {"type": "dict", "required": True},
            "desired_hosts": {"type": "dict", "required": True},
            "service_catalog": {"type": "dict", "required": True},
            "inventory_hosts": {"type": "list", "elements": "str", "required": True},
            "artifact_path": {"type": "path", "required": True},
            "contracts_root": {"type": "path", "required": True},
        },
        supports_check_mode=True,
    )

    result = validate_project(
        manifest=module.params["manifest"],
        topology=module.params["topology"],
        desired_hosts=module.params["desired_hosts"],
        service_catalog=module.params["service_catalog"],
        inventory_hosts=module.params["inventory_hosts"],
    )
    try:
        schema_validator = SchemaValidator(module.params["contracts_root"])
        contracts_root = os.path.abspath(os.path.expanduser(module.params["contracts_root"]))
        schema_specs = [
            (os.path.join(contracts_root, "project", "v2alpha1", "project-manifest.schema.json"), module.params["manifest"]),
            (os.path.join(contracts_root, "project", "v2alpha1", "desired-state.schema.json"), module.params["topology"]),
            (os.path.join(contracts_root, "service-catalog", "v1alpha1", "schema.json"), module.params["service_catalog"]),
        ]
        for schema_path, document in schema_specs:
            result["findings"].extend(schema_validator.validate(document, schema_path))
        host_schema = os.path.join(contracts_root, "project", "v2alpha1", "host-desired-vars.schema.json")
        for host_name in sorted(module.params["desired_hosts"]):
            result["findings"].extend(schema_validator.validate(module.params["desired_hosts"][host_name], host_schema))
    except SchemaValidationError as error:
        result["findings"].append(
            {
                "apiVersion": "platform.installer/finding/v1alpha1",
                "kind": "Finding",
                "code": "SCHEMA_VALIDATION_ENGINE_ERROR",
                "status": "BLOCKED",
                "category": "schema-validation",
                "field": "schema",
                "safeMessage": "Не удалось выполнить проверку опубликованной схемы",
                "safeDetails": {"reason": str(error).split(":", 1)[0]},
            }
        )
    result["findings"].sort(key=lambda item: (item.get("field", ""), item.get("code", "")))
    result["summary"]["blocked"] = len(result["findings"])
    result["summary"]["pass"] = 0 if result["findings"] else 1
    result["status"] = "BLOCKED" if result["findings"] else "PASS"
    artifact_path = os.path.abspath(os.path.expanduser(module.params["artifact_path"]))

    try:
        write_validation_artifact(artifact_path, result)
    except OSError as error:
        module.fail_json(
            msg="Unable to write the structured validation artifact",
            error_code="VALIDATION_ARTIFACT_WRITE_FAILED",
            safe_details=str(error),
            artifact_path=artifact_path,
        )

    payload = {
        "changed": False,
        "validation": result,
        "artifact_path": artifact_path,
    }
    if result["status"] == "BLOCKED":
        module.fail_json(
            msg="Platform project validation is blocked; inspect the structured findings artifact",
            error_code="PROJECT_VALIDATION_BLOCKED",
            **payload,
        )
    module.exit_json(**payload)


if __name__ == "__main__":
    main()

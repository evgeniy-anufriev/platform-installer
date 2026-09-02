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
  inventory_deployments_by_host:
    description: Canonical inventory platform_deployments keyed by target host.
    type: dict
    required: false
  inventory_host_addresses:
    description: Safe inventory address projection for host-addressed service validation.
    type: dict
    required: false
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
from ansible_collections.platform.core.plugins.module_utils.project_state import (
    canonical_inventory_members,
    canonical_placements,
    select_desired_state,
    synthesize_ansible_manifest,
    topology_with_inventory_members,
)


def main():
    module = AnsibleModule(
        argument_spec={
            "manifest": {"type": "dict", "required": True},
            "topology": {"type": "dict", "required": True},
            "ansible_desired_state": {"type": "dict", "required": False, "default": {}},
            "generated_state": {"type": "dict", "required": False, "default": {}},
            "project_id": {"type": "str", "required": False, "default": "ansible-project"},
            "desired_hosts": {"type": "dict", "required": True},
            "service_catalog": {"type": "dict", "required": True},
            "inventory_hosts": {"type": "list", "elements": "str", "required": True},
            "placement_by_host": {"type": "dict", "required": False, "default": None},
            "inventory_deployments_by_host": {"type": "dict", "required": False, "default": None},
            "inventory_host_addresses": {"type": "dict", "required": False, "default": {}},
            "artifact_path": {"type": "path", "required": True},
            "contracts_root": {"type": "path", "required": True},
        },
        supports_check_mode=True,
    )

    native = module.params["ansible_desired_state"]
    topology, state_findings = select_desired_state(module.params["manifest"], module.params["topology"], native)
    manifest = module.params["manifest"]
    if native and not isinstance(manifest.get("desiredState"), dict):
        manifest = synthesize_ansible_manifest(topology, module.params["service_catalog"], module.params["project_id"])
    schema_topology = topology
    use_placements = isinstance(module.params["manifest"].get("desiredState"), dict) or bool(module.params["placement_by_host"])
    placements, placement_findings = canonical_placements(module.params["placement_by_host"] or {}, module.params["inventory_hosts"])
    inventory_deployments = module.params["inventory_deployments_by_host"]
    if isinstance(inventory_deployments, dict):
        inventory_members, inventory_findings = canonical_inventory_members(
            inventory_deployments, module.params["inventory_hosts"]
        )
        host_scoped_deployments = {}
        for host_id, host_deployments in sorted(inventory_deployments.items()):
            if not isinstance(host_deployments, dict):
                continue
            for deployment_id, host_configuration in sorted(host_deployments.items()):
                if isinstance(host_configuration, dict) and "members" not in host_configuration:
                    host_scoped_deployments.setdefault(deployment_id, {})[host_id] = dict(host_configuration)
        topology = topology_with_inventory_members(topology, inventory_members)
        for deployment_id in host_scoped_deployments:
            if isinstance(topology.get("serviceDeployments", {}).get(deployment_id), dict):
                topology["serviceDeployments"][deployment_id].pop("members", None)
        placements = {key: member["host"] for key, member in inventory_members.items()}
        placement_findings.extend(inventory_findings)
        deployments = schema_topology.get("serviceDeployments", {})
        for deployment_id, deployment in (sorted(deployments.items()) if isinstance(deployments, dict) else []):
            if isinstance(deployment, dict) and "members" in deployment:
                placement_findings.append({
                    "apiVersion": "platform.installer/finding/v1alpha1",
                    "kind": "Finding", "code": "PERSISTED_MEMBERS_NOT_ALLOWED",
                    "status": "BLOCKED", "category": "project-state",
                    "field": "serviceDeployments.%s.members" % deployment_id,
                    "safeMessage": "Ansible desired state must not duplicate inventory-owned service members",
                })
        for deployment_id, member_id in sorted(inventory_members):
            if deployment_id not in deployments:
                placement_findings.append({
                    "apiVersion": "platform.installer/finding/v1alpha1",
                    "kind": "Finding", "code": "INVENTORY_DEPLOYMENT_NOT_FOUND",
                    "status": "BLOCKED", "category": "project-state",
                    "field": "platform_deployments.%s.%s" % (inventory_members[(deployment_id, member_id)]["host"], deployment_id),
                    "safeMessage": "Inventory member references an unknown deployment",
                })
        use_placements = True
    result = validate_project(
        manifest=manifest,
        topology=topology,
        desired_hosts=module.params["desired_hosts"],
        service_catalog=module.params["service_catalog"],
        inventory_hosts=module.params["inventory_hosts"],
        placements=placements if use_placements else None,
        host_scoped_deployments=host_scoped_deployments if isinstance(inventory_deployments, dict) else None,
        inventory_host_addresses=module.params["inventory_host_addresses"],
    )
    if use_placements:
        result["findings"].extend(placement_findings)
    try:
        schema_validator = SchemaValidator(module.params["contracts_root"])
        contracts_root = os.path.abspath(os.path.expanduser(module.params["contracts_root"]))
        schema_specs = [
            (os.path.join(contracts_root, "project", "v2alpha1", "project-manifest.schema.json"), manifest),
            (os.path.join(contracts_root, "project", "v2alpha1", "desired-state.schema.json"), schema_topology),
            (os.path.join(contracts_root, "service-catalog", "v1alpha1", "schema.json"), module.params["service_catalog"]),
        ]
        if module.params["generated_state"]:
            schema_specs.append((os.path.join(contracts_root, "project", "v2alpha1", "generated-state.schema.json"), module.params["generated_state"]))
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
    result["findings"].extend(state_findings)
    result["findings"].sort(key=lambda item: (item.get("field", ""), item.get("code", "")))
    blocked = [item for item in result["findings"] if item.get("status") == "BLOCKED"]
    result["summary"]["blocked"] = len(blocked)
    result["summary"]["pass"] = 0 if blocked else 1
    result["status"] = "BLOCKED" if blocked else "PASS"
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

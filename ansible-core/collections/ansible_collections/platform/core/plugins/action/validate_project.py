from __future__ import absolute_import, division, print_function

__metaclass__ = type

import os

from ansible.plugins.action import ActionBase

from ansible_collections.platform.core.plugins.module_utils.project_validation import (
    validate_project,
    write_validation_artifact,
)
from ansible_collections.platform.core.plugins.module_utils.project_state import (
    canonical_inventory_members,
    canonical_placements,
    select_desired_state,
    synthesize_ansible_manifest,
    topology_with_inventory_members,
)
from ansible_collections.platform.core.plugins.module_utils.schema_validation import (
    SchemaValidationError,
    SchemaValidator,
)


class ActionModule(ActionBase):
    """Run the controller-only validator without an AnsiballZ transfer."""

    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        del tmp
        task_vars = task_vars or {}
        args = self._task.args
        native = args.get("ansible_desired_state", {})
        topology, state_findings = select_desired_state(args["manifest"], args["topology"], native)
        manifest = args["manifest"]
        if native and not isinstance(manifest.get("desiredState"), dict):
            manifest = synthesize_ansible_manifest(topology, args["service_catalog"], args.get("project_id", "ansible-project"))
        schema_topology = topology
        inventory_deployments = args.get("inventory_deployments_by_host")
        use_inventory_members = isinstance(inventory_deployments, dict)
        use_placements = bool(native) or isinstance(args["manifest"].get("desiredState"), dict) or bool(args.get("placement_by_host"))
        placements, placement_findings = canonical_placements(
            args.get("placement_by_host", {}), args["inventory_hosts"]
        )
        if use_inventory_members:
            inventory_members, inventory_findings = canonical_inventory_members(
                inventory_deployments, args["inventory_hosts"]
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
            desired_hosts=args["desired_hosts"],
            service_catalog=args["service_catalog"],
            inventory_hosts=args["inventory_hosts"],
            placements=placements if use_placements else None,
            host_scoped_deployments=host_scoped_deployments if use_inventory_members else None,
            inventory_host_addresses=args.get("inventory_host_addresses", {}),
        )
        if use_placements:
            result["findings"].extend(placement_findings)
        try:
            validator = SchemaValidator(args["contracts_root"])
            root = os.path.abspath(os.path.expanduser(args["contracts_root"]))
            specs = [
                (os.path.join(root, "project", "v2alpha1", "project-manifest.schema.json"), manifest),
                (os.path.join(root, "project", "v2alpha1", "desired-state.schema.json"), schema_topology),
                (os.path.join(root, "service-catalog", "v1alpha1", "schema.json"), args["service_catalog"]),
            ]
            if args.get("generated_state"):
                specs.append((os.path.join(root, "project", "v2alpha1", "generated-state.schema.json"), args["generated_state"]))
            for schema_path, document in specs:
                result["findings"].extend(validator.validate(document, schema_path))
            host_schema = os.path.join(root, "project", "v2alpha1", "host-desired-vars.schema.json")
            for host in sorted(args["desired_hosts"]):
                result["findings"].extend(validator.validate(args["desired_hosts"][host], host_schema))
        except SchemaValidationError as error:
            result["findings"].append({
                "apiVersion": "platform.installer/finding/v1alpha1",
                "kind": "Finding",
                "code": "SCHEMA_VALIDATION_ENGINE_ERROR",
                "status": "BLOCKED",
                "category": "schema-validation",
                "field": "schema",
                "safeMessage": "Не удалось выполнить проверку опубликованной схемы",
                "safeDetails": {"reason": str(error).split(":", 1)[0]},
            })
        result["findings"].extend(state_findings)
        result["findings"].sort(key=lambda item: (item.get("field", ""), item.get("code", "")))
        blocked = [item for item in result["findings"] if item.get("status") == "BLOCKED"]
        result["summary"]["blocked"] = len(blocked)
        result["summary"]["pass"] = 0 if blocked else 1
        result["status"] = "BLOCKED" if blocked else "PASS"

        artifact_path = os.path.abspath(os.path.expanduser(args["artifact_path"]))
        write_validation_artifact(artifact_path, result)
        response = {
            "changed": False,
            "validation": result,
            "artifact_path": artifact_path,
        }
        if result["status"] == "BLOCKED":
            response.update({
                "failed": True,
                "msg": "Platform project validation is blocked; inspect the structured findings artifact",
                "error_code": "PROJECT_VALIDATION_BLOCKED",
            })
        return response

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import os

from ansible.plugins.action import ActionBase

from ansible_collections.platform.core.plugins.module_utils.project_validation import (
    validate_project,
    write_validation_artifact,
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
        result = validate_project(
            manifest=args["manifest"],
            topology=args["topology"],
            desired_hosts=args["desired_hosts"],
            service_catalog=args["service_catalog"],
            inventory_hosts=args["inventory_hosts"],
        )
        try:
            validator = SchemaValidator(args["contracts_root"])
            root = os.path.abspath(os.path.expanduser(args["contracts_root"]))
            specs = [
                (os.path.join(root, "project", "v2alpha1", "project-manifest.schema.json"), args["manifest"]),
                (os.path.join(root, "project", "v2alpha1", "desired-state.schema.json"), args["topology"]),
                (os.path.join(root, "service-catalog", "v1alpha1", "schema.json"), args["service_catalog"]),
            ]
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
        result["findings"].sort(key=lambda item: (item.get("field", ""), item.get("code", "")))
        result["summary"]["blocked"] = len(result["findings"])
        result["summary"]["pass"] = 0 if result["findings"] else 1
        result["status"] = "BLOCKED" if result["findings"] else "PASS"

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

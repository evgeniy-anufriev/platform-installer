"""Standalone authority assembly without enabling the Installer planner."""
import os
from ansible.plugins.action import ActionBase
from ansible_collections.platform.core.plugins.module_utils.application_runtime import prepare_runtime
from ansible_collections.platform.core.plugins.module_utils.schema_validation import SchemaValidator


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        values = task_vars or {}
        try:
            args = self._task.args
            root = os.path.realpath(args["project_root"])
            manifest_path = os.path.join(root, "project.yml")
            manifest = self._loader.load_from_file(manifest_path) if os.path.isfile(manifest_path) else {}
            native_lock = values.get("platform_artifact_lock")
            manifest_lock = (manifest or {}).get("artifactLock")
            if native_lock is not None and manifest_lock is not None and native_lock != manifest_lock:
                raise ValueError("APPLICATION_ARTIFACT_LOCK_CONFLICT")
            snapshot = args["snapshot"]
            jobs = prepare_runtime(root, snapshot, values["platform_application_rows"],
                                   values["platform_desired_state"], native_lock or manifest_lock or {},
                                   SchemaValidator(args["contracts_root"]), self._loader.load_from_file)
            for job in jobs:
                job["projectId"] = snapshot["project"]["id"]
            return {"changed": False, "jobs": jobs, "status": "PASS"}
        except (ValueError, KeyError, TypeError, OSError) as error:
            code = str(error)
            if not code.startswith("APPLICATION_") or not code.replace("_", "").isalnum():
                code = "APPLICATION_RUNTIME_INPUT_INVALID"
            return {"changed": False, "jobs": [], "status": "BLOCKED", "code": code}

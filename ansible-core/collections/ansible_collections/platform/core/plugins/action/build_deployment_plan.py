import json
import os
import tempfile

from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleError

from ansible_collections.platform.core.plugins.module_utils.deployment_plan import build_deployment_plan


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        del tmp, task_vars
        try:
            result = build_deployment_plan(self._task.args.get("snapshot"), self._task.args.get("service_catalog"), self._task.args.get("runtime_release"), self._task.args.get("created_at", "1970-01-01T00:00:00Z"), self._task.args.get("bundle_artifact_sources"), self._task.args.get("pki_materialization"))
            destination = os.environ.get("PLATFORM_EXECUTION_MANIFEST_OUTPUT")
            manifest = result["executionManifest"]
            if destination and manifest:
                parent = os.path.dirname(os.path.realpath(destination))
                if not os.path.isdir(parent) or os.path.islink(destination):
                    raise ValueError("DEPLOYMENT_PLAN_MANIFEST_DESTINATION_INVALID")
                descriptor, temporary = tempfile.mkstemp(prefix=".execution-manifest-", dir=parent)
                try:
                    os.fchmod(descriptor, 0o600)
                    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                        json.dump(manifest, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
                        stream.flush(); os.fsync(stream.fileno())
                    os.replace(temporary, destination)
                    os.chmod(destination, 0o600)
                finally:
                    if os.path.exists(temporary): os.unlink(temporary)
            return {"changed": False, "deployment_plan": result["deploymentPlan"], "execution_manifest_digest": result["executionManifestDigest"]}
        except (TypeError, ValueError, KeyError) as error:
            raise AnsibleError("DEPLOYMENT_PLAN_INPUT_INVALID: %s" % error)

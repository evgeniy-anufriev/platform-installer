import json
import os
import tempfile

from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleError

from ansible_collections.platform.core.plugins.module_utils.deployment_plan import build_deployment_plan
from ansible_collections.platform.core.plugins.module_utils.pki_reissue_state import inspect_reissue
from ansible_collections.platform.core.plugins.module_utils.project_validation import canonical_digest


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        del tmp, task_vars
        try:
            snapshot = self._task.args.get("snapshot")
            pki = self._task.args.get("pki_materialization")
            project = snapshot.get("project", {}) if isinstance(snapshot, dict) else {}
            reissue = []
            if (isinstance(snapshot, dict) and
                    isinstance(pki, dict) and pki.get("status") == "PASS" and
                    project.get("identitySource") == "PROJECT_MANIFEST" and
                    isinstance(snapshot.get("validation"), dict) and snapshot["validation"].get("status") == "PASS"):
                reissue = inspect_reissue(self._task.args.get("pki_state_root"), project.get("id"), pki.get("requests", []))
            result = build_deployment_plan(snapshot, self._task.args.get("service_catalog"), self._task.args.get("runtime_release"), self._task.args.get("created_at", "1970-01-01T00:00:00Z"), self._task.args.get("bundle_artifact_sources"), pki, self._task.args.get("execution_configuration"), self._task.args.get("execution_connections"), reissue, self._task.args.get("deployment_order"), application_image_lock=self._task.args.get("application_image_lock"), application_vault_sources=self._task.args.get("application_vault_sources"), application_library_order=self._task.args.get("application_library_order"), skip_application_libraries=self._task.args.get("skip_application_libraries"))
            mode = self._task.args.get("execution_mode") or ('FULL_PROJECT' if self._task.args.get('application_image_metadata') or self._task.args.get('skip_application_libraries') is not None else None)
            if mode is not None:
                import sys
                from pathlib import Path
                tools = str(Path(__file__).resolve().parents[6] / 'tools')
                if tools not in sys.path:
                    sys.path.insert(0, tools)
                from infrastructure_verification import scope_plan
                result = scope_plan(result, mode, self._task.args.get("pki_state_root"),
                                    self._task.args.get('skip_infrastructure_verify', False))
            if self._task.args.get('application_image_metadata'):
                result['deploymentPlan'].update(apiVersion='platform.installer/plan/v1alpha7',
                    skipInfrastructureVerify=self._task.args.get('skip_infrastructure_verify', False))
                if result.get('executionManifest'):
                    result['executionManifest'].update(apiVersion='platform.installer/execution-manifest/v1alpha5',
                        skipInfrastructureVerify=self._task.args.get('skip_infrastructure_verify', False))
            if self._task.args.get('skip_application_libraries') is not None:
                from ansible_collections.platform.core.plugins.module_utils.application_selection import execution_scope
                scope = execution_scope(snapshot, self._task.args.get('application_library_order'), self._task.args['skip_application_libraries'])
                for document, version in ((result['deploymentPlan'], 'platform.installer/plan/v1alpha8'),
                                          (result.get('executionManifest'), 'platform.installer/execution-manifest/v1alpha6')):
                    if document is not None:
                        document.update(apiVersion=version, skipApplicationLibraries=scope['skippedLibraries'], applicationExecutionScope=scope,
                                        skipInfrastructureVerify=self._task.args.get('skip_infrastructure_verify', False))
            from ansible_collections.platform.core.plugins.module_utils.application_post_install import promote
            from ansible_collections.platform.core.plugins.module_utils.application_selection import execution_scope
            result = promote(result, execution_scope(snapshot, self._task.args.get('application_library_order'), self._task.args.get('skip_application_libraries')),
                             self._task.args.get('skip_infrastructure_verify', False))
            result['executionManifestDigest'] = canonical_digest(result['executionManifest']) if result.get('executionManifest') else None
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

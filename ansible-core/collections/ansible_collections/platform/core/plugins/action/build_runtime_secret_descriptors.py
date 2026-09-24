from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleError

from ansible_collections.platform.core.plugins.module_utils.deployment_plan import _pki_store_password_requirements, _service_runtime_secret_requirements
from ansible_collections.platform.core.plugins.module_utils.project_validation import canonical_digest


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        del tmp, task_vars
        snapshot, catalog = self._task.args.get("snapshot"), self._task.args.get("service_catalog")
        if not isinstance(snapshot, dict) or not isinstance(catalog, dict):
            raise AnsibleError("RUNTIME_SECRET_DESCRIPTORS_INPUT_INVALID")
        definitions = catalog.get("definitions", {})
        deployments = snapshot.get("serviceDeployments", {})
        hosts = sorted(snapshot.get("hosts", {}).keys()) if isinstance(snapshot.get("hosts"), dict) else []
        public, private, findings = _service_runtime_secret_requirements(deployments, definitions, hosts)
        pki_public, _, pki_findings = _pki_store_password_requirements(self._task.args.get("pki_materialization"))
        findings.extend(pki_findings)
        if findings:
            raise AnsibleError("RUNTIME_SECRET_DESCRIPTORS_BLOCKED")
        labels = {}
        for deployment_id, deployment in deployments.items():
            definition = definitions.get(deployment.get("serviceType"), {}) if isinstance(deployment, dict) else {}
            for setting in ((definition.get("configuration") or {}).get("settings") or {}).values():
                extension = ((setting.get("ui") or {}).get("x-runtimeSecretRequirement") if isinstance(setting, dict) else None)
                if isinstance(extension, dict) and isinstance(extension.get("requirementRef"), str):
                    labels[(deployment_id, extension["requirementRef"])] = (setting.get("ui") or {}).get("label")
        descriptors = [{"requirementRef": item["requirementRef"], "purpose": item["purpose"], "serviceDeployment": None, "displayLabel": "PKI store password", "hosts": item["hosts"]} for item in pki_public]
        for item in private:
            label = labels.get((item["serviceDeployment"], item["requirementRef"]))
            if not isinstance(label, str) or not label or len(label.encode("utf-8")) > 160:
                raise AnsibleError("RUNTIME_SECRET_DESCRIPTORS_BLOCKED")
            descriptors.append({"requirementRef": item["requirementRef"], "purpose": item["purpose"], "serviceDeployment": item["serviceDeployment"], "displayLabel": label, "hosts": item["hosts"]})
        descriptors.sort(key=lambda item: (item["serviceDeployment"] or "", item["requirementRef"]))
        if len(descriptors) > 16 or any(len(item["hosts"]) > 256 for item in descriptors):
            raise AnsibleError("RUNTIME_SECRET_DESCRIPTORS_BLOCKED")
        return {"changed": False, "runtime_secret_descriptors": {"projectIdentity": snapshot.get("project", {}).get("id"), "projectRevision": snapshot.get("projectRevision"), "descriptors": descriptors, "descriptorSetFingerprint": canonical_digest([{key: item[key] for key in ("requirementRef", "purpose", "serviceDeployment", "hosts")} for item in descriptors])}}

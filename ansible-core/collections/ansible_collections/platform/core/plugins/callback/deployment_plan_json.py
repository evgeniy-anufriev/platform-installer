from __future__ import absolute_import, division, print_function
import json
import os
import tempfile
from ansible.plugins.callback import CallbackBase


class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "aggregate"
    CALLBACK_NAME = "platform.core.deployment_plan_json"
    CALLBACK_NEEDS_ENABLED = True

    def _write(self, payload, variable="PLATFORM_DEPLOYMENT_PLAN_OUTPUT"):
        destination = os.environ.get(variable)
        if not destination or not os.path.isdir(os.path.dirname(os.path.realpath(destination))):
            return
        descriptor, temporary = tempfile.mkstemp(prefix=".deployment-plan-", dir=os.path.dirname(os.path.realpath(destination)))
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
                stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, destination)
            os.chmod(destination, 0o600)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)

    def v2_runner_on_ok(self, result):
        if getattr(result._task, "action", "") == "platform.core.build_deployment_plan":
            plan = result._result.get("deployment_plan")
            if isinstance(plan, dict): self._write(plan)

    def v2_runner_on_failed(self, result, ignore_errors=False):
        del ignore_errors
        value = result._result if isinstance(result._result, dict) else {}
        finding = value.get("finding") if isinstance(value.get("finding"), dict) else {}
        safe_finding = {
            key: finding[key]
            for key in ("apiVersion", "kind", "code", "status", "category", "field", "safeMessage")
            if isinstance(finding.get(key), str)
        }
        payload = {
            "apiVersion": "platform.installer/core-diagnostic/v1alpha1",
            "status": "FAILED",
            "operation": getattr(result._task, "action", "") or "UNKNOWN",
            "errorCode": value.get("error_code") if isinstance(value.get("error_code"), str) else "CORE_OPERATION_FAILED",
            "findings": [safe_finding] if safe_finding.get("code") else [],
        }
        self._write(payload, "PLATFORM_CORE_DIAGNOSTIC_OUTPUT")

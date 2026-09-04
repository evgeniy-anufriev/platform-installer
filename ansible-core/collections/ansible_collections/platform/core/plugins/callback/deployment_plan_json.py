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

    def _write(self, payload):
        destination = os.environ.get("PLATFORM_DEPLOYMENT_PLAN_OUTPUT")
        if not destination or not os.path.isdir(os.path.dirname(os.path.realpath(destination))):
            return
        descriptor, temporary = tempfile.mkstemp(prefix=".deployment-plan-", dir=os.path.dirname(os.path.realpath(destination)))
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
                stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)

    def v2_runner_on_ok(self, result):
        if getattr(result._task, "action", "") == "platform.core.build_deployment_plan":
            plan = result._result.get("deployment_plan")
            if isinstance(plan, dict): self._write(plan)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.plugins.callback import CallbackBase
from ansible_collections.platform.core.plugins.module_utils.project_snapshot_output import write_snapshot_output, snapshot_failure_published


class CallbackModule(CallbackBase):
    """Write the UI-BE ProjectSnapshot response to a caller-owned temp file."""

    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "aggregate"
    CALLBACK_NAME = "platform.core.project_snapshot_json"
    CALLBACK_NEEDS_ENABLED = True

    def _write(self, payload):
        write_snapshot_output(payload)

    def v2_runner_on_ok(self, result):
        if getattr(result._task, "action", "") == "platform.core.project_snapshot":
            snapshot = result._result.get("snapshot")
            if isinstance(snapshot, dict):
                self._write(snapshot)

    def v2_runner_on_failed(self, result, ignore_errors=False):
        del ignore_errors
        if getattr(result._task, "action", "") == "platform.core.project_snapshot":
            if snapshot_failure_published():
                return
            self._write({"adapterError": result._result.get("finding", {
                "code": "PROJECT_SNAPSHOT_INPUT_INVALID",
                "safeMessage": "Задача platform.core.project_snapshot завершилась без диагностического результата action.",
            })})

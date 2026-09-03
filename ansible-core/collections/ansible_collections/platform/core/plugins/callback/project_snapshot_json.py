from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
import os
import tempfile

from ansible.plugins.callback import CallbackBase


class CallbackModule(CallbackBase):
    """Write the UI-BE ProjectSnapshot response to a caller-owned temp file."""

    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "aggregate"
    CALLBACK_NAME = "platform.core.project_snapshot_json"
    CALLBACK_NEEDS_ENABLED = True

    def _write(self, payload):
        destination = os.environ.get("PLATFORM_PROJECT_SNAPSHOT_OUTPUT")
        if not destination:
            return
        directory = os.path.dirname(os.path.realpath(destination))
        if not os.path.isdir(directory):
            return
        descriptor, temporary = tempfile.mkstemp(prefix=".project-snapshot-", dir=directory)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                json.dump(payload, output, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def v2_runner_on_ok(self, result):
        if getattr(result._task, "action", "") == "platform.core.project_snapshot":
            snapshot = result._result.get("snapshot")
            if isinstance(snapshot, dict):
                self._write(snapshot)

    def v2_runner_on_failed(self, result, ignore_errors=False):
        del ignore_errors
        if getattr(result._task, "action", "") == "platform.core.project_snapshot":
            self._write({"adapterError": result._result.get("finding", {
                "code": "PROJECT_SNAPSHOT_INPUT_INVALID",
                "safeMessage": "Project snapshot could not be built",
            })})

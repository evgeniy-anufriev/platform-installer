from __future__ import absolute_import, division, print_function

import os
import re
import sys
import time

from ansible.plugins.callback import CallbackBase


DOCUMENTATION = r"""
name: execution_events_json
type: aggregate
short_description: Emit safe Ansible task progress into an owned execution journal
version_added: "1.0.0"
description:
  - Emits bounded task lifecycle details into the authoritative Execution Node journal.
  - The callback is disabled unless explicitly enabled by the trusted execution controller.
requirements:
  - A controller-owned active Platform Installer execution journal.
"""


_CORE_ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", ".."))
_TOOLS_ROOT = os.path.join(_CORE_ROOT, "tools")
if _TOOLS_ROOT not in sys.path:
    sys.path.insert(0, _TOOLS_ROOT)

from execution_lifecycle import Journal  # noqa: E402


EXECUTION_STATE_ROOT = "/var/lib/platform-installer/execution"
SAFE_ROLE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,255}$")


class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "aggregate"
    CALLBACK_NAME = "platform.core.execution_events_json"
    CALLBACK_NEEDS_ENABLED = True

    def __init__(self):
        super(CallbackModule, self).__init__()
        self._starts = {}

    def _context(self):
        return {
            "phaseId": os.environ.get("PLATFORM_EXECUTION_PHASE_ID", ""),
            "actionId": os.environ.get("PLATFORM_EXECUTION_ACTION_ID", ""),
            "serviceDeployment": os.environ.get("PLATFORM_EXECUTION_SERVICE_DEPLOYMENT", ""),
        }

    def _run_id(self):
        return os.environ.get("PLATFORM_EXECUTION_RUN_ID", "")

    def _uuid(self, task):
        value = getattr(task, "_uuid", "")
        return str(value) if value is not None else ""

    def _role(self, task):
        role = getattr(task, "_role", None)
        try:
            value = role.get_name() if role is not None else ""
        except Exception:
            return ""
        return value if isinstance(value, str) and SAFE_ROLE.match(value) else ""

    def _name(self, task, no_log):
        if no_log:
            return ""
        try:
            value = task.get_name()
        except Exception:
            return ""
        return value if isinstance(value, str) else ""

    def _no_log(self, task, result=None):
        if bool(getattr(task, "no_log", False)):
            return True
        payload = getattr(result, "_result", {}) if result is not None else {}
        return isinstance(payload, dict) and bool(payload.get("_ansible_no_log"))

    def _host(self, result):
        host = getattr(result, "_host", None)
        try:
            value = host.get_name() if host is not None else ""
        except Exception:
            return ""
        return value if isinstance(value, str) else ""

    def _elapsed(self, task_uuid):
        started = self._starts.get(task_uuid)
        if started is None:
            return None
        return max(0, int((time.monotonic() - started) * 1000))

    def _emit(self, event_type, status, task, result=None):
        run_id = self._run_id()
        if not run_id:
            return
        task_uuid = self._uuid(task)
        no_log = self._no_log(task, result)
        try:
            Journal(EXECUTION_STATE_ROOT, run_id).task_event(
                event_type,
                status,
                task_uuid,
                host=self._host(result) if result is not None else "",
                role=self._role(task),
                name=self._name(task, no_log),
                elapsed_milliseconds=self._elapsed(task_uuid) if event_type == "TASK_COMPLETED" else None,
                no_log=no_log,
                **self._context()
            )
        except Exception:
            try:
                Journal(EXECUTION_STATE_ROOT, run_id).mark_task_observability_degraded("TASK_EVENT_WRITE_FAILED")
            except Exception:
                pass

    def v2_playbook_on_task_start(self, task, is_conditional):
        del is_conditional
        task_uuid = self._uuid(task)
        if task_uuid:
            self._starts[task_uuid] = time.monotonic()
        self._emit("TASK_STARTED", "RUNNING", task)

    def v2_runner_on_ok(self, result):
        payload = result._result if isinstance(result._result, dict) else {}
        self._emit("TASK_COMPLETED", "CHANGED" if payload.get("changed") else "SUCCESS", result._task, result)

    def v2_runner_on_skipped(self, result):
        self._emit("TASK_COMPLETED", "SKIPPED", result._task, result)

    def v2_runner_on_failed(self, result, ignore_errors=False):
        del ignore_errors
        self._emit("TASK_COMPLETED", "FAILED", result._task, result)

    def v2_runner_on_unreachable(self, result):
        self._emit("TASK_COMPLETED", "FAILED", result._task, result)

    def v2_runner_on_async_ok(self, result):
        self.v2_runner_on_ok(result)

    def v2_runner_on_async_failed(self, result):
        self.v2_runner_on_failed(result)

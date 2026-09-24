from __future__ import absolute_import, division, print_function
import json
import os
import tempfile
from ansible.plugins.callback import CallbackBase


class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "aggregate"
    CALLBACK_NAME = "platform.core.runtime_secret_descriptors_json"
    CALLBACK_NEEDS_ENABLED = True

    def v2_runner_on_ok(self, result):
        if getattr(result._task, "action", "") != "platform.core.build_runtime_secret_descriptors":
            return
        payload = result._result.get("runtime_secret_descriptors")
        destination = os.environ.get("PLATFORM_RUNTIME_SECRET_DESCRIPTORS_OUTPUT")
        if not isinstance(payload, dict) or not destination:
            return
        parent = os.path.dirname(os.path.realpath(destination))
        if not os.path.isdir(parent):
            return
        descriptor, temporary = tempfile.mkstemp(prefix=".runtime-secret-descriptors-", dir=parent)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
                stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, destination); os.chmod(destination, 0o600)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)

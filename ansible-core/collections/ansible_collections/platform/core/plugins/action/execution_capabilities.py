from __future__ import absolute_import, division, print_function

__metaclass__ = type

import os

from ansible.errors import AnsibleError
from ansible.plugins.action import ActionBase

from ansible_collections.platform.core.plugins.module_utils.execution_capabilities import build_capabilities, core_version


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        del tmp, task_vars
        try:
            runtime_root = os.path.realpath(self._task.args.get("runtime_root", ""))
            manifest_path = os.path.join(runtime_root, "manifest.yaml")
            if not os.path.isfile(manifest_path):
                raise AnsibleError("Activated runtime manifest is missing")
            manifest = self._loader.load_from_file(manifest_path)
            manifest["bundleDigest"] = self._task.args.get("bundle_digest", "")
            collection_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            return {
                "changed": False,
                "capabilities": build_capabilities(manifest, core_version(collection_root)),
            }
        except (AnsibleError, OSError, TypeError, ValueError):
            return {
                "failed": True,
                "changed": False,
                "error_code": "EXECUTION_RUNTIME_CAPABILITIES_INVALID",
                "msg": "Activated Execution runtime capabilities could not be verified",
            }

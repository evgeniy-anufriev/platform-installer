"""Execute the production file-model tasks; no services or target files change."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml


ROLE = Path(__file__).resolve().parents[1] / "ansible_collections/platform/haproxy/roles/haproxy"


class BackendHostScopeRuntimeTests(unittest.TestCase):
    def test_full_and_partial_models_filter_hosts_and_preserve_other_sources(self):
        executable = shutil.which("ansible-playbook")
        if not executable:
            self.skipTest("ansible-playbook is required")
        tasks = yaml.safe_load((ROLE / "tasks/prepare.yml").read_text(encoding="utf-8"))
        names = {"Select complete managed application backend file model",
                 "Retain exact proven backend inventory in base mode",
                 "Select only this source deployment backend for partial integration"}
        selected = [task for task in tasks if task.get("name") in names]
        backend = {"targetDeploymentId": "app", "providerHostIds": ["node1", "node2"],
                   "configFileName": "30-backend-app-public.cfg"}
        plays = []
        for partial in (False, True):
            for host in ("node1", "node2", "node3"):
                expected = [backend["configFileName"]] if host != "node3" else []
                if partial:
                    expected.append("30-backend-other-public.cfg")
                variables = {
                    "inventory_hostname": host, "platform_deployments": {"proxy": {}},
                    "platform_haproxy_full_reconcile": not partial,
                    "platform_haproxy_runtime_projection": {"backends": {"backends": {"proxy": [backend]}}},
                    "_platform_haproxy_prior_backend_capture": {"previousInventory": [
                        {"name": "30-backend-app-old.cfg"}, {"name": "30-backend-other-public.cfg"}]},
                    "expected_files": sorted(expected),
                    "expected_source_count": 0 if host == "node3" else 1,
                }
                if partial:
                    variables["platform_haproxy_partial_deployment_id"] = "app"
                plays.append({"hosts": "localhost", "connection": "local", "gather_facts": False,
                              "vars": variables, "tasks": selected + [{"ansible.builtin.assert": {"fail_msg": "{{ platform_haproxy_managed_application_backend_files }} != {{ expected_files }}", "that": [
                                  "platform_haproxy_managed_application_backend_files == expected_files",
                                  "platform_haproxy_application_backends | length == expected_source_count",
                              ]}}]})
        with tempfile.TemporaryDirectory(prefix="platform-haproxy-hosts-") as temporary:
            path = Path(temporary, "test.yml")
            path.write_text(yaml.safe_dump(plays, sort_keys=False), encoding="utf-8")
            result = subprocess.run([executable, "-i", "localhost,", str(path)],
                                    capture_output=True, text=True, timeout=60)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_all_partial_phases_target_only_resolved_hosts(self):
        executable = shutil.which("ansible-playbook")
        if not executable:
            self.skipTest("ansible-playbook is required")
        source = yaml.safe_load((ROLE.parents[4] / "playbooks/integrate.yml").read_text(encoding="utf-8"))
        plays = [{"hosts": "localhost", "gather_facts": False, "tasks": [{"ansible.builtin.set_fact": {
            "platform_service_integration_projection": {"haproxyHosts": ["node2"]}}}]}]
        for original in source:
            plays.append({"hosts": original["hosts"], "gather_facts": False, "tasks": [
                {"ansible.builtin.assert": {"that": ["inventory_hostname == 'node2'"]}}]})
        with tempfile.TemporaryDirectory(prefix="platform-haproxy-phases-") as temporary:
            path = Path(temporary, "test.yml")
            path.write_text(yaml.safe_dump(plays, sort_keys=False), encoding="utf-8")
            result = subprocess.run([executable, "-i", "localhost,node1,node2,node3,", str(path)],
                                    capture_output=True, text=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertNotIn("ok: [node1]", result.stdout)
        self.assertNotIn("ok: [node3]", result.stdout)


if __name__ == "__main__":
    unittest.main()

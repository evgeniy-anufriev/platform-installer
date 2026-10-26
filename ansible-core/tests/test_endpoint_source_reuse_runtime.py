"""Exercise endpoint orchestration and the real endpoint action across host scopes."""
import os
import copy
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

CORE = Path(__file__).resolve().parents[1] / "collections/ansible_collections/platform/core"


class EndpointSourceReuseRuntimeTests(unittest.TestCase):
    def test_service_shortcuts_keep_app_fallback_and_validate_partial_scope(self):
        if not shutil.which("ansible-playbook"):
            self.skipTest("Ansible runtime required")
        root_repo = CORE.parents[4]
        integration = yaml.safe_load((root_repo / "services/integrations/tasks/resolve-source.yml").read_text())
        service_include = copy.deepcopy(next(t for t in integration if "ansible.builtin.include_role" in t))
        haproxy = root_repo / "services/haproxy/ansible_collections/platform/haproxy/roles/haproxy/tasks"
        proxy_include = copy.deepcopy(next(t for t in yaml.safe_load((haproxy / "resolve.yml").read_text())
                                           if "ansible.builtin.include_role" in t))
        for task in (service_include, proxy_include):
            task["ansible.builtin.include_role"]["name"] = "qa_endpoint"
        with tempfile.TemporaryDirectory(prefix="platform-service-endpoint-") as directory:
            root = Path(directory)
            role = root / "roles/qa_endpoint/tasks"
            role.mkdir(parents=True)
            (role / "main.yml").write_text(yaml.safe_dump([{"ansible.builtin.set_fact": {
                "resolver_called": True, "platform_endpoint_sources": {"gateway-app": {}}}}]))
            service_include["vars"] = {"_platform_integration_source_id": "infra"}
            app_include = copy.deepcopy(service_include)
            app_include["vars"] = {"_platform_integration_source_id": "gateway-app"}
            tasks = [service_include, {"ansible.builtin.assert": {"that": [
                "resolver_called is not defined", "platform_endpoint_sources is not defined"]}},
                app_include, {"ansible.builtin.assert": {"that": ["resolver_called | bool", "'gateway-app' in platform_endpoint_sources"]}}]
            cases = [(False, ["infra"], False, True), (False, ["infra", "gateway-app"], True, True),
                     (True, None, True, True), (False, [], False, False), (False, ["bad/id"], False, False)]
            plays = [{"hosts": "localhost", "connection": "local", "gather_facts": False,
                      "vars": {"platform_desired_state": {"serviceDeployments": {"infra": {}}}}, "tasks": tasks}]
            for full, partial, called, success in cases:
                variables = {"platform_desired_state": {"serviceDeployments": {"infra": {}}},
                             "platform_haproxy_full_reconcile": full}
                if partial is not None:
                    variables["platform_haproxy_partial_deployment_ids"] = partial
                plays.append({"hosts": "localhost", "connection": "local", "gather_facts": False,
                    "vars": variables, "tasks": [
                        {"ansible.builtin.set_fact": {"resolver_called": False}},
                        {"ansible.builtin.include_tasks": str(haproxy / "partial_scope.yml")}, proxy_include,
                        {"ansible.builtin.assert": {"that": ["resolver_called | bool == " + str(called).lower()]}}]})
            for number, play_data in enumerate(plays):
                file = root / "play.yml"
                file.write_text(yaml.safe_dump([play_data]))
                result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(file)],
                                        cwd=root, capture_output=True, text=True, timeout=60)
                expected = number == 0 or cases[number - 1][3]
                self.assertEqual(expected, result.returncode == 0, result.stdout + result.stderr)

    def test_controller_rows_standalone_fallback_and_existing_sources(self):
        if not shutil.which("ansible-playbook"):
            self.skipTest("Ansible runtime required")
        rows = [{"instanceId": "gateway-sdku", "libraryId": "sdku", "hostId": host,
                 "settings": {"ports": {"http": {"published": 18081}},
                              "endpoint": {"enabled": True, "listener": "http", "endpoint_group": "apps",
                                           "probe": {"path": "/status"}}}} for host in ("h1", "h2")]
        desired = {"applicationLibraryDeployments": {"sdku": {}},
                   "endpointGroups": {"apps": {"address": {"domain": "apps.example.test"}}},
                   "serviceDeployments": {"vip": {"serviceType": "keepalived", "endpointGroupRef": "apps"},
                                          "proxy": {"serviceType": "haproxy", "endpointGroup": "apps"}}}
        with tempfile.TemporaryDirectory(prefix="platform-endpoint-reuse-") as directory:
            root = Path(directory)
            collection = root / "collections/ansible_collections/platform/core"
            (collection / "roles").mkdir(parents=True)
            shutil.copytree(CORE / "roles/resolve_endpoint_sources", collection / "roles/resolve_endpoint_sources")
            # Only the expensive input resolver is replaced. The endpoint action
            # and its projection/validation modules are the production plugins.
            (collection / "plugins").symlink_to(CORE / "plugins", target_is_directory=True)
            fallback = collection / "roles/resolve_application_libraries/tasks"
            fallback.mkdir(parents=True)
            (fallback / "main.yml").write_text(yaml.safe_dump([{"ansible.builtin.set_fact": {
                "resolver_called": True, "platform_application_rows": rows}}]))
            inventory = root / "inventory.yml"
            inventory.write_text(yaml.safe_dump({"all": {"children": {"platform_targets": {"hosts": {
                host: {"ansible_connection": "local", "ansible_host": address,
                       "platform_deployments": {"vip": {}, "proxy": {}}}
                for host, address in (("h1", "192.0.2.1"), ("h2", "192.0.2.2"))}}}}}))
            catalog = root / "catalog.yml"
            catalog.write_text(yaml.safe_dump({"definitions": {"haproxy": {"endpoint": {}}}}))
            environment = dict(os.environ)
            environment["ANSIBLE_COLLECTIONS_PATH"] = str(root / "collections") + ":" + str(CORE.parents[2])
            for mode in ("controller-rows", "standalone", "existing-sources"):
                with self.subTest(mode=mode):
                    setup = []
                    if mode == "controller-rows":
                        setup = [{"ansible.builtin.set_fact": {"platform_application_rows": rows}}]
                    elif mode == "existing-sources":
                        setup = [{"ansible.builtin.set_fact": {"platform_endpoint_sources": {"retained": {}}}}]
                    assertions = ["(resolver_called | default(false) | bool) == " +
                                  ("true" if mode == "standalone" else "false")]
                    if mode == "existing-sources":
                        assertions.append("hostvars['localhost'].platform_endpoint_sources == {'retained': {}}")
                    else:
                        assertions += ["hostvars['localhost'].platform_endpoint_sources['gateway-sdku'].targets | length == 2",
                                       "hostvars['localhost'].platform_endpoint_sources['gateway-sdku'].targets | map(attribute='hostId') | sort == ['h1', 'h2']"]
                    plays = [{"hosts": "localhost", "gather_facts": False, "tasks": setup},
                             {"hosts": "platform_targets", "gather_facts": False,
                              "vars": {"platform_desired_state": desired, "platform_service_catalog_path": str(catalog)},
                              "tasks": [{"ansible.builtin.include_role": {"name": "platform.core.resolve_endpoint_sources"}},
                                        {"ansible.builtin.assert": {"that": assertions}, "run_once": True}]}]
                    play = root / "play.yml"
                    play.write_text(yaml.safe_dump(plays))
                    result = subprocess.run(["ansible-playbook", "-i", str(inventory), str(play)],
                                            cwd=root, env=environment, capture_output=True, text=True, timeout=60)
                    self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                    self.assertRegex(result.stdout, r"changed=0\s")


if __name__ == "__main__":
    unittest.main()

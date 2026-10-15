import os
import unittest

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined


ROOT = os.path.join(os.path.dirname(__file__), "..")
ROLE = os.path.join(ROOT, "ansible_collections", "platform", "haproxy", "roles", "haproxy")


class HAProxyGlobalLogContractTests(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROLE, "defaults", "main.yml"), encoding="utf-8") as stream:
            self.defaults = yaml.safe_load(stream)
        self.template = Environment(
            loader=FileSystemLoader(os.path.join(ROLE, "templates")),
            trim_blocks=True, lstrip_blocks=True, undefined=StrictUndefined,
        ).get_template("haproxy.cfg.j2")

    def render(self, logs):
        settings = dict(self.defaults["platform_haproxy_global"])
        settings["log"] = logs
        return self.template.render(
            platform_haproxy_global=settings,
            platform_haproxy_defaults=self.defaults["platform_haproxy_defaults"],
            platform_haproxy_runtime_socket_path=self.defaults["platform_haproxy_runtime_socket_path"],
        )

    def test_address_and_facility_render_as_one_log_directive(self):
        rendered = self.render([{"address": "/dev/log", "facility": "local0"}])
        self.assertIn("    log /dev/log local0\n", rendered)
        self.assertIn("    maxconn ", rendered)

    def test_optional_level_renders_on_same_directive(self):
        rendered = self.render([{"address": "/dev/log", "facility": "local1", "level": "notice"}])
        self.assertIn("    log /dev/log local1 notice\n", rendered)

    def test_template_requires_facility_in_input_contract(self):
        with self.assertRaises(Exception):
            self.render([{"address": "/dev/log"}])

    def test_multiple_logs_render_deterministically(self):
        rendered = self.render([
            {"address": "z-log", "facility": "local1"},
            {"address": "a-log", "facility": "local0"},
        ])
        self.assertLess(rendered.index("log a-log local0"), rendered.index("log z-log local1"))


class HAProxySystemdRuntimeDirectoryTests(unittest.TestCase):
    def test_dropin_creates_socket_parent_at_each_service_start(self):
        with open(os.path.join(ROLE, "templates", "haproxy-runtime-directory.conf.j2"), encoding="utf-8") as stream:
            dropin = stream.read()
        with open(os.path.join(ROLE, "tasks", "start.yml"), encoding="utf-8") as stream:
            start_tasks = yaml.safe_load(stream)
        with open(os.path.join(ROLE, "defaults", "main.yml"), encoding="utf-8") as stream:
            defaults = yaml.safe_load(stream)

        self.assertIn("RuntimeDirectory=haproxy", dropin)
        self.assertIn("RuntimeDirectoryMode=0755", dropin)
        self.assertEqual("/run/haproxy/admin.sock", defaults["platform_haproxy_runtime_socket_path"])
        self.assertEqual(4, len(start_tasks))
        self.assertTrue(start_tasks[1]["ansible.builtin.template"]["src"].endswith("runtime-directory.conf.j2"))
        service_task = start_tasks[2]["ansible.builtin.systemd"]
        self.assertTrue(service_task["daemon_reload"])
        self.assertIn("_platform_haproxy_runtime_dropin.changed", service_task["state"])
        self.assertEqual("(platform_haproxy_partial_deployment_id is not defined and platform_haproxy_partial_deployment_ids is not defined)", start_tasks[2]["when"])
        partial_reload = start_tasks[3]
        self.assertEqual("reloaded", partial_reload["ansible.builtin.systemd"]["state"])
        self.assertIn("platform_haproxy_active_artifacts_changed | default(false) | bool", partial_reload["when"])


if __name__ == "__main__":
    unittest.main()

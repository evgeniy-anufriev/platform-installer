import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("ansible-playbook"), "Ansible runtime required")
class RuntimeRoleVariablesTests(unittest.TestCase):
    def run_role(self, variables, assertions, native=False, expected=0):
        play = [{"hosts": "localhost", "connection": "local", "gather_facts": False,
                 "vars": {"platform_execution_role_variables_by_host": variables},
                 "tasks": [{"include_role": {"name": "platform.core.runtime_role_variables"}},
                           {"assert": {"that": assertions}}]}]
        with tempfile.TemporaryDirectory(prefix="runtime-fact-test-") as directory:
            path = Path(directory) / "probe.json"
            path.write_text(json.dumps(play), encoding="utf-8")
            result = subprocess.run(
                ["ansible-playbook", "-i", "localhost,", str(path)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60,
                env=dict(os.environ, ANSIBLE_CONFIG=str(ROOT / "ansible.cfg"),
                         ANSIBLE_COLLECTIONS_PATH=str(ROOT / "collections"),
                         ANSIBLE_JINJA2_NATIVE=str(native), ANSIBLE_NOCOLOR="1"))
        self.assertEqual(expected, result.returncode, "Local typed fact probe failed")
        if expected == 0:
            self.assertIn(b"changed=0", result.stdout)

    def test_native_types_and_string_identity_are_preserved(self):
        values = {"qa_integer": 8200, "qa_number": 1.5, "qa_boolean": True,
                  "qa_string": "8200", "qa_false_string": "false",
                  "qa_list": [8200, "8200", False], "qa_map": {"port": 8200},
                  "qa_null": None}
        assertions = ["qa_integer is integer and qa_integer == 8200",
                      "qa_number is number and qa_number == 1.5",
                      "qa_boolean is boolean and qa_boolean",
                      "qa_string is string and qa_string == '8200'",
                      "qa_false_string is string and qa_false_string == 'false'",
                      "qa_list[0] is integer", "qa_list[1] is string",
                      "qa_list[2] is boolean", "qa_map.port is integer", "qa_null is none"]
        values = {"platform_" + key: value for key, value in values.items()}
        assertions = [item.replace("qa_", "platform_qa_") for item in assertions]
        for native in (False, True):
            with self.subTest(native=native):
                self.run_role({"localhost": values}, assertions, native)

    def test_empty_mapping_is_a_noop(self):
        self.run_role({"localhost": {}}, ["platform_qa_integer is not defined"])

    def test_missing_host_and_malformed_mapping_fail_closed(self):
        for values in ({}, {"localhost": []}, [], {"localhost": {"ansible_connection": "ssh"}},
                       {"localhost": {"platform_bad-name": "value"}}):
            with self.subTest(values=values):
                self.run_role(values, ["true"], expected=2)

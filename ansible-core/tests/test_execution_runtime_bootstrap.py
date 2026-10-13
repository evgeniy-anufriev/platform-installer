"""Supplementary POSIX bootstrap behavior tests; RPM/DNF are isolated fakes."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "tools/bootstrap_execution_runtime.sh"
REQUIRED = ["python3", "ansible-core", "openssl", "ca-certificates", "tar", "gzip"]


class RuntimeBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="runtime-bootstrap-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.state = self.root / "state.json"
        self.state.write_text(json.dumps(REQUIRED), encoding="utf-8")
        self.calls = self.root / "dnf.json"
        identity = {}
        for line in Path("/etc/os-release").read_text().splitlines():
            key, _, value = line.partition("=")
            if key in {"ID", "VERSION_ID"}:
                identity[key] = value.strip('"\'')
        if identity.get("ID") != "redos":
            self.skipTest("requires RED OS current-source QA environment")
        self.platform = "{}:{}:{}".format(identity["ID"], identity["VERSION_ID"], os.uname().machine)
        self.packages = self.root / "runtime/packages" / identity["ID"] / identity["VERSION_ID"] / os.uname().machine
        self.packages.mkdir(parents=True)
        self.environment = dict(os.environ, PATH=str(self.bin) + ":" + os.environ["PATH"],
                                TEST_STATE=str(self.state), TEST_CALLS=str(self.calls))
        for name, content in {
            "id": "#!/bin/sh\nprintf '0\\n'\n",
            "rpm": """#!/usr/bin/python3
import json, os, pathlib, sys
if sys.argv[1] == '-q':
    sys.exit(0 if sys.argv[2] in json.loads(pathlib.Path(os.environ['TEST_STATE']).read_text()) else 1)
data=pathlib.Path(sys.argv[-1]).read_text()
if data == 'CORRUPT': sys.exit(1)
print(data,end='')
""",
            "dnf": """#!/usr/bin/python3
import json, os, pathlib, sys
pathlib.Path(os.environ['TEST_CALLS']).write_text(json.dumps(sys.argv[1:]))
if os.environ.get('TEST_DNF_FAIL') == '1': sys.exit(1)
state=pathlib.Path(os.environ['TEST_STATE']); installed=json.loads(state.read_text())
for item in sys.argv[sys.argv.index('install')+1:]:
    installed.append(pathlib.Path(item).read_text() if item.endswith('.rpm') else item)
state.write_text(json.dumps(installed))
""",
        }.items():
            target = self.bin / name
            target.write_text(content, encoding="utf-8")
            target.chmod(0o700)

    def run_bootstrap(self, platform=None):
        return subprocess.run(["sh", str(SCRIPT), str(self.root), platform or self.platform],
                              env=self.environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True)

    def missing(self, *names):
        self.state.write_text(json.dumps([name for name in REQUIRED if name not in names]))

    def test_installed_prerequisites_do_not_query_or_call_dnf(self):
        result = self.run_bootstrap()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("BOOTSTRAP_SOURCE=INSTALLED", result.stdout)
        self.assertFalse(self.calls.exists())

    def test_empty_payload_uses_only_missing_repository_names(self):
        self.missing("python3", "ansible-core")
        result = self.run_bootstrap()
        self.assertEqual(0, result.returncode, result.stderr)
        call = json.loads(self.calls.read_text())
        self.assertEqual(["python3", "ansible-core"], call[call.index("install") + 1:])
        self.assertNotIn("--disablerepo=*", call)

    def test_supplied_rpms_disable_repositories(self):
        self.missing("python3", "ansible-core")
        for name in ("python3", "ansible-core"):
            (self.packages / (name + ".rpm")).write_text(name)
        result = self.run_bootstrap()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("--disablerepo=*", json.loads(self.calls.read_text()))
        self.assertIn("BOOTSTRAP_SOURCE=OFFLINE_BUNDLE", result.stdout)

    def test_mixed_payload_uses_local_rpm_and_only_absent_repository_name(self):
        self.missing("python3", "ansible-core")
        (self.packages / "python3.rpm").write_text("python3")
        result = self.run_bootstrap()
        self.assertEqual(0, result.returncode, result.stderr)
        args = json.loads(self.calls.read_text())
        self.assertIn(str(self.packages / "python3.rpm"), args)
        self.assertIn("ansible-core", args)
        self.assertNotIn("python3", args)

    def test_corrupt_rpm_does_not_switch_to_repository(self):
        self.missing("python3")
        (self.packages / "bad.rpm").write_text("CORRUPT")
        self.assertNotEqual(0, self.run_bootstrap().returncode)
        self.assertFalse(self.calls.exists())

    def test_offline_install_failure_is_not_retried_online(self):
        self.missing("python3")
        (self.packages / "python3.rpm").write_text("python3")
        self.environment["TEST_DNF_FAIL"] = "1"
        result = self.run_bootstrap()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("EXECUTION_BOOTSTRAP_OFFLINE_INSTALL_FAILED", result.stderr)
        self.assertIn("--disablerepo=*", json.loads(self.calls.read_text()))

    def test_platform_mismatch_fails_before_transaction(self):
        self.missing("python3")
        result = self.run_bootstrap("redos:unsupported:x86_64")
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(self.calls.exists())


if __name__ == "__main__":
    unittest.main()

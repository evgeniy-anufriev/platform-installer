import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
SPEC = importlib.util.spec_from_file_location("acquire_redos8_infrastructure", TOOLS / "acquire_redos8_infrastructure.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Redos8AcquisitionTests(unittest.TestCase):
    def test_current_requirements_include_ancillary_packages_and_exact_versions(self):
        groups = MODULE.requirements(TOOLS.parents[1])
        first = {group[0] for group in groups}
        self.assertTrue({"python3", "ansible-core", "openssl", "ca-certificates", "tar", "gzip",
                         "bind", "bind-utils", "haproxy", "keepalived", "dnsmasq", "logrotate",
                         "java-21-openjdk-headless", "redis-8.6.4-1.red80.*",
                         "vault-1.21.2-*", "docker-ce-29.7.2-*"}.issubset(first))
        self.assertTrue(any(len(group) == 2 and "postgresql16-server" in group[1] for group in groups))
        self.assertFalse(any("kafka-binary" in item for group in groups for item in group))

    def test_repository_ids_must_be_explicit(self):
        for repos in ([], ["*"], ["repo,other"], ["--nogpgcheck"], ["https://example.org"]):
            with self.subTest(repos=repos), self.assertRaises(ValueError):
                MODULE.dnf_options(repos)
        options = MODULE.dnf_options(["approved-redos8"])
        self.assertIn("--disablerepo=*", options)
        self.assertIn("--setopt=gpgcheck=True", options)

    def test_disabled_or_missing_repositories_are_rejected(self):
        with patch.object(MODULE, "run", return_value="repo id  repo name\nbase RED OS\n"):
            MODULE.check_enabled_repositories(["base"])
            with self.assertRaises(ValueError):
                MODULE.check_enabled_repositories(["disabled"])

    def test_unavailable_version_does_not_fall_back_to_latest(self):
        with patch.object(MODULE, "run", return_value="") as call:
            with self.assertRaisesRegex(ValueError, "required packages unavailable: vault-1.21.2"):
                MODULE.resolve_roots([("vault-1.21.2-*",)], ["dnf"])
            self.assertEqual("vault-1.21.2-*", call.call_args.args[0][-1])

    def test_postgresql_uses_a_complete_family(self):
        groups = [("postgresql-16.14-*", "postgresql16-16.14-*"),
                  ("postgresql-server-16.14-*", "postgresql16-server-16.14-*")]
        def query(argv, phase):
            spec = argv[-1]
            if spec == "postgresql-server-16.14-*":
                return ""
            return spec.replace("-*", "-1.x86_64")
        with patch.object(MODULE, "run", side_effect=query):
            roots = MODULE.resolve_roots(groups, ["dnf"])
        self.assertTrue(all(root.startswith("postgresql16") for root in roots))

    def test_dependency_check_is_empty_root_network_isolated_and_transaction_free(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(MODULE, "run") as call:
            work = Path(temporary)
            MODULE.offline_check(work, ["vault-0:1.21.2-1.x86_64"], work,
                                 {"VERSION_ID": "8.0.3", "PLATFORM_ID": "platform:red80"})
            argv = call.call_args.args[0]
            self.assertEqual(["unshare", "--net", "dnf"], argv[:3])
            self.assertIn("--downloadonly", argv)
            self.assertIn("--noplugins", argv)
            self.assertIn("--disablerepo=*", argv)
            self.assertIn("--installroot=" + str(work / "empty-root"), argv)

    def test_subprocess_errors_do_not_disclose_repository_credentials(self):
        result = subprocess.CompletedProcess([], 1, "https://user:secret@repo", "private error")
        with patch.object(MODULE.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(ValueError, "download failed \\(exit 1\\)") as error:
                MODULE.run(["dnf", "download"], "download")
            self.assertNotIn("secret", str(error.exception))

    def test_non_redos_host_is_rejected(self):
        with patch.object(MODULE.platform, "system", return_value="Windows"):
            with self.assertRaises(ValueError):
                MODULE.host_identity()


if __name__ == "__main__":
    unittest.main()

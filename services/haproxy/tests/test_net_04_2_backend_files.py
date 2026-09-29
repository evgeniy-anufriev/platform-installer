from pathlib import Path
import unittest


ROLE = Path(__file__).resolve().parents[1] / "ansible_collections" / "platform" / "haproxy" / "roles" / "haproxy"


class BackendFileContractTests(unittest.TestCase):
    def test_application_backends_have_a_dedicated_template(self):
        template = (ROLE / "templates" / "30-application-backend.cfg.j2").read_text(encoding="utf-8")
        self.assertIn("platform_haproxy_application_backend.backendName", template)
        self.assertIn("platform_haproxy_application_backend.targets", template)

    def test_stats_fragment_no_longer_renders_application_backends(self):
        template = (ROLE / "templates" / "90-stats-backends.cfg.j2").read_text(encoding="utf-8")
        self.assertNotIn("platform_haproxy_runtime_projection.backends.backends", template)

    def test_prepare_and_activation_manage_only_reserved_backend_files(self):
        prepare = (ROLE / "tasks" / "prepare.yml").read_text(encoding="utf-8")
        activate = (ROLE / "tasks" / "activate.yml").read_text(encoding="utf-8")
        self.assertIn("30-backend-*.cfg", prepare)
        self.assertIn("platform_haproxy_managed_application_backend_files", activate)
        self.assertIn("platform.haproxy.archive_managed_backends", activate)
        self.assertNotIn("Remove stale Platform-managed HAProxy application backend fragments", activate)

    def test_service_backend_defaults_are_not_owned_by_haproxy_role(self):
        defaults = (ROLE / "defaults" / "main.yml").read_text(encoding="utf-8")
        resolve = (ROLE / "tasks" / "resolve.yml").read_text(encoding="utf-8")
        self.assertNotIn("platform_haproxy_backend_defaults", defaults)
        self.assertIn("backend_defaults: {}", resolve)

    def test_tls_probe_exits_after_verification_without_weakening_checks(self):
        prepare = (ROLE / "tasks" / "prepare.yml").read_text(encoding="utf-8")
        self.assertIn("stdin: 'Q'", prepare)
        self.assertIn("- -verify_hostname", prepare)
        self.assertIn("- -verify_return_error", prepare)
        self.assertIn("- -CAfile", prepare)


if __name__ == "__main__":
    unittest.main()

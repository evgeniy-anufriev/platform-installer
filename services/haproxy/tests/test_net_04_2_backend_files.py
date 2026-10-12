from pathlib import Path
import unittest

from jinja2 import Environment, FileSystemLoader, StrictUndefined


ROLE = Path(__file__).resolve().parents[1] / "ansible_collections" / "platform" / "haproxy" / "roles" / "haproxy"


class BackendFileContractTests(unittest.TestCase):
    def test_base_public_routes_use_configured_groups_without_source_endpoints(self):
        template = Environment(
            loader=FileSystemLoader(ROLE / "templates"),
            undefined=StrictUndefined,
        ).get_template("10-public.cfg.j2")
        rendered = template.render(
            platform_haproxy_public_port=443,
            platform_haproxy_pki_directory="/etc/haproxy/pki",
            platform_desired_state={"endpointGroups": {
                "asutp": {"address": {"domain": "asutp.scada.local"}},
                "prod": {"address": {"domain": "prod.scada.local"}},
            }},
        )
        self.assertIn("acl asutp var(txn.route_host) -m end -i .asutp.scada.local", rendered)
        self.assertIn("acl prod var(txn.route_host) -m end -i .prod.scada.local", rendered)
        self.assertIn("use_backend %[var(txn.route_host),field(1,'.')]-asutp if asutp", rendered)
        self.assertNotIn("vault", rendered)

    def test_base_skips_backend_resolution_and_preserves_proven_fragments(self):
        resolve = (ROLE / "tasks" / "resolve.yml").read_text(encoding="utf-8")
        prepare = (ROLE / "tasks" / "prepare.yml").read_text(encoding="utf-8")
        reconcile = (ROLE.parents[4] / "playbooks" / "reconcile.yml").read_text(encoding="utf-8")
        self.assertIn("platform_haproxy_full_reconcile | bool or platform_haproxy_partial_deployment_id is defined", resolve)
        self.assertIn("else {'endpoints': {}, 'hostEndpoints': {}, 'findings': [], 'status': 'PASS'}", resolve)
        self.assertIn("else {'backends': {}, 'findings': [], 'status': 'PASS'}", resolve)
        self.assertNotIn("when: platform_haproxy_full_reconcile | bool or platform_haproxy_partial_deployment_id is defined", resolve.split("- name: Publish HAProxy runtime projection", 1)[1])
        self.assertIn("_platform_haproxy_prior_backend_capture.previousInventory", prepare)
        self.assertIn("when: not (platform_haproxy_full_reconcile | bool)", prepare)
        self.assertIn("platform_haproxy_full_reconcile: true", reconcile)

    def test_source_integration_rebuilds_only_its_backend_and_preserves_others(self):
        prepare = (ROLE / "tasks" / "prepare.yml").read_text(encoding="utf-8")
        integrate = (ROLE.parents[4] / "playbooks" / "integrate.yml").read_text(encoding="utf-8")
        self.assertIn("Select only this source deployment backend for partial integration", prepare)
        self.assertIn("reject('in', _platform_haproxy_partial_source_files)", prepare)
        self.assertIn("platform_haproxy_partial_deployment_id", integrate)
        self.assertEqual(3, integrate.count("platform_haproxy_phase:"))

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
        checks = (ROLE / "tasks" / "check_targets.yml").read_text(encoding="utf-8")
        self.assertIn("stdin: 'Q'", checks)
        self.assertIn("- -verify_hostname", checks)
        self.assertIn("- -verify_return_error", checks)
        self.assertIn("- -CAfile", checks)


if __name__ == "__main__":
    unittest.main()

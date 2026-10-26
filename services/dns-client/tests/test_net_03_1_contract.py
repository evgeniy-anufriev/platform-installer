from pathlib import Path
import unittest

from jinja2 import Template


ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "ansible_collections" / "platform" / "dns_client" / "roles" / "dns_client"


class Net031DnsClientContractTests(unittest.TestCase):
    def test_is_a_separate_host_scoped_service_with_one_logical_link(self):
        manifest = (ROOT / "service.yml").read_text(encoding="utf-8")
        self.assertIn("id: dns-client", manifest)
        self.assertIn("host-resolver", manifest)
        self.assertIn("hostScoped: true", manifest)
        self.assertIn("dnsServerRef", manifest)
        self.assertNotIn("advancedConfig", manifest)
        self.assertNotIn("virtualAddresses", manifest)

    def test_projection_reuses_core_dns_without_future_endpoint_requirements(self):
        projection = (ROOT / "playbooks" / "projection.yml").read_text(encoding="utf-8")
        self.assertIn("platform.core.resolve_dns_zones", projection)
        self.assertNotIn("platform.core.resolve_service_endpoints", projection)
        self.assertIn("primary] +", projection)
        self.assertIn("'hostRecord':", projection)
        self.assertNotIn("endpointRecord", projection)
        self.assertNotIn("wildcardRecord", projection)
        self.assertNotIn("platform_generated_state", projection)
        self.assertNotIn("Persist", projection)

    def test_verify_is_separate_and_read_only(self):
        verify = (ROOT / "playbooks" / "verify.yml").read_text(encoding="utf-8")
        role_verify = (ROLE / "tasks" / "verify.yml").read_text(encoding="utf-8")
        self.assertIn("import_playbook: projection.yml", verify)
        self.assertIn("platform_dns_client_phase: verify", verify)
        self.assertNotIn("import_playbook: apply.yml", verify)
        self.assertIn("getent, hosts, \"{{ platform_dns_client_local.hostRecord }}\"", role_verify)
        self.assertNotIn("endpointRecord", role_verify)
        self.assertNotIn("wildcardRecord", role_verify)

    def test_backend_selection_requires_loaded_and_active_service(self):
        discovery = (ROLE / "tasks" / "discover.yml").read_text(encoding="utf-8")
        self.assertIn("systemd-resolved.service", discovery)
        self.assertIn("NetworkManager.service", discovery)
        self.assertIn("systemctl, is-active, systemd-resolved.service", discovery)
        self.assertIn("systemctl, is-active, NetworkManager.service", discovery)
        self.assertGreaterEqual(discovery.count("| trim == 'loaded'"), 2)
        self.assertGreaterEqual(discovery.count("| trim == 'active'"), 2)
        self.assertIn("'systemd-resolved'", discovery)
        self.assertIn("DNS_CLIENT_BACKEND_UNSUPPORTED", discovery)

    def test_resolv_conf_conflicts_are_blocked_without_replacement(self):
        discovery = (ROLE / "tasks" / "discover.yml").read_text(encoding="utf-8")
        self.assertIn("DNS_CLIENT_RESOLV_CONF_CONFLICT", discovery)
        self.assertIn("readlink", discovery)
        self.assertNotIn("state: link", discovery)
        self.assertNotIn("ln -sf", discovery)

    def test_resolved_dropin_is_route_only_and_deterministic(self):
        template = Template((ROLE / "templates" / "platform-installer.conf.j2").read_text(encoding="utf-8"))
        rendered = template.render(platform_dns_client_local={"servers": ["192.0.2.1", "192.0.2.2", "192.0.2.3"], "managedZone": "scada.local"})
        self.assertIn("DNS=192.0.2.1 192.0.2.2 192.0.2.3", rendered)
        self.assertIn("Domains=~scada.local", rendered)
        self.assertNotIn("FallbackDNS", rendered)

    def test_networkmanager_fallback_never_uses_connection_down_up(self):
        networkmanager = (ROLE / "tasks" / "networkmanager.yml").read_text(encoding="utf-8")
        verify = (ROLE / "tasks" / "verify.yml").read_text(encoding="utf-8")
        self.assertIn("DNS_CLIENT_SPLIT_DNS_UNSUPPORTED", networkmanager)
        self.assertIn("networkManagerConnection", networkmanager)
        self.assertIn("DNS_CLIENT_NM_CONNECTION_AMBIGUOUS", networkmanager)
        self.assertIn("nmcli, device, reapply", networkmanager)
        self.assertNotIn("connection, down", networkmanager)
        self.assertNotIn("connection, up", networkmanager)
        self.assertIn("getent, hosts", verify)

    def test_runtime_role_uses_controller_projection_for_apply_and_verify(self):
        main = (ROLE / "tasks" / "main.yml").read_text(encoding="utf-8")
        self.assertIn("hostvars['localhost'].platform_dns_client_runtime_projection", main)
        self.assertIn("platform_dns_client_phase == 'apply'", main)
        self.assertIn("platform_dns_client_phase == 'verify'", main)


if __name__ == "__main__":
    unittest.main()

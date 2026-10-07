import os
import unittest


ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


class Net042PlaybookContractTests(unittest.TestCase):
    def read(self, relative_path):
        with open(os.path.join(ROOT, relative_path), encoding="utf-8") as handle:
            return handle.read()

    def test_postgresql_apply_does_not_assume_an_endpoint_or_reconcile_providers(self):
        playbook = self.read("services/postgresql/playbooks/apply.yml")
        self.assertIn("platform.postgresql.postgresql", playbook)
        self.assertNotIn("../../integrations/playbooks/reconcile.yml", playbook)

    def test_shared_stage_orders_provider_owned_entrypoints(self):
        playbook = self.read("services/integrations/playbooks/reconcile.yml")
        self.assertIn("platform.core.resolve_service_integrations", playbook)
        self.assertLess(playbook.index("../../bind/playbooks/reconcile.yml"), playbook.index("../../haproxy/playbooks/reconcile.yml"))
        self.assertIn("platform_provider_integration_recursion: false", playbook)

    def test_provider_reconcile_entrypoints_delegate_to_full_apply(self):
        self.assertIn("import_playbook: apply.yml", self.read("services/bind/playbooks/reconcile.yml"))
        self.assertIn("import_playbook: apply.yml", self.read("services/haproxy/playbooks/reconcile.yml"))


if __name__ == "__main__":
    unittest.main()

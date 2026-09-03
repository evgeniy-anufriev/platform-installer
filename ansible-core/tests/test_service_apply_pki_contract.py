import os
import unittest


ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


class ServiceApplyPkiContractTests(unittest.TestCase):
    def test_tls_service_apply_playbooks_scope_pki_before_role_reconcile(self):
        cases = {
            "kafka": "services/kafka/playbooks/apply.yml",
            "postgresql": "services/postgresql/playbooks/apply.yml",
            "haproxy": "services/haproxy/playbooks/apply.yml",
        }
        for service_type, relative_path in cases.items():
            with open(os.path.join(ROOT, relative_path), encoding="utf-8") as handle:
                playbook = handle.read()
            pki_import = "import_playbook: ../../../ansible-core/playbooks/pki-apply.yml"
            self.assertIn(pki_import, playbook)
            self.assertIn("platform_pki_service_types: [%s]" % service_type, playbook)
            self.assertLess(playbook.index(pki_import), playbook.index("roles:"))


if __name__ == "__main__":
    unittest.main()

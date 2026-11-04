from pathlib import Path
import unittest


PLAYBOOK = Path(__file__).resolve().parents[1] / "playbooks" / "verify.yml"


class VerifyPlaybookContractTests(unittest.TestCase):
    def test_verify_uses_existing_instance_tls_without_pki_preparation(self):
        content = PLAYBOOK.read_text(encoding="utf-8")
        self.assertNotIn("../../../ansible-core/playbooks/pki-resolve.yml", content)
        self.assertNotIn("../../../ansible-core/playbooks/pki-apply.yml", content)


if __name__ == "__main__":
    unittest.main()

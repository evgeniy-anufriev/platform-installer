from pathlib import Path
import unittest


PLAYBOOK = Path(__file__).resolve().parents[1] / "playbooks" / "verify.yml"


class VerifyPlaybookContractTests(unittest.TestCase):
    def test_verify_reconstructs_pki_requests_without_materialization(self):
        content = PLAYBOOK.read_text(encoding="utf-8")
        self.assertIn("../../../ansible-core/playbooks/pki-verify.yml", content)
        self.assertNotIn("../../../ansible-core/playbooks/pki-apply.yml", content)


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT / "collections" / "ansible_collections" / "platform" / "core" / "roles" / "execution_environment"


class ExecutionHardeningTests(unittest.TestCase):
    def test_identity_is_outside_ephemeral_workspace(self):
        defaults = (ROLE / "defaults" / "main.yml").read_text(encoding="utf-8")
        self.assertIn("platform_execution_identity_root: \"{{ platform_execution_state_root }}/identities/default\"", defaults)
        self.assertIn("platform_execution_known_hosts_path", defaults)
        self.assertIn("platform_execution_identity_root }}/id_ed25519", defaults)

    def test_identity_generation_remains_idempotent(self):
        tasks = (ROLE / "tasks" / "main.yml").read_text(encoding="utf-8")
        self.assertIn("Создать постоянную SSH-пару ключей технического пользователя, если она отсутствует", tasks)
        self.assertIn("creates: \"{{ platform_execution_ssh_key_path }}\"", tasks)
        self.assertIn("Создать постоянный файл known_hosts, если он отсутствует", tasks)

    def test_access_gate_reuses_existing_boundaries(self):
        playbook = (ROOT / "playbooks" / "ensure-execution-access.yml").read_text(encoding="utf-8")
        self.assertIn("prepare-execution-node.yml", playbook)
        self.assertIn("bootstrap-targets.yml", playbook)
        self.assertIn("target-connectivity.yml", playbook)


if __name__ == "__main__":
    unittest.main()

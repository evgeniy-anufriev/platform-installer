import unittest
from pathlib import Path

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.playbook.conditional import Conditional
from ansible.template import Templar


ROLE = Path(__file__).resolve().parents[1] / "ansible_collections/platform/vault/roles/vault_tls"


class AppRoleConfigurationTests(unittest.TestCase):
    def test_enable_preserves_existing_mount_and_uses_protected_api(self):
        tasks = yaml.safe_load((ROLE / "tasks/configure.yml").read_text(encoding="utf-8"))
        enable = next(t for t in tasks if t["name"] == "Включить аутентификацию AppRole только при ее отсутствии")
        api = enable["ansible.builtin.uri"]
        self.assertTrue(api["url"].endswith("/v1/sys/auth/approle"))
        self.assertEqual(api["method"], "POST")
        self.assertEqual(api["body"], {"type": "approle"})
        self.assertTrue(api["validate_certs"])
        self.assertTrue(enable["no_log"])
        loader = DataLoader()
        for mounts, expected in [({}, True), ({"approle/": {"type": "approle"}}, False)]:
            variables = {"_platform_vault_owned_configuration": {
                "results": [{}, {}, {"json": {"data": mounts}}]}}
            check = Conditional(loader=loader)
            check.when = [enable["when"]]
            self.assertEqual(check.evaluate_conditional(Templar(loader=loader, variables=variables), variables), expected)

    def test_conflicting_mount_rejected_before_any_write(self):
        tasks = yaml.safe_load((ROLE / "tasks/configure.yml").read_text(encoding="utf-8"))
        guard = next(t for t in tasks if t["name"].startswith("Отклонить несовместимую существующую конфигурацию аудита, KV или аутентификации перед изменением"))
        expression = next(x for x in guard["ansible.builtin.assert"]["that"] if "approle/" in x)
        self.assertLess(tasks.index(guard), next(i for i, t in enumerate(tasks) if t.get("ansible.builtin.uri", {}).get("method") == "POST"))
        loader = DataLoader()
        for mounts, expected in [({}, True), ({"approle/": {"type": "approle"}}, True),
                                 ({"approle/": {"type": "userpass"}}, False)]:
            variables = {"_platform_vault_owned_configuration": {
                "results": [{}, {}, {"json": {"data": mounts}}]}}
            check = Conditional(loader=loader)
            check.when = [expression]
            self.assertEqual(check.evaluate_conditional(Templar(loader=loader, variables=variables), variables), expected)

    def test_verify_requires_approle_without_mutation(self):
        tasks = yaml.safe_load((ROLE / "tasks/verify.yml").read_text(encoding="utf-8"))
        guard = next(t for t in tasks if t["name"].startswith("Требовать одобренное устройство аудита, KV v2 и монтирование аутентификации"))
        expressions = [x for x in guard["ansible.builtin.assert"]["that"] if "approle/" in x]
        self.assertEqual(len(expressions), 2)
        loader = DataLoader()
        for mounts, expected in [({}, False), ({"approle/": {"type": "approle"}}, True),
                                 ({"approle/": {"type": "userpass"}}, False)]:
            variables = {"_platform_vault_configuration": {"results": [{}, {}, {"json": {"data": mounts}}]}}
            check = Conditional(loader=loader)
            check.when = expressions
            self.assertEqual(check.evaluate_conditional(Templar(loader=loader, variables=variables), variables), expected)
        self.assertFalse(any(t.get("ansible.builtin.uri", {}).get("method") in ["POST", "PUT", "DELETE"] for t in tasks))


if __name__ == "__main__":
    unittest.main()

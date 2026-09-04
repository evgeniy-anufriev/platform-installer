import os
import unittest


ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


class ServiceApplyPkiContractTests(unittest.TestCase):
    def test_pki_resolution_reloads_portable_manifest_for_stable_project_identity(self):
        resolve_tasks = os.path.join(
            ROOT,
            "ansible-core/collections/ansible_collections/platform/core/roles/pki_materialize/tasks/resolve.yml",
        )
        with open(resolve_tasks, encoding="utf-8") as handle:
            tasks = handle.read()
        self.assertIn("platform_project_manifest_path", tasks)
        self.assertIn("_platform_pki_project_manifest_document.metadata.id", tasks)

    def test_transient_request_workspace_is_project_scoped(self):
        request_tasks = os.path.join(
            ROOT,
            "ansible-core/collections/ansible_collections/platform/core/roles/pki_materialize/tasks/request.yml",
        )
        with open(request_tasks, encoding="utf-8") as handle:
            tasks = handle.read()
        self.assertIn(
            "platform_pki_runtime_root }}/{{ platform_pki_project_id }}/{{ platform_pki_request.id }}",
            tasks,
        )

    def test_pki_deploy_publishes_a_non_secret_change_signal(self):
        deploy_tasks = os.path.join(
            ROOT,
            "ansible-core/collections/ansible_collections/platform/core/roles/pki_deploy/tasks/plan.yml",
        )
        with open(deploy_tasks, encoding="utf-8") as handle:
            tasks = handle.read()
        self.assertIn("platform_pki_material_changed:", tasks)

    def test_tls_service_apply_playbooks_use_project_wide_pki_before_role_reconcile(self):
        cases = {
            "kafka": "services/kafka/playbooks/apply.yml",
            "postgresql": "services/postgresql/playbooks/apply.yml",
            "haproxy": "services/haproxy/playbooks/apply.yml",
        }
        for _service_type, relative_path in cases.items():
            with open(os.path.join(ROOT, relative_path), encoding="utf-8") as handle:
                playbook = handle.read()
            pki_import = "import_playbook: ../../../ansible-core/playbooks/pki-apply.yml"
            self.assertIn(pki_import, playbook)
            self.assertNotIn("platform_pki_service_types:", playbook)
            self.assertLess(playbook.index(pki_import), playbook.index("roles:"))


if __name__ == "__main__":
    unittest.main()

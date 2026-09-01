import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1] / "collections" / "ansible_collections" / "platform" / "core" / "plugins" / "module_utils"
SPEC = importlib.util.spec_from_file_location("identity_persistence", ROOT / "identity_persistence.py")
persistence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(persistence)


class IdentityPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.project_path = root / "project.yml"
        self.inventory_path = root / "hosts.yml"
        self.project = {"metadata": {"id": "p"}, "desiredState": {"serviceDeployments": {"k": {"identity": {"clusterId": "c"}}}}, "x-unknown": {"kept": True}}
        self.inventory = {"all": {"hosts": {"node1": {"ansible_host": "192.0.2.1", "platform_deployments": {"k": {"members": {"m": {"roles": ["controller"], "identity": {"directoryId": "D"}}}}}}}, "children": {}}}
        self.project_path.write_text(yaml.safe_dump(self.project, sort_keys=False), encoding="utf-8")
        self.inventory_path.write_text(yaml.safe_dump(self.inventory, sort_keys=False), encoding="utf-8")

    def tearDown(self):
        self.directory.cleanup()

    def test_commit_preserves_unrelated_semantics(self):
        candidate = dict(self.project, desiredState={"serviceDeployments": {"k": {"identity": {"clusterId": "new"}}}})
        result = persistence.persist_identity_documents(self.project_path, self.inventory_path, candidate, self.inventory)
        self.assertTrue(result["changed"])
        self.assertEqual("new", yaml.safe_load(self.project_path.read_text(encoding="utf-8"))["desiredState"]["serviceDeployments"]["k"]["identity"]["clusterId"])
        self.assertEqual(self.inventory, yaml.safe_load(self.inventory_path.read_text(encoding="utf-8")))

    def test_noop_does_not_rewrite(self):
        before = (self.project_path.stat().st_mtime_ns, self.inventory_path.stat().st_mtime_ns)
        result = persistence.persist_identity_documents(self.project_path, self.inventory_path, self.project, self.inventory)
        self.assertFalse(result["changed"])
        self.assertEqual(before, (self.project_path.stat().st_mtime_ns, self.inventory_path.stat().st_mtime_ns))

    def test_concurrent_edit_is_rejected(self):
        def edit(paths):
            path = Path(paths[0])
            path.write_bytes(path.read_bytes() + b"\nchanged: true\n")
        with self.assertRaises(RuntimeError):
            persistence.persist_identity_documents(
                self.project_path, self.inventory_path,
                dict(self.project, desiredState={"changed": True}), self.inventory,
                before_commit=edit)

    def test_failure_before_replace_preserves_originals(self):
        original = (self.project_path.read_bytes(), self.inventory_path.read_bytes())
        with self.assertRaisesRegex(RuntimeError, "injected"):
            persistence.persist_identity_documents(
                self.project_path, self.inventory_path,
                dict(self.project, desiredState={"changed": True}), self.inventory,
                before_commit=lambda _paths: (_ for _ in ()).throw(RuntimeError("injected before replace")))
        self.assertEqual(original, (self.project_path.read_bytes(), self.inventory_path.read_bytes()))

    def test_failure_after_first_replace_rolls_back(self):
        original = (self.project_path.read_bytes(), self.inventory_path.read_bytes())
        real_replace = persistence.os.replace
        calls = [0]
        def fail_second(source, target):
            calls[0] += 1
            if calls[0] == 2:
                raise RuntimeError("injected replace failure")
            return real_replace(source, target)
        persistence.os.replace = fail_second
        try:
            with self.assertRaisesRegex(RuntimeError, "replace failure"):
                persistence.persist_identity_documents(
                    self.project_path, self.inventory_path,
                    dict(self.project, desiredState={"changed": True}), self.inventory)
        finally:
            persistence.os.replace = real_replace
        self.assertEqual(original, (self.project_path.read_bytes(), self.inventory_path.read_bytes()))

    def test_orphan_transaction_recovery_rolls_back_mixed_state(self):
        original_project = self.project_path.read_bytes()
        original_inventory = self.inventory_path.read_bytes()
        rollback_project = self.project_path.with_name(".tx.project.yml.rollback")
        rollback_inventory = self.inventory_path.with_name(".tx.hosts.yml.rollback")
        rollback_project.write_bytes(original_project)
        rollback_inventory.write_bytes(original_inventory)
        candidate_project = yaml.safe_dump(dict(self.project, desiredState={"changed": True}), sort_keys=False).encode()
        self.project_path.write_bytes(candidate_project)
        mixed_inventory = self.inventory_path.read_bytes() + b"\nchanged: true\n"
        self.inventory_path.write_bytes(mixed_inventory)
        marker = self.project_path.with_name(".identity-materialization-tx.json")
        marker.write_text(json.dumps({
            "targets": [str(self.project_path), str(self.inventory_path)],
            "rollbackPaths": [str(rollback_project), str(rollback_inventory)],
            "originalHashes": [persistence._hash(original_project), persistence._hash(original_inventory)],
            "candidateHashes": [persistence._hash(candidate_project), persistence._hash(original_inventory)],
        }), encoding="utf-8")
        result = persistence.recover_identity_transaction(str(marker))
        self.assertEqual("ROLLED_BACK", result["status"])
        self.assertEqual(original_project, self.project_path.read_bytes())
        self.assertEqual(original_inventory, self.inventory_path.read_bytes())


if __name__ == "__main__":
    unittest.main()

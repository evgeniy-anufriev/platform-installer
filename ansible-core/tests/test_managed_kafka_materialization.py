import importlib.util
import tempfile
import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1] / "collections" / "ansible_collections" / "platform" / "core" / "plugins" / "module_utils"
for dependency in ("kafka_identity", "identity_persistence"):
    dependency_spec = importlib.util.spec_from_file_location(dependency, ROOT / (dependency + ".py"))
    dependency_module = importlib.util.module_from_spec(dependency_spec)
    import sys
    sys.modules[dependency] = dependency_module
    dependency_spec.loader.exec_module(dependency_module)
spec = importlib.util.spec_from_file_location("managed_kafka_materialization", ROOT / "managed_kafka_materialization.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ManagedKafkaMaterializationTests(unittest.TestCase):
    def test_ansible_native_generate_persist_reload_and_noop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            desired = {"serviceDeployments": {"k": {"serviceType": "kafka", "identity": {}}}}
            inventory = {"all": {"hosts": {"n": {"platform_deployments": {"k": {"members": {"c": {"roles": ["controller"], "configuration": {"nodeId": 1}}}}}}}}}
            (root / "hosts.yml").write_text(yaml.safe_dump(inventory, sort_keys=False), encoding="utf-8")
            group_vars = root / "group_vars" / "all"
            host_vars = root / "host_vars"
            group_vars.mkdir(parents=True)
            host_vars.mkdir()
            opaque_group = group_vars / "custom.yml"
            opaque_host = host_vars / "n.yml"
            opaque_group.write_text("company_custom: '{{ untouched }}'\n", encoding="utf-8")
            opaque_host.write_text("host_custom:\n  nested: true\n", encoding="utf-8")
            opaque_before = (opaque_group.read_bytes(), opaque_host.read_bytes())
            discovery = {"n": [{"deploymentId": "k", "memberId": "c", "state": "UNINITIALIZED"}]}
            values = iter([b"a" * 16, b"b" * 16])
            first = module.materialize_ansible_kafka(desired, root / "hosts.yml", root / "platform-state.yml", discovery, "p", lambda _: next(values))
            self.assertTrue(first["changed"])
            state = first["stateDocument"]["platform_generated_state"]
            self.assertIn("clusterId", state["serviceDeployments"]["k"]["identity"])
            self.assertIn("directoryId", state["serviceDeployments"]["k"]["members"]["c"]["identity"])
            before = (root / "hosts.yml").read_bytes()
            second = module.materialize_ansible_kafka(desired, root / "hosts.yml", root / "platform-state.yml", discovery, "p", lambda _: (_ for _ in ()).throw(AssertionError("regenerated")))
            self.assertFalse(second["changed"])
            self.assertEqual(before, (root / "hosts.yml").read_bytes())
            self.assertEqual(opaque_before, (opaque_group.read_bytes(), opaque_host.read_bytes()))

    def test_ansible_native_materialization_reads_canonical_host_vars_members(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            desired = {"serviceDeployments": {"k": {"serviceType": "kafka", "identity": {}}}}
            inventory = {"all": {"hosts": {"n": {"ansible_host": "192.0.2.10"}}}}
            (root / "hosts.yml").write_text(yaml.safe_dump(inventory, sort_keys=False), encoding="utf-8")
            host_vars = root / "host_vars" / "n"
            host_vars.mkdir(parents=True)
            (host_vars / "platform-installer.yml").write_text(yaml.safe_dump({
                "platform_deployments": {"k": {"members": {"c": {"roles": ["controller"], "configuration": {"nodeId": 1}}}}}
            }, sort_keys=False), encoding="utf-8")
            result = module.materialize_ansible_kafka(
                desired,
                root / "hosts.yml",
                root / "platform-state.yml",
                {"n": [{"deploymentId": "k", "memberId": "c", "state": "UNINITIALIZED"}]},
                "p",
                lambda _: b"a" * 16,
            )
            self.assertTrue(result["changed"])
            state = result["stateDocument"]["platform_generated_state"]
            self.assertIn("directoryId", state["serviceDeployments"]["k"]["members"]["c"]["identity"])

    def test_installer_managed_host_document_precedes_legacy_flat_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            desired = {"serviceDeployments": {"k": {"serviceType": "kafka", "identity": {}}}}
            inventory = {"all": {"hosts": {"n": {"ansible_host": "192.0.2.10"}}}}
            (root / "hosts.yml").write_text(yaml.safe_dump(inventory, sort_keys=False), encoding="utf-8")
            host_vars = root / "host_vars"
            managed = host_vars / "n"
            managed.mkdir(parents=True)
            (host_vars / "n.yml").write_text(yaml.safe_dump({
                "platform_deployments": {"k": {"members": {"legacy": {"roles": ["controller"]}}}}
            }, sort_keys=False), encoding="utf-8")
            (managed / "platform-installer.yml").write_text(yaml.safe_dump({
                "platform_deployments": {"k": {"members": {"managed": {"roles": ["controller"], "configuration": {"nodeId": 1}}}}}
            }, sort_keys=False), encoding="utf-8")
            result = module.materialize_ansible_kafka(
                desired, root / "hosts.yml", root / "platform-state.yml",
                {"n": [{"deploymentId": "k", "memberId": "managed", "state": "UNINITIALIZED"}]},
                "p", lambda _: b"a" * 16,
            )
            self.assertEqual("PASS", result["status"])
            members = result["stateDocument"]["platform_generated_state"]["serviceDeployments"]["k"]["members"]
            self.assertEqual(["managed"], sorted(members))

    def test_generate_persist_reload_and_noop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = {"desiredState": {"serviceDeployments": {"k": {"serviceType": "kafka", "identity": {}}}}}
            inventory = {"all": {"hosts": {"n": {"platform_deployments": {"k": {"members": {"c": {"roles": ["controller"], "configuration": {"nodeId": 1}, "identity": {}}}}}}}}}
            (root / "project.yml").write_text(yaml.safe_dump(project, sort_keys=False), encoding="utf-8")
            (root / "hosts.yml").write_text(yaml.safe_dump(inventory, sort_keys=False), encoding="utf-8")
            values = iter([b"a" * 16, b"b" * 16])
            first = module.materialize_managed_kafka(root / "project.yml", root / "hosts.yml", {"n": {"k": {"c": {"state": "UNINITIALIZED"}}}}, lambda _: next(values))
            self.assertTrue(first["changed"])
            self.assertIn("clusterId", first["project"]["desiredState"]["serviceDeployments"]["k"]["identity"])
            second = module.materialize_managed_kafka(root / "project.yml", root / "hosts.yml", {"n": {"k": {"c": {"state": "UNINITIALIZED"}}}}, lambda _: (_ for _ in ()).throw(AssertionError("regenerated")))
            self.assertFalse(second["changed"])


if __name__ == "__main__":
    unittest.main()

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

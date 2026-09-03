import importlib.util
from pathlib import Path
import tempfile
import unittest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
SPEC = importlib.util.spec_from_file_location(
    "build_execution_runtime_bundle", TOOLS / "build_execution_runtime_bundle.py"
)
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class ExecutionRuntimeBundleTests(unittest.TestCase):
    def test_bundle_preserves_repository_relative_core_layout(self):
        destinations = [destination for destination, _source in BUILDER.SOURCE_ROOTS]
        self.assertIn("ansible-core", destinations)
        self.assertNotIn("core", destinations)

        for service in ("kafka", "keepalived"):
            playbook = BUILDER.REPOSITORY / "services" / service / "playbooks" / "apply.yml"
            core_imports = 0
            for line in playbook.read_text(encoding="utf-8").splitlines():
                marker = "import_playbook:"
                if marker not in line:
                    continue
                imported = line.split(marker, 1)[1].strip()
                if "ansible-core/" not in imported:
                    continue
                core_imports += 1
                resolved = (Path("services") / service / "playbooks" / imported).resolve()
                expected = (Path("ansible-core") / "playbooks").resolve()
                self.assertTrue(resolved.is_relative_to(expected), (service, imported))
            if service == "kafka":
                self.assertGreater(core_imports, 0)

    def test_runtime_platforms_requires_python_and_package_closure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, "packages/ and python"):
                BUILDER.runtime_platforms(root)
            (root / "packages" / "redos" / "8.0" / "x86_64").mkdir(parents=True)
            (root / "python").mkdir()
            with self.assertRaisesRegex(ValueError, "no package platform"):
                BUILDER.runtime_platforms(root)
            (root / "packages" / "redos" / "8.0" / "x86_64" / "ansible-core.rpm").write_bytes(b"rpm")
            self.assertEqual([{"os": "redos", "version": "8.0", "architecture": "x86_64"}], BUILDER.runtime_platforms(root))

    def test_components_are_sorted_and_do_not_include_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "b").mkdir()
            (root / "b" / "two").write_bytes(b"two")
            (root / "a").write_bytes(b"one")
            (root / "manifest.yaml").write_text("ignored", encoding="utf-8")
            self.assertEqual(["a", "b/two"], [item["path"] for item in BUILDER.components(root)])


if __name__ == "__main__":
    unittest.main()

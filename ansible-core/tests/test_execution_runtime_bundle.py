import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


TOOLS = Path(__file__).resolve().parents[1] / "tools"
SPEC = importlib.util.spec_from_file_location(
    "build_execution_runtime_bundle", TOOLS / "build_execution_runtime_bundle.py"
)
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class ExecutionRuntimeBundleTests(unittest.TestCase):
    def test_current_application_closure_is_copied_and_fingerprinted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for destination, source in BUILDER.SOURCE_ROOTS:
                BUILDER.copy_tree(source, root / destination)
            BUILDER.validate_catalog_layout(root)
            indexed = {item['path']: item for item in BUILDER.components(root)}
            required = [
                'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils/application_plan.py',
                'ansible-core/playbooks/applications/apply.yml',
                'ansible-core/playbooks/applications/verify.yml',
                'contracts/plan/v1alpha4/schema.json',
                'contracts/runtime-secret-descriptors/v1alpha3/schema.json',
                'contracts/execution-manifest/v1alpha2/application-operation.schema.json',
            ]
            application_playbooks = sorted((BUILDER.REPOSITORY / 'ansible-core/playbooks/applications').rglob('*.yml'))
            self.assertTrue(application_playbooks)
            required.extend(path.relative_to(BUILDER.REPOSITORY).as_posix() for path in application_playbooks)
            for relative in required:
                self.assertIn(relative, indexed)
                self.assertEqual(BUILDER.digest_file(root / relative), BUILDER.digest_file(BUILDER.REPOSITORY / relative))
            self.assertFalse(any('.runtime' in Path(relative).parts or 'tests' in Path(relative).parts for relative in indexed))

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

    def test_runtime_platforms_supports_empty_payload_and_existing_closure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            explicit = {"os": "redos", "version": "8.0", "architecture": "x86_64"}
            self.assertEqual([explicit], BUILDER.runtime_platforms(root, ["redos:8.0:x86_64"]))
            (root / "packages" / "redos" / "8.0" / "x86_64").mkdir(parents=True)
            (root / "python").mkdir()
            with patch.object(BUILDER, "host_platform", return_value=explicit):
                self.assertEqual([explicit], BUILDER.runtime_platforms(root))
            (root / "packages" / "redos" / "8.0" / "x86_64" / "ansible-core.rpm").write_bytes(b"rpm")
            self.assertEqual([{"os": "redos", "version": "8.0", "architecture": "x86_64"}], BUILDER.runtime_platforms(root))

    def test_os_release_identity_is_data_not_shell(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "os-release"
            source.write_text('NAME="RED OS"\nID=redos\nVERSION_ID="8.0.3"\n', encoding="utf-8")
            self.assertEqual({"os": "redos", "version": "8.0.3", "architecture": "x86_64"},
                             BUILDER.host_platform(source, "x86_64"))
            for content in ('ID=redos\n', 'ID="$(touch /tmp/never)"\nVERSION_ID=8\n', 'ID=redos\nID=other\nVERSION_ID=8\n'):
                source.write_text(content, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "cannot infer"):
                    BUILDER.host_platform(source, "x86_64")

    def test_declared_platforms_are_validated_deduplicated_and_sorted(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = BUILDER.runtime_platforms(Path(temporary), ["redos:8.0:x86_64", "redos:7.3:x86_64", "redos:8.0:x86_64"])
            self.assertEqual(["7.3", "8.0"], [p["version"] for p in result])
            for value in ("", "redos:8", "redos:../8:x86_64", "redos:..:x86_64", "redos:8:*"):
                with self.assertRaisesRegex(ValueError, "platform must"):
                    BUILDER.parse_platform(value)

    def test_empty_runtime_build_has_fixed_layout_without_mutating_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = root / "input"
            runtime.mkdir()
            output = root / "bundle"
            BUILDER.build(output, runtime, "empty-test", "0.1.0", ["redos:8.0:x86_64"])
            self.assertTrue((output / "runtime/packages").is_dir())
            self.assertTrue((output / "runtime/python").is_dir())
            self.assertEqual([], list(runtime.iterdir()))
            self.assertTrue((output / "ansible-core/tools/bootstrap_execution_runtime.sh").is_file())
            with self.assertRaisesRegex(ValueError, "output already exists"):
                BUILDER.build(output, runtime, "empty-test", "0.1.0", ["redos:8.0:x86_64"])

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

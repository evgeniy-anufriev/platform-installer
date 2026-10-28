"""The service validation path is target-free and separate from full validation."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
PLAYBOOKS = ROOT / "ansible-core/playbooks"


@unittest.skipUnless(shutil.which("ansible-playbook"), "Ansible runtime required")
class InfrastructureValidationRuntimeTests(unittest.TestCase):
    def run_validation(self, root, entry, desired, success=True, stale=False):
        artifact = root / (entry + ".json")
        variables = {"platform_desired_state": desired, "platform_project_root": str(root),
                     "platform_project_manifest_path": str(root / "project.yml"),
                     "platform_service_catalog_path": str(ROOT / "examples/catalog/service-catalog.yml"),
                     "platform_contracts_root": str(ROOT / "contracts"),
                     "platform_validation_artifact": str(artifact)}
        if stale:
            variables["platform_application_validation"] = {"snapshot": {"findings": [{"code": "STALE_APP_ERROR", "severity": "ERROR"}]}}
        result = subprocess.run(["ansible-playbook", "-i", str(root / "inventory/hosts.yml"),
                                 str(PLAYBOOKS / entry), "-e", json.dumps(variables)],
                                env=dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(ROOT / "ansible-core/collections")),
                                capture_output=True, text=True, timeout=90)
        self.assertEqual(success, result.returncode == 0, result.stdout + result.stderr)
        if success:
            self.assertTrue(artifact.is_file())
            self.assertRegex(result.stdout, r"changed=0\s")
        return result.stdout + result.stderr

    def fixture(self, directory, legacy=False):
        root = Path(directory)
        shutil.copytree(ROOT / "examples/valid/empty/inventory", root / "inventory")
        if legacy:
            shutil.copyfile(ROOT / "examples/valid/empty/project.yml", root / "project.yml")
        if not legacy:
            file = root / "inventory/group_vars/all/platform.yml"
            values = yaml.safe_load(file.read_text())
            values.pop("platform_project", None)
            file.write_text(yaml.safe_dump(values))
        return root

    def test_legacy_inventory_remains_supported(self):
        with tempfile.TemporaryDirectory(prefix="platform-infra-legacy-") as directory:
            self.run_validation(self.fixture(directory, legacy=True), "validate-infrastructure.yml", {})

    def test_bad_application_is_blocked_by_full_validation_but_not_loaded_for_infrastructure(self):
        with tempfile.TemporaryDirectory(prefix="platform-infra-validation-") as directory:
            root = self.fixture(directory)
            desired = {"serviceDeployments": {}, "applicationLibraryDeployments": {"bad": {"libraryRef": "missing@1"}}}
            self.run_validation(root, "validate-infrastructure.yml", desired, stale=True)
            self.run_validation(root, "validate.yml", desired, success=False)

    def test_invalid_infrastructure_still_blocks(self):
        with tempfile.TemporaryDirectory(prefix="platform-infra-invalid-") as directory:
            root = self.fixture(directory)
            self.run_validation(root, "validate-infrastructure.yml", {"serviceDeployments": {
                "broken": {"serviceType": "not-a-service", "mode": "invalid"}}}, success=False)

    def test_manifest_loading_replaces_prior_fact_and_missing_file_clears_it(self):
        with tempfile.TemporaryDirectory(prefix="platform-manifest-refresh-") as directory:
            root = Path(directory)
            manifest = root / "project.yml"
            manifest.write_text(yaml.safe_dump({"metadata": {"id": "current-project"}}))
            prepare = {"ansible.builtin.include_tasks": str(PLAYBOOKS / "tasks/prepare-validation.yml")}
            play = root / "play.yml"
            play.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False,
                "vars": {"platform_project_manifest_path": str(manifest),
                         "platform_service_catalog_path": str(ROOT / "examples/catalog/service-catalog.yml")},
                "tasks": [{"ansible.builtin.set_fact": {"platform_project_manifest_document": {"metadata": {"id": "stale"}}}},
                          prepare, {"ansible.builtin.assert": {"that": ["platform_project_manifest_document.metadata.id == 'current-project'"]}},
                          {"ansible.builtin.file": {"path": str(manifest), "state": "absent"}},
                          prepare, {"ansible.builtin.assert": {"that": ["platform_project_manifest_document == {}"]}}]}]))
            result = subprocess.run(["ansible-playbook", "-i", "localhost,", str(play)],
                                    env=dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(ROOT / "ansible-core/collections")),
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_full_and_infrastructure_sequences_keep_distinct_results(self):
        with tempfile.TemporaryDirectory(prefix="platform-infra-sequence-") as directory:
            root = self.fixture(directory)
            wrapper = root / "sequence.yml"
            common = {"platform_desired_state": {"serviceDeployments": {}}}
            plays = [{"import_playbook": str(PLAYBOOKS / "validate.yml"),
                      "vars": dict(common, platform_validation_artifact=str(root / "full-before.json"))},
                     {"hosts": "localhost", "gather_facts": False, "tasks": [{"ansible.builtin.set_fact": {
                         "platform_application_validation": {"snapshot": {"findings": [{"code": "STALE_APP_ERROR", "status": "BLOCKED"}]}}}}]},
                     {"import_playbook": str(PLAYBOOKS / "validate-infrastructure.yml"),
                      "vars": dict(common, platform_validation_artifact=str(root / "infrastructure.json"))},
                     {"import_playbook": str(PLAYBOOKS / "validate.yml"),
                      "vars": dict(common, platform_validation_artifact=str(root / "full-after.json"))}]
            wrapper.write_text(yaml.safe_dump(plays))
            variables = {"platform_project_root": str(root),
                         "platform_service_catalog_path": str(ROOT / "examples/catalog/service-catalog.yml"),
                         "platform_contracts_root": str(ROOT / "contracts")}
            result = subprocess.run(["ansible-playbook", "-i", str(root / "inventory/hosts.yml"),
                                     str(wrapper), "-e", json.dumps(variables)],
                                    env=dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(ROOT / "ansible-core/collections")),
                                    capture_output=True, text=True, timeout=90)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertTrue(all((root / name).is_file() for name in
                                ("full-before.json", "infrastructure.json", "full-after.json")))
            for entry, name in (("validate.yml", "validation-result.json"),
                                ("validate-infrastructure.yml", "infrastructure-validation-result.json")):
                plays = yaml.safe_load((PLAYBOOKS / entry).read_text())
                caller = plays[0]["tasks"][-1]
                self.assertTrue(caller["vars"]["platform_validation_default_artifact"].endswith(name))


if __name__ == "__main__":
    unittest.main()

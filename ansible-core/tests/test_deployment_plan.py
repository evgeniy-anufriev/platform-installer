import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "collections" / "ansible_collections" / "platform" / "core" / "plugins" / "module_utils"
sys.path.insert(0, str(ROOT))

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module); return module

load("project_validation")
PLAN = load("deployment_plan")
SCHEMA = load("schema_validation")
DIGEST = "sha256:" + "a" * 64

def catalog():
    return {"digest": DIGEST, "definitions": {
        "provider": {"metadata": {"version": "1"}, "capabilities": ["service.provider"], "dependencies": [], "artifacts": [], "roleEntrypoints": {"apply": {"fqcn": "p.p.r"}, "verify": {"fqcn": "p.p.r"}}, "x-definitionDigest": DIGEST},
        "consumer": {"metadata": {"version": "1"}, "capabilities": [], "dependencies": [{"capability": "service.provider"}], "artifacts": [{"id": "consumer", "version": "4.3.1", "digest": DIGEST, "requiredOffline": True}], "roleEntrypoints": {"apply": {"fqcn": "c.c.r"}, "verify": {"fqcn": "c.c.r"}}, "x-definitionDigest": DIGEST},
    }}

def snapshot(identity_source="PROJECT_MANIFEST"):
    return {"project": {"id": "project-a", "identitySource": identity_source}, "projectRevision": DIGEST, "catalogRevision": DIGEST, "validation": {"status": "PASS"}, "findings": [], "hosts": {"node1": {}}, "serviceDeployments": {"provider": {"serviceType": "provider"}, "consumer": {"serviceType": "consumer"}}, "pki": {"certificateIdentities": [{"consumers": [{"deploymentId": "consumer"}]}]}}

def runtime(digest=DIGEST): return {"bundleDigest": digest, "coreVersion": "0.1.0", "catalogDigest": DIGEST, "planningProtocol": "v1alpha1"}

class DeploymentPlanTests(unittest.TestCase):
    def test_deterministic_public_private_and_schema_safe(self):
        first = PLAN.build_deployment_plan(snapshot(), catalog(), runtime())
        second = PLAN.build_deployment_plan(snapshot(), catalog(), runtime(), "2099-01-01T00:00:00Z")
        self.assertEqual(first["deploymentPlan"]["fingerprints"]["plan"], second["deploymentPlan"]["fingerprints"]["plan"])
        self.assertEqual(first["executionManifest"]["planFingerprint"], first["deploymentPlan"]["fingerprints"]["plan"])
        self.assertNotIn("executionManifest", first["deploymentPlan"])
        self.assertNotRegex(json.dumps(first["deploymentPlan"]), r"OFFLINE_BUNDLE|REPOSITORY|/var/|playbook|password")
        contracts = Path(__file__).resolve().parents[2] / "contracts"
        self.assertEqual([], SCHEMA.SchemaValidator(contracts).validate(first["deploymentPlan"], contracts / "plan" / "v1alpha2" / "schema.json"))

    def test_semantic_changes_change_fingerprint_and_dependencies_are_core_ordered(self):
        first = PLAN.build_deployment_plan(snapshot(), catalog(), runtime())["deploymentPlan"]
        changed = copy.deepcopy(snapshot()); changed["serviceDeployments"]["consumer"]["serviceType"] = "provider"
        second = PLAN.build_deployment_plan(changed, catalog(), runtime())["deploymentPlan"]
        self.assertNotEqual(first["fingerprints"]["plan"], second["fingerprints"]["plan"])
        apply_phase = next(item for item in first["phases"] if item["id"] == "apply")
        consumer = next(item for item in apply_phase["actions"] if item["id"] == "apply:consumer")
        self.assertIn("apply:provider", consumer["dependsOn"])
        self.assertIn("pki:apply", consumer["dependsOn"])

    def test_blocked_identity_has_no_manifest(self):
        result = PLAN.build_deployment_plan(snapshot("PATH_FALLBACK"), catalog(), runtime())
        self.assertEqual("BLOCKED", result["deploymentPlan"]["status"])
        self.assertIsNone(result["executionManifest"])
        self.assertIn("PROJECT_IDENTITY_REQUIRED", [item["code"] for item in result["deploymentPlan"]["findings"]])

    def test_runtime_identity_is_semantic_but_path_is_not_an_input(self):
        first = PLAN.build_deployment_plan(snapshot(), catalog(), runtime())["deploymentPlan"]
        changed = PLAN.build_deployment_plan(snapshot(), catalog(), runtime("sha256:" + "b" * 64))["deploymentPlan"]
        self.assertNotEqual(first["fingerprints"]["plan"], changed["fingerprints"]["plan"])

if __name__ == "__main__": unittest.main()

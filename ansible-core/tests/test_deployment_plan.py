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
        "consumer": {"metadata": {"version": "1"}, "capabilities": [], "dependencies": [{"capability": "service.provider"}], "artifacts": [{"id": "consumer", "name": "consumer", "version": "4.3.1", "os": "redos", "architecture": "x86_64", "digest": DIGEST, "requiredOffline": True}], "roleEntrypoints": {"apply": {"fqcn": "c.c.r"}, "verify": {"fqcn": "c.c.r"}}, "x-definitionDigest": DIGEST},
    }}

def snapshot(identity_source="PROJECT_MANIFEST"):
    return {"project": {"id": "project-a", "identitySource": identity_source}, "projectRevision": DIGEST, "catalogRevision": DIGEST, "validation": {"status": "PASS"}, "findings": [], "hosts": {"node1": {}}, "serviceDeployments": {"provider": {"serviceType": "provider"}, "consumer": {"serviceType": "consumer"}}, "pki": {"certificateIdentities": [{"consumers": [{"deploymentId": "consumer"}]}]}}

def runtime(digest=DIGEST): return {"bundleDigest": digest, "coreVersion": "0.1.0", "catalogDigest": DIGEST, "planningProtocol": "v1alpha1"}

def sources():
    return [{"serviceType": "consumer", "requirementId": "consumer", "name": "consumer", "version": "4.3.1", "os": "redos", "architecture": "x86_64", "digest": DIGEST, "ref": "runtime/artifacts/consumer/consumer.tgz", "sha256": DIGEST, "size": 1, "type": "archive"}]

class DeploymentPlanTests(unittest.TestCase):
    def test_deterministic_public_private_and_schema_safe(self):
        first = PLAN.build_deployment_plan(snapshot(), catalog(), runtime(), bundle_artifact_sources=sources())
        second = PLAN.build_deployment_plan(snapshot(), catalog(), runtime(), "2099-01-01T00:00:00Z", sources())
        self.assertEqual(first["deploymentPlan"]["fingerprints"]["plan"], second["deploymentPlan"]["fingerprints"]["plan"])
        self.assertEqual(first["executionManifest"]["planFingerprint"], first["deploymentPlan"]["fingerprints"]["plan"])
        self.assertNotIn("executionManifest", first["deploymentPlan"])
        self.assertNotRegex(json.dumps(first["deploymentPlan"]), r"OFFLINE_BUNDLE|REPOSITORY|/var/|playbook|password")
        contracts = Path(__file__).resolve().parents[2] / "contracts"
        self.assertEqual([], SCHEMA.SchemaValidator(contracts).validate(first["deploymentPlan"], contracts / "plan" / "v1alpha2" / "schema.json"))

    def test_core_binds_exact_offline_source_into_private_manifest(self):
        result = PLAN.build_deployment_plan(snapshot(), catalog(), runtime(), bundle_artifact_sources=sources())
        authority = result["executionManifest"]["artifactSourceAuthorities"][0]
        self.assertEqual("REPOSITORY_THEN_OFFLINE", authority["sourcePolicy"])
        self.assertEqual("runtime/artifacts/consumer/consumer.tgz", authority["offlineBundle"]["ref"])
        self.assertNotIn("artifactSourceAuthorities", result["deploymentPlan"])

    def test_offline_required_missing_or_ambiguous_is_blocked(self):
        missing = PLAN.build_deployment_plan(snapshot(), catalog(), runtime(), bundle_artifact_sources=[])
        self.assertEqual("BLOCKED", missing["deploymentPlan"]["status"])
        self.assertIn("ARTIFACT_SOURCE_OFFLINE_REQUIRED", [item["code"] for item in missing["deploymentPlan"]["findings"]])
        alternate = copy.deepcopy(sources()[0]); alternate["ref"] = "runtime/artifacts/consumer/other.tgz"
        ambiguous = PLAN.build_deployment_plan(snapshot(), catalog(), runtime(), bundle_artifact_sources=sources() + [alternate])
        self.assertEqual("BLOCKED", ambiguous["deploymentPlan"]["status"])
        self.assertIn("ARTIFACT_SOURCE_AMBIGUOUS", [item["code"] for item in ambiguous["deploymentPlan"]["findings"]])

    def test_private_manifest_digest_binds_source_authority(self):
        first = PLAN.build_deployment_plan(snapshot(), catalog(), runtime(), bundle_artifact_sources=sources())
        changed_sources = copy.deepcopy(sources()); changed_sources[0]["ref"] = "runtime/artifacts/consumer/repacked.tgz"
        changed = PLAN.build_deployment_plan(snapshot(), catalog(), runtime(), bundle_artifact_sources=changed_sources)
        self.assertEqual(first["deploymentPlan"]["fingerprints"]["plan"], changed["deploymentPlan"]["fingerprints"]["plan"])
        self.assertNotEqual(first["executionManifestDigest"], changed["executionManifestDigest"])

    def test_unsafe_bundle_ref_is_rejected_before_manifest_creation(self):
        unsafe = copy.deepcopy(sources()); unsafe[0]["ref"] = "runtime/artifacts/../escape.tgz"
        with self.assertRaisesRegex(ValueError, "BUNDLE_SOURCE_INDEX_INVALID"):
            PLAN.build_deployment_plan(snapshot(), catalog(), runtime(), bundle_artifact_sources=unsafe)

    def test_bundle_source_requires_logical_digest_to_equal_file_checksum(self):
        mismatch = copy.deepcopy(sources()); mismatch[0]["sha256"] = "sha256:" + "d" * 64
        with self.assertRaisesRegex(ValueError, "BUNDLE_SOURCE_INDEX_INVALID"):
            PLAN.build_deployment_plan(snapshot(), catalog(), runtime(), bundle_artifact_sources=mismatch)
        missing = copy.deepcopy(sources()); missing[0]["digest"] = ""
        with self.assertRaisesRegex(ValueError, "BUNDLE_SOURCE_INDEX_INVALID"):
            PLAN.build_deployment_plan(snapshot(), catalog(), runtime(), bundle_artifact_sources=missing)

    def test_bundle_source_digest_uses_canonical_sha256_grammar(self):
        malformed = (
            "sha256:not-a-digest",
            "sha256:1234",
            "sha256:" + "a" * 63,
            "sha256:" + "a" * 65,
            "sha512:" + "a" * 64,
            "SHA256:" + "a" * 64,
            "sha256:" + "A" * 64,
        )
        for digest in malformed:
            with self.subTest(digest=digest):
                invalid = copy.deepcopy(sources()); invalid[0]["digest"] = digest; invalid[0]["sha256"] = digest
                with self.assertRaisesRegex(ValueError, "BUNDLE_SOURCE_INDEX_INVALID"):
                    PLAN.build_deployment_plan(snapshot(), catalog(), runtime(), bundle_artifact_sources=invalid)
        invalid_checksum = copy.deepcopy(sources()); invalid_checksum[0]["sha256"] = "sha256:not-a-digest"
        with self.assertRaisesRegex(ValueError, "BUNDLE_SOURCE_INDEX_INVALID"):
            PLAN.build_deployment_plan(snapshot(), catalog(), runtime(), bundle_artifact_sources=invalid_checksum)

    def test_pki_store_password_requirement_uses_existing_public_schema_only(self):
        pki = {"materializationPlans": [
            {"hostId": "node2", "storePasswordSecretRef": "runtime:pki-store-password"},
            {"hostId": "node1", "storePasswordSecretRef": "runtime:pki-store-password"},
            {"hostId": "node1", "storePasswordSecretRef": "runtime:pki-store-password"},
        ]}
        result = PLAN.build_deployment_plan(snapshot(), catalog(), runtime(), bundle_artifact_sources=sources(), pki_materialization=pki)
        plan, manifest = result["deploymentPlan"], result["executionManifest"]
        self.assertEqual([{"requirementRef": "pki-store-password", "purpose": "PKI_STORE_PASSWORD", "hosts": ["node1", "node2"]}], plan["requiredCredentials"])
        self.assertNotIn("runtime:pki-store-password", json.dumps(plan))
        self.assertEqual("runtime:pki-store-password", manifest["runtimeSecretRequirements"][0]["runtimeReference"])
        contracts = Path(__file__).resolve().parents[2] / "contracts"
        self.assertEqual([], SCHEMA.SchemaValidator(contracts).validate(plan, contracts / "plan" / "v1alpha2" / "schema.json"))

    def test_unsupported_pki_runtime_reference_blocks_without_exposure(self):
        result = PLAN.build_deployment_plan(snapshot(), catalog(), runtime(), bundle_artifact_sources=sources(), pki_materialization={"materializationPlans": [{"hostId": "node1", "storePasswordSecretRef": "runtime:other"}]})
        self.assertEqual("BLOCKED", result["deploymentPlan"]["status"])
        self.assertIn("PKI_STORE_PASSWORD_REFERENCE_UNSUPPORTED", [item["code"] for item in result["deploymentPlan"]["findings"]])
        self.assertNotIn("runtime:other", json.dumps(result["deploymentPlan"]))

    def test_semantic_changes_change_fingerprint_and_dependencies_are_core_ordered(self):
        first = PLAN.build_deployment_plan(snapshot(), catalog(), runtime(), bundle_artifact_sources=sources())["deploymentPlan"]
        changed = copy.deepcopy(snapshot()); changed["serviceDeployments"]["consumer"]["serviceType"] = "provider"
        second = PLAN.build_deployment_plan(changed, catalog(), runtime(), bundle_artifact_sources=sources())["deploymentPlan"]
        self.assertNotEqual(first["fingerprints"]["plan"], second["fingerprints"]["plan"])
        apply_phase = next(item for item in first["phases"] if item["id"] == "apply")
        consumer = next(item for item in apply_phase["actions"] if item["id"] == "apply:consumer")
        self.assertIn("apply:provider", consumer["dependsOn"])
        self.assertIn("pki:apply", consumer["dependsOn"])

    def test_blocked_identity_has_no_manifest(self):
        result = PLAN.build_deployment_plan(snapshot("PATH_FALLBACK"), catalog(), runtime(), bundle_artifact_sources=sources())
        self.assertEqual("BLOCKED", result["deploymentPlan"]["status"])
        self.assertIsNone(result["executionManifest"])
        self.assertIn("PROJECT_IDENTITY_REQUIRED", [item["code"] for item in result["deploymentPlan"]["findings"]])

    def test_runtime_identity_is_semantic_but_path_is_not_an_input(self):
        first = PLAN.build_deployment_plan(snapshot(), catalog(), runtime(), bundle_artifact_sources=sources())["deploymentPlan"]
        changed = PLAN.build_deployment_plan(snapshot(), catalog(), runtime("sha256:" + "b" * 64), bundle_artifact_sources=sources())["deploymentPlan"]
        self.assertNotEqual(first["fingerprints"]["plan"], changed["fingerprints"]["plan"])

if __name__ == "__main__": unittest.main()

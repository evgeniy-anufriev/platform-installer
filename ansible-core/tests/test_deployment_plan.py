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
_build_deployment_plan = PLAN.build_deployment_plan


def _test_build_deployment_plan(*args, **kwargs):
    if "deployment_order" not in kwargs:
        projects = args[0].get("serviceDeployments", {}) if args and isinstance(args[0], dict) else {}
        catalog_value = args[1] if len(args) > 1 and isinstance(args[1], dict) else {}
        definitions = catalog_value.get("definitions", catalog_value)
        pending = set(projects)
        ordered = []
        while pending:
            ready = []
            for deployment_id in sorted(pending):
                deployment = projects.get(deployment_id, {})
                definition = definitions.get(deployment.get("serviceType"), {}) if isinstance(deployment, dict) else {}
                required = set()
                for dependency in definition.get("dependencies", []) if isinstance(definition, dict) else []:
                    capability = dependency.get("capability") if isinstance(dependency, dict) else None
                    required.update(
                        candidate_id for candidate_id, candidate in projects.items()
                        if candidate_id != deployment_id and isinstance(candidate, dict)
                        and capability in definitions.get(candidate.get("serviceType"), {}).get("capabilities", [])
                    )
                if required.issubset(set(ordered)):
                    ready.append(deployment_id)
            if not ready:
                ordered.extend(sorted(pending))
                break
            ordered.extend(ready)
            pending.difference_update(ready)
        kwargs["deployment_order"] = ordered
    return _build_deployment_plan(*args, **kwargs)


PLAN.build_deployment_plan = _test_build_deployment_plan

def catalog():
    return {"digest": DIGEST, "definitions": {
        "provider": {"metadata": {"version": "1"}, "capabilities": ["service.provider"], "dependencies": [], "artifacts": [], "roleEntrypoints": {"apply": {"fqcn": "p.p.r"}, "verify": {"fqcn": "p.p.r"}}, "x-definitionDigest": DIGEST},
        "consumer": {"metadata": {"version": "1"}, "capabilities": [], "dependencies": [{"capability": "service.provider"}], "artifacts": [{"id": "consumer", "name": "consumer", "version": "4.3.1", "os": "redos", "architecture": "x86_64", "digest": DIGEST, "requiredOffline": True}], "roleEntrypoints": {"apply": {"fqcn": "c.c.r"}, "verify": {"fqcn": "c.c.r"}}, "x-definitionDigest": DIGEST},
    }}

def snapshot(identity_source="PROJECT_MANIFEST"):
    return {"project": {"id": "project-a", "identitySource": identity_source}, "projectRevision": DIGEST, "catalogRevision": DIGEST, "validation": {"status": "PASS"}, "findings": [], "hosts": {"node1": {}}, "serviceDeployments": {"provider": {"serviceType": "provider"}, "consumer": {"serviceType": "consumer"}}, "topology": {"placementsByHost": {"node1": {"provider": {}, "consumer": {}}}}, "pki": {"certificateIdentities": [{"consumers": [{"deploymentId": "consumer"}]}]}}

def runtime(digest=DIGEST): return {"bundleDigest": digest, "coreVersion": "0.1.0", "catalogDigest": DIGEST, "planningProtocol": "v1alpha1"}

def sources():
    return [{"serviceType": "consumer", "requirementId": "consumer", "name": "consumer", "version": "4.3.1", "os": "redos", "architecture": "x86_64", "digest": DIGEST, "ref": "runtime/artifacts/consumer/consumer.tgz", "sha256": DIGEST, "size": 1, "type": "archive"}]

class DeploymentPlanTests(unittest.TestCase):
    def test_service_actions_use_only_selected_hosts_for_member_and_host_scoped_placement(self):
        state = snapshot()
        state["hosts"] = {"node1": {}, "node2": {}, "node3": {}}
        state["pki"] = {"certificateIdentities": []}
        state["topology"] = {"placementsByHost": {
            "node1": {"provider": {"priority": 70}},
            "node2": {"consumer": {"members": {"consumer-1": {"roles": ["client"]}}}},
            "node3": {},
        }}
        connections = {
            host_id: {"address": "192.0.2.%d" % index, "port": 22,
                      "mode": "ssh", "unsupportedOptions": False}
            for index, host_id in enumerate(("node1", "node2", "node3"), start=1)
        }
        result = PLAN.build_deployment_plan(
            state, catalog(), runtime(), bundle_artifact_sources=sources(),
            execution_connections=connections,
        )
        self.assertEqual("EXECUTABLE", result["deploymentPlan"]["status"])
        public = {item["id"]: item for phase in result["deploymentPlan"]["phases"] for item in phase["actions"]}
        private = {item["operationId"]: item for item in result["executionManifest"]["operations"]}
        for suffix, hosts in (("provider", ["node1"]), ("consumer", ["node2"])):
            for prefix in ("apply", "verify"):
                key = "%s:%s" % (prefix, suffix)
                self.assertEqual(hosts, public[key]["targets"])
                self.assertEqual(hosts, private[key]["targets"])
        self.assertNotIn("node3", json.dumps([item["targets"] for item in private.values() if item["operation"] in ("SERVICE_APPLY", "SERVICE_VERIFY")]))
        self.assertEqual({"node1", "node2"}, set(result["executionManifest"]["targetConnections"]))

    def test_missing_or_invalid_placement_blocks_execution_without_all_host_fallback(self):
        for placements in (None, {}, {"node1": {"provider": {}}, "node2": {"consumer": {}}, "node3": []}):
            with self.subTest(placements=placements):
                state = snapshot()
                state["hosts"] = {"node1": {}, "node2": {}, "node3": {}}
                state["topology"] = {"placementsByHost": placements} if placements is not None else None
                result = PLAN.build_deployment_plan(state, catalog(), runtime(), bundle_artifact_sources=sources())
                self.assertEqual("BLOCKED", result["deploymentPlan"]["status"])
                self.assertIsNone(result["executionManifest"])
                self.assertIn("SERVICE_TARGETS_UNAVAILABLE", [item["code"] for item in result["deploymentPlan"]["findings"]])

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

    def test_private_manifest_digest_binds_pki_materialization_plans(self):
        plan = {"materializationPlans": [{"id": "scope--node1", "requestId": "scope", "tlsProfileId": "tls", "authorityId": "ca", "hostId": "node1", "targetDirectory": "/etc/platform/project/scope", "formats": ["PEM", "PKCS12_KEYSTORE", "PKCS12_TRUSTSTORE"], "keyAlias": "platform-scope", "trustAlias": "platform-ca-ca", "storePasswordSecretRef": None, "materializationFingerprint": DIGEST}]}
        first = PLAN.build_deployment_plan(snapshot(), catalog(), runtime(), bundle_artifact_sources=sources(), pki_materialization=plan)
        changed_plan = copy.deepcopy(plan); changed_plan["materializationPlans"][0]["targetDirectory"] = "/etc/platform/project/other"
        changed = PLAN.build_deployment_plan(snapshot(), catalog(), runtime(), bundle_artifact_sources=sources(), pki_materialization=changed_plan)
        self.assertEqual(first["deploymentPlan"]["fingerprints"]["plan"], changed["deploymentPlan"]["fingerprints"]["plan"])
        self.assertNotEqual(first["executionManifestDigest"], changed["executionManifestDigest"])

    def test_private_manifest_binds_core_resolved_host_role_variables(self):
        value, state = catalog(), snapshot()
        value["definitions"]["provider"]["roleEntrypoints"] = {"apply": {"fqcn": "p.p.r", "variablesPrefix": "platform_provider_"}, "verify": {"fqcn": "p.p.r", "variablesPrefix": "platform_provider_"}}
        value["definitions"]["provider"]["configuration"] = {"settings": {"enabled": {"roleVariable": "platform_provider_enabled"}}}
        state["serviceDeployments"] = {"provider": {"serviceType": "provider"}}
        configuration = {"services": {"provider": {"mode": "active", "configuration": {"enabled": {"state": "RESOLVED", "value": True}}, "members": {"member-1": {"variableContext": {"hostId": "node1"}, "configuration": {"enabled": {"state": "RESOLVED", "value": True}}}}}}}
        result = PLAN.build_deployment_plan(state, value, runtime(), bundle_artifact_sources=[], execution_configuration=configuration)
        operation = next(item for item in result["executionManifest"]["operations"] if item["operationId"] == "apply:provider")
        self.assertEqual({"node1": {"platform_provider_mode": "active", "platform_provider_enabled": True}}, operation["roleVariablesByHost"])
        self.assertNotIn("roleVariablesByHost", result["deploymentPlan"])

    def test_private_manifest_projects_declared_member_list_from_resolved_topology(self):
        value, state = catalog(), snapshot()
        entrypoint = {"fqcn": "p.p.r", "variablesPrefix": "platform_provider_", "x-memberListVariable": "platform_provider_instances"}
        value["definitions"]["provider"]["roleEntrypoints"] = {"apply": entrypoint, "verify": entrypoint}
        value["definitions"]["provider"]["configuration"] = {"settings": {"enabled": {"roleVariable": "platform_provider_enabled"}}}
        state["serviceDeployments"] = {"provider": {"serviceType": "provider"}}
        state["hosts"] = {"node1": {"ansibleHost": "192.0.2.10"}, "node2": {"ansibleHost": "192.0.2.11"}}
        state["topology"] = {"resolved": {"serviceDeployments": {"provider": {"members": {
            "monitor": {"host": "node1", "roles": ["monitor"]},
            "data": {"host": "node2", "roles": ["database"]},
        }}}}, "placementsByHost": {"node1": {"provider": {}}, "node2": {"provider": {}}}}
        configuration = {"services": {"provider": {"mode": "active", "configuration": {"enabled": {"state": "RESOLVED", "value": True}}, "members": {
            "monitor": {"variableContext": {"hostId": "node1"}, "configuration": {"enabled": {"state": "RESOLVED", "value": True}}},
            "data": {"variableContext": {"hostId": "node2"}, "configuration": {"enabled": {"state": "RESOLVED", "value": True}}},
        }}}}
        result = PLAN.build_deployment_plan(state, value, runtime(), bundle_artifact_sources=[], execution_configuration=configuration)
        operation = next(item for item in result["executionManifest"]["operations"] if item["operationId"] == "apply:provider")
        expected = [
            {"id": "data", "host": "node2", "hostname": "node2", "address": "192.0.2.11", "roles": ["database"]},
            {"id": "monitor", "host": "node1", "hostname": "node1", "address": "192.0.2.10", "roles": ["monitor"]},
        ]
        self.assertEqual(expected, operation["roleVariablesByHost"]["node1"]["platform_provider_instances"])
        self.assertEqual(expected, operation["roleVariablesByHost"]["node2"]["platform_provider_instances"])
        self.assertNotIn("roleVariablesByHost", result["deploymentPlan"])

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
            {"id": "scope--node2", "requestId": "scope", "tlsProfileId": "tls", "authorityId": "ca", "hostId": "node2", "targetDirectory": "/etc/platform/project/scope", "formats": ["PEM", "PKCS12_KEYSTORE", "PKCS12_TRUSTSTORE"], "keyAlias": "platform-scope", "trustAlias": "platform-ca-ca", "storePasswordSecretRef": "runtime:pki-store-password", "materializationFingerprint": DIGEST},
            {"id": "scope--node1", "requestId": "scope", "tlsProfileId": "tls", "authorityId": "ca", "hostId": "node1", "targetDirectory": "/etc/platform/project/scope", "formats": ["PEM", "PKCS12_KEYSTORE", "PKCS12_TRUSTSTORE"], "keyAlias": "platform-scope", "trustAlias": "platform-ca-ca", "storePasswordSecretRef": "runtime:pki-store-password", "materializationFingerprint": DIGEST},
        ]}
        result = PLAN.build_deployment_plan(snapshot(), catalog(), runtime(), bundle_artifact_sources=sources(), pki_materialization=pki)
        plan, manifest = result["deploymentPlan"], result["executionManifest"]
        self.assertEqual([{"requirementRef": "pki-store-password", "purpose": "PKI_STORE_PASSWORD", "hosts": ["node1", "node2"]}], plan["requiredCredentials"])
        self.assertNotIn("runtime:pki-store-password", json.dumps(plan))
        self.assertEqual("runtime:pki-store-password", manifest["runtimeSecretRequirements"][0]["runtimeReference"])
        self.assertEqual(pki["materializationPlans"], manifest["pkiMaterializationPlans"])
        self.assertNotIn("pkiMaterializationPlans", plan)
        contracts = Path(__file__).resolve().parents[2] / "contracts"
        self.assertEqual([], SCHEMA.SchemaValidator(contracts).validate(plan, contracts / "plan" / "v1alpha2" / "schema.json"))

    def test_changed_pki_request_is_visible_and_privately_bound(self):
        pki = {"requests": [{"id": "tls--node1", "certificateRequestFingerprint": DIGEST,
                              "authorityId": "ca", "authorityFingerprint": DIGEST,
                              "consumers": [{"deploymentId": "consumer", "hostId": "node1"}]}],
               "materializationPlans": [{"requestId": "tls--node1", "hostId": "node1"}]}
        old = "sha256:" + "b" * 64
        selected = [{"requestId": "tls--node1", "expectedOldFingerprint": old,
                     "desiredFingerprint": DIGEST, "recoveryFingerprint": None,
                     "authorityId": "ca", "authorityFingerprint": DIGEST}]
        result = PLAN.build_deployment_plan(snapshot(), catalog(), runtime(),
                                            bundle_artifact_sources=sources(),
                                            pki_materialization=pki, pki_reissue=selected)
        plan, manifest = result["deploymentPlan"], result["executionManifest"]
        reissue, apply = plan["phases"][0]["actions"]
        self.assertEqual(("PKI_REISSUE", ["node1"]), (reissue["type"], reissue["targets"]))
        self.assertIn("tls--node1", reissue["summary"])
        self.assertIn("consumer", reissue["summary"])
        self.assertIn("node1", reissue["summary"])
        self.assertEqual(["pki:reissue"], apply["dependsOn"])
        self.assertEqual(selected, manifest["operations"][0]["reissueRequests"])
        self.assertNotIn(old, json.dumps(plan))
        contracts = Path(__file__).resolve().parents[2] / "contracts"
        self.assertEqual([], SCHEMA.SchemaValidator(contracts).validate(plan, contracts / "plan" / "v1alpha2" / "schema.json"))

    def test_many_reissue_requests_keep_complete_consumer_scope_in_bounded_summary(self):
        requests = [{"id": "tls-profile-long-name-%02d--node1" % index,
                     "certificateRequestFingerprint": DIGEST,
                     "authorityId": "ca", "authorityFingerprint": DIGEST,
                     "consumers": [{"deploymentId": "consumer", "hostId": "node1"}]}
                    for index in range(12)]
        pki = {"requests": requests, "materializationPlans": [
            {"requestId": item["id"], "hostId": "node1"} for item in requests]}
        selected = [{"requestId": item["id"], "expectedOldFingerprint": "sha256:" + "b" * 64,
                     "desiredFingerprint": DIGEST, "recoveryFingerprint": None,
                     "authorityId": "ca", "authorityFingerprint": DIGEST} for item in requests]
        result = PLAN.build_deployment_plan(snapshot(), catalog(), runtime(),
                                            bundle_artifact_sources=sources(),
                                            pki_materialization=pki, pki_reissue=selected)
        action = result["deploymentPlan"]["phases"][0]["actions"][0]
        self.assertLessEqual(len(action["summary"].encode("utf-8")), 512)
        self.assertIn("12 запросов", action["summary"])
        self.assertIn("сервисы: consumer", action["summary"])
        self.assertIn("серверы: node1", action["summary"])
        self.assertEqual(["node1"], action["targets"])
        self.assertEqual(selected, result["executionManifest"]["operations"][0]["reissueRequests"])

    def test_reissue_fingerprint_binds_old_and_recovery_observations(self):
        pki = {"requests": [{"id": "tls--node1", "certificateRequestFingerprint": DIGEST,
                              "authorityId": "ca", "authorityFingerprint": DIGEST,
                              "consumers": [{"deploymentId": "consumer", "hostId": "node1"}]}],
               "materializationPlans": [{"requestId": "tls--node1", "hostId": "node1"}]}
        selected = [{"requestId": "tls--node1", "expectedOldFingerprint": "sha256:" + "b" * 64,
                     "desiredFingerprint": DIGEST, "recoveryFingerprint": None,
                     "authorityId": "ca", "authorityFingerprint": DIGEST}]
        first = PLAN.build_deployment_plan(snapshot(), catalog(), runtime(), bundle_artifact_sources=sources(),
                                           pki_materialization=pki, pki_reissue=selected)["deploymentPlan"]
        changed_old = copy.deepcopy(selected)
        changed_old[0]["expectedOldFingerprint"] = "sha256:" + "c" * 64
        changed = PLAN.build_deployment_plan(snapshot(), catalog(), runtime(), bundle_artifact_sources=sources(),
                                             pki_materialization=pki, pki_reissue=changed_old)["deploymentPlan"]
        self.assertEqual(first["phases"], changed["phases"])
        self.assertNotEqual(first["fingerprints"]["plan"], changed["fingerprints"]["plan"])
        self.assertNotEqual(first["id"], changed["id"])
        resumed = copy.deepcopy(selected)
        resumed[0]["recoveryFingerprint"] = DIGEST
        recovery_plan = PLAN.build_deployment_plan(snapshot(), catalog(), runtime(), bundle_artifact_sources=sources(),
                                                   pki_materialization=pki, pki_reissue=resumed)["deploymentPlan"]
        self.assertNotEqual(first["fingerprints"]["plan"], recovery_plan["fingerprints"]["plan"])

    def test_shared_host_request_discloses_both_consuming_deployments(self):
        pki = {"requests": [{"id": "tls--node1", "certificateRequestFingerprint": DIGEST,
                              "authorityId": "ca", "authorityFingerprint": DIGEST,
                              "consumers": [{"deploymentId": "provider", "hostId": "node1"},
                                            {"deploymentId": "consumer", "hostId": "node1"}]}],
               "materializationPlans": [{"requestId": "tls--node1", "hostId": "node1"}]}
        selected = [{"requestId": "tls--node1", "expectedOldFingerprint": "sha256:" + "b" * 64,
                     "desiredFingerprint": DIGEST, "recoveryFingerprint": None,
                     "authorityId": "ca", "authorityFingerprint": DIGEST}]
        plan = PLAN.build_deployment_plan(snapshot(), catalog(), runtime(), bundle_artifact_sources=sources(),
                                          pki_materialization=pki, pki_reissue=selected)["deploymentPlan"]
        summary = plan["phases"][0]["actions"][0]["summary"]
        self.assertIn("consumer", summary)
        self.assertIn("provider", summary)
        self.assertIn("node1", summary)

    def test_service_secret_requirement_is_catalog_declared_and_private_bound(self):
        value, state = catalog(), snapshot()
        value["definitions"]["provider"].update({"configuration": {"settings": {"credential": {"schema": {"type": "object", "additionalProperties": False, "required": ["passwordSecretRef"], "properties": {"passwordSecretRef": {"type": "string"}}}, "ui": {"label": "Provider password", "x-runtimeSecretRequirement": {"requirementRef": "provider-password", "purpose": "SERVICE_PASSWORD"}}}}}, "roleEntrypoints": {"apply": {"fqcn": "p.p.r", "variablesPrefix": "platform_provider_"}, "verify": {"fqcn": "p.p.r", "variablesPrefix": "platform_provider_"}}})
        state["serviceDeployments"]["provider"]["configuration"] = {"credential": {"passwordSecretRef": "runtime:provider-password"}}
        result = PLAN.build_deployment_plan(state, value, runtime(), bundle_artifact_sources=sources())
        self.assertIn({"requirementRef": "provider-password", "purpose": "SERVICE_PASSWORD", "hosts": ["node1"]}, result["deploymentPlan"]["requiredCredentials"])
        private = next(item for item in result["executionManifest"]["runtimeSecretRequirements"] if item["requirementRef"] == "provider-password")
        self.assertEqual(("provider", "runtime:provider-password"), (private["serviceDeployment"], private["runtimeReference"]))
        self.assertNotIn("runtime:provider-password", json.dumps(result["deploymentPlan"]))

    def test_typed_service_inputs_are_target_free_opaque_and_bound_to_deployment_hosts(self):
        value, state = catalog(), snapshot()
        value["definitions"]["vault"] = {
            "metadata": {"version": "1.0.0"}, "capabilities": [], "dependencies": [],
            "artifacts": [], "runtimeRequirements": [{"id": "vault-runtime", "name": "vault", "version": "1.21.2", "os": "redos", "architecture": "x86_64", "requiredOffline": False}],
            "x-secretInputs": {"apiVersion": "ServiceSecretInputs/v1alpha1", "inputs": [
                {"requirementRef": "vault-admin-token", "purpose": "SERVICE_ADMIN_TOKEN", "displayLabel": "Administrative token", "requiredWhen": "INITIALIZED", "operations": ["SERVICE_APPLY", "SERVICE_VERIFY"]},
                {"requirementRef": "vault-unseal-shares", "purpose": "SERVICE_UNSEAL_SHARES", "displayLabel": "Unseal keys", "requiredWhen": "SEALED", "operations": ["SERVICE_APPLY"]},
            ]},
            "roleEntrypoints": {"apply": {"fqcn": "p.p.r", "variablesPrefix": "platform_vault_", "x-memberListVariable": "platform_vault_instances"}, "verify": {"fqcn": "p.p.r", "variablesPrefix": "platform_vault_", "x-memberListVariable": "platform_vault_instances"}},
            "configuration": {"settings": {"tlsProfile": {"roleVariable": "platform_vault_tls_profile"}}},
        }
        state["hosts"] = {"node1": {"ansibleHost": "192.0.2.11"}, "node2": {"ansibleHost": "192.0.2.12"}, "node3": {"ansibleHost": "192.0.2.13"}}
        state["serviceDeployments"] = {"vault-ha": {"serviceType": "vault", "mode": "raft-ha"}}
        state["pki"] = {"certificateIdentities": [{"consumers": [{"deploymentId": "vault-ha"}]}]}
        state["topology"] = {"resolved": {"serviceDeployments": {"vault-ha": {"members": {
            "vault-1": {"host": "node1", "roles": ["vault"]},
            "vault-2": {"host": "node2", "roles": ["vault"]},
            "vault-3": {"host": "node3", "roles": ["vault"]},
        }}}}, "placementsByHost": {"node1": {"vault-ha": {}}, "node2": {"vault-ha": {}}, "node3": {"vault-ha": {}}}}
        execution_configuration = {"services": {"vault-ha": {
            "mode": "raft-ha", "configuration": {"tlsProfile": {"state": "RESOLVED", "value": "infra-tls"}},
            "members": {"vault-%d" % index: {"variableContext": {"hostId": "node%d" % index}, "configuration": {"tlsProfile": {"state": "RESOLVED", "value": "infra-tls"}}}
                        for index in range(1, 4)},
        }}}
        pki = {"materializationPlans": [{"id": "infra-tls--vault-ha", "requestId": "infra-tls--vault-ha", "tlsProfileId": "infra-tls", "authorityId": "ca", "hostId": "node1", "targetDirectory": "/etc/platform/project/infra-tls", "formats": ["PEM"], "keyAlias": "platform-vault", "trustAlias": "platform-ca-ca", "storePasswordSecretRef": None, "materializationFingerprint": DIGEST}]}
        requirement = PLAN._artifact_requirements(state["serviceDeployments"], value["definitions"])[0]
        source = {key: requirement[key] for key in ("serviceType", "requirementId", "name", "version", "os", "architecture", "digest")}
        source.update({"ref": "runtime/artifacts/vault/vault.rpm", "sha256": requirement["digest"], "size": 2048, "type": "package"})
        result = PLAN.build_deployment_plan(state, value, runtime(), bundle_artifact_sources=[source], pki_materialization=pki, execution_configuration=execution_configuration)
        self.assertEqual("EXECUTABLE", result["deploymentPlan"]["status"])
        self.assertEqual(1, len(result["deploymentPlan"]["artifactRequirements"]))
        refs = [item for item in result["deploymentPlan"]["requiredCredentials"] if item["purpose"] in ("SERVICE_ADMIN_TOKEN", "SERVICE_UNSEAL_SHARES")]
        self.assertEqual(2, len(refs))
        self.assertTrue(all(item["requirementRef"].startswith("si-") and len(item["requirementRef"]) == 43 for item in refs))
        self.assertTrue(all(item["hosts"] == ["node1", "node2", "node3"] for item in refs))
        private = result["executionManifest"]["runtimeSecretInputs"]
        # Exercise the actual closed Start consumer, not a parallel field check.
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        try:
            import execution_secret_lease
            admitted = execution_secret_lease._validate_typed_secret_requirements(private)
            self.assertEqual(2, len(admitted))
            for item in private:
                self.assertNotIn("displayLabel", item)
            public_inputs, _, input_findings = PLAN._service_input_requirements(
                state["serviceDeployments"], value["definitions"], state["topology"]["resolved"])
            self.assertEqual([], input_findings)
            self.assertEqual({"Administrative token", "Unseal keys"},
                             {item["displayLabel"] for item in public_inputs})
            malformed = copy.deepcopy(private)
            malformed[0]["displayLabel"] = "Presentation only"
            with self.assertRaisesRegex(execution_secret_lease.LifecycleError, "EXECUTION_MANIFEST_INVALID"):
                execution_secret_lease._validate_typed_secret_requirements(malformed)
        finally:
            sys.path.pop(0)
        self.assertEqual({"vault-admin-token", "vault-unseal-shares"}, {item["manifestRequirementRef"] for item in private})
        self.assertEqual({"INITIALIZED", "SEALED"}, {item["requiredWhen"] for item in private})
        operations_by_purpose = {item["purpose"]: item["operations"] for item in private}
        self.assertEqual(["SERVICE_APPLY", "SERVICE_VERIFY"], operations_by_purpose["SERVICE_ADMIN_TOKEN"])
        self.assertEqual(["SERVICE_APPLY"], operations_by_purpose["SERVICE_UNSEAL_SHARES"])
        self.assertNotIn("root_token", json.dumps(result))
        self.assertNotIn("unseal_keys", json.dumps(result))
        self.assertNotIn("vault-admin-token", json.dumps(result["deploymentPlan"]))
        apply = next(item for item in result["executionManifest"]["operations"] if item["operationId"] == "apply:vault-ha")
        apply_action = next(action for phase in result["deploymentPlan"]["phases"] for action in phase["actions"] if action["id"] == "apply:vault-ha")
        self.assertIn("pki:apply", apply_action["dependsOn"])
        self.assertEqual(pki["materializationPlans"], result["executionManifest"]["pkiMaterializationPlans"])
        authority = result["executionManifest"]["artifactSourceAuthorities"][0]
        self.assertEqual("redos", authority["requirement"]["os"])
        self.assertEqual("runtime/artifacts/vault/vault.rpm", authority["offlineBundle"]["ref"])
        for host in ("node1", "node2", "node3"):
            self.assertEqual("raft-ha", apply["roleVariablesByHost"][host]["platform_vault_mode"])
            self.assertEqual("infra-tls", apply["roleVariablesByHost"][host]["platform_vault_tls_profile"])
            self.assertEqual(["vault-1", "vault-2", "vault-3"], [item["id"] for item in apply["roleVariablesByHost"][host]["platform_vault_instances"]])

    def test_member_client_port_override_uses_existing_member_list_without_host_conflict(self):
        definition = {
            "configuration": {"settings": {"port": {"roleVariable": "platform_vault_api_port", "scopes": ["deployment", "member"]}}},
            "x-backendClientListener": {"listener": "client", "allocation": {"kind": "HOST_LOCAL_ORDINAL", "stride": 2}},
        }
        resolved = {"members": {"vault-1": {"host": "node1", "roles": ["vault"]},
                                "vault-2": {"host": "node1", "roles": ["vault"]}}}
        service = {"services": {"vault-ha": {"mode": "raft-ha",
            "configuration": {"port": {"state": "RESOLVED", "source": "ROLE_DEFAULT", "value": 8200}},
            "members": {
                "vault-1": {"variableContext": {"hostId": "node1"}, "configuration": {"port": {"state": "RESOLVED", "source": "ROLE_DEFAULT", "value": 8200}}},
                "vault-2": {"variableContext": {"hostId": "node1"}, "configuration": {"port": {"state": "RESOLVED", "source": "MEMBER_OVERRIDE", "value": 8210}}},
            }}}}
        values = PLAN._execution_role_variables("vault-ha", definition, "platform_vault_", service,
            ["node1"], resolved, {"node1": {"ansibleHost": "192.0.2.1"}}, "platform_vault_instances")
        self.assertNotIn("platform_vault_api_port", values["node1"])
        self.assertEqual([{}, {"port": 8210}], [
            {key: item[key] for key in item if key == "port"}
            for item in values["node1"]["platform_vault_instances"]])

    def test_role_defaults_are_not_promoted_to_runtime_facts(self):
        settings = {key: {"roleVariable": "platform_vault_" + key} for key in
                    ("literal", "reference", "dynamic", "deployment", "document", "member")}
        definition = {"configuration": {"settings": settings}}
        base = {
            "literal": {"state": "RESOLVED", "source": "ROLE_DEFAULT", "value": 1},
            "reference": {"state": "RESOLVED", "source": "STATIC_REFERENCE", "origin": "ROLE_DEFAULT", "value": 2},
            "dynamic": {"state": "DEFERRED", "source": "RUNTIME_DEFERRED", "reason": "NON_LITERAL_ROLE_DEFAULT"},
            "deployment": {"state": "RESOLVED", "source": "DEPLOYMENT_OVERRIDE", "value": 3},
            "document": {"state": "RESOLVED", "source": "DEPLOYMENT_OVERRIDE", "physicalOrigin": "group_vars/all.yml", "value": 4},
            "member": {"state": "RESOLVED", "source": "ROLE_DEFAULT", "value": 5},
        }
        member = copy.deepcopy(base)
        member["member"] = {"state": "RESOLVED", "source": "MEMBER_OVERRIDE", "value": 6}
        execution = {"services": {"vault-ha": {"mode": "raft-ha", "configuration": base,
                                           "members": {"vault-1": {"variableContext": {"hostId": "node1"},
                                                                   "configuration": member}}}}}
        values = PLAN._execution_role_variables("vault-ha", definition, "platform_vault_", execution, ["node1"])
        self.assertEqual({"platform_vault_mode": "raft-ha", "platform_vault_deployment": 3,
                          "platform_vault_document": 4, "platform_vault_member": 6}, values["node1"])

    def test_source_integration_depends_on_derived_base_haproxy_providers(self):
        deployments = {"haproxy": {"serviceType": "haproxy", "endpointGroup": "public"},
                       "vip": {"serviceType": "keepalived", "endpointGroupRef": "public"},
                       "vault-ha": {"serviceType": "vault", "endpointGroup": "public"}}
        placements = {"node1": {"haproxy": {}, "vip": {}}}
        provider_dependencies = PLAN._service_dependencies("haproxy", deployments["haproxy"], {}, deployments, placements)
        self.assertEqual([], provider_dependencies)
        source_dependencies = PLAN._service_dependencies("vault-ha", deployments["vault-ha"], {}, deployments, placements)
        self.assertEqual(["apply:haproxy"], source_dependencies)

    def test_requested_order_interleaves_apply_and_verify_and_checks_dependencies(self):
        state, definitions = snapshot(), catalog()
        result = PLAN.build_deployment_plan(
            state, definitions, runtime(), bundle_artifact_sources=sources(),
            deployment_order=["provider", "consumer"])
        services = result["deploymentPlan"]["phases"][-1]["actions"]
        self.assertEqual(["apply:provider", "verify:provider", "apply:consumer", "verify:consumer"],
                         [item["id"] for item in services])
        self.assertEqual(["pki:apply", "verify:provider"], services[2]["dependsOn"])
        self.assertEqual([], result["deploymentPlan"]["findings"])

        reversed_result = PLAN.build_deployment_plan(
            state, definitions, runtime(), bundle_artifact_sources=sources(),
            deployment_order=["consumer", "provider"])
        self.assertIn("EXECUTION_ORDER_DEPENDENCY_CONFLICT",
                      [item["code"] for item in reversed_result["deploymentPlan"]["findings"]])

    def test_deployment_order_must_match_exact_membership(self):
        expected = {"one": {}, "two": {}}
        for value in (None, [], ["one"], ["one", "one"], ["one", "three"]):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "DEPLOYMENT_ORDER_INVALID"):
                PLAN._validated_deployment_order(expected, value)
        self.assertEqual([], PLAN._validated_deployment_order({}, []))

    def test_secret_output_declaration_is_private_and_bound_to_apply_deployment(self):
        value, state = catalog(), snapshot()
        value["definitions"]["provider"]["x-secretOutputs"] = {
            "protocol": "SecretOutputDelivery/v1alpha1",
            "entries": ["admin-token", "unseal-shares"],
        }
        state["serviceDeployments"] = {"provider": {"serviceType": "provider"}}
        result = PLAN.build_deployment_plan(state, value, runtime(), bundle_artifact_sources=[])
        self.assertEqual([{
            "protocol": "SecretOutputDelivery/v1alpha1",
            "serviceDeployment": "provider",
            "entries": ["admin-token", "unseal-shares"],
        }], result["executionManifest"]["runtimeSecretOutputs"])
        self.assertNotIn("runtimeSecretOutputs", result["deploymentPlan"])
        malformed = copy.deepcopy(value)
        malformed["definitions"]["provider"]["x-secretOutputs"]["sourcePath"] = "/untrusted"
        with self.assertRaisesRegex(ValueError, "SECRET_OUTPUT_DECLARATION_INVALID"):
            PLAN.build_deployment_plan(state, malformed, runtime(), bundle_artifact_sources=[])

    def test_vault_descriptor_v2_is_closed_bounded_and_target_free(self):
        value, state = catalog(), snapshot()
        value["definitions"]["vault"] = {
            "metadata": {"version": "1"}, "dependencies": [], "capabilities": [], "artifacts": [],
            "configuration": {"settings": {"tlsProfile": {"ui": {"label": "TLS profile"}}}},
            "x-secretInputs": {"apiVersion": "ServiceSecretInputs/v1alpha1", "inputs": [
                {"requirementRef": "vault-admin-token", "purpose": "SERVICE_ADMIN_TOKEN", "displayLabel": "Administrative token", "requiredWhen": "INITIALIZED", "operations": ["SERVICE_APPLY", "SERVICE_VERIFY"]},
                {"requirementRef": "vault-unseal-shares", "purpose": "SERVICE_UNSEAL_SHARES", "displayLabel": "Unseal keys", "requiredWhen": "SEALED", "operations": ["SERVICE_APPLY"]},
            ]},
        }
        state["serviceDeployments"] = {"vault-ha": {"serviceType": "vault", "mode": "raft-ha"}}
        state["topology"] = {"resolved": {"serviceDeployments": {"vault-ha": {"members": {
            "vault-1": {"host": "node1"}, "vault-2": {"host": "node1"}, "vault-3": {"host": "node1"},
        }}}}}
        descriptors = PLAN.build_runtime_secret_descriptors(
            state, value, {"materializationPlans": [{"hostId": "node1", "storePasswordSecretRef": "runtime:pki-store-password"}]})
        self.assertEqual("BuildRuntimeSecretDescriptors/v1alpha2", descriptors["apiVersion"])
        self.assertEqual("PKI_STORE_PASSWORD", descriptors["descriptors"][0]["purpose"])
        self.assertIsNone(descriptors["descriptors"][0]["serviceDeployment"])
        self.assertEqual(["node1"], descriptors["descriptors"][1]["hosts"])
        self.assertEqual({"ALWAYS", "INITIALIZED", "SEALED"}, {item["requiredWhen"] for item in descriptors["descriptors"]})
        self.assertNotIn("vault-admin-token", json.dumps(descriptors))
        self.assertNotIn("sensitive-test-canary", json.dumps(descriptors))
        contracts = Path(__file__).resolve().parents[2] / "contracts"
        findings = SCHEMA.SchemaValidator(contracts).validate(
            descriptors, contracts / "runtime-secret-descriptors" / "v1alpha2" / "schema.json")
        self.assertEqual([], findings)
        shares = next(item for item in descriptors["descriptors"] if item["purpose"] == "SERVICE_UNSEAL_SHARES")
        self.assertEqual(["SERVICE_APPLY"], shares["operations"])
        invalid_descriptors = copy.deepcopy(descriptors)
        next(item for item in invalid_descriptors["descriptors"] if item["purpose"] == "SERVICE_UNSEAL_SHARES")["operations"] = ["SERVICE_APPLY", "SERVICE_VERIFY"]
        self.assertTrue(SCHEMA.SchemaValidator(contracts).validate(
            invalid_descriptors, contracts / "runtime-secret-descriptors" / "v1alpha2" / "schema.json"))

    def test_typed_service_input_hosts_follow_resolved_placement_and_one_host_three_members(self):
        value, state = catalog(), snapshot()
        value["definitions"]["vault"] = {"x-secretInputs": {"apiVersion": "ServiceSecretInputs/v1alpha1", "inputs": [
            {"requirementRef": "vault-admin-token", "purpose": "SERVICE_ADMIN_TOKEN", "displayLabel": "Administrative token", "requiredWhen": "INITIALIZED", "operations": ["SERVICE_APPLY", "SERVICE_VERIFY"]},
        ]}, "artifacts": [], "runtimeRequirements": [], "dependencies": [], "capabilities": [], "metadata": {"version": "1"}}
        state["serviceDeployments"] = {"vault-ha": {"serviceType": "vault"}}
        state["topology"] = {"resolved": {"serviceDeployments": {"vault-ha": {"members": {
            "vault-1": {"host": "node1", "roles": ["vault"]},
            "vault-2": {"host": "node1", "roles": ["vault"]},
            "vault-3": {"host": "node1", "roles": ["vault"]},
        }}}}, "placementsByHost": {"node1": {"vault-ha": {}}}}
        result = PLAN.build_deployment_plan(state, value, runtime())
        self.assertEqual(["node1"], result["deploymentPlan"]["requiredCredentials"][0]["hosts"])
        private = result["executionManifest"]["runtimeSecretInputs"][0]
        self.assertEqual(["node1"], private["hosts"])

        standalone = copy.deepcopy(state)
        standalone["serviceDeployments"]["vault-ha"]["mode"] = "standalone"
        standalone["topology"]["resolved"]["serviceDeployments"]["vault-ha"]["members"] = {
            "vault-1": {"host": "node1", "roles": ["vault"]},
        }
        single = PLAN.build_deployment_plan(standalone, value, runtime())
        self.assertEqual(["node1"], single["deploymentPlan"]["requiredCredentials"][0]["hosts"])
        self.assertEqual(["node1"], single["executionManifest"]["runtimeSecretInputs"][0]["hosts"])

    def test_typed_service_input_metadata_fails_closed_and_never_creates_a_manifest(self):
        value, state = catalog(), snapshot()
        value["definitions"]["provider"]["x-secretInputs"] = {"apiVersion": "ServiceSecretInputs/v1alpha1", "inputs": [
            {"requirementRef": "vault-admin-token", "purpose": "SERVICE_ADMIN_TOKEN", "displayLabel": "Token", "requiredWhen": "ALWAYS", "operations": ["SERVICE_APPLY", "SERVICE_VERIFY"]},
        ]}
        state["serviceDeployments"]["provider"]["configuration"] = {}
        state["topology"] = {"resolved": {"serviceDeployments": {"provider": {"members": {"member-1": {"host": "node1", "roles": []}}}}}}
        result = PLAN.build_deployment_plan(state, value, runtime(), bundle_artifact_sources=sources())
        self.assertEqual("BLOCKED", result["deploymentPlan"]["status"])
        self.assertIsNone(result["executionManifest"])
        self.assertIn("SERVICE_SECRET_INPUT_METADATA_INVALID", [item["code"] for item in result["deploymentPlan"]["findings"]])

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
        apply_phase = next(item for item in first["phases"] if item["id"] == "services")
        consumer = next(item for item in apply_phase["actions"] if item["id"] == "apply:consumer")
        self.assertIn("verify:provider", consumer["dependsOn"])
        self.assertNotIn("apply:provider", consumer["dependsOn"])
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

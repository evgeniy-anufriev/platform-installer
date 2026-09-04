"""Deterministic, target-free DeploymentPlan construction for UI-BE-04B."""

from __future__ import absolute_import, division, print_function

import copy
import hashlib
import json

try:
    from .project_validation import canonical_digest
except ImportError:
    from project_validation import canonical_digest


API_VERSION = "platform.installer/plan/v1alpha2"
MANIFEST_API_VERSION = "platform.installer/execution-manifest/v1alpha1"
PLANNING_PROTOCOL = "v1alpha1"


def _digest(value):
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _finding(code, field, message):
    return {
        "apiVersion": "platform.installer/finding/v1alpha1",
        "kind": "Finding",
        "code": code,
        "status": "BLOCKED",
        "category": "deployment-plan",
        "field": field,
        "safeMessage": message,
    }


def _safe_findings(items):
    result = []
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict):
            result.append(copy.deepcopy(item))
    return sorted(result, key=lambda item: (item.get("field", ""), item.get("code", ""), item.get("safeMessage", "")))


def _runtime_release(value):
    value = value if isinstance(value, dict) else {}
    result = {
        "bundleDigest": value.get("bundleDigest"),
        "coreVersion": value.get("coreVersion"),
        "catalogDigest": value.get("catalogDigest"),
        "planningProtocol": value.get("planningProtocol", PLANNING_PROTOCOL),
    }
    if any(not isinstance(item, str) or not item for item in result.values()):
        raise ValueError("DEPLOYMENT_PLAN_RUNTIME_RELEASE_INVALID")
    if not result["bundleDigest"].startswith("sha256:") or not result["catalogDigest"].startswith("sha256:"):
        raise ValueError("DEPLOYMENT_PLAN_RUNTIME_RELEASE_INVALID")
    return result


def _artifact_requirements(deployments, definitions):
    requirements = []
    for deployment_id, deployment in sorted(deployments.items()):
        service_type = deployment.get("serviceType") if isinstance(deployment, dict) else None
        definition = definitions.get(service_type, {}) if isinstance(definitions, dict) else {}
        for artifact in definition.get("artifacts", []) if isinstance(definition, dict) else []:
            if isinstance(artifact, dict) and all(isinstance(artifact.get(key), str) and artifact[key] for key in ("id", "version", "digest")):
                requirements.append({
                    "id": "%s:%s" % (deployment_id, artifact["id"]),
                    "serviceDeployment": deployment_id,
                    "serviceType": service_type,
                    "requirementId": artifact["id"],
                    "version": artifact["version"],
                    "digest": artifact["digest"],
                    "requiredOffline": bool(artifact.get("requiredOffline", True)),
                })
    return requirements


def _service_dependencies(deployment_id, deployment, definitions, deployments):
    definition = definitions.get(deployment.get("serviceType"), {}) if isinstance(deployment, dict) and isinstance(definitions, dict) else {}
    required = definition.get("dependencies", []) if isinstance(definition, dict) else []
    result = []
    for dependency in required if isinstance(required, list) else []:
        capability = dependency.get("capability") if isinstance(dependency, dict) else None
        if not isinstance(capability, str):
            continue
        providers = []
        for candidate_id, candidate in sorted(deployments.items()):
            candidate_definition = definitions.get(candidate.get("serviceType"), {}) if isinstance(candidate, dict) else {}
            if capability in (candidate_definition.get("capabilities", []) if isinstance(candidate_definition, dict) else []):
                providers.append("apply:%s" % candidate_id)
        result.extend(providers)
    return sorted(set(result))


def _pki_consumers(snapshot):
    identities = ((snapshot.get("pki") or {}).get("certificateIdentities", []) if isinstance(snapshot, dict) else [])
    deployments = set()
    for identity in identities if isinstance(identities, list) else []:
        for consumer in identity.get("consumers", []) if isinstance(identity, dict) else []:
            if isinstance(consumer, dict) and isinstance(consumer.get("deploymentId"), str):
                deployments.add(consumer["deploymentId"])
    return sorted(deployments)


def build_deployment_plan(snapshot, service_catalog, runtime_release, created_at="1970-01-01T00:00:00Z"):
    """Return a public plan and private manifest from already resolved Core data."""
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    catalog = service_catalog.get("platform_service_catalog", service_catalog) if isinstance(service_catalog, dict) else {}
    definitions = catalog.get("definitions", {}) if isinstance(catalog, dict) else {}
    release = _runtime_release(runtime_release)
    project = snapshot.get("project", {}) if isinstance(snapshot.get("project"), dict) else {}
    identity = project.get("id")
    explicit_identity = project.get("identitySource") == "PROJECT_MANIFEST"
    deployments = snapshot.get("serviceDeployments", {}) if isinstance(snapshot.get("serviceDeployments"), dict) else {}
    findings = _safe_findings(snapshot.get("findings"))
    if not explicit_identity or not isinstance(identity, str) or not identity:
        findings.append(_finding("PROJECT_IDENTITY_REQUIRED", "project.metadata.id", "Installer-managed execution requires project.yml metadata.id"))
    if snapshot.get("validation", {}).get("status") != "PASS":
        findings.append(_finding("PROJECT_VALIDATION_BLOCKED", "validation", "Authoritative project validation is blocked"))
    findings = _safe_findings(findings)
    executable = not findings
    artifact_requirements = _artifact_requirements(deployments, definitions)
    artifact_digest = canonical_digest(artifact_requirements)
    targets = sorted(snapshot.get("hosts", {}).keys()) if isinstance(snapshot.get("hosts"), dict) else []
    pki_consumers = _pki_consumers(snapshot)
    actions = []
    if pki_consumers:
        actions.append({"id": "pki:apply", "type": "PKI_APPLY", "targets": targets, "dependsOn": [], "mutating": True, "reboot": "NONE", "summary": "Materialize approved PKI inputs"})
    apply_actions = []
    for deployment_id, deployment in sorted(deployments.items()):
        dependencies = _service_dependencies(deployment_id, deployment, definitions, deployments)
        if deployment_id in pki_consumers:
            dependencies.append("pki:apply")
        apply_actions.append({"id": "apply:%s" % deployment_id, "type": "SERVICE_APPLY", "serviceDeployment": deployment_id, "targets": targets, "dependsOn": sorted(set(dependencies)), "mutating": True, "reboot": "NONE", "summary": "Apply service deployment %s" % deployment_id})
    verify_actions = [{"id": "verify:%s" % deployment_id, "type": "SERVICE_VERIFY", "serviceDeployment": deployment_id, "targets": targets, "dependsOn": ["apply:%s" % deployment_id], "mutating": False, "reboot": "NONE", "summary": "Verify service deployment %s" % deployment_id} for deployment_id in sorted(deployments)]
    phases = []
    if actions:
        phases.append({"id": "pki", "order": len(phases), "actions": actions})
    phases.append({"id": "apply", "order": len(phases), "actions": apply_actions})
    phases.append({"id": "verify", "order": len(phases), "actions": verify_actions})
    semantic = {
        "apiVersion": API_VERSION,
        "planningProtocol": release["planningProtocol"],
        "projectIdentity": identity if explicit_identity else None,
        "projectRevision": snapshot.get("projectRevision"),
        "catalogDigest": catalog.get("digest"),
        "runtimeRelease": release,
        "artifactRequirements": artifact_requirements,
        "phases": phases,
        "acknowledgements": [],
        "status": "EXECUTABLE" if executable else "BLOCKED",
    }
    plan_fingerprint = canonical_digest(semantic)
    plan = {
        "apiVersion": API_VERSION,
        "kind": "DeploymentPlan",
        "id": "plan-" + plan_fingerprint.split(":", 1)[1][:24],
        "createdAt": created_at,
        "projectIdentity": identity if explicit_identity else None,
        "projectRevision": snapshot.get("projectRevision"),
        "planner": {"coreVersion": release["coreVersion"], "planningProtocol": release["planningProtocol"]},
        "runtimeRelease": release,
        "fingerprints": {"project": snapshot.get("projectRevision"), "catalog": catalog.get("digest"), "artifacts": artifact_digest, "core": _digest(release["coreVersion"] + "\x00" + release["planningProtocol"]), "plan": plan_fingerprint},
        "status": "EXECUTABLE" if executable else "BLOCKED",
        "readiness": "REQUIRES_PREPARATION" if executable else "BLOCKED",
        "artifactRequirements": artifact_requirements,
        "phases": phases,
        "requiredCredentials": [],
        "acknowledgements": [],
        "findings": findings,
    }
    manifest = None
    if executable:
        manifest = {"apiVersion": MANIFEST_API_VERSION, "kind": "ExecutionManifest", "projectIdentity": identity, "planFingerprint": plan_fingerprint, "runtimeRelease": release, "operations": [{"actionId": action["id"], "operation": action["type"], "serviceDeployment": action.get("serviceDeployment")} for phase in phases for action in phase["actions"]]}
    return {"deploymentPlan": plan, "executionManifest": manifest, "executionManifestDigest": canonical_digest(manifest) if manifest else None}

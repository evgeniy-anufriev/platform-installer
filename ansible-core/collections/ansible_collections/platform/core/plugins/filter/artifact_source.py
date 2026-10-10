"""Closed target-local realization of Core-authorized artifact sources."""
from __future__ import absolute_import, division, print_function
import copy
import json


def _version_matches(required, actual):
    if not required:
        return True
    left, right = required.split("."), actual.split(".")
    return len(left) == len(right) and all(item.lower() == "x" or item == candidate for item, candidate in zip(left, right))


def resolve_artifact_source(authority, requirement, target, target_os="", stdout="", returncode=1):
    """Apply the only approved policy: compatible repository, then offline."""
    if not isinstance(authority, dict) or not isinstance(requirement, dict) or not isinstance(target, str):
        raise ValueError("ARTIFACT_SOURCE_AUTHORITY_INVALID")
    if authority.get("apiVersion") == "platform.installer/artifact-source-authority/v1alpha2":
        return resolve_image_source(authority, requirement, target, target_os, stdout, returncode)
    source_requirement = authority.get("requirement")
    if (authority.get("apiVersion") != "platform.installer/artifact-source-authority/v1alpha1" or
            authority.get("kind") != "ArtifactSourceAuthority" or
            authority.get("sourcePolicy") != "REPOSITORY_THEN_OFFLINE" or
            not isinstance(source_requirement, dict) or
            source_requirement.get("requirementId") != requirement.get("id") or
            source_requirement.get("name") != requirement.get("name")):
        raise ValueError("ARTIFACT_SOURCE_AUTHORITY_INVALID")
    repository = False
    if target_os == source_requirement.get("os") and returncode == 0 and isinstance(stdout, str):
        for line in stdout.splitlines():
            parts = line.split("\t")
            if len(parts) == 3 and parts[0] == source_requirement.get("name") and parts[2] == source_requirement.get("architecture") and _version_matches(source_requirement.get("version", ""), parts[1]):
                repository = True
                break
    result = {
        "apiVersion": "platform.installer/artifact-source/v1alpha1",
        "kind": "ResolvedArtifactSource",
        "requirement": {"id": requirement["id"], "name": requirement["name"], "version": source_requirement.get("version", ""), "os": source_requirement.get("os", ""), "architecture": source_requirement.get("architecture", "")},
        "targetNode": target,
        "source": "REPOSITORY" if repository else "BLOCKED",
        "version": source_requirement.get("version", ""),
        "reason": "REPOSITORY_COMPATIBLE" if repository else "BUNDLE_MISSING_OR_INCOMPATIBLE",
    }
    if repository:
        return result
    offline = authority.get("offlineBundle")
    if isinstance(offline, dict) and set(offline) == {"kind", "bundleDigest", "ref", "sha256", "size", "type"} and offline.get("kind") == "OFFLINE_BUNDLE":
        result.update({"source": "OFFLINE_BUNDLE", "reason": "BUNDLE_COMPATIBLE", "artifactRef": source_requirement.get("requirementId"), "artifacts": [{"ref": offline["ref"], "sha256": offline["sha256"], "size": offline["size"], "type": offline["type"]}]})
    return result


def resolve_image_source(authority, requirement, target, platform, stdout, returncode):
    expected = authority.get("requirement", {})
    if (authority.get("kind") != "ArtifactSourceAuthority" or authority.get("sourcePolicy") != "REPOSITORY_THEN_OFFLINE" or
            expected != requirement or expected.get("artifactType") != "container-image"):
        raise ValueError("ARTIFACT_SOURCE_AUTHORITY_INVALID")
    result = {"apiVersion": "platform.installer/artifact-source/v1alpha2", "kind": "ResolvedArtifactSource",
              "requirement": copy.deepcopy(expected), "targetNode": target, "source": "BLOCKED", "reason": "IMAGE_SOURCE_UNAVAILABLE"}
    if platform != expected["platform"]:
        result["reason"] = "IMAGE_PLATFORM_INCOMPATIBLE"
        return result
    registry = authority["repository"]
    if registry.get("reference"):
        if returncode not in (0, 2):
            result["reason"] = "IMAGE_REGISTRY_PROBE_FAILED"
            return result
        if returncode == 0:
            try:
                manifest = json.loads(stdout)
            except (ValueError, TypeError):
                result["reason"] = "IMAGE_REGISTRY_PROBE_INVALID"
                return result
            if manifest.get("config", {}).get("digest") == expected["imageId"]:
                result.update(source="REPOSITORY", reason="REPOSITORY_COMPATIBLE")
                return result
    if authority.get("offlineBundle"):
        result.update(source="OFFLINE_BUNDLE", reason="BUNDLE_COMPATIBLE", artifacts=[copy.deepcopy(authority["offlineBundle"])])
    return result


class FilterModule(object):
    def filters(self):
        return {"platform_resolve_artifact_source": resolve_artifact_source}

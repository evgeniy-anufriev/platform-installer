"""Generate a derived service catalog from an explicit set of manifests."""

import copy
import hashlib
import json
import os
from pathlib import Path
import sys

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "collections"))
from ansible_collections.platform.core.plugins.module_utils.schema_validation import SchemaValidator


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value):
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_yaml(path):
    with Path(path).open("r", encoding="utf-8") as stream:
        value = yaml.safe_load(stream)
    if not isinstance(value, dict):
        raise ValueError("%s must contain a YAML object" % path)
    return value


def relocate_manifest_references(manifest, source, output):
    def reference(value):
        if not isinstance(value, str) or "://" in value or value.startswith("/"):
            return value
        target = (source.parent / value).resolve()
        return Path(os.path.relpath(target, output.parent)).as_posix()

    relocated = copy.deepcopy(manifest)
    schema = relocated.get("configurationSchema", {})
    if isinstance(schema, dict) and "$ref" in schema:
        schema["$ref"] = reference(schema["$ref"])
    if "compatibilityRef" in relocated:
        relocated["compatibilityRef"] = reference(relocated["compatibilityRef"])
    for mode in relocated.get("modes", {}).values():
        if isinstance(mode, dict) and "configurationSchemaRef" in mode:
            mode["configurationSchemaRef"] = reference(mode["configurationSchemaRef"])
    return relocated


def expand_artifact_references(manifest, source, repository):
    """Compile authored references into the established expanded runtime DTO."""
    version = manifest.get("apiVersion")
    if version != "platform.installer/service-manifest/v1alpha2":
        raise ValueError("unsupported service manifest version")
    contracts = repository / "contracts"
    validator = SchemaValidator(contracts)
    if validator.validate(manifest, contracts / "service-manifest/v1alpha2/schema.json"):
        raise ValueError("invalid referenced service manifest")
    compiled = copy.deepcopy(manifest)
    compiled["apiVersion"] = "platform.installer/service-manifest/v1alpha1"
    references = manifest.get("artifacts", [])
    metadata = (load_yaml(source.parent / "artifacts.yml") if references else
                dict(apiVersion="platform.installer/artifacts/v1alpha1", service=manifest["metadata"]["id"], artifacts=[]))
    if (validator.validate(metadata, contracts / "artifacts/v1alpha1/schema.json") or
            metadata.get("service") != manifest["metadata"]["id"]):
        raise ValueError("invalid service artifact metadata")
    by_id = {}
    for artifact in metadata["artifacts"]:
        if artifact["id"] in by_id:
            raise ValueError("duplicate service artifact metadata ID")
        by_id[artifact["id"]] = artifact
    if "artifacts" in manifest:
        compiled["artifacts"] = []
    seen = set()
    for reference in references:
        key = reference["artifactRef"]
        if key not in by_id or key in seen:
            raise ValueError("missing or duplicate service artifact reference")
        seen.add(key)
        metadata_entry = by_id[key]
        artifact = {key: metadata_entry[key] for key in ("id", "name", "version", "os", "architecture")}
        artifact["digest"] = "sha256:" + metadata_entry["sha256"].removeprefix("sha256:")
        artifact.update({key: copy.deepcopy(value) for key, value in reference.items() if key != "artifactRef"})
        compiled["artifacts"].append(artifact)
    if validator.validate(compiled, contracts / "service-manifest/v1alpha1/schema.json"):
        raise ValueError("invalid compiled service manifest")
    return compiled


def build_catalog(repository, sources, output):
    definitions = {}
    for service_type, source in sources:
        manifest = load_yaml(source)
        if manifest.get("metadata", {}).get("id") != service_type:
            raise ValueError("%s metadata.id must be %s" % (source, service_type))
        if service_type in definitions:
            raise ValueError("duplicate catalog service: %s" % service_type)
        definition = relocate_manifest_references(expand_artifact_references(manifest, source, repository), source, output)
        definition["x-definitionDigest"] = digest(definition)
        definition["x-sourceManifest"] = source.relative_to(repository).as_posix()
        definitions[service_type] = definition
    unsigned = {
        "apiVersion": "platform.installer/catalog/v1alpha1",
        "kind": "ServiceCatalog",
        "definitions": definitions,
    }
    return dict(unsigned, digest=digest(unsigned))

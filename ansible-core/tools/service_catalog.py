"""Generate a derived service catalog from an explicit set of manifests."""

import copy
import hashlib
import json
import os
from pathlib import Path

import yaml


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


def build_catalog(repository, sources, output):
    definitions = {}
    for service_type, source in sources:
        manifest = load_yaml(source)
        if manifest.get("metadata", {}).get("id") != service_type:
            raise ValueError("%s metadata.id must be %s" % (source, service_type))
        if service_type in definitions:
            raise ValueError("duplicate catalog service: %s" % service_type)
        definition = relocate_manifest_references(manifest, source, output)
        definition["x-definitionDigest"] = digest(definition)
        definition["x-sourceManifest"] = source.relative_to(repository).as_posix()
        definitions[service_type] = definition
    unsigned = {
        "apiVersion": "platform.installer/catalog/v1alpha1",
        "kind": "ServiceCatalog",
        "definitions": definitions,
    }
    return dict(unsigned, digest=digest(unsigned))

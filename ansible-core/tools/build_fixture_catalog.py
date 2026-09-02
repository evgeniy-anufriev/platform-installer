#!/usr/bin/env python3
"""Build/check the CORE-01 derived fixture catalog using offline PyYAML."""

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys

import yaml


REPOSITORY = Path(__file__).resolve().parents[2]
OUTPUT = REPOSITORY / "examples" / "catalog" / "service-catalog.yml"
SOURCES = (
    ("kafka", REPOSITORY / "services" / "kafka" / "service.yml"),
    ("postgresql", REPOSITORY / "services" / "postgresql" / "service.yml"),
    ("keepalived", REPOSITORY / "services" / "keepalived" / "service.yml"),
    ("etcd", REPOSITORY / "examples" / "catalog" / "manifests" / "etcd.yml"),
)
PROJECT_MANIFEST_GLOBS = (
    "examples/valid/*/project.yml",
    "examples/invalid/*/project.yml",
    "ansible-core/examples/*/project.yml",
)


def canonical_bytes(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def digest(value):
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_yaml(path):
    with path.open("r", encoding="utf-8") as stream:
        value = yaml.safe_load(stream)
    if not isinstance(value, dict):
        raise ValueError("%s must contain a YAML object" % path)
    return value


def _catalog_relative_reference(source, reference):
    if not isinstance(reference, str) or "://" in reference or reference.startswith("/"):
        return reference
    target = (source.parent / reference).resolve()
    return Path(os.path.relpath(target, OUTPUT.parent)).as_posix()


def _relocate_manifest_references(manifest, source):
    """Keep relative manifest references valid after embedding in the catalog."""
    relocated = copy.deepcopy(manifest)
    configuration_schema = relocated.get("configurationSchema", {})
    if isinstance(configuration_schema, dict) and "$ref" in configuration_schema:
        configuration_schema["$ref"] = _catalog_relative_reference(
            source, configuration_schema["$ref"]
        )
    if "compatibilityRef" in relocated:
        relocated["compatibilityRef"] = _catalog_relative_reference(
            source, relocated["compatibilityRef"]
        )
    for mode in relocated.get("modes", {}).values():
        if isinstance(mode, dict) and "configurationSchemaRef" in mode:
            mode["configurationSchemaRef"] = _catalog_relative_reference(
                source, mode["configurationSchemaRef"]
            )
    return relocated


def build_catalog():
    definitions = {}
    for service_type, source in SOURCES:
        manifest = load_yaml(source)
        metadata = manifest.get("metadata", {})
        if metadata.get("id") != service_type:
            raise ValueError("%s metadata.id must be %s" % (source, service_type))
        definition = _relocate_manifest_references(manifest, source)
        definition["x-definitionDigest"] = digest(definition)
        definition["x-sourceManifest"] = source.relative_to(REPOSITORY).as_posix()
        definitions[service_type] = definition

    unsigned = {
        "apiVersion": "platform.installer/catalog/v1alpha1",
        "kind": "ServiceCatalog",
        "definitions": definitions,
    }
    return {
        "apiVersion": unsigned["apiVersion"],
        "kind": unsigned["kind"],
        "digest": digest(unsigned),
        "definitions": definitions,
    }


def dump_yaml(value):
    return yaml.safe_dump(
        value,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=100,
    )


def project_manifests():
    manifests = []
    for pattern in PROJECT_MANIFEST_GLOBS:
        manifests.extend(REPOSITORY.glob(pattern))
    return sorted(set(manifests))


def lock_values(catalog, service_type):
    definition = catalog["definitions"][service_type]
    return {
        "definitionVersion": definition["metadata"]["version"],
        "digest": definition["x-definitionDigest"],
    }


def synchronize_project_locks(catalog):
    for path in project_manifests():
        manifest = load_yaml(path)
        lock = manifest.get("catalogLock", {})
        lock["digest"] = catalog["digest"]
        for service_type in list(lock.get("services", {})):
            if service_type not in catalog["definitions"]:
                raise ValueError("%s locks unknown service %s" % (path, service_type))
            lock["services"][service_type] = lock_values(catalog, service_type)
        path.write_text(dump_yaml(manifest), encoding="utf-8", newline="\n")


def verify_project_locks(catalog):
    errors = []
    for path in project_manifests():
        manifest = load_yaml(path)
        lock = manifest.get("catalogLock", {})
        if lock.get("digest") != catalog["digest"]:
            errors.append("%s has a stale catalog digest" % path)
        for service_type, service_lock in lock.get("services", {}).items():
            if service_type not in catalog["definitions"]:
                errors.append("%s locks unknown service %s" % (path, service_type))
            elif service_lock != lock_values(catalog, service_type):
                errors.append("%s has a stale %s lock" % (path, service_type))
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when the committed catalog differs semantically from generated output",
    )
    args = parser.parse_args()
    expected = build_catalog()

    if args.check:
        actual = load_yaml(OUTPUT)
        if actual != expected:
            print("fixture catalog is stale; run %s" % Path(__file__).name, file=sys.stderr)
            return 1
        lock_errors = verify_project_locks(expected)
        if lock_errors:
            print("\n".join(lock_errors), file=sys.stderr)
            return 1
        print("fixture catalog is reproducible: %s" % expected["digest"])
        return 0

    temporary = OUTPUT.with_suffix(".yml.tmp")
    temporary.write_text(dump_yaml(expected), encoding="utf-8", newline="\n")
    temporary.replace(OUTPUT)
    synchronize_project_locks(expected)
    print("wrote %s (%s)" % (OUTPUT, expected["digest"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

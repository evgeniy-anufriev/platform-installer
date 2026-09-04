#!/usr/bin/env python3
"""Build a deterministic, versioned offline Execution Node runtime directory.

The builder never downloads.  Missing runtime packages can be acquired by the
explicit Go acquisition operation from a selected node's configured repository,
then supplied here as a local input.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

import yaml


REPOSITORY = Path(__file__).resolve().parents[2]
SOURCE_ROOTS = (
    ("ansible-core", REPOSITORY / "ansible-core"),
    ("services", REPOSITORY / "services"),
    ("contracts", REPOSITORY / "contracts"),
    ("catalog", REPOSITORY / "examples" / "catalog"),
)
EXCLUDED_PARTS = {"tests", "__pycache__", ".pytest_cache", ".git", "docs"}


def digest_bytes(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()


def digest_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def copy_tree(source, destination):
    if not source.is_dir():
        raise ValueError("required source is missing: %s" % source)
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        target = destination / relative
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.is_symlink():
            raise ValueError("symlink source is not allowed: %s" % path)
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            if path.name in {"README.md", "README.rst"}:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        else:
            raise ValueError("unsupported source entry: %s" % path)


def validate_catalog_layout(root):
    catalog_path = root / "catalog" / "service-catalog.yml"
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    definitions = catalog.get("definitions", {}) if isinstance(catalog, dict) else {}
    for service_type, definition in definitions.items():
        references = []
        schema = definition.get("configurationSchema", {}) if isinstance(definition, dict) else {}
        if isinstance(schema, dict) and isinstance(schema.get("$ref"), str):
            references.append(schema["$ref"])
        if isinstance(definition, dict) and isinstance(definition.get("compatibilityRef"), str):
            references.append(definition["compatibilityRef"])
        for reference in references:
            if reference.startswith("../../services/"):
                candidate = root / reference[6:]
            elif reference.startswith("../fixtures/"):
                candidate = root / "catalog" / reference[3:]
            else:
                candidate = (catalog_path.parent / reference).resolve()
            if root not in candidate.resolve().parents and candidate.resolve() != root:
                raise ValueError("catalog reference escapes bundle: %s.%s" % (service_type, reference))
            if not candidate.is_file():
                raise ValueError("catalog reference is missing from bundle: %s" % reference)


def components(root):
    result = []
    files = [path for path in root.rglob("*") if path.is_file()]
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        if not path.is_file() or path.name == "manifest.yaml":
            continue
        if path.is_symlink():
            raise ValueError("bundle symlink is not allowed: %s" % path)
        result.append({
            "path": path.relative_to(root).as_posix(),
            "sha256": digest_file(path),
            "size": path.stat().st_size,
        })
    return result


def catalog_digest():
    catalog = REPOSITORY / "examples" / "catalog" / "service-catalog.yml"
    value = yaml.safe_load(catalog.read_text(encoding="utf-8"))
    digest = value.get("digest") if isinstance(value, dict) else None
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        raise ValueError("published catalog digest is missing")
    return digest


def schema_digest():
    entries = []
    for path in sorted((REPOSITORY / "contracts").rglob("*.json")):
        entries.append((path.relative_to(REPOSITORY).as_posix(), digest_file(path)))
    return digest_bytes(json.dumps(entries, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def runtime_platforms(runtime_root):
    platforms = []
    package_root = runtime_root / "packages"
    python_root = runtime_root / "python"
    if not package_root.is_dir() or not python_root.is_dir():
        raise ValueError("runtime input must contain packages/ and python/")
    for os_root in sorted(package_root.iterdir()):
        for version_root in sorted(os_root.iterdir()):
            for architecture_root in sorted(version_root.iterdir()):
                if not architecture_root.is_dir() or not any(architecture_root.iterdir()):
                    continue
                platforms.append({
                    "os": os_root.name,
                    "version": version_root.name,
                    "architecture": architecture_root.name,
                })
    if not platforms:
        raise ValueError("runtime input contains no package platform")
    return platforms


def build(output, runtime, bundle_version, core_version):
    output = output.resolve()
    if output.exists():
        raise ValueError("output already exists: %s" % output)
    temporary = output.with_name(output.name + ".tmp")
    if temporary.exists():
        raise ValueError("temporary output already exists: %s" % temporary)
    try:
        temporary.mkdir(parents=True)
        for destination, source in SOURCE_ROOTS:
            copy_tree(source, temporary / destination)
        copy_tree(runtime, temporary / "runtime")
        validate_catalog_layout(temporary)
        manifest = {
            "apiVersion": "platform.installer/execution-bundle/v1alpha1",
            "kind": "ExecutionRuntimeBundle",
            "bundleVersion": bundle_version,
            "bootstrapProtocol": "v1alpha1",
            "coreVersion": core_version,
            "catalogDigest": catalog_digest(),
            "schemaDigest": schema_digest(),
            "platforms": runtime_platforms(runtime),
            "components": components(temporary),
        }
        (temporary / "manifest.yaml").write_text(
            yaml.safe_dump(manifest, allow_unicode=True, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
            newline="\n",
        )
        temporary.replace(output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime-input", type=Path, required=True)
    parser.add_argument("--bundle-version", required=True)
    parser.add_argument("--core-version", default="0.1.0")
    args = parser.parse_args()
    try:
        build(args.output, args.runtime_input.resolve(), args.bundle_version, args.core_version)
    except ValueError as error:
        print("execution runtime bundle blocked: %s" % error, file=sys.stderr)
        return 2
    print("execution runtime bundle created: %s" % args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

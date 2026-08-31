#!/usr/bin/env python3
"""Generate/check tracked configuration schemas from service manifests."""

import argparse
import json
from pathlib import Path
import sys

import yaml

REPOSITORY = Path(__file__).resolve().parents[2]
MODULE_UTILS = REPOSITORY / "ansible-core" / "collections" / "ansible_collections" / "platform" / "core" / "plugins" / "module_utils"
sys.path.insert(0, str(MODULE_UTILS))
from service_configuration_contract import generated_schema, validate_defaults


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def service_manifests():
    return sorted((REPOSITORY / "services").glob("*/service.yml"))


def output_path(manifest_path):
    return manifest_path.with_name("configuration.schema.json")


def role_defaults_path(manifest_path, manifest):
    entrypoints = manifest.get("roleEntrypoints", {})
    apply_entrypoint = entrypoints.get("apply", {}) if isinstance(entrypoints, dict) else {}
    fqcn = apply_entrypoint.get("fqcn", "") if isinstance(apply_entrypoint, dict) else ""
    parts = fqcn.split(".")
    if len(parts) != 3:
        return None
    return manifest_path.parent / "ansible_collections" / parts[0] / parts[1] / "roles" / parts[2] / "defaults" / "main.yml"


def is_literal(value):
    return not (isinstance(value, str) and any(marker in value for marker in ("{{", "}}", "{%", "%}", "{#", "#}")))


def build(manifest_path):
    with manifest_path.open("r", encoding="utf-8") as stream:
        manifest = yaml.safe_load(stream)
    if not isinstance(manifest, dict):
        raise ValueError("%s must contain a YAML object" % manifest_path)
    defaults_path = role_defaults_path(manifest_path, manifest)
    if defaults_path is not None and defaults_path.exists():
        with defaults_path.open("r", encoding="utf-8") as stream:
            defaults = yaml.safe_load(stream) or {}
        issues = validate_defaults(manifest, defaults, is_literal)
        if issues:
            raise ValueError("%s: %s" % (issues[0]["path"], issues[0]["message"]))
    return canonical_json(generated_schema(manifest))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail when tracked schemas are stale")
    parser.add_argument("--service", action="append", default=[], help="service id to generate/check; defaults to all services")
    args = parser.parse_args()
    manifests = service_manifests()
    if args.service:
        requested = set(args.service)
        manifests = [path for path in manifests if path.parent.name in requested]
        missing = requested.difference({path.parent.name for path in manifests})
        if missing:
            parser.error("unknown service(s): %s" % ", ".join(sorted(missing)))
    stale = []
    for manifest in manifests:
        expected = build(manifest)
        output = output_path(manifest)
        if args.check:
            actual = output.read_text(encoding="utf-8") if output.exists() else None
            if actual != expected:
                stale.append(output.relative_to(REPOSITORY).as_posix())
        else:
            output.write_text(expected, encoding="utf-8", newline="\n")
    if stale:
        print("generated configuration schemas are stale: %s" % ", ".join(stale), file=sys.stderr)
        return 1
    print("configuration schemas are reproducible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

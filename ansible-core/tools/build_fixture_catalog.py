#!/usr/bin/env python3
"""Build/check the CORE-01 derived fixture catalog using offline PyYAML."""

import argparse
from pathlib import Path
import sys

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from service_catalog import build_catalog as generate_catalog, canonical_bytes, digest, load_yaml


REPOSITORY = Path(__file__).resolve().parents[2]
OUTPUT = REPOSITORY / "examples" / "catalog" / "service-catalog.yml"
SOURCES = (
    ("clickhouse", REPOSITORY / "services" / "clickhouse" / "service.yml"),
    ("docker", REPOSITORY / "services" / "docker" / "service.yml"),
    ("kafka", REPOSITORY / "services" / "kafka" / "service.yml"),
    ("postgresql", REPOSITORY / "services" / "postgresql" / "service.yml"),
    ("redis", REPOSITORY / "services" / "redis" / "service.yml"),
    ("vault", REPOSITORY / "services" / "vault" / "service.yml"),
    ("keepalived", REPOSITORY / "services" / "keepalived" / "service.yml"),
    ("bind", REPOSITORY / "services" / "bind" / "service.yml"),
    ("dns-client", REPOSITORY / "services" / "dns-client" / "service.yml"),
    ("haproxy", REPOSITORY / "services" / "haproxy" / "service.yml"),
    ("etcd", REPOSITORY / "examples" / "catalog" / "manifests" / "etcd.yml"),
)
PROJECT_MANIFEST_GLOBS = (
    "examples/valid/*/project.yml",
    "examples/invalid/*/project.yml",
    "ansible-core/examples/*/project.yml",
)


def build_catalog():
    return generate_catalog(REPOSITORY, SOURCES, OUTPUT)


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

#!/usr/bin/env python3
"""Create a minimal image context from an ordinary checkout and pinned npm archives."""
import argparse
from pathlib import Path
import shutil
import hashlib
import json
import base64

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("project", type=Path)
parser.add_argument("npm_tarballs", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
source = args.project.resolve()
output = args.output.resolve()
if output.exists():
    raise SystemExit("Context destination must be new")
lock = json.loads((source / "frontend/package-lock.json").read_text(encoding="utf-8"))
if lock.get("lockfileVersion") != 3:
    raise SystemExit("Expected npm lockfileVersion 3")
archives = {}
for package_path, entry in lock["packages"].items():
    if not package_path:
        continue
    def allows(field, target):
        values = entry.get(field, [])
        return (not values or target in values or
                (all(value.startswith("!") for value in values) and "!" + target not in values))
    if not all(allows(field, target) for field, target in (("os", "linux"), ("cpu", "x64"), ("libc", "glibc"))):
        if entry.get("optional") is not True:
            raise SystemExit("Required npm package incompatible with Linux x64/glibc: " + package_path)
        continue
    integrity = entry.get("integrity", "")
    if not integrity.startswith("sha512-"):
        raise SystemExit("Expected pinned npm SHA-512: " + package_path)
    expected = base64.b64decode(integrity[7:], validate=True)
    if len(expected) != 64:
        raise SystemExit("Invalid npm SHA-512")
    archives["npm-tarballs/" + expected.hex() + ".tgz"] = expected
if not archives:
    raise SystemExit("Empty npm closure")
tarballs = args.npm_tarballs.resolve()
for name, expected in archives.items():
    archive = tarballs / Path(name).name
    if hashlib.sha512(archive.read_bytes()).digest() != expected:
        raise SystemExit("npm archive integrity mismatch: " + archive.name)
output.mkdir(parents=True)
shutil.copytree(source / "third_party/wails", output / "wails",
                ignore=shutil.ignore_patterns(".git", ".runtime", "node_modules", "__pycache__"))
(output / "frontend").mkdir()
for name in ("package.json", "package-lock.json"):
    shutil.copyfile(source / "frontend" / name, output / "frontend" / name)
(output / "npm-tarballs").mkdir()
for name in archives:
    shutil.copyfile(tarballs / Path(name).name, output / name)
for name in ("Dockerfile", "build-target.sh"):
    shutil.copyfile(Path(__file__).parent / name, output / name)
print("Docker context: " + str(output))

#!/usr/bin/env python3
"""Export, restore, and build Platform Installer from one UTF-8 text file."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile


FORMAT = "platform-installer-source-text/v1"
EXCLUDED_DIRS = {
    ".git",
    ".runtime",
    "__pycache__",
    "build",
    "bundle",
    "dist",
    "docs",
    "node_modules",
    "test",
    "tests",
    "testdata",
    "vendor",
    "_vendor",
    "__tests__",
}
EXCLUDED_SUFFIXES = ("_test.go", ".test.js", ".test.jsx", ".test.ts", ".test.tsx", ".spec.js", ".spec.jsx", ".spec.ts", ".spec.tsx")
EXCLUDED_PREFIXES = ("test_",)
EXCLUDED_EXTENSIONS = {".md", ".rst", ".adoc", ".pyc", ".pyo"}
SECRET_EXTENSIONS = {".key", ".pem", ".p12", ".pfx", ".vault-password"}
WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def is_excluded(path: str) -> bool:
    candidate = PurePosixPath(path)
    parts = candidate.parts
    lower_parts = {part.lower() for part in parts}
    name = candidate.name.lower()
    suffix = candidate.suffix.lower()
    return (
        bool(lower_parts & EXCLUDED_DIRS)
        or suffix in EXCLUDED_EXTENSIONS | SECRET_EXTENSIONS
        or name.startswith(EXCLUDED_PREFIXES)
        or name.endswith(EXCLUDED_SUFFIXES)
        or ".test." in name
        or ".spec." in name
        or (len(parts) > 1 and parts[0].lower() == "scripts" and name.startswith("qa-"))
        or name in {"readme", "readme.txt", "license", "license.txt"}
        or name.startswith(".env")
        or name.endswith((".secret", ".secrets"))
    )


def repository_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    paths = [os.fsdecode(item) for item in result.stdout.split(b"\0") if item]
    return sorted(set(paths), key=lambda value: value.casefold())


def export_source(root: Path, output: Path) -> int:
    output_resolved = output.resolve()
    entries = []
    skipped_binary = 0
    for relative in repository_files(root):
        normalized = relative.replace("\\", "/")
        if is_excluded(normalized):
            continue
        source = root / Path(*PurePosixPath(normalized).parts)
        if source.resolve() == output_resolved or not source.is_file() or source.is_symlink():
            continue
        content = source.read_bytes()
        if b"\0" in content:
            skipped_binary += 1
            continue
        try:
            content.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            skipped_binary += 1
            continue
        entries.append(
            {
                "path": normalized,
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "contentBase64": base64.b64encode(content).decode("ascii"),
            }
        )

    document = {"format": FORMAT, "files": entries}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    total = sum(entry["size"] for entry in entries)
    print(f"Exported {len(entries)} text files ({total:,} source bytes) to {output}")
    if skipped_binary:
        print(f"Skipped {skipped_binary} non-UTF-8 or binary files")
    return 0


def safe_relative_path(value: object) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or "\0" in value:
        raise ValueError("invalid file path in source file")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"unsafe file path: {value!r}")
    if re.match(r"^[A-Za-z]:", value):
        raise ValueError(f"drive-qualified path is not allowed: {value!r}")
    for part in path.parts:
        if part.endswith((".", " ")) or part.split(".", 1)[0].upper() in WINDOWS_RESERVED:
            raise ValueError(f"Windows-unsafe path component: {part!r}")
    return path


def restore_source(source_file: Path, destination: Path) -> int:
    document = json.loads(source_file.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("format") != FORMAT or not isinstance(document.get("files"), list):
        raise ValueError("unsupported source text format")

    destination = destination.resolve()
    if destination.exists():
        raise ValueError(f"destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.restore-", dir=destination.parent))
    seen: set[str] = set()
    try:
        for entry in document["files"]:
            if not isinstance(entry, dict):
                raise ValueError("invalid file entry")
            relative = safe_relative_path(entry.get("path"))
            collision_key = relative.as_posix().casefold()
            if collision_key in seen:
                raise ValueError(f"duplicate or case-colliding path: {relative}")
            seen.add(collision_key)
            encoded = entry.get("contentBase64")
            if not isinstance(encoded, str):
                raise ValueError(f"missing file content: {relative}")
            try:
                content = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as error:
                raise ValueError(f"invalid Base64 content: {relative}") from error
            expected_size = entry.get("size")
            expected_hash = entry.get("sha256")
            if isinstance(expected_size, bool) or not isinstance(expected_size, int) or expected_size != len(content):
                raise ValueError(f"size mismatch: {relative}")
            if not isinstance(expected_hash, str) or hashlib.sha256(content).hexdigest() != expected_hash:
                raise ValueError(f"SHA-256 mismatch: {relative}")
            target = staging.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)

        staging.rename(destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    print(f"Restored {len(seen)} files to {destination}")
    return 0


def build_application(root: Path) -> int:
    root = root.resolve()
    frontend = root / "frontend"
    if not (frontend / "package-lock.json").is_file():
        raise ValueError(f"frontend package lock is missing: {frontend / 'package-lock.json'}")

    npm = "npm.cmd" if os.name == "nt" else "npm"
    commands = [
        ([npm, "ci"], frontend),
        ([npm, "run", "build"], frontend),
        (["wails", "build", "-nopackage", "-clean"], root),
    ]
    for command, cwd in commands:
        print("+ " + " ".join(command), flush=True)
        subprocess.run(command, cwd=cwd, check=True)
    print(f"Build complete: {root / 'build' / 'bin'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export", help="pack source files into one UTF-8 text file")
    export_parser.add_argument("--root", type=Path, default=Path.cwd(), help="Git repository root (default: current directory)")
    export_parser.add_argument("--output", type=Path, required=True, help="output .txt file")

    restore_parser = subparsers.add_parser("restore", help="verify and restore a source text file")
    restore_parser.add_argument("--input", type=Path, required=True, help="source text file")
    restore_parser.add_argument("--destination", type=Path, required=True, help="new destination directory; it must not exist")

    build_parser = subparsers.add_parser("build", help="build the Wails application from a restored source tree")
    build_parser.add_argument("--root", type=Path, default=Path.cwd(), help="restored repository root (default: current directory)")

    args = parser.parse_args()
    try:
        if args.command == "export":
            return export_source(args.root.resolve(), args.output.resolve())
        if args.command == "restore":
            return restore_source(args.input.resolve(), args.destination)
        return build_application(args.root)
    except (OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"source-text: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

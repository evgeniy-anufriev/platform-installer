#!/usr/bin/env python3
"""Acquire a lockfile-complete npm payload explicitly; install it offline."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import platform
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

import portable_source as portable

MANIFEST = "npm-manifest.json"
PREFIX = "npm-source"
SCRIPT = "npm_offline.py"
KIND = "platform-installer-npm-offline-v1"
LINUX_PROFILE = "linux-x64-glibc"
FORMAT = "platform-installer-npm-source-v1"


def read_manifest(source):
    manifest = json.loads((source / MANIFEST).read_text(encoding="utf-8"))
    portable.require(manifest.get("format") == FORMAT and manifest.get("maxPartBytes") == portable.LIMIT
                     and type(manifest.get("files")) is int and manifest["files"] > 0
                     and isinstance(manifest.get("parts"), list) and bool(manifest["parts"]),
                     "Invalid npm manifest")
    for index, part in enumerate(manifest["parts"], 1):
        portable.require(part["name"] == "npm-source-{:04d}.txt".format(index), "Invalid npm part order")
    return manifest


def read_part(source, part):
    data = (source / part["name"]).read_bytes()
    portable.require(len(data) <= portable.LIMIT, "npm part exceeds transport limit")
    data = data.replace(b"\r\n", b"\n")
    portable.require(b"\r" not in data and len(data) == part["bytes"]
                     and portable.digest(data) == part["sha256"],
                     "npm part checksum/size mismatch: " + part["name"])
    return data


def read_payload(source):
    manifest = read_manifest(source)
    files, seen, blocks = [], set(), []
    current, next_index, total = None, 0, 0
    for part in manifest["parts"]:
        for line in read_part(source, part).splitlines(keepends=True):
            portable.require(line.startswith(b"@@NPM ") and line.endswith(b"\n"), "Invalid npm record")
            record = json.loads(line[6:].decode("ascii"))
            portable.require(isinstance(record.get("path"), str) and
                             re.fullmatch(r"npm-tarballs/[a-f0-9]{128}\.tgz", record["path"]) and
                             type(record.get("index")) is int and type(record.get("count")) is int and
                             record["count"] > 0 and type(record.get("size")) is int and record["size"] > 0 and
                             isinstance(record.get("sha256"), str) and re.fullmatch(r"[a-f0-9]{64}", record["sha256"]),
                             "Invalid npm file metadata")
            if record["index"] == 0:
                portable.require(current is None and record["path"] not in seen, "Duplicate/incomplete npm archive")
                current, blocks, next_index = record, [], 0
                seen.add(record["path"])
            portable.require(current is not None and record["index"] == next_index and next_index < record["count"]
                             and all(record[key] == current[key] for key in ("path", "count", "size", "sha256")),
                             "Invalid npm block order")
            content = base64.b64decode(record["data"], validate=True)
            portable.require(0 < len(content) <= portable.BLOCK and
                             base64.b64encode(content).decode("ascii") == record["data"], "Invalid npm Base64")
            blocks.append(content)
            next_index += 1
            if next_index == current["count"]:
                content = b"".join(blocks)
                portable.require(len(content) == current["size"] and portable.digest(content) == current["sha256"],
                                 "npm archive checksum/size mismatch")
                files.append((current, content))
                total += len(content)
                current, blocks = None, []
    portable.require(current is None and len(files) == manifest["files"] and total == manifest["sourceBytes"],
                     "Incomplete npm payload")
    return manifest, files


def pack_payload(files, output, package, lock, profile):
    """Write only npm-* files; ordinary source parts are never read or rewritten."""
    portable.require(not output.exists(), "Output already exists: " + str(output))
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".npm-pack-", dir=str(output.parent)))
    manifest = dict(format=FORMAT, maxPartBytes=portable.LIMIT, files=len(files), sourceBytes=0,
                    npmKind=KIND, npmLockSHA256=json_digest(lock), npmPackageSHA256=json_digest(package),
                    npmPlatform=profile, parts=[])
    lines, length = [], 0

    def flush():
        nonlocal lines, length
        if not lines:
            return
        data = b"".join(lines)
        name = "npm-source-{:04d}.txt".format(len(manifest["parts"]) + 1)
        (staging / name).write_bytes(data)
        manifest["parts"].append(dict(name=name, bytes=len(data), sha256=portable.digest(data)))
        lines, length = [], 0

    try:
        for name, _, path in files:
            data = path.read_bytes()
            portable.require(bool(data), "Empty npm archive")
            manifest["sourceBytes"] += len(data)
            checksum = portable.digest(data)
            count = (len(data) + portable.BLOCK - 1) // portable.BLOCK
            for index in range(count):
                record = dict(path=name, size=len(data), sha256=checksum, index=index, count=count,
                              data=base64.b64encode(data[index * portable.BLOCK:(index + 1) * portable.BLOCK]).decode("ascii"))
                line = b"@@NPM " + json.dumps(record, separators=(",", ":")).encode("ascii") + b"\n"
                transport_length = len(line) + 1  # Allow LF->CRLF without exceeding 5 MB.
                portable.require(transport_length <= portable.LIMIT, "npm record exceeds part limit")
                if length + transport_length > portable.LIMIT:
                    flush()
                lines.append(line)
                length += transport_length
        flush()
        (staging / MANIFEST).write_bytes((json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
        shutil.copyfile(Path(__file__), staging / SCRIPT)
        shutil.copyfile(Path(portable.__file__), staging / "portable_source.py")
        staging.rename(output)
    except Exception:
        shutil.rmtree(staging)
        raise
    print("Packed {} npm archives into {} separate npm-source parts".format(len(files), len(manifest["parts"])))


def json_digest(value):
    return portable.digest(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode())


def project_inputs(root):
    frontend = root / "frontend"
    package = json.loads((frontend / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((frontend / "package-lock.json").read_text(encoding="utf-8"))
    portable.require(lock.get("lockfileVersion") == 3, "Expected npm lockfileVersion 3")
    return package, lock


def archives(lock, profile=LINUX_PROFILE):
    portable.require(profile in {LINUX_PROFILE, "all"}, "Unsupported npm platform profile")
    result = {}
    for path, entry in lock["packages"].items():
        if not path:
            continue
        if profile == LINUX_PROFILE:
            def allows(field, target):
                values = entry.get(field, [])
                return (not values or target in values or
                        (all(value.startswith("!") for value in values) and "!" + target not in values))
            compatible = all(allows(field, target) for field, target in
                             (("os", "linux"), ("cpu", "x64"), ("libc", "glibc")))
            if not compatible:
                portable.require(entry.get("optional") is True,
                                 "Required npm package incompatible with Linux x64/glibc: " + path)
                continue
        integrity = entry.get("integrity", "")
        portable.require(integrity.startswith("sha512-") and " " not in integrity,
                         "Missing/unsupported npm integrity: " + path)
        checksum = base64.b64decode(integrity[7:], validate=True)
        portable.require(len(checksum) == 64, "Invalid npm SHA-512: " + path)
        url = entry.get("resolved", "")
        parsed = urllib.parse.urlparse(url)
        portable.require(parsed.scheme == "https" and parsed.hostname == "registry.npmjs.org"
                         and not parsed.username and not parsed.password,
                         "Expected pinned HTTPS npm registry tarball: " + path)
        name = "npm-tarballs/" + checksum.hex() + ".tgz"
        result.setdefault(name, (url, checksum))
    portable.require(bool(result), "Empty npm lockfile")
    return result


def verify_package(source, root):
    package, lock = project_inputs(root)
    manifest, records = read_payload(source)
    portable.require(manifest.get("npmKind") == KIND and
                     manifest.get("npmLockSHA256") == json_digest(lock) and
                     manifest.get("npmPackageSHA256") == json_digest(package),
                     "Offline npm payload does not match package.json/package-lock.json; acquire a new payload")
    expected = archives(lock, manifest.get("npmPlatform"))
    portable.require({record["path"] for record, _ in records} == set(expected),
                     "Incomplete/extra npm tarballs")
    for record, content in records:
        portable.require(hashlib.sha512(content).digest() == expected[record["path"]][1],
                         "npm lockfile integrity mismatch: " + record["path"])
    return manifest, records


def acquire(root, output, profile=LINUX_PROFILE):
    """The only network-enabled operation; never called by ci or build."""
    portable.require(not output.exists(), "Output already exists: " + str(output))
    package, lock = project_inputs(root)
    wanted = archives(lock, profile)
    with tempfile.TemporaryDirectory(prefix="npm-acquire-") as temporary:
        payload = Path(temporary)
        (payload / "npm-tarballs").mkdir()

        def download(item):
            name, (url, checksum) = item
            request = urllib.request.Request(url, headers={"User-Agent": "platform-installer-offline-acquisition"})
            with urllib.request.urlopen(request, timeout=120) as response:
                portable.require(response.url.startswith("https://registry.npmjs.org/"), "Unexpected npm redirect")
                content = response.read()
            portable.require(hashlib.sha512(content).digest() == checksum, "Downloaded npm integrity mismatch: " + name)
            (payload / name).write_bytes(content)

        with ThreadPoolExecutor(max_workers=6) as executor:
            list(executor.map(download, sorted(wanted.items())))
        files = [(name, 0o644, payload / name) for name in sorted(wanted)]
        pack_payload(files, output, package, lock, profile)
    verify_package(output, root)
    print("PASS: acquired {} pinned npm archives ({})".format(len(wanted), profile))


def ci(source, root):
    manifest, records = verify_package(source, root)  # Fail before npm or filesystem writes.
    if manifest["npmPlatform"] == LINUX_PROFILE:
        portable.require(sys.platform.startswith("linux") and platform.machine() in {"x86_64", "AMD64"}
                         and platform.libc_ver()[0] == "glibc",
                         "This npm payload requires a Linux x86-64/glibc build host")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    portable.require(npm is not None, "Offline npm ci requires npm in PATH")
    package, _ = project_inputs(root)
    actual = subprocess.check_output([npm, "--version"], text=True).strip()
    portable.require(package.get("packageManager") == "npm@" + actual,
                     "Expected " + package.get("packageManager", "pinned npm") + "; found npm@" + actual)
    runtime = root / ".runtime"
    runtime.mkdir(exist_ok=True)
    # Always start with a private empty cache; never rely on the operator's cache.
    with tempfile.TemporaryDirectory(prefix="npm-offline-", dir=str(runtime)) as temporary:
        workspace = Path(temporary)
        tarballs = workspace / "tarballs"
        tarballs.mkdir()
        paths = []
        for index, (_, content) in enumerate(records):
            path = tarballs / (str(index) + ".tgz")
            path.write_bytes(content)
            paths.append(str(path))
        cache = workspace / "cache"
        environment = dict(os.environ, npm_config_offline="true", npm_config_audit="false",
                           npm_config_fund="false", npm_config_update_notifier="false",
                           npm_config_cache=str(cache), PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD="1")
        environment["npm_config_userconfig"] = str(workspace / "empty.npmrc")
        (workspace / "empty.npmrc").write_text("", encoding="utf-8")
        common = ["--offline", "--cache", str(cache), "--no-audit", "--no-fund"]
        for start in range(0, len(paths), 25):
            subprocess.run([npm, "cache", "add", *common, *paths[start:start + 25]],
                           cwd=str(root / "frontend"), env=environment, check=True)
        subprocess.run([npm, "ci", *common], cwd=str(root / "frontend"), env=environment, check=True)
    print("PASS: npm ci --offline with an initially empty private cache")


def build(source, root, target, webkit="auto"):
    verify_package(source, root)
    target_linux = target == "linux/amd64"
    tags = portable.linux_build_tags(webkit) if target_linux else []
    environment = dict(os.environ, GOFLAGS="-mod=vendor", GOPROXY="off", GOSUMDB="off",
                       GOWORK="off", GOTOOLCHAIN="local", npm_config_offline="true",
                       npm_config_audit="false", npm_config_fund="false", npm_config_update_notifier="false")
    if not target_linux:
        environment["CGO_ENABLED"] = "0"
    subprocess.run([sys.executable, str(source / "portable_source.py"), "build-wails", str(root)],
                   env=environment, check=True)
    ci(source, root)
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    subprocess.run([npm, "run", "build"], cwd=str(root / "frontend"), env=environment, check=True)
    wails = root / ".runtime/tools" / ("wails.exe" if os.name == "nt" else "wails")
    subprocess.run([str(wails), "build", "-platform", target, "-nopackage", "-clean", "-m",
                    "-nosyncgomod", "-skipbindings", "-s", *tags], cwd=str(root), env=environment, check=True)
    if target_linux:
        resources = root / "build/bin/linux-resources"
        resources.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / "build/linux/platform-installer-ui.desktop", resources / "platform-installer-ui.desktop")
        shutil.copyfile(root / "build/linux/icon.png", resources / "platform-installer-ui.png")
    print("PASS: offline build " + target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("acquire", help="Explicit DEV network acquisition from the lockfile")
    command.add_argument("root", type=Path)
    command.add_argument("output", type=Path)
    command.add_argument("--profile", choices=[LINUX_PROFILE, "all"], default=LINUX_PROFILE)
    for name in ("verify", "ci", "build"):
        command = commands.add_parser(name)
        command.add_argument("source", type=Path)
        command.add_argument("root", type=Path)
        if name == "build":
            command.add_argument("--platform", choices=["windows/amd64", "linux/amd64"], default="windows/amd64")
            command.add_argument("--webkit", choices=["auto", "4.0", "4.1"], default="auto")
    command = commands.add_parser("verify-part")
    command.add_argument("source", type=Path)
    command.add_argument("part")
    args = parser.parse_args()
    try:
        if args.command == "acquire":
            acquire(args.root.resolve(), args.output.resolve(), args.profile)
        elif args.command == "verify-part":
            manifest = read_manifest(args.source.resolve())
            part = next((part for part in manifest["parts"] if part["name"] == args.part), None)
            portable.require(part is not None, "Part not listed in npm manifest: " + args.part)
            read_part(args.source.resolve(), part)
            print("PASS: {} ; LF/CRLF normalized; other parts not checked".format(args.part))
        elif args.command == "verify":
            manifest, _ = verify_package(args.source.resolve(), args.root.resolve())
            print("PASS: {} npm tarballs; lockfile integrity verified".format(manifest["files"]))
        elif args.command == "build":
            build(args.source.resolve(), args.root.resolve(), args.platform, args.webkit)
        else:
            ci(args.source.resolve(), args.root.resolve())
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print("npm-offline: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

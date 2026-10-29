#!/usr/bin/env python3
"""Pack/restore application and Core sources in text parts of at most 5,000,000 bytes."""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

LEGACY_FORMAT = "platform-installer-portable-source-v2"
FORMAT = "platform-installer-portable-source-v3"
LIMIT = 5_000_000
BLOCK = 48_000
HEADER = b"@@PORTABLE "
FOOTER = b"\n@@END\n"
SCRIPT = "scripts/portable_source.py"
RESOURCES = ["build/appicon.png", "build/windows/icon.ico", "build/windows/info.json",
             "build/windows/wails.exe.manifest", "build/linux/build.sh",
             "build/linux/platform-installer-ui.desktop", "build/linux/icon.png"]
WAILS_SOURCE = "third_party/wails"
WAILS_VERSION = "v2.15.0"
# CLI templates are compile-time go:embed resources, including their README files.
WAILS_EMBED_TREES = ("pkg/templates/templates/", "pkg/templates/ides/",
                     "pkg/templates/generate/assets/", "pkg/buildassets/build/",
                     "cmd/wails/internal/template/base/")
EXCLUDED_DIRS = {".git", ".github", ".runtime", ".agents", ".codex", "docs", "tests", "test",
                 "testdata", "__tests__", "e2e", "node_modules", "__pycache__",
                 ".pytest_cache", "dist", "cache", "bundle", "runs", "secrets",
                 "projects", "coverage", "bin", "portable-source"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe_path(name):
    require(isinstance(name, str) and bool(name), "Missing path")
    for part in name.split("/"):
        require(part not in {"", ".", ".."} and
                not re.search(r'[\\<>:"|?*\x00-\x1f]', part) and
                not part.endswith((".", " ")) and
                not re.match(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", part, re.I),
                "Unsafe path: " + name)
    return name


def included(name):
    # Dependency package names (for example cache) are not runtime directories.
    if name.startswith("vendor/"):
        return not name.endswith("_test.go")
    if name.startswith(WAILS_SOURCE + "/"):
        relative = name[len(WAILS_SOURCE) + 1:]
        if "/" not in relative and relative not in {"go.mod", "go.sum", "wails.go", "LICENSE", "SOURCE.json"}:
            return False
        if relative.startswith(WAILS_EMBED_TREES):
            return True
        # Vendored CLI dependencies already omit tests; preserve compile-time resources.
        if relative.startswith("vendor/"):
            return not relative.endswith("_test.go")
        if relative.split("/")[0] in {"test", "tests", "tools"}:
            return False
        if relative.endswith(".exe") and relative != "internal/webview2runtime/MicrosoftEdgeWebview2Setup.exe":
            return False
        if relative == "internal/webview2runtime/MicrosoftEdgeWebview2Setup.exe":
            return True
    parts = name.lower().split("/")
    leaf = parts[-1]
    if set(parts) & EXCLUDED_DIRS:
        return False
    if leaf in {"agents.md", "current_state.md"} or re.match(r"readme(?:\.|$)", leaf):
        return False
    # Licence/notice files are required for dependency redistribution.
    if re.search(r"\.(md|rst|adoc|docx?|pdf)$", leaf) and not re.match(r"(license|licence|copying|notice)", leaf):
        return False
    if re.search(r"(_test\.go|\.(test|spec)\.[^.]+)$", leaf) or leaf.startswith("test_"):
        return False
    if re.match(r"(vitest|playwright|eslint|prettier)\.config\.", leaf) or leaf == "test-setup.ts":
        return False
    if parts[0] == "scripts" and (leaf.startswith("qa-") or leaf in {"source_text.py", "portable-source.cjs"}):
        return False
    if leaf.startswith((".env", ".coverage")) or re.search(r"\.(key|pem|p12|pfx|vault-password|private-key|log|pyc|pyo|tmp|syso)$", leaf):
        return False
    if re.search(r"\.(rpm|deb|whl|bin|zip|tar|gz|xz|bz2|7z|iso)$", leaf):
        return False
    # Wails vendor has executable/DLL assets embedded in Go at compile time.
    if parts[0] != "vendor" and re.search(r"\.(exe|dll|so|a|lib)$", leaf):
        return False
    return True


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args])


def source_files(root):
    modes = {}
    for entry in git(root, "ls-files", "--stage", "-z").split(b"\0"):
        if not entry:
            continue
        metadata, name = entry.split(b"\t", 1)
        mode, _, stage = metadata.split(b" ")
        require(stage == b"0", "Unmerged source file")
        decoded = name.decode("utf-8")
        if included(decoded):
            require(mode in {b"100644", b"100755"}, "Unsupported Git entry: " + decoded)
            modes[decoded] = 0o755 if mode == b"100755" else 0o644
    for name in [SCRIPT, *RESOURCES]:
        modes[name] = 0o755 if name.endswith(".sh") else 0o644
    wails_root = root / WAILS_SOURCE
    require((wails_root / "vendor/modules.txt").is_file(), "Missing vendored Wails CLI sources")
    for directory, directories, filenames in os.walk(str(wails_root), followlinks=False):
        directories[:] = [name for name in directories if name not in {".git", "node_modules", "__pycache__"}]
        for filename in filenames:
            target = Path(directory) / filename
            name = target.relative_to(root).as_posix()
            if included(name):
                modes.setdefault(name, 0o755 if name.endswith(".sh") else 0o644)
    files = []
    seen = set()
    for name in sorted(modes):
        safe_path(name)
        require(name.casefold() not in seen, "Case-colliding source path: " + name)
        seen.add(name.casefold())
        target = root.joinpath(*name.split("/"))
        require(target.is_file() and not target.is_symlink(), "Missing/nonregular source: " + name)
        files.append((name, modes[name], target))
    validate_vendor_packages(root, [name for name, _, _ in files])
    return files


def validate_vendor_packages(root, names):
    """Reject snapshots missing a package declared by either vendor manifest."""
    package_dirs = {name.rsplit("/", 1)[0] for name in names if name.endswith(".go")}
    for vendor in ("vendor", WAILS_SOURCE + "/vendor"):
        for line in (root / vendor / "modules.txt").read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#"):
                require(vendor + "/" + line in package_dirs,
                        "Missing vendored Go package: " + vendor + "/" + line)


def pack(root, output):
    require(not output.exists(), "Output already exists: " + str(output))
    files = source_files(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".portable-pack-", dir=str(output.parent)))
    manifest = {"format": FORMAT, "maxPartBytes": LIMIT,
                "sourceRevision": git(root, "rev-parse", "HEAD").decode().strip(),
                "files": len(files), "sourceBytes": 0, "textFiles": 0, "binaryFiles": 0, "parts": []}
    lines = []
    length = 0

    def flush():
        nonlocal lines, length
        if not length:
            return
        data = b"".join(lines)
        name = "source-{:04d}.txt".format(len(manifest["parts"]) + 1)
        (staging / name).write_bytes(data)
        manifest["parts"].append({"name": name, "bytes": len(data), "sha256": digest(data)})
        lines, length = [], 0

    try:
        for name, mode, target in files:
            data = target.read_bytes()
            manifest["sourceBytes"] += len(data)
            checksum = digest(data)
            newline = "lf"
            try:
                text = data.decode("utf-8")
                require("\0" not in text, "Binary NUL")
                if "\r" in text:
                    normalized = text.replace("\r\n", "\n")
                    require("\r" not in normalized and text.count("\n") == text.count("\r\n"),
                            "Mixed or bare CR: preserve as Base64")
                    text, newline = normalized, "crlf"
            except (UnicodeDecodeError, ValueError):
                encoding = "base64"
                chunks = [base64.b64encode(data[start:start + BLOCK])
                          for start in range(0, len(data), BLOCK)] or [b""]
                manifest["binaryFiles"] += 1
            else:
                encoding = "utf-8"
                chunks = [text[start:start + BLOCK].encode("utf-8")
                          for start in range(0, len(text), BLOCK)] or [b""]
                manifest["textFiles"] += 1
            count = len(chunks)
            for index, payload in enumerate(chunks):
                record = {"path": name, "mode": mode, "size": len(data), "sha256": checksum,
                          "index": index, "count": count,
                          "newline": newline,
                          "encoding": encoding, "payloadBytes": len(payload)}
                line = HEADER + json.dumps(record, ensure_ascii=True, separators=(",", ":")).encode("ascii") + b"\n" + payload + FOOTER
                transport_length = len(line) + line.count(b"\n")
                require(transport_length <= LIMIT, "Record exceeds part limit")
                if length + transport_length > LIMIT:
                    flush()
                lines.append(line)
                length += transport_length
        flush()
        manifest_data = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
        require(len(manifest_data) <= LIMIT, "Manifest exceeds part limit")
        (staging / "manifest.json").write_bytes(manifest_data)
        shutil.copyfile(Path(__file__), staging / "portable_source.py")
        require(not output.exists(), "Output appeared during pack")
        staging.rename(output)
    except Exception:
        shutil.rmtree(staging)
        raise
    print(json.dumps({"files": manifest["files"], "sourceBytes": manifest["sourceBytes"],
                      "parts": len(manifest["parts"]),
                      "textFiles": manifest["textFiles"], "binaryFiles": manifest["binaryFiles"],
                      "maxPartBytes": max(part["bytes"] for part in manifest["parts"]),
                      "output": str(output)}))


def read_package(source):
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    require(manifest.get("format") in {FORMAT, LEGACY_FORMAT} and manifest.get("maxPartBytes") == LIMIT and
            type(manifest.get("files")) is int and manifest["files"] > 0 and
            isinstance(manifest.get("parts"), list) and bool(manifest["parts"]), "Invalid manifest")
    files, seen, blocks = [], set(), []
    current, next_index, total = None, 0, 0
    encodings = {"utf-8": 0, "base64": 0}
    for part_index, part in enumerate(manifest["parts"], 1):
        require(part["name"] == "source-{:04d}.txt".format(part_index), "Invalid part order")
        data = (source / part["name"]).read_bytes()
        require(len(data) <= LIMIT, "Part exceeds transport limit")
        if manifest["format"] == FORMAT:
            data = data.replace(b"\r\n", b"\n")
            require(b"\r" not in data, "Bare CR in normalized part")
        require(len(data) <= LIMIT and len(data) == part["bytes"] and digest(data) == part["sha256"],
                "Part checksum/size mismatch: " + part["name"])
        stream = io.BytesIO(data)
        while stream.tell() < len(data):
            header = stream.readline(16385)
            require(len(header) <= 16384 and header.startswith(HEADER) and header.endswith(b"\n"), "Invalid record header")
            record = json.loads(header[len(HEADER):].decode("ascii"))
            if manifest["format"] == FORMAT:
                require(record.get("newline") in {"lf", "crlf"} and
                        (record.get("encoding") == "utf-8" or record["newline"] == "lf"),
                        "Invalid newline metadata")
            safe_path(record["path"])
            require(type(record.get("size")) is int and record["size"] >= 0 and
                    type(record.get("count")) is int and record["count"] > 0 and
                    type(record.get("index")) is int and isinstance(record.get("sha256"), str) and
                    re.fullmatch(r"[a-f0-9]{64}", record["sha256"]) and record.get("mode") in {0o644, 0o755} and
                    record.get("encoding") in {"utf-8", "base64"} and
                    type(record.get("payloadBytes")) is int and 0 <= record["payloadBytes"] <= BLOCK * 4,
                    "Invalid file metadata")
            if record["index"] == 0:
                require(current is None and record["path"].casefold() not in seen,
                        "Duplicate/incomplete file: " + record["path"])
                seen.add(record["path"].casefold())
                current, blocks, next_index = record, [], 0
            require(current is not None and record["index"] == next_index and
                    record["index"] < record["count"] and
                    all(record.get(key) == current.get(key) for key in ("path", "mode", "size", "sha256", "count", "encoding", "newline")),
                    "Invalid block order/metadata")
            payload = stream.read(record["payloadBytes"])
            require(len(payload) == record["payloadBytes"] and stream.read(len(FOOTER)) == FOOTER,
                    "Incomplete payload or invalid footer")
            if record["encoding"] == "utf-8":
                decoded = payload.decode("utf-8").encode("utf-8")
                require(b"\0" not in decoded, "Binary NUL in text")
            else:
                decoded = base64.b64decode(payload, validate=True)
                require(base64.b64encode(decoded) == payload and len(decoded) <= BLOCK, "Invalid Base64")
            blocks.append(decoded)
            next_index += 1
            if next_index == current["count"]:
                content = b"".join(blocks)
                if manifest["format"] == FORMAT and current["encoding"] == "utf-8" and current["newline"] == "crlf":
                    content = content.replace(b"\n", b"\r\n")
                require(len(content) == current["size"] and digest(content) == current["sha256"],
                        "File checksum mismatch: " + current["path"])
                files.append((current, content))
                encodings[current["encoding"]] += 1
                total += len(content)
                current, blocks = None, []
    require(current is None and len(files) == manifest["files"] and total == manifest["sourceBytes"],
            "Incomplete package")
    require(manifest.get("textFiles") == encodings["utf-8"] and manifest.get("binaryFiles") == encodings["base64"],
            "Encoding counts mismatch")
    return manifest, files


def unpack(source, destination):
    require(not destination.exists(), "Destination already exists: " + str(destination))
    _, files = read_package(source)  # Validate every part before writing.
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".portable-restore-", dir=str(destination.parent)))
    try:
        for record, content in files:
            target = staging.joinpath(*record["path"].split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(content)
            target.chmod(record["mode"])
        require(not destination.exists(), "Destination appeared during restoration")
        staging.rename(destination)
    except Exception:
        shutil.rmtree(staging)
        raise
    print("Restored {} files to {}".format(len(files), destination))


def verify(source, root=None):
    manifest, files = read_package(source)
    if root is not None:
        for record, _ in files:
            target = root.joinpath(*record["path"].split("/"))
            require(not target.is_symlink() and digest(target.read_bytes()) == record["sha256"],
                    "Source mismatch: " + record["path"])
    print("PASS: {} files, {} parts; SHA-256 {}".format(len(files), len(manifest["parts"]),
          "matches source tree" if root else "verified"))


def linux_build_tags(webkit):
    require(shutil.which("pkg-config") and shutil.which("cc"),
            "Linux build requires a C compiler and pkg-config")
    def available(package):
        return subprocess.run(["pkg-config", "--exists", package],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    require(available("gtk+-3.0"), "Linux build requires GTK3 development libraries")
    abi = webkit
    if abi == "auto":
        abi = "4.1" if available("webkit2gtk-4.1") else "4.0"
    require(available("webkit2gtk-" + abi), "Linux build requires WebKit2GTK " + abi + " development libraries")
    return ["-tags", "webkit2_41"] if abi == "4.1" else []


def build_wails(root):
    source = root / WAILS_SOURCE
    require((source / "go.mod").is_file() and (source / "vendor/modules.txt").is_file(),
            "Missing Wails v2.15.0 sources/vendor")
    require((source / "cmd/wails/internal/version.txt").read_text(encoding="utf-8").strip() == WAILS_VERSION,
            "Unexpected Wails source version")
    require(shutil.which("go"), "Building Wails requires Go")
    output = root / ".runtime/tools" / ("wails.exe" if os.name == "nt" else "wails")
    output.parent.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ, GOFLAGS="-mod=vendor", GOPROXY="off", GOSUMDB="off", GOWORK="off", GOTOOLCHAIN="local")
    command = ["go", "build", "-mod=vendor", "-trimpath", "-o", str(output), "./cmd/wails"]
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=str(source), env=environment, check=True)
    subprocess.run([str(output), "version"], cwd=str(root), env=environment, check=True)
    return output


def build(root, webkit="auto"):
    require((root / "vendor/modules.txt").is_file(), "Missing Go vendor")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    require(npm and shutil.which("go"), "Build requires Node/npm and Go")
    tags = linux_build_tags(webkit) if sys.platform.startswith("linux") else []
    wails = str(build_wails(root))
    environment = dict(os.environ, GOFLAGS="-mod=vendor", GOPROXY="off", GOSUMDB="off", GOWORK="off", GOTOOLCHAIN="local")
    for command, cwd in [([npm, "ci"], root / "frontend"),
                         ([npm, "run", "build"], root / "frontend"),
                         ([wails, "build", "-nopackage", "-clean", "-m", "-nosyncgomod", "-skipbindings", "-s", *tags], root)]:
        print("+ " + " ".join(command), flush=True)
        subprocess.run(command, cwd=str(cwd), env=environment, check=True)
    if sys.platform.startswith("linux"):
        resources = root / "build/bin/linux-resources"
        resources.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / "build/linux/platform-installer-ui.desktop",
                        resources / "platform-installer-ui.desktop")
        shutil.copyfile(root / "build/linux/icon.png", resources / "platform-installer-ui.png")
    print("Build complete: " + str(root / "build/bin"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, first, second in [("pack", "root", "output"), ("unpack", "source", "destination"),
                                ("verify", "source", "root"), ("build", "root", None), ("build-wails", "root", None)]:
        command = commands.add_parser(name)
        command.add_argument(first, type=Path)
        if name == "build":
            command.add_argument("--webkit", choices=["auto", "4.0", "4.1"], default="auto",
                                 help="Linux WebKit2GTK ABI; auto prefers 4.1")
        if second:
            command.add_argument(second, type=Path, nargs="?" if name == "verify" else None)
    args = parser.parse_args()
    try:
        if args.command == "pack":
            pack(args.root.resolve(), args.output.resolve())
        elif args.command == "unpack":
            unpack(args.source.resolve(), args.destination.resolve())
        elif args.command == "verify":
            verify(args.source.resolve(), args.root.resolve() if args.root else None)
        elif args.command == "build-wails":
            build_wails(args.root.resolve())
        else:
            build(args.root.resolve(), args.webkit)
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print("portable-source: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

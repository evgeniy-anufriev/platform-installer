#!/usr/bin/env python3
"""Package existing CI artifacts; never compile, download or activate a bundle."""

import argparse
import hashlib
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile
import zipfile


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unpack_bundle(project, destination):
    archive = project / ".runtime/ci-output/execution-runtime-bundle.tar.gz"
    checksum = archive.with_name(archive.name + ".sha256")
    fields = checksum.read_text(encoding="utf-8").split()
    if len(fields) != 2 or fields[1] != archive.name or fields[0] != sha256(archive):
        raise ValueError("runtime bundle archive checksum mismatch")
    with tarfile.open(archive, "r:gz") as source:
        # Bundle builders emit directories and regular files only. Do not allow
        # links or special files to escape the release staging directory.
        seen = set()
        for member in source:
            path = PurePosixPath(member.name)
            if (path.is_absolute() or ".." in path.parts or "\\" in member.name
                    or not path.parts or path.parts[0] != "execution-bundle"
                    or path in seen or not (member.isdir() or member.isfile())):
                raise ValueError("unsafe runtime bundle archive entry")
            seen.add(path)
            target = destination.joinpath(*path.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(member) as incoming, target.open("wb") as outgoing:
                    shutil.copyfileobj(incoming, outgoing)
                target.chmod(0o755 if member.mode & 0o111 else 0o644)
    if not (destination / "execution-bundle/manifest.yaml").is_file():
        raise ValueError("runtime bundle manifest is missing")


def stage_application(project, root, target):
    name = "platform-installer-ui" + (".exe" if target == "windows" else "")
    binary = root / "build/bin" / name
    binary.parent.mkdir(parents=True)
    shutil.copyfile(project / "build/bin" / name, binary)
    binary.chmod(0o755)
    config = root / "config/application.yml"
    config.parent.mkdir()
    shutil.copyfile(project / "config/application.yml", config)
    config.chmod(0o644)
    unpack_bundle(project, root / "bundle")


def rpm_release(project, workspace, app, output, version):
    payload = workspace / "payload"
    installed = payload / "opt/platform-installer"
    installed.parent.mkdir(parents=True)
    shutil.copytree(app, installed)
    resources = project / "build/bin/linux-resources"
    for source, relative in (
        (resources / "platform-installer-ui.desktop", "usr/share/applications/platform-installer-ui.desktop"),
        (resources / "platform-installer-ui.png", "usr/share/pixmaps/platform-installer-ui.png"),
    ):
        destination = payload / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        destination.chmod(0o644)
    launcher = payload / "usr/bin/platform-installer-ui"
    launcher.parent.mkdir(parents=True)
    launcher.write_text('#!/bin/sh\nexec /opt/platform-installer/build/bin/platform-installer-ui "$@"\n', encoding="utf-8")
    launcher.chmod(0o755)
    topdir = workspace / "rpmbuild"
    topdir.mkdir()
    spec = workspace / "platform-installer.spec"
    spec.write_text("""%global debug_package %{nil}
%global _build_id_links none
# The bundle manifest covers exact bytes. RPM post-processing must not strip
# binaries, rewrite shebangs or byte-compile Python inside this immutable input.
%global __os_install_post %{nil}
%global __requires_exclude_from ^/opt/platform-installer/bundle/.*$
%global __provides_exclude_from ^/opt/platform-installer/bundle/.*$
%global release_payload PAYLOAD
Name: platform-installer
Version: VERSION
Release: 1
Summary: Platform Installer desktop application and execution runtime bundle
License: LicenseRef-Unknown
BuildArch: x86_64
Requires: gtk3, webkit2gtk4.1, openssh-clients

%description
Platform Installer UI with its configuration and an immutable execution bundle.
The bundle is packaged without acquiring dependencies or starting installations.

%prep
%build
%install
mkdir -p %{buildroot}
cp -a %{release_payload}/. %{buildroot}/

%files
%defattr(-,root,root,-)
%dir /opt/platform-installer
%dir /opt/platform-installer/config
%config(noreplace) /opt/platform-installer/config/application.yml
/opt/platform-installer/build
/opt/platform-installer/bundle
/usr/bin/platform-installer-ui
/usr/share/applications/platform-installer-ui.desktop
/usr/share/pixmaps/platform-installer-ui.png
""".replace("VERSION", version).replace("PAYLOAD", str(payload)), encoding="utf-8")
    subprocess.run(["rpmbuild", "-bb", "--define", "_topdir " + str(topdir), str(spec)], check=True)
    packages = list((topdir / "RPMS/x86_64").glob("*.rpm"))
    if len(packages) != 1:
        raise ValueError("expected exactly one release RPM")
    result = output / packages[0].name
    shutil.copyfile(packages[0], result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=("linux", "windows"))
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    if re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,3}", args.version) is None:
        parser.error("version must contain 2 to 4 dot-separated numeric components")
    project = args.project.resolve()
    output = project / ".runtime/releases"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="release-", dir=output) as temporary:
        workspace = Path(temporary)
        app = workspace / "platform-installer"
        stage_application(project, app, args.target)
        if args.target == "linux":
            artifact = rpm_release(project, workspace, app, output, args.version)
        else:
            artifact = output / ("platform-installer-" + args.version + "-windows-amd64.zip")
            with zipfile.ZipFile(artifact, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
                for path in sorted(app.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(workspace).as_posix())
    artifact.with_name(artifact.name + ".sha256").write_text(
        sha256(artifact) + "  " + artifact.name + "\n", encoding="utf-8")
    print("Release created: " + str(artifact))


if __name__ == "__main__":
    main()

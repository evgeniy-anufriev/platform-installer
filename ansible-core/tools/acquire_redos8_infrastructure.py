#!/usr/bin/env python3
"""DEV-only RED OS 8 RPM acquisition; never installs or publishes a bundle.

Run on a trusted acquisition host with an existing Python/Core runtime.
The embedded file repository must be configured separately on each target.
"""

import argparse
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile

import yaml

import build_execution_runtime_bundle as builder


def run(argv, phase):
    # Repository diagnostics can contain credential-bearing URLs. Do not relay
    # raw DNF output, environment, or command arguments to Installer logs.
    result = subprocess.run([str(arg) for arg in argv], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    if result.returncode:
        raise ValueError("%s failed (exit %s)" % (phase, result.returncode))
    return result.stdout


def load(path):
    with path.open(encoding="utf-8") as source:
        return yaml.safe_load(source)


def host_identity():
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ValueError("requires a trusted RED OS 8 x86_64 acquisition host")
    values = {}
    for line in Path("/etc/os-release").read_text().splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value.strip('"\'')
    if values.get("ID") != "redos" or values.get("VERSION_ID", "").split(".")[0] != "8":
        raise ValueError("requires RED OS 8; cross-distribution acquisition is not supported")
    return values


def requirements(root):
    """Read package names/versions from current service manifests and defaults.

    This is an acquisition list, not an Ansible precedence/source resolver.
    PostgreSQL uses the same two package-family alternatives as its role.
    """
    groups = []
    bootstrap = (root / "ansible-core/tools/bootstrap_execution_runtime.sh").read_text()
    names = re.search(r"for package in ([a-z0-9 -]+); do", bootstrap)
    if not names:
        raise ValueError("bootstrap prerequisite list could not be read")
    groups.extend([[name]] for name in names.group(1).split())
    for manifest_path in sorted((root / "services").glob("*/service.yml")):
        service = load(manifest_path)
        service_id = manifest_path.parent.name
        fqcn = service["roleEntrypoints"]["apply"]["fqcn"].split(".")
        defaults_path = (manifest_path.parent / "ansible_collections" / fqcn[0] /
                         fqcn[1] / "roles" / fqcn[2] / "defaults/main.yml")
        defaults = load(defaults_path)
        versions = {item["name"]: str(item.get("version", ""))
                    for item in service.get("runtimeRequirements", [])}
        names = set(versions)
        for key, value in defaults.items():
            if key.endswith("_package") and isinstance(value, str):
                names.add(value)
            if key.endswith("_packages") and isinstance(value, list):
                names.update(value)
        if service_id == "redis":
            versions["redis"] = str(defaults["platform_redis_version"])
        if service_id == "vault":
            # Literal ancillary package in vault_tls/tasks/provision.yml.
            names.add("logrotate")
        for name in sorted(names):
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9+_.-]*", name):
                raise ValueError("nonliteral package default: %s" % service_id)
            version = versions.get(name, "")
            if version and not re.fullmatch(r"[A-Za-z0-9+_.-]+", version):
                raise ValueError("nonliteral package version: %s" % service_id)
            suffix = ".*" if service_id == "redis" and version else "-*"
            groups.append([name + "-" + version + suffix if version else name])
        if service_id == "postgresql":
            version = str(defaults["platform_postgresql_version"])
            major = version.split(".")[0]
            for legacy, scoped in (("postgresql", "postgresql" + major),
                                   ("postgresql-server", "postgresql" + major + "-server"),
                                   ("postgresql-contrib", "postgresql" + major + "-contrib")):
                groups.append([legacy + "-" + version + "-*", scoped + "-" + version + "-*"])
            failover = str(defaults["platform_postgresql_pg_auto_failover_version"])
            groups.append(["pg_auto_failover-" + major + "-" + failover + "-*",
                           "pg_auto_failover-" + failover + "-*"])
    return sorted(set(tuple(group) for group in groups))


def dnf_options(repos):
    if not repos or any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]*", repo) for repo in repos):
        raise ValueError("--repo requires explicit configured repository IDs, without globs")
    return ["dnf", "-q", "--disablerepo=*"] + ["--enablerepo=" + repo for repo in repos] + [
        "--setopt=install_weak_deps=False", "--setopt=skip_if_unavailable=False",
        "--setopt=gpgcheck=True", "--setopt=sslverify=True"]


def check_enabled_repositories(repos):
    output = run(["dnf", "-q", "repolist", "--enabled"], "enabled repository inspection")
    enabled = {line.split()[0] for line in output.splitlines() if line.split()}
    if not set(repos).issubset(enabled):
        raise ValueError("all --repo IDs must already be configured and enabled")


def resolve_roots(groups, options):
    roots = []
    missing = []
    def query(spec):
        output = run(options + ["repoquery", "--available", "--latest-limit=1",
                               "--archlist=x86_64,noarch", "--qf",
                               "%{name}-%{epoch}:%{version}-%{release}.%{arch}", spec],
                     "repository query")
        return [line for line in output.splitlines()
                if re.fullmatch(r"[A-Za-z0-9+_.:-]+\.(x86_64|noarch)", line)]

    postgres = [group for group in groups if len(group) == 2 and group[0].startswith("postgresql")]
    if postgres:
        for family in (0, 1):
            candidates = [query(group[family]) for group in postgres]
            if all(candidates):
                roots.extend(item for entries in candidates for item in entries)
                break
        else:
            missing.append("complete PostgreSQL package family")
    for alternatives in groups:
        if alternatives in postgres:
            continue
        for spec in alternatives:
            candidates = query(spec)
            if candidates:
                roots.extend(candidates)
                break
        else:
            missing.append(" or ".join(alternatives))
    if missing:
        raise ValueError("required packages unavailable: " + ", ".join(missing))
    return sorted(set(roots))


def validate_bundle(cli, path):
    return json.loads(run([cli, "-command", "validate-bundle", "-bundle", path],
                          "standard bundle validation"))


def offline_check(repository, roots, work, identity):
    """Solve against an empty rpmdb and only the freshly collected file repo.

    --downloadonly never executes an RPM transaction; unshare blocks external
    networking even if a host plugin attempts an unexpected network request.
    Every RPM was signature-checked against the acquisition host's trusted keys.
    """
    empty_repos = work / "empty-repos"
    empty_repos.mkdir()
    options = ["unshare", "--net", "dnf", "-q", "-y", "--noplugins",
               "--installroot=" + str(work / "empty-root"),
               "--releasever=" + identity["VERSION_ID"], "--disablerepo=*",
               "--setopt=reposdir=" + str(empty_repos),
               "--repofrompath=collected," + repository.as_uri(), "--enablerepo=collected",
               "--setopt=collected.gpgcheck=False", "--setopt=install_weak_deps=False",
               "--setopt=module_platform_id=" + identity.get("PLATFORM_ID", "platform:red80"),
               "install", "--downloadonly", "--downloaddir=" + str(work / "solve-downloads")]
    run(options + roots, "network-isolated empty-root dependency solve")


def acquire(args):
    identity = host_identity()
    if os.geteuid() != 0:
        raise ValueError("run with sudo -n: the isolated empty-root check requires root")
    for tool in ("dnf", "rpmkeys", "createrepo_c", "unshare"):
        if not shutil.which(tool):
            raise ValueError("missing acquisition prerequisite: " + tool)
    base = args.base_bundle.resolve()
    output = args.output.absolute()
    if output.exists() or output.is_symlink() or output.with_name(output.name + ".tmp").exists():
        raise ValueError("output or its .tmp path already exists")
    if base == output or base in output.parents or output in base.parents:
        raise ValueError("output must be separate from the immutable base bundle")
    for protected in (builder.REPOSITORY / "cache", builder.REPOSITORY / "bundle"):
        if output.resolve() == protected.resolve() or protected.resolve() in output.resolve().parents:
            raise ValueError("use a staging output; active cache requires the standard publisher")
    verified = validate_bundle(args.installer_cli, base)
    manifest = verified["Manifest"]
    expected_platform = {"os": "redos", "version": identity["VERSION_ID"], "architecture": "x86_64"}
    if manifest["platforms"] != [expected_platform]:
        raise ValueError("base bundle must target only this exact RED OS 8 host platform")
    options = dnf_options(args.repo)
    check_enabled_repositories(args.repo)
    groups = requirements(builder.REPOSITORY)
    roots = resolve_roots(groups, options)
    print("Resolved %d root packages; acquiring full dependency closure" % len(roots), flush=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="redos8-acquisition-", dir=output.parent) as temporary:
        work = Path(temporary)
        runtime = work / "runtime-input"
        builder.copy_tree(base / "runtime", runtime)
        repository = runtime / "artifacts/redos8-repository"
        if repository.exists():
            raise ValueError("base already contains redos8-repository; start from an unextended base")
        repository.mkdir(parents=True)
        run(options + ["download", "--resolve", "--alldeps", "--arch=x86_64,noarch",
                       "--destdir=" + str(repository)] + roots, "RPM closure download")
        rpms = sorted(repository.glob("*.rpm"))
        if not rpms:
            raise ValueError("RPM closure is empty")
        records = []
        package_names = set()
        for rpm in rpms:
            signature = run(["rpmkeys", "--checksig", rpm], "RPM signature validation")
            if "signatures OK" not in signature:
                raise ValueError("RPM must have a signature verified by an already trusted host key")
            name = run(["rpm", "-qp", "--qf", "%{NAME}", rpm], "RPM name inspection").strip()
            if name in package_names:
                raise ValueError("duplicate RPM name in closure: " + name)
            package_names.add(name)
            records.append({"file": rpm.name, "sha256": builder.digest_file(rpm),
                            "size": rpm.stat().st_size})
        run(["createrepo_c", "--quiet", repository], "local repository metadata generation")
        offline_check(repository, roots, work, identity)
        # Bootstrap's fixed loader looks here, not under runtime/artifacts.
        # Include the entire closure so its --disablerepo='*' install can solve.
        packages = runtime / "packages/redos" / identity["VERSION_ID"] / "x86_64"
        packages.mkdir(parents=True, exist_ok=True)
        if any(packages.iterdir()):
            raise ValueError("base bootstrap RPM directory must be empty (avoid mixed/ambiguous versions)")
        for rpm in rpms:
            shutil.copyfile(rpm, packages / rpm.name)
        report = {"baseBundleDigest": verified["Digest"], "platform": expected_platform,
                  "repositoryIds": args.repo, "requested": groups, "resolvedRoots": roots,
                  "rpmCount": len(records), "packages": records,
                  "signaturesVerified": True, "emptyRootOfflineSolve": True,
                  "weakDependencies": False,
                  "targetRepositoryConfigurationRequired": True}
        (repository / "acquisition.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        images = [(item["reference"], item["archiveRef"][len("runtime/"):])
                  for item in manifest.get("containerImages", [])]
        candidate = work / "bundle"
        builder.build(candidate, runtime, args.bundle_version, manifest["coreVersion"],
                      ["redos:" + identity["VERSION_ID"] + ":x86_64"], images)
        result = validate_bundle(args.installer_cli, candidate)
        # No incomplete/unchecked bundle is placed at the requested output.
        candidate.rename(output)
    print(json.dumps({"bundle": str(output), "digest": result["Digest"],
                      "rpmCount": len(records), "published": False}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bundle-version", required=True)
    parser.add_argument("--installer-cli", type=Path, required=True,
                        help="absolute path to the native Linux platform-installer CLI")
    parser.add_argument("--repo", action="append", required=True,
                        help="approved, already configured RED OS 8 repository ID; repeat as needed")
    args = parser.parse_args()
    try:
        acquire(args)
    except (ValueError, OSError, KeyError) as error:
        print("RED OS 8 acquisition blocked: %s" % error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

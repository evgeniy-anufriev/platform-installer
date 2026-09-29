#!/usr/bin/env python3
"""SI08-F test-only tool: retire one already-cleared, exact QA Vault member.

This is not a service uninstall API. It preserves every source byte in a
root-only archive and refuses paths outside the known QA Vault layout.
"""

import argparse
from contextlib import ExitStack
import hashlib
import json
import os
import pwd
import re
import socket
import stat
import subprocess
import sys
import types


ARCHIVE_ROOT = "/var/lib/platform-vault-qa-archive"
ARCHIVE_STAGE = "si08f-20260928"
MEMBERS = {
    "redos-node1": {"vault-1": "d84df0dc93eee8673276981fa94a2d7a20bd6373fa7cffea3a4271fd3216e89d",
                    "vault-ha-1": "c6a54fca6cede1c53b935f828accb75bf5413e97c167e083674603efc7fc4f03",
                    "vault-ha-2": "c6a54fca6cede1c53b935f828accb75bf5413e97c167e083674603efc7fc4f03",
                    "vault-ha-3": "c6a54fca6cede1c53b935f828accb75bf5413e97c167e083674603efc7fc4f03",
                    "vault-hb-1": "fd43413180b166e3bd439eb5916d5d98094cf2e98d6e15c2b6320ba8fc66c3e4"},
    "redos-node2": {"vault-hb-2": "fd43413180b166e3bd439eb5916d5d98094cf2e98d6e15c2b6320ba8fc66c3e4"},
    "redos-node3": {"vault-hb-3": "fd43413180b166e3bd439eb5916d5d98094cf2e98d6e15c2b6320ba8fc66c3e4"},
}
ROLE = "roles/vault_tls/"
PKG_HASHES = {
    "d84df0dc93eee8673276981fa94a2d7a20bd6373fa7cffea3a4271fd3216e89d":
        ("39705c60b931afe67b2b5194ed83d571b06b843be3b7a13c8e68f3317465cd12",
         "f439385aca8aaf9a34e162aec3533f2dea3ff4c30daabf2f382d7781d2cb4895",
         "be7d95025e14ce6f47b75f0256a7015ed06dc36c9f538fb49681d3163173bcf9"),
    "c6a54fca6cede1c53b935f828accb75bf5413e97c167e083674603efc7fc4f03":
        ("c3b5dd7ed4742baf24a1974e9bbfd162a6d32c81063f32fd226b970695fb58e0",
         "f439385aca8aaf9a34e162aec3533f2dea3ff4c30daabf2f382d7781d2cb4895",
         "f8b076ed3841cce3959c5448e96f5248a8cc80c558de239fd52420e3e72b9ee6"),
    "fd43413180b166e3bd439eb5916d5d98094cf2e98d6e15c2b6320ba8fc66c3e4":
        ("c3b5dd7ed4742baf24a1974e9bbfd162a6d32c81063f32fd226b970695fb58e0",
         "f439385aca8aaf9a34e162aec3533f2dea3ff4c30daabf2f382d7781d2cb4895",
         "f8b076ed3841cce3959c5448e96f5248a8cc80c558de239fd52420e3e72b9ee6"),
}
TEMPLATE_HASHES = {
    "templates/vault.service.j2": "9cdc3f0b8f5002d58fc83b8333af70b90456489dcd31cfcf27c9774ccea537bc",
    "templates/vault-audit.logrotate.j2": "6eb17e3130607c0574cb8ee3a650f58e48004249fb8f369d01a4a4490ed189e0",
}
CLEAR_HASH = "4fb63760360410dfe30df6e0b39aef0f1a0615a5c484cd703b55afcd0f295e31"
COMPAT_RELEASE = "fd43413180b166e3bd439eb5916d5d98094cf2e98d6e15c2b6320ba8fc66c3e4"


class RetirementBlocked(Exception):
    pass


def require(condition, code):
    if not condition:
        raise RetirementBlocked(code)


def read_package_file(release_root, release_digest, relative, limit=512 * 1024):
    """Read one pinned component through no-follow handles; hash those bytes."""
    require(os.path.basename(os.path.normpath(release_root)) == release_digest and
            release_root.startswith("/") and ".." not in release_root.split("/") and
            all(part not in ("", ".", "..") for part in relative.split("/")),
            "VAULT_QA_PACKAGE_PATH_INVALID")
    with ExitStack() as stack:
        current = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        stack.callback(os.close, current)
        for part in (part for part in release_root.split("/") if part):
            current = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                              dir_fd=current)
            stack.callback(os.close, current)
        parts = ("services/vault/ansible_collections/platform/vault/" + relative).split("/")
        for part in parts[:-1]:
            current = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                              dir_fd=current)
            stack.callback(os.close, current)
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                     dir_fd=current)
        stack.callback(os.close, fd)
        meta = os.fstat(fd)
        require(stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1 and
                meta.st_size <= limit, "VAULT_QA_PACKAGE_FILE_INVALID")
        data = os.read(fd, limit + 1)
        require(len(data) == meta.st_size and len(data) <= limit,
                "VAULT_QA_PACKAGE_FILE_INVALID")
        return data


def exact_default(defaults, name):
    matches = re.findall(r"^" + re.escape(name) + r": ([^\r\n]+)$",
                         defaults.decode("utf-8"), re.MULTILINE)
    require(len(matches) == 1, "VAULT_QA_PACKAGE_DEFAULT_INVALID")
    return matches[0]


def load_pinned_identity(member, release_root, compat_root=None):
    digest = MEMBERS[socket.gethostname()][member]
    defaults, normalized, provisioned = (
        read_package_file(release_root, digest, ROLE + relative)
        for relative in ("defaults/main.yml", "tasks/normalize.yml", "tasks/provision.yml"))
    expected = PKG_HASHES[digest]
    require(tuple(hashlib.sha256(data).hexdigest() for data in
                  (defaults, normalized, provisioned)) == expected,
            "VAULT_QA_PINNED_PACKAGE_MISMATCH")
    for relative, expected_hash in TEMPLATE_HASHES.items():
        data = read_package_file(release_root, digest, ROLE + relative)
        require(hashlib.sha256(data).hexdigest() == expected_hash,
                "VAULT_QA_PINNED_PACKAGE_MISMATCH")
    deployment = exact_default(defaults, "platform_vault_deployment_id")
    user = exact_default(defaults, "platform_vault_user")
    roots = tuple(exact_default(defaults, key) for key in
                  ("platform_vault_config_root", "platform_vault_data_root",
                   "platform_vault_log_root"))
    require(deployment == "vault" and user == "platform-vault" and
            all(re.fullmatch(r"/[a-z0-9/-]+", value) for value in roots),
            "VAULT_QA_PACKAGE_DEFAULT_INVALID")
    # The standalone package predates clear_member. Only that pinned member
    # may use the owner-approved later byte-identical clear implementation.
    source_digest, source_root = digest, release_root
    if digest == "d84df0dc93eee8673276981fa94a2d7a20bd6373fa7cffea3a4271fd3216e89d":
        require(compat_root is not None, "VAULT_QA_COMPAT_CLEAR_REQUIRED")
    if compat_root is not None:
        require(digest == "d84df0dc93eee8673276981fa94a2d7a20bd6373fa7cffea3a4271fd3216e89d" and
                member == "vault-1", "VAULT_QA_COMPAT_CLEAR_FORBIDDEN")
        source_digest, source_root = COMPAT_RELEASE, compat_root
    clear_bytes = read_package_file(source_root, source_digest,
                                    "plugins/modules/clear_member.py")
    require(hashlib.sha256(clear_bytes).hexdigest() == CLEAR_HASH,
            "VAULT_QA_CLEAR_PACKAGE_MISMATCH")
    module = types.ModuleType("si08f_pinned_clear_member")
    exec(compile(clear_bytes, "<verified-pinned-clear-member>", "exec"), module.__dict__)
    require((module.DATA_ROOT, module.CONFIG_ROOT, module.UNIT_ROOT, module.SERVICE) ==
            (roots[1], roots[0], "/etc/systemd/system", user),
            "VAULT_QA_CLEAR_PACKAGE_MISMATCH")
    sources = (
        ("unit", module.UNIT_ROOT, False),
        ("logrotate", "/etc/logrotate.d", False),
        ("config", roots[0] + "/" + deployment, True),
        ("data", roots[1] + "/" + deployment, True),
        ("log", roots[2] + "/" + deployment, True),
    )
    return deployment, user, module, sources


def open_root_directory(stack, path):
    require(path.startswith("/") and ".." not in path.split("/"), "VAULT_QA_PATH_INVALID")
    current = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    stack.callback(os.close, current)
    for part in (part for part in path.split("/") if part):
        current = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                          dir_fd=current)
        stack.callback(os.close, current)
        meta = os.fstat(current)
        require(stat.S_ISDIR(meta.st_mode) and meta.st_uid == 0 and
                meta.st_mode & 0o022 == 0, "VAULT_QA_PARENT_UNSAFE")
    return current


def child_dir(stack, parent, name, create=False):
    if create:
        try:
            os.mkdir(name, 0o700, dir_fd=parent)
        except FileExistsError:
            pass
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    stack.callback(os.close, fd)
    meta = os.fstat(fd)
    require(meta.st_uid == 0 and stat.S_IMODE(meta.st_mode) == 0o700 and
            meta.st_dev == os.fstat(parent).st_dev, "VAULT_QA_ARCHIVE_UNSAFE")
    return fd


def fixed_file(parent, name, expected_header, mode):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    try:
        meta = os.fstat(fd)
        require(stat.S_ISREG(meta.st_mode) and meta.st_uid == 0 and
                stat.S_IMODE(meta.st_mode) == mode and meta.st_nlink == 1 and
                meta.st_size <= 65536 and meta.st_dev == os.fstat(parent).st_dev,
                "VAULT_QA_FILE_UNSAFE")
        first = os.read(fd, 512).split(b"\n", 1)[0]
        require(first == expected_header, "VAULT_QA_OWNERSHIP_UNKNOWN")
        return meta
    finally:
        os.close(fd)


def checked_directory(parent, name, service_uid, mode):
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    try:
        meta = os.fstat(fd)
        require(meta.st_uid == service_uid and stat.S_IMODE(meta.st_mode) == mode and
                meta.st_dev == os.fstat(parent).st_dev,
                "VAULT_QA_MEMBER_DIRECTORY_UNSAFE")
        return meta
    finally:
        os.close(fd)


def retire(member, inspect_only, release_root, compat_root=None):
    node = socket.gethostname()
    require(member in MEMBERS.get(node, ()), "VAULT_QA_MEMBER_NOT_ALLOWED_ON_HOST")
    require(os.geteuid() == 0, "VAULT_QA_ROOT_REQUIRED")
    deployment, service_user, clear, sources = load_pinned_identity(
        member, release_root, compat_root)
    # The identical versioned clear module validates marker, HCL, systemd unit,
    # source inode and mounts. After a successful clear only its marker remains.
    require(clear.clear_member(deployment, member, deployment, True) is False,
            "VAULT_QA_RAFT_NOT_CLEARED")
    service_uid = pwd.getpwnam(service_user).pw_uid
    with ExitStack() as stack:
        data_parent = open_root_directory(stack, sources[3][1])
        data_fd = os.open(member, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                          dir_fd=data_parent)
        stack.callback(os.close, data_fd)
        marker_fd = os.open(".platform-vault-member.json",
                            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=data_fd)
        try:
            marker_meta = os.fstat(marker_fd)
            require(stat.S_ISREG(marker_meta.st_mode) and marker_meta.st_uid == service_uid and
                    stat.S_IMODE(marker_meta.st_mode) == 0o600 and
                    marker_meta.st_size <= 4096, "VAULT_QA_MARKER_UNSAFE")
            marker = json.loads(os.read(marker_fd, 4097))
        finally:
            os.close(marker_fd)
        require(marker.get("apiVersion") == "platform.installer/vault-member-marker/v1alpha1" and
                marker.get("deploymentId") == deployment and marker.get("memberId") == member,
                "VAULT_QA_MARKER_MISMATCH")
        unit = marker.get("instanceName")
        require(isinstance(unit, str) and len(unit) == len("platform-vault-") + 64 and
                unit.startswith("platform-vault-") and
                all(char in "0123456789abcdef" for char in unit[len("platform-vault-"):]),
                "VAULT_QA_UNIT_ID_INVALID")
        properties = clear.unit_properties(unit)
        require(properties.get("ActiveState") in ("inactive", "failed") and
                properties.get("MainPID") == "0", "VAULT_QA_MEMBER_RUNNING")
        names = {"unit": unit + ".service", "logrotate": unit,
                 "config": member, "data": member, "log": member}
        parents, observed = {}, {}
        for kind, source_path, is_directory in sources:
            parent = open_root_directory(stack, source_path)
            parents[kind] = parent
            name = names[kind]
            if is_directory:
                mode = 0o750 if kind == "log" else 0o700
                observed[kind] = checked_directory(parent, name, service_uid, mode)
                clear.reject_submounts(source_path + "/" + name)
            elif kind == "unit":
                observed[kind] = fixed_file(parent, name,
                    ("# platform-vault-managed: " + deployment + "/" + member).encode(), 0o644)
            else:
                observed[kind] = fixed_file(parent, name,
                    ("# platform-vault-managed: " + deployment + "/" + member).encode(), 0o644)
        if inspect_only:
            return unit
        archive_parent = open_root_directory(stack, "/var/lib")
        archive_root = child_dir(stack, archive_parent, "platform-vault-qa-archive", create=True)
        stage = child_dir(stack, archive_root, ARCHIVE_STAGE, create=True)
        require(unit not in os.listdir(stage), "VAULT_QA_ALREADY_ARCHIVED")
        archive_member = child_dir(stack, stage, unit, create=True)
        moved = []
        try:
            for kind, _, _ in sources:
                name = names[kind]
                source = parents[kind]
                now = os.stat(name, dir_fd=source, follow_symlinks=False)
                before = observed[kind]
                require((now.st_dev, now.st_ino, now.st_mtime_ns) ==
                        (before.st_dev, before.st_ino, before.st_mtime_ns),
                        "VAULT_QA_SOURCE_CHANGED")
                require(now.st_dev == os.fstat(archive_member).st_dev and
                        kind not in os.listdir(archive_member),
                        "VAULT_QA_ARCHIVE_CONFLICT")
                os.rename(name, kind, src_dir_fd=source, dst_dir_fd=archive_member)
                moved.append(kind)
                placed = os.stat(kind, dir_fd=archive_member, follow_symlinks=False)
                require((placed.st_dev, placed.st_ino) == (before.st_dev, before.st_ino),
                        "VAULT_QA_MOVED_IDENTITY_MISMATCH")
            os.fsync(archive_member)
            for source in parents.values():
                os.fsync(source)
        except BaseException:
            for kind in reversed(moved):
                source = parents[kind]
                if names[kind] not in os.listdir(source):
                    os.rename(kind, names[kind], src_dir_fd=archive_member,
                              dst_dir_fd=source)
            raise
    result = subprocess.run(["/usr/bin/systemctl", "daemon-reload"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            timeout=30, check=False)
    require(result.returncode == 0, "VAULT_QA_DAEMON_RELOAD_FAILED")
    return unit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("member", choices=sorted(set(sum((list(v) for v in MEMBERS.values()), []))))
    parser.add_argument("--pinned-release-root", required=True)
    parser.add_argument("--compat-clear-release-root")
    parser.add_argument("--retire", action="store_true")
    args = parser.parse_args()
    try:
        unit = retire(args.member, inspect_only=not args.retire,
                      release_root=args.pinned_release_root,
                      compat_root=args.compat_clear_release_root)
        print("VAULT_QA_RETIRE_PASS" if args.retire else "VAULT_QA_RETIRE_INSPECT_PASS", unit)
    except Exception as error:
        # Fixed diagnostic only: never print HCL, marker, keys, paths or traceback.
        code = str(error) if isinstance(error, RetirementBlocked) else "VAULT_QA_RETIRE_FAILED"
        print(code, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

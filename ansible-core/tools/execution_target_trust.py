"""Narrow per-run SSH host-key trust for Installer-owned execution.

The private manifest supplies Core-resolved endpoints.  Operator-approved keys
are staged only for the matching plan and verified again before target contact.
"""
import base64
import fcntl
import hashlib
import ipaddress
import json
import os
import re
import stat

from execution_lifecycle import LifecycleError, digest


_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,62}\Z")
_HOST = re.compile(r"[A-Za-z0-9][A-Za-z0-9.-]{0,252}\Z")
_KEY_TYPES = frozenset(("ssh-ed25519", "ecdsa-sha2-nistp256", "ssh-rsa"))
_FILE_LIMIT = 65536
_MARKER = ".target-host-trust.json"
_FILE = "known_hosts"


def _fail():
    raise LifecycleError("TARGET_HOST_TRUST_INVALID")


def _run_directory(state_root, run_id):
    # Planning uses a bounded decimal ID; the node creates a 32-character
    # lowercase hexadecimal ID for the authoritative run at Start.
    if not isinstance(run_id, str) or not re.fullmatch(r"installer-(?:[0-9]{1,39}|[0-9a-f]{32})", run_id):
        _fail()
    path = os.path.join(state_root, "runs", run_id)
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    details = os.fstat(descriptor)
    if not stat.S_ISDIR(details.st_mode) or details.st_uid != os.geteuid() or stat.S_IMODE(details.st_mode) & 0o022:
        os.close(descriptor)
        _fail()
    return descriptor


def _read_file(directory, name, limit=_FILE_LIMIT):
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
    try:
        details = os.fstat(descriptor)
        if (not stat.S_ISREG(details.st_mode) or details.st_uid != os.geteuid()
                or stat.S_IMODE(details.st_mode) != 0o600 or details.st_nlink != 1
                or details.st_size > limit):
            _fail()
        content = os.read(descriptor, limit + 1)
        if len(content) > limit or len(content) != details.st_size:
            _fail()
        return content
    finally:
        os.close(descriptor)


def _write_new(directory, name, content):
    temporary = ".target-trust-" + os.urandom(8).hex()
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        # The staging directory is root-owned and locked by the caller.
        if _exists(directory, name):
            _fail()
        os.rename(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)
    finally:
        try:
            os.unlink(temporary, dir_fd=directory)
        except FileNotFoundError:
            pass


def _exists(directory, name):
    try:
        os.stat(name, dir_fd=directory, follow_symlinks=False)
        return True
    except FileNotFoundError:
        return False


def _address(value):
    if not isinstance(value, str) or len(value) > 253 or not value or any(char in value for char in " \t\r\n[]*,!"):
        _fail()
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        if not _HOST.fullmatch(value) or ".." in value or value.endswith("."):
            _fail()
        return value


def _connections(manifest):
    values = manifest.get("targetConnections")
    if not isinstance(values, dict) or len(values) > 256:
        _fail()
    result = {}
    for host_id, item in values.items():
        if not isinstance(host_id, str) or not _ID.fullmatch(host_id) or not isinstance(item, dict) or set(item) != {"address", "port", "mode", "unsupportedOptions"}:
            _fail()
        address, port = _address(item["address"]), item["port"]
        if type(port) is not int or not 1 <= port <= 65535 or item["mode"] != "ssh" or item["unsupportedOptions"] is not False:
            _fail()
        result[host_id] = (address, port)
    return result


def _key(value):
    if not isinstance(value, str) or len(value) > 12000:
        _fail()
    try:
        data = base64.b64decode(value, validate=True)
    except (ValueError, base64.binascii.Error):
        _fail()
    if len(data) < 36 or len(data) > 8192:
        _fail()
    size = int.from_bytes(data[:4], "big")
    if size < 1 or 4 + size > len(data):
        _fail()
    return data[4:4 + size].decode("ascii", errors="ignore")


def _known_hosts(manifest, approvals):
    connections = _connections(manifest)
    if not isinstance(approvals, list) or len(approvals) != len(connections):
        _fail()
    seen, lines = set(), []
    for item in approvals:
        if not isinstance(item, dict) or set(item) != {"hostId", "address", "port", "keyType", "publicKey"}:
            _fail()
        host_id = item["hostId"]
        if host_id in seen or host_id not in connections or (item["address"], item["port"]) != connections[host_id]:
            _fail()
        seen.add(host_id)
        kind, key = item["keyType"], item["publicKey"]
        if kind not in _KEY_TYPES or _key(key) != kind:
            _fail()
        address, port = connections[host_id]
        host = address if port == 22 else "[%s]:%d" % (address, port)
        lines.append((host, kind, key))
    if seen != set(connections):
        _fail()
    by_endpoint = {}
    for host, kind, key in lines:
        previous = by_endpoint.setdefault(host, (kind, key))
        if previous != (kind, key):
            _fail()
    content = "".join("%s %s %s\n" % item for item in sorted(set(lines))).encode("ascii")
    if not content or len(content) > _FILE_LIMIT:
        _fail()
    return content


def _binding(manifest, manifest_digest, known_hosts):
    return {"projectIdentity": manifest.get("projectIdentity"),
            "projectRevision": manifest.get("projectRevision"),
            "planFingerprint": manifest.get("planFingerprint"),
            "runtimeRelease": manifest.get("runtimeRelease"),
            "manifestDigest": manifest_digest,
            "knownHostsDigest": "sha256:" + hashlib.sha256(known_hosts).hexdigest()}


def stage(state_root, request):
    if not isinstance(request, dict) or set(request) != {"stagingId", "projectIdentity", "projectRevision", "planFingerprint", "runtimeRelease", "manifestDigest", "approvals"}:
        _fail()
    directory = _run_directory(state_root, request["stagingId"])
    try:
        fcntl.flock(directory, fcntl.LOCK_EX)
        manifest = json.loads(_read_file(directory, "manifest.json"))
        manifest_digest = digest(manifest)
        if any(request[field] != manifest.get(field) for field in ("projectIdentity", "projectRevision", "planFingerprint", "runtimeRelease")) or request["manifestDigest"] != manifest_digest:
            _fail()
        content = _known_hosts(manifest, request["approvals"])
        if _exists(directory, _FILE) or _exists(directory, _MARKER):
            _fail()
        marker = json.dumps(_binding(manifest, manifest_digest, content), sort_keys=True, separators=(",", ":")).encode("ascii")
        _write_new(directory, _FILE, content)
        _write_new(directory, _MARKER, marker)
    finally:
        os.close(directory)


def verify(state_root, run_id, manifest):
    directory = _run_directory(state_root, run_id)
    try:
        content = _read_file(directory, _FILE)
        marker = json.loads(_read_file(directory, _MARKER, 4096))
        if marker != _binding(manifest, digest(manifest), content):
            _fail()
        # Reconstruct the exact approved file from its lines and the private
        # manifest; no extra trust entries may be added after staging.
        approvals = []
        by_endpoint = {}
        for line in content.decode("ascii").splitlines():
            fields = line.split(" ")
            if len(fields) != 3:
                _fail()
            by_endpoint[(fields[0], fields[1])] = fields[2]
        for host_id, (address, port) in _connections(manifest).items():
            host = address if port == 22 else "[%s]:%d" % (address, port)
            matches = [(kind, key) for (candidate, kind), key in by_endpoint.items() if candidate == host]
            if len(matches) != 1:
                _fail()
            approvals.append({"hostId": host_id, "address": address, "port": port,
                              "keyType": matches[0][0], "publicKey": matches[0][1]})
        if _known_hosts(manifest, approvals) != content:
            _fail()
        return os.path.join(state_root, "runs", run_id, _FILE)
    finally:
        os.close(directory)


def required(manifest):
    return any(isinstance(item, dict) and item.get("operation") in ("PKI_REISSUE", "PKI_APPLY", "SERVICE_APPLY", "SERVICE_VERIFY", "APPLICATION_LIBRARIES_APPLY", "APPLICATION_LIBRARIES_VERIFY")
               for item in manifest.get("operations", []))

"""Private, descriptor-bound bootstrap output storage on Linux Execution Nodes.

Only trusted controller calls publish. No request supplies a path or owner.
This foundation does not advertise a protocol or authorize ACK/cleanup yet.
"""
import contextlib
import fcntl
import json
import os
import re
import secrets
import stat

from secret_output_wire import encode_fetch, OutputWireError

_ID = re.compile(r"[0-9a-f]{32}\Z")


def _safe_object(fd, directory=False):
    details = os.fstat(fd)
    valid = stat.S_ISDIR(details.st_mode) if directory else stat.S_ISREG(details.st_mode)
    if not valid or details.st_uid != os.geteuid() or details.st_mode & 0o077:
        raise OutputWireError("OUTPUT_ACCESS_DENIED")
    if not directory and details.st_nlink != 1:
        raise OutputWireError("OUTPUT_ACCESS_DENIED")


@contextlib.contextmanager
def _directory(name, parent=None, create=False):
    if create:
        try:
            os.mkdir(name, 0o700, dir_fd=parent)
            if parent is not None:
                os.fsync(parent)
        except FileExistsError:
            pass
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
    try:
        _safe_object(fd, directory=True)
        yield fd
    finally:
        os.close(fd)


@contextlib.contextmanager
def _package(state_root, package_id, create=False):
    if not isinstance(package_id, str) or _ID.fullmatch(package_id) is None:
        raise OutputWireError("OUTPUT_REQUEST_INVALID")
    # state_root is an existing trusted execution root, never client input.
    with _directory(state_root) as state:
        with _directory("secret-outputs", state, create=create) as root:
            with _directory(package_id, root, create=create) as package:
                lock = os.open(".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
                               0o600, dir_fd=package)
                try:
                    _safe_object(lock)
                    fcntl.flock(lock, fcntl.LOCK_EX)
                    yield package
                finally:
                    os.close(lock)


def _read(package, name, bound):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=package)
    try:
        _safe_object(fd)
        if os.fstat(fd).st_size > bound:
            raise OutputWireError("OUTPUT_TRANSFER_FAILED")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(bound + 1)
        if len(data) > bound:
            raise OutputWireError("OUTPUT_TRANSFER_FAILED")
        return data
    finally:
        os.close(fd)


def _exclusive(package, name, data):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                 0o600, dir_fd=package)
    try:
        _safe_object(fd)
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(fd)
        os.fsync(package)
    finally:
        os.close(fd)


def _metadata(package):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise OutputWireError("OUTPUT_RECOVERY_REQUIRED")
            value[key] = item
        return value
    return json.loads(_read(package, "metadata.json", 8192).decode("utf-8"), object_pairs_hook=unique)


def publish(state_root, metadata, token, shares, validator, schema_path):
    """Publish READY last, after both entries are durable; never overwrite.

    On failure, partial files intentionally remain protected and unadvertised.
    No pathname cleanup can destroy the last bootstrap material. Retry can
    finish identical partial entries; conflicting bytes/identity fail closed.
    """
    try:
        encode_fetch(metadata, token, shares, validator, schema_path)
        with _package(state_root, metadata["packageId"], create=True) as package:
            encoded = json.dumps(metadata, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
            try:
                _exclusive(package, ".binding.json", encoded)
            except FileExistsError:
                if _read(package, ".binding.json", 8192) != encoded:
                    raise OutputWireError("OUTPUT_IDENTITY_MISMATCH")
            try:
                existing = _metadata(package)
            except FileNotFoundError:
                existing = None
            if existing is not None and existing != metadata:
                raise OutputWireError("OUTPUT_IDENTITY_MISMATCH")
            for name, data, bound in (("admin-token", token, 4096), ("unseal-shares", shares, 32768)):
                try:
                    _exclusive(package, name, data)
                except FileExistsError:
                    if _read(package, name, bound) != data:
                        raise OutputWireError("OUTPUT_IDENTITY_MISMATCH")
            if existing is None:
                temporary = ".metadata-" + secrets.token_hex(16)
                _exclusive(package, temporary, encoded)
                os.replace(temporary, "metadata.json", src_dir_fd=package, dst_dir_fd=package)
                os.fsync(package)
        return dict(metadata)
    except OutputWireError:
        raise
    except (OSError, ValueError, TypeError, KeyError):
        raise OutputWireError("OUTPUT_RECOVERY_REQUIRED") from None


def fetch(state_root, package_id, project_id, generation, validator, schema_path):
    """Trusted runtime caller supplies authenticated owner context via euid.

    Directory/file ownership plus exact project/generation are all required.
    Returned bytes belong solely to the confidential transport, never logs.
    """
    try:
        if type(generation) is not int or not 1 <= generation <= 2147483647:
            raise OutputWireError("OUTPUT_REQUEST_INVALID")
        with _package(state_root, package_id) as package:
            metadata = _metadata(package)
            if metadata.get("packageId") != package_id or metadata.get("projectId") != project_id or metadata.get("generation") != generation:
                raise OutputWireError("OUTPUT_IDENTITY_MISMATCH")
            token = _read(package, "admin-token", 4096)
            shares = _read(package, "unseal-shares", 32768)
            return encode_fetch(metadata, token, shares, validator, schema_path)
    except OutputWireError:
        raise
    except (OSError, ValueError, TypeError, KeyError):
        raise OutputWireError("OUTPUT_TRANSFER_FAILED") from None

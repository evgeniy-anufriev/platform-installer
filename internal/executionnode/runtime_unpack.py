# Sent by the Installer over authenticated SSH, before using any bundle code.
import base64
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tarfile


class BoundedHeader(tarfile.TarInfo):
    # Reject oversized extended headers before tarfile allocates their payload.
    def _extension(self, archive, parse):
        depth = getattr(archive, "bundle_header_depth", 0)
        if not 0 < self.size <= 65536 or depth >= 4:
            raise ValueError("oversized or nested bundle header")
        archive.bundle_header_depth = depth + 1
        try:
            return parse(archive)
        finally:
            archive.bundle_header_depth = depth

    def _proc_pax(self, archive):
        return self._extension(archive, super()._proc_pax)

    def _proc_gnulong(self, archive):
        return self._extension(archive, super()._proc_gnulong)

    def _reject_sparse(self, *args):
        raise ValueError("sparse bundle member")

    _proc_sparse = _reject_sparse
    _proc_gnusparse_00 = _reject_sparse
    _proc_gnusparse_01 = _reject_sparse
    _proc_gnusparse_10 = _reject_sparse


def verified_unpack(stage, candidate, entries):
    expected = {}
    for entry in entries:
        name = entry["path"]
        if name in expected or any(part in ("", ".", "..") for part in name.split("/")):
            raise ValueError("invalid expected path")
        expected[name] = (entry["size"], entry["sha256"])

    directory = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        descriptor = os.open("bundle.tar", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(descriptor, "rb") as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.fstat(directory).st_uid:
                raise ValueError("unsafe archive")
            with tarfile.open(fileobj=source, mode="r|", tarinfo=BoundedHeader, bufsize=1024 * 1024) as archive:
                for member in archive:
                    size, digest = expected.pop(member.name)
                    if member.type not in (tarfile.REGTYPE, tarfile.AREGTYPE) or member.sparse is not None or member.size != size:
                        raise ValueError("unexpected member type or size")
                    target = candidate / member.name
                    target.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
                    checksum = hashlib.sha256()
                    with archive.extractfile(member) as data, target.open("xb") as output:
                        while block := data.read(1024 * 1024):
                            checksum.update(block)
                            output.write(block)
                    if "sha256:" + checksum.hexdigest() != digest:
                        raise ValueError("component checksum mismatch")
            if expected:
                raise ValueError("bundle components missing")
            for directory_name in ("runtime/packages", "runtime/python"):
                (candidate / directory_name).mkdir(mode=0o750, parents=True, exist_ok=True)
    finally:
        os.close(directory)


if __name__ == "__main__":
    os.umask(0o027)
    try:
        verified_unpack(sys.argv[1], Path(sys.argv[2]), json.loads(base64.b64decode(verified_manifest)))
    except (OSError, EOFError, ValueError, KeyError, tarfile.TarError):
        sys.exit(78)

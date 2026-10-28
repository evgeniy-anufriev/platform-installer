import os
import re
import stat
import uuid
import hashlib

NAME = re.compile(r"30-backend-[a-z][a-z0-9._-]*\.cfg\Z")
MAX_FILE = 8 * 1024 * 1024
MAX_FILES = 256
MAX_TOTAL = 32 * 1024 * 1024
OPEN_DIR = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


class ArchiveError(Exception):
    pass


def require(ok, code):
    if not ok:
        raise ArchiveError(code)


def secure_directory(fd):
    info = os.fstat(fd)
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0, "HAPROXY_ARCHIVE_DIRECTORY_UNSAFE")
    # A root-owned sticky ancestor such as /var/tmp cannot rename a root-owned
    # child; every actual HAProxy/archival directory remains non-writable.
    require(not (info.st_mode & 0o022) or bool(info.st_mode & stat.S_ISVTX),
            "HAPROXY_ARCHIVE_DIRECTORY_UNSAFE")
    return info


def open_directory_path(path):
    require(isinstance(path, str) and path.startswith("/") and
            not any(part in (".", "..") for part in path.split("/")),
            "HAPROXY_ARCHIVE_PATH_INVALID")
    current = os.open("/", OPEN_DIR)
    try:
        secure_directory(current)
        for part in (value for value in path.split("/") if value):
            next_fd = os.open(part, OPEN_DIR, dir_fd=current)
            secure_directory(next_fd)
            os.close(current)
            current = next_fd
        return current
    except BaseException:
        os.close(current)
        raise


def child_directory(parent, name, create=False):
    if create:
        try:
            os.mkdir(name, 0o700, dir_fd=parent)
        except FileExistsError:
            pass
    fd = os.open(name, OPEN_DIR, dir_fd=parent)
    info = secure_directory(fd)
    require(not (info.st_mode & 0o077), "HAPROXY_ARCHIVE_DIRECTORY_UNSAFE")
    require(info.st_dev == os.fstat(parent).st_dev, "HAPROXY_ARCHIVE_MOUNT_UNSAFE")
    return fd


def read_regular(parent, name):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == 0 and
                not (before.st_mode & 0o022) and before.st_nlink == 1 and
                before.st_size <= MAX_FILE and before.st_dev == os.fstat(parent).st_dev,
                "HAPROXY_ARCHIVE_FILE_UNSAFE")
        data = bytearray()
        while len(data) <= MAX_FILE:
            block = os.read(fd, min(65536, MAX_FILE + 1 - len(data)))
            if not block:
                break
            data.extend(block)
        after = os.fstat(fd)
        require(len(data) <= MAX_FILE and len(data) == before.st_size and
                (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
                "HAPROXY_ARCHIVE_FILE_CHANGED")
        return bytes(data), before
    finally:
        os.close(fd)


def write_snapshot(parent, name, data, source):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o600, dir_fd=parent)
    try:
        with os.fdopen(fd, "wb", closefd=False) as output:
            output.write(data)
            output.flush()
        os.fchown(fd, source.st_uid, source.st_gid)
        os.fchmod(fd, stat.S_IMODE(source.st_mode))
        os.fsync(fd)
    finally:
        os.close(fd)


def capture_prior_candidate(config_directory, name_prefix=''):
    """Prove old active backends against the retained complete candidate graph."""
    try:
        config_fd = open_directory_path(config_directory)
    except FileNotFoundError:
        return []  # A fresh installation has no active backend inventory.
    try:
        try:
            active_fd = os.open("conf.d", OPEN_DIR, dir_fd=config_fd)
        except FileNotFoundError:
            return []
        try:
            secure_directory(active_fd)
            active_names = sorted(os.listdir(active_fd))
            backend_names = [name for name in active_names if name.startswith("30-backend-")]
            if not backend_names:
                return []
            require(len(active_names) <= MAX_FILES and
                    all(isinstance(name, str) and "/" not in name for name in active_names),
                    "HAPROXY_PRIOR_GRAPH_INVALID")
            # Old releases retained their validated .platform-candidate. If it
            # is missing or differs, no old file is automatically owned.
            candidate_fd = os.open("." + (name_prefix + "-" if name_prefix else "") + "candidate", OPEN_DIR, dir_fd=config_fd)
            try:
                secure_directory(candidate_fd)
                require(os.fstat(candidate_fd).st_dev == os.fstat(config_fd).st_dev,
                        "HAPROXY_PRIOR_GRAPH_INVALID")
                candidate_conf_fd = os.open("conf.d", OPEN_DIR, dir_fd=candidate_fd)
                try:
                    secure_directory(candidate_conf_fd)
                    require(os.fstat(candidate_conf_fd).st_dev == os.fstat(active_fd).st_dev and
                            sorted(os.listdir(candidate_conf_fd)) == active_names,
                            "HAPROXY_PRIOR_GRAPH_INVALID")
                    active_main, _ = read_regular(config_fd, "haproxy.cfg")
                    candidate_main, _ = read_regular(candidate_fd, "haproxy.cfg")
                    require(active_main == candidate_main, "HAPROXY_PRIOR_GRAPH_MISMATCH")
                    total = len(active_main)
                    inventory = []
                    for name in active_names:
                        active, _ = read_regular(active_fd, name)
                        candidate, _ = read_regular(candidate_conf_fd, name)
                        total += len(active)
                        require(total <= MAX_TOTAL and active == candidate,
                                "HAPROXY_PRIOR_GRAPH_MISMATCH")
                        if name in backend_names:
                            require(NAME.fullmatch(name), "HAPROXY_BACKEND_OWNERSHIP_UNPROVEN")
                            inventory.append({"name": name, "sha256": hashlib.sha256(active).hexdigest()})
                    return inventory
                finally:
                    os.close(candidate_conf_fd)
            finally:
                os.close(candidate_fd)
        finally:
            os.close(active_fd)
    finally:
        os.close(config_fd)


def archive(config_directory, candidate_files, activation_required, previous_inventory=None, name_prefix=''):
    if previous_inventory is None:
        previous_inventory = []
    require(isinstance(candidate_files, list) and len(candidate_files) <= MAX_FILES and
            len(set(candidate_files)) == len(candidate_files) and
            all(isinstance(name, str) and NAME.fullmatch(name) for name in candidate_files),
            "HAPROXY_ARCHIVE_CANDIDATE_INVALID")
    require(isinstance(previous_inventory, list) and len(previous_inventory) <= MAX_FILES and
            all(isinstance(item, dict) and set(item) == {"name", "sha256"} and
                isinstance(item["name"], str) and NAME.fullmatch(item["name"]) and
                isinstance(item["sha256"], str) and
                re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
                for item in previous_inventory), "HAPROXY_PRIOR_INVENTORY_INVALID")
    proof = {item["name"]: item["sha256"] for item in previous_inventory}
    require(len(proof) == len(previous_inventory), "HAPROXY_PRIOR_INVENTORY_INVALID")
    config_fd = open_directory_path(config_directory)
    try:
        conf_fd = os.open("conf.d", OPEN_DIR, dir_fd=config_fd)
        try:
            conf_info = secure_directory(conf_fd)
            require(conf_info.st_dev == os.fstat(config_fd).st_dev,
                    "HAPROXY_ARCHIVE_MOUNT_UNSAFE")
            names = sorted(os.listdir(conf_fd))
            backend_names = [name for name in names if name.startswith("30-backend-")]
            owned_names = sorted(set(backend_names).union(
                ("10-public.cfg", "20-local-stats.cfg", "90-stats-backends.cfg")).intersection(names))
            require(len(owned_names) <= MAX_FILES, "HAPROXY_ARCHIVE_FILE_LIMIT")
            previous = {}
            total = 0
            require(set(proof) == set(backend_names), "HAPROXY_BACKEND_OWNERSHIP_UNPROVEN")
            for name in owned_names:
                data, metadata = read_regular(conf_fd, name)
                total += len(data)
                require(total <= MAX_TOTAL, "HAPROXY_ARCHIVE_SIZE_LIMIT")
                previous[name] = (data, metadata)
                if name in backend_names:
                    require(NAME.fullmatch(name) and
                            hashlib.sha256(data).hexdigest() == proof[name],
                            "HAPROXY_BACKEND_OWNERSHIP_UNPROVEN")
            stale = sorted(set(backend_names).difference(candidate_files))
            if not activation_required:
                require(not stale, "HAPROXY_BACKEND_STALE_WITHOUT_ACTIVATION")
                return {"changed": False, "archived": [], "archivePath": None}
            try:
                main = read_regular(config_fd, "haproxy.cfg")
            except FileNotFoundError:
                require(not previous, "HAPROXY_ARCHIVE_MAIN_MISSING")
                main = None
            if main is None:
                return {"changed": False, "archived": [], "archivePath": None}
            archive_name = "." + (name_prefix + "-" if name_prefix else "") + "backend-archive"
            archive_fd = child_directory(config_fd, archive_name, create=True)
            try:
                token = "activation-" + uuid.uuid4().hex
                session_fd = child_directory(archive_fd, token, create=True)
                try:
                    previous_fd = child_directory(session_fd, "previous", create=True)
                    stale_fd = child_directory(session_fd, "stale", create=True)
                    try:
                        previous_conf_fd = child_directory(previous_fd, "conf.d", create=True)
                        try:
                            write_snapshot(previous_fd, "haproxy.cfg", *main)
                            for name, (data, metadata) in previous.items():
                                write_snapshot(previous_conf_fd, name, data, metadata)
                            os.fsync(previous_conf_fd)
                            os.fsync(previous_fd)
                            moved = []
                            try:
                                for name in stale:
                                    original = previous[name][1]
                                    current = os.stat(name, dir_fd=conf_fd, follow_symlinks=False)
                                    require((current.st_dev, current.st_ino, current.st_mtime_ns) ==
                                            (original.st_dev, original.st_ino, original.st_mtime_ns),
                                            "HAPROXY_ARCHIVE_FILE_CHANGED")
                                    os.rename(name, name, src_dir_fd=conf_fd, dst_dir_fd=stale_fd)
                                    moved.append(name)
                                    archived = os.stat(name, dir_fd=stale_fd, follow_symlinks=False)
                                    require(archived.st_ino == original.st_ino and archived.st_dev == original.st_dev,
                                            "HAPROXY_ARCHIVE_IDENTITY_MISMATCH")
                                os.fsync(stale_fd)
                                os.fsync(conf_fd)
                            except BaseException:
                                for name in reversed(moved):
                                    if name not in os.listdir(conf_fd):
                                        os.rename(name, name, src_dir_fd=stale_fd, dst_dir_fd=conf_fd)
                                raise
                        finally:
                            os.close(previous_conf_fd)
                    finally:
                        os.close(previous_fd)
                        os.close(stale_fd)
                    os.fsync(session_fd)
                finally:
                    os.close(session_fd)
            finally:
                os.close(archive_fd)
            return {"changed": True, "archived": stale,
                    "archivePath": os.path.join(config_directory, archive_name, token)}
        finally:
            os.close(conf_fd)
    finally:
        os.close(config_fd)

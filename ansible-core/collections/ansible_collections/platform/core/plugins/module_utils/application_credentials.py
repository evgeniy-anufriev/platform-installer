"""Shared private runtime credential path guard; no secret values returned."""
import os
import stat
from ansible.errors import AnsibleFilterError


def protected_secret_files(files, refs, runtime_root, maximum=4096):
    """No values returned; paths must remain under caller's private runtime root."""
    try:
        root = os.path.abspath(runtime_root)
        if not runtime_root or root != os.path.realpath(root):
            raise ValueError()
        owner = os.getuid()
        root_stat = os.lstat(root)
        if not stat.S_ISDIR(root_stat.st_mode) or root_stat.st_uid != owner or root_stat.st_mode & 0o077:
            raise ValueError()
        for ref in set(refs):
            path = os.path.abspath(files[ref])
            if path == root or os.path.commonpath([root, path]) != root or os.path.realpath(path) != path:
                raise ValueError()
            current = path
            while current != root:
                info = os.lstat(current)
                if info.st_uid != owner or info.st_mode & 0o077 or stat.S_ISLNK(info.st_mode):
                    raise ValueError()
                if current == path:
                    if not stat.S_ISREG(info.st_mode) or info.st_size < 1 or info.st_size > maximum:
                        raise ValueError()
                elif not stat.S_ISDIR(info.st_mode):
                    raise ValueError()
                current = os.path.dirname(current)
        return True
    except (ValueError, OSError, KeyError, TypeError):
        raise AnsibleFilterError('APPLICATION_PROVIDER_SECRET_FILE_INVALID')

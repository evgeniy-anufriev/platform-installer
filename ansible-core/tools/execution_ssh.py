"""Operation-private OpenSSH control sockets; no credentials or session registry."""
import hashlib
import os
import re
import stat
import subprocess
import time


def _root():
    # OpenSSH also appends a dot and 16 random bytes before its atomic rename.
    return '/tmp/p' + str(os.geteuid())


def _private_directory(path, create=False):
    if create:
        try:
            os.mkdir(path, 0o700)
        except FileExistsError:
            pass
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise ValueError('EXECUTION_SSH_CONTROL_DIRECTORY_INVALID')


def _run_prefix(journal):
    key = os.path.realpath(journal.root) + '\0' + journal.run_id
    return hashlib.sha256(key.encode()).hexdigest()[:20]


def _operation_name(journal, operation):
    return _run_prefix(journal) + hashlib.sha256(operation['operationId'].encode()).hexdigest()[:12]


def control_path(journal, operation):
    root = _root()
    directory = os.path.join(root, _operation_name(journal, operation))
    for path in (root, directory):
        _private_directory(path, create=True)
    result = os.path.join(directory, '%C')
    if len(result.encode()) - 2 + 40 + 17 >= 108:
        raise ValueError('EXECUTION_SSH_CONTROL_PATH_INVALID')
    return result


def cleanup(journal, operation=None):
    root = _root()
    if not os.path.lexists(root):
        return
    _private_directory(root)
    names = ([_operation_name(journal, operation)] if operation else
             [name for name in os.listdir(root) if name.startswith(_run_prefix(journal))])
    for name in names:
        if re.fullmatch('[0-9a-f]{32}', name) is None:
            raise ValueError('EXECUTION_SSH_CONTROL_DIRECTORY_INVALID')
        directory = os.path.join(root, name)
        if not os.path.lexists(directory):
            continue
        _private_directory(directory)
        for socket_name in os.listdir(directory):
            path = os.path.join(directory, socket_name)
            try:
                info = os.lstat(path)
            except FileNotFoundError:
                # ControlPersist can expire between listing and inspection.
                continue
            if (re.fullmatch('[0-9a-f]{40}', socket_name) is None or
                    not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.geteuid()):
                raise ValueError('EXECUTION_SSH_CONTROL_SOCKET_INVALID')
            # -O never falls back to a normal SSH session. No key/host data needed.
            try:
                result = subprocess.run(['ssh', '-F', 'none', '-S', path, '-O', 'exit', '127.0.0.1'],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                        timeout=3, check=False)
            except subprocess.TimeoutExpired:
                raise ValueError('EXECUTION_SSH_CONTROL_CLEANUP_FAILED') from None
            if result.returncode == 0:
                # Exit acknowledgement precedes the master's socket unlink.
                deadline = time.monotonic() + 3
                while os.path.lexists(path):
                    if time.monotonic() >= deadline:
                        raise ValueError('EXECUTION_SSH_CONTROL_CLEANUP_FAILED')
                    time.sleep(0.02)
            if result.returncode != 0 and os.path.lexists(path):
                # A stopped control-group can leave a stale socket. Prove no master.
                import socket
                probe = socket.socket(socket.AF_UNIX)
                try:
                    probe.settimeout(1)
                    probe.connect(path)
                except ConnectionRefusedError:
                    os.unlink(path)
                except FileNotFoundError:
                    pass
                else:
                    raise ValueError('EXECUTION_SSH_CONTROL_CLEANUP_FAILED')
                finally:
                    probe.close()
        os.rmdir(directory)

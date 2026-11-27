"""Manage the exact set of controller-local, operation-scoped credential files."""
import os
import secrets
import stat

from ansible.errors import AnsibleError
from ansible.plugins.action import ActionBase
from ansible_collections.platform.core.plugins.module_utils.application_vault import segment


DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def open_root(path):
    if not isinstance(path, str) or not path.startswith('/') or os.path.normpath(path) != path or path == '/':
        raise ValueError()
    directory = os.open('/', DIRECTORY_FLAGS)
    try:
        for part in path[1:].split('/'):
            child = os.open(part, DIRECTORY_FLAGS, dir_fd=directory)
            os.close(directory)
            directory = child
        metadata = os.fstat(directory)
        if metadata.st_uid != os.geteuid() or metadata.st_mode & 0o077:
            raise ValueError()
        return os.dup(directory)
    finally:
        os.close(directory)


def write_file(directory, name, content):
    # This exact name class is also removed by execution journal recovery.
    temporary = '.runtime-application-secret-' + secrets.token_hex(32)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    descriptor = os.open(temporary, flags, 0o600, dir_fd=directory)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(content.encode('utf-8'))
        os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
    finally:
        try:
            os.unlink(temporary, dir_fd=directory)
        except FileNotFoundError:
            pass


def update_files(root, entries, cleanup, check):
    if not entries:
        return
    try:
        directory = open_root(root)
    except FileNotFoundError:
        if cleanup:
            return
        raise
    try:
        failed = False
        for name in entries:
            try:
                try:
                    metadata = os.stat(name, dir_fd=directory, follow_symlinks=False)
                except FileNotFoundError:
                    metadata = None
                if metadata and (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid()):
                    raise ValueError()
                if cleanup:
                    if metadata and not check:
                        os.unlink(name, dir_fd=directory)
                elif not check:
                    write_file(directory, name, entries[name])
            except (ValueError, OSError):
                if not cleanup:
                    raise
                failed = True
        if failed:
            raise ValueError()
    finally:
        os.close(directory)


class ActionModule(ActionBase):
    TRANSFERS_FILES = False
    _requires_connection = False

    def run(self, tmp=None, task_vars=None):
        values = task_vars or {}
        try:
            args = self._templar.template(self._task.args)
            root = args['root']
            if args['operation'] == 'remove':
                if not isinstance(args['names'], list):
                    raise ValueError()
                names = dict.fromkeys(segment(name) for name in args['names'])
                update_files(root, names, True, self._task.check_mode)
                return dict(changed=False)
            if args['operation'] != 'write':
                raise ValueError()
            generated = values.get('platform_application_generated_values', {})
            if not isinstance(generated, dict):
                raise ValueError()
            entries = {segment(name): content for name, content in generated.items()}
            if any(not isinstance(content, str) for content in entries.values()):
                raise ValueError()
            update_files(root, entries, False, self._task.check_mode)
            files = dict(values.get('platform_application_credential_files', {}))
            files.update((name, os.path.join(root, name)) for name in entries)
            return dict(changed=False, ansible_facts={'platform_application_credential_files': files},
                        _ansible_facts_cacheable=False)
        except (AnsibleError, OSError, ValueError, TypeError, KeyError):
            return dict(changed=False, failed=True, msg='APPLICATION_PROVIDER_SECRET_FILE_INVALID', _ansible_no_log=True)

"""Stage private local script inputs without one module process per file."""
import os
from pathlib import Path
import stat
import tempfile
from ansible.plugins.action import ActionBase


class ActionModule(ActionBase):
    TRANSFERS_FILES = False
    _requires_connection = False

    def run(self, tmp=None, task_vars=None):
        if getattr(self._task, 'check_mode', False) or not self._task.args['files']:
            return dict(changed=False)
        try:
            directory = Path(self._task.args['directory'])
            if not directory.is_absolute() or str(directory.resolve()) != str(directory):
                raise ValueError()
            directory.parent.mkdir(mode=0o700, exist_ok=True)
            directory.mkdir(mode=0o700, exist_ok=True)
            for path in (directory.parent, directory):
                info = path.lstat()
                if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
                    raise ValueError()
            for item in self._task.args['files']:
                destination = Path(item['dest'])
                if destination.parent != directory or item['mode'] != '0600':
                    raise ValueError()
                raw = (Path(item['src']).read_bytes()
                       if 'src' in item else item['content'].encode('utf-8'))
                fd, temporary = tempfile.mkstemp(dir=directory)
                try:
                    with os.fdopen(fd, 'wb') as stream:
                        stream.write(raw)
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(temporary, destination)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)
            return dict(changed=False)
        except Exception:
            return dict(failed=True, msg='APPLICATION_SCRIPT_INPUT_STAGING_FAILED')

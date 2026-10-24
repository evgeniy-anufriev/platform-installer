"""Runtime credential input availability; no secret values returned."""
import os
import json
from ansible.errors import AnsibleFilterError


def script_failure(result):
    """Project only bounded numeric diagnostics, never arbitrary script output."""
    safe = {'code': 'APPLICATION_SCRIPT_EXECUTION_FAILED'}
    if type(result.get('rc')) is int and -255 <= result['rc'] <= 65535:
        safe['rc'] = result['rc']
    try:
        raw = result.get('stdout', '')
        value = json.loads(raw) if isinstance(raw, str) and len(raw) <= 2048 else {}
        if isinstance(value, dict) and value.get('status') == 'error':
            for key, maximum in (('step', 65535), ('http_status', 599), ('curl_exit', 255)):
                item = value.get(key)
                if type(item) is int and 0 <= item <= maximum:
                    safe[key] = item
    except (ValueError, TypeError):
        pass
    return safe


def protected_secret_files(files, refs, runtime_root=None, maximum=None):
    """Require readable, nonempty regular files for explicitly bound references."""
    try:
        for ref in set(refs):
            path = files[ref]
            if not os.path.isfile(path):
                raise ValueError()
            with open(path, 'rb') as stream:
                if not stream.read(1):
                    raise ValueError()
        return True
    except (ValueError, OSError, KeyError, TypeError):
        raise AnsibleFilterError('APPLICATION_PROVIDER_SECRET_FILE_INVALID')

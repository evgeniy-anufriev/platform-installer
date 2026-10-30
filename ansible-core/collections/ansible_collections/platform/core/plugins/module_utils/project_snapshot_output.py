"""Public snapshot artifact shared by the action and its redacting callback."""
import json
import os
import tempfile


def write_snapshot_output(payload):
    destination = os.environ.get('PLATFORM_PROJECT_SNAPSHOT_OUTPUT')
    if not destination:
        return
    directory = os.path.dirname(os.path.realpath(destination))
    if not os.path.isdir(directory):
        return
    descriptor, temporary = tempfile.mkstemp(prefix='.project-snapshot-', dir=directory)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            json.dump(payload, output, ensure_ascii=True, sort_keys=True, separators=(',', ':'))
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def snapshot_failure_published():
    """A no_log callback must not overwrite the action's safe error artifact."""
    path = os.environ.get('PLATFORM_PROJECT_SNAPSHOT_OUTPUT')
    if not path or os.path.islink(path):
        return False
    try:
        with open(path, 'r', encoding='utf-8') as stream:
            raw = stream.read(4097)
        if len(raw) > 4096:
            return False
        payload = json.loads(raw)
        finding = payload.get('adapterError') if isinstance(payload, dict) else None
        return (isinstance(finding, dict)
                and finding.get('code') == 'PROJECT_SNAPSHOT_INPUT_INVALID'
                and isinstance(finding.get('safeMessage'), str)
                and 0 < len(finding['safeMessage'].encode('utf-8')) <= 512)
    except (OSError, ValueError):
        return False

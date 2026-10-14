"""Closed diagnostic vocabulary: arbitrary Ansible text never leaves this module."""


def safe_task_error(result, no_log=False):
    result = result if isinstance(result, dict) else {}
    if no_log or result.get('_ansible_no_log') or 'censored' in result:
        return {'code': 'ANSIBLE_FAILURE_REDACTED', 'summary': 'Ansible task failed; result hidden by no_log'}
    children = result.get('results')
    if isinstance(children, list):
        for child in children[:256]:
            if not isinstance(child, dict) or not (child.get('failed') or child.get('unreachable')):
                continue
            # One bounded loop level; never descend through arbitrary payload trees.
            nested = safe_task_error({key: value for key, value in child.items() if key != 'results'})
            if nested['code'] != 'ANSIBLE_TASK_FAILED':
                return nested
    message = ' '.join(result[key][:8192] for key in ('msg', 'stderr', 'module_stderr')
                       if isinstance(result.get(key), str)).lower()
    code, summary = 'ANSIBLE_TASK_FAILED', 'Ansible task failed; untrusted result text withheld'
    for candidate, description, phrases in (
        ('ANSIBLE_UNDEFINED_VARIABLE', 'Undefined Ansible variable or attribute', ('is undefined', 'has no attribute', 'undefined variable')),
        ('ANSIBLE_BECOME_TIMEOUT', 'Privilege escalation timed out', ('timeout waiting for privilege escalation prompt',)),
        ('ANSIBLE_BECOME_FAILED', 'Privilege escalation requires valid credentials', ('missing sudo password', 'incorrect sudo password', 'sudo: a password is required')),
        ('ANSIBLE_SSH_AUTH_FAILED', 'SSH authentication failed', ('permission denied (publickey', 'permission denied (password')),
        ('ANSIBLE_CONNECTION_TIMEOUT', 'Connection timed out', ('connection timed out', 'connection timeout')),
        ('ANSIBLE_CONNECTION_LOST', 'Connection closed or reset', ('connection reset by peer', 'connection closed by remote host', 'broken pipe')),
        ('ANSIBLE_FILESYSTEM_FULL', 'Filesystem has no free space', ('no space left on device',)),
        ('ANSIBLE_FILESYSTEM_READ_ONLY', 'Filesystem is read-only', ('read-only file system',)),
        ('ANSIBLE_PERMISSION_DENIED', 'Filesystem or operation permission denied', ('permission denied', 'operation not permitted')),
        ('ANSIBLE_FILE_NOT_FOUND', 'Required file or executable not found', ('no such file or directory', 'could not find or access')),
        ('ANSIBLE_TLS_VERIFY_FAILED', 'TLS certificate verification failed', ('certificate verify failed', 'certificate verification failed')),
    ):
        if any(phrase in message for phrase in phrases):
            code, summary = candidate, description
            break
    else:
        if result.get('unreachable') is True:
            code, summary = 'ANSIBLE_HOST_UNREACHABLE', 'Ansible target host is unreachable'
        elif isinstance(result.get('assertion'), str):
            code, summary = 'ANSIBLE_ASSERTION_FAILED', 'Ansible assertion failed'
    # Numeric exit/status codes are useful without exposing command/output values.
    for key, label in (('rc', 'exit code'), ('status', 'HTTP status')):
        value = result.get(key)
        if type(value) is int and -255 <= value <= 65535:
            summary += '; %s %d' % (label, value)
    return {'code': code, 'summary': summary}

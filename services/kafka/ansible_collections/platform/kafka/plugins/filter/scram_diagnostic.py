"""Project private Kafka CLI results into a closed public failure record."""
import re


def scram_read_diagnostic(result):
    result = result if isinstance(result, dict) else {}
    output = '\n'.join(result.get(key, '') for key in ('stdout', 'stderr')
                       if isinstance(result.get(key), str))
    text = output.lower()
    reason = 'CLI_FAILURE'
    for category, markers in (
        ('TLS', ('sslhandshakeexception', 'ssl handshake', 'pkix', 'certificate_unknown')),
        ('AUTHENTICATION', ('saslauthenticationexception', 'authentication failed', 'invalid credentials')),
        ('AUTHORIZATION', ('authorizationexception', 'not authorized', 'authorization failed')),
        ('TIMEOUT', ('timeoutexception', 'timed out', 'timeout expired')),
        ('CONNECTION', ('connectexception', 'connection refused', 'unknownhostexception')),
    ):
        if any(marker in text for marker in markers):
            reason = category
            break
    partial = min(65535, sum(line.startswith('Error retrieving SCRAM credential configs')
                             for line in output.splitlines()))
    if reason == 'CLI_FAILURE' and partial:
        reason = 'PARTIAL_METADATA'
    rc = result.get('rc')
    public = {'code': 'APPLICATION_KAFKA_SCRAM_READ_FAILED',
              'rc': rc if type(rc) is int and -255 <= rc <= 65535 else -1,
              'reason': reason, 'partial_count': partial}
    delta = result.get('delta')
    match = re.fullmatch(r'(\d{1,2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?', delta) if isinstance(delta, str) else None
    if match:
        hours, minutes, seconds = map(int, match.group(1, 2, 3))
        elapsed = ((hours * 60 + minutes) * 60 + seconds) * 1000 + int((match[4] or '').ljust(6, '0')) // 1000
        if minutes < 60 and seconds < 60 and elapsed <= 86400000:
            public['elapsed_ms'] = elapsed
    return public


class FilterModule:
    def filters(self):
        return {'scram_read_diagnostic': scram_read_diagnostic}

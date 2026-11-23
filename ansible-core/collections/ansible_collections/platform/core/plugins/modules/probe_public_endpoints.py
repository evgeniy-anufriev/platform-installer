"""Check resolved public endpoints on the execution node with bounded concurrency."""
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from itertools import repeat
from multiprocessing import get_context
import re
import socket
import subprocess
import time
from urllib.error import HTTPError

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import open_url


def resolved_addresses(name):
    try:
        result = subprocess.run(['getent', 'ahostsv4', name], capture_output=True,
                                text=True, check=False)
    except OSError:
        return set()
    return ({line.split()[0] for line in result.stdout.splitlines() if line.strip()}
            if result.returncode == 0 else set())


def https_probe(row, ca_path, request=open_url, pause=time.sleep):
    settings = row['probe']
    expected = settings.get('expected_status')
    timeout = settings.get('timeout', 10)
    port = row['port']
    authority = row['name'] if port == 443 else f"{row['name']}:{port}"
    url = f"https://{authority}{settings.get('path', '/')}"
    status = -1
    for attempt in range(1, 5):
        status = -1
        reason = 'REQUEST_FAILED'
        try:
            with request(url, method='GET', validate_certs=settings.get('validate_certs', False),
                         ca_path=ca_path, timeout=timeout, follow_redirects='none',
                         http_agent='ansible-httpget') as response:
                status = response.getcode()
        except HTTPError as error:
            status = error.code
            error.close()
        except Exception as error:
            message = str(error).lower()
            if 'certificate_verify_failed' in message:
                reason = 'CERTIFICATE_VERIFY_FAILED'
            elif 'timed out' in message:
                reason = 'TIMEOUT'
            elif 'connection refused' in message:
                reason = 'CONNECTION_REFUSED'
            elif 'name or service not known' in message or 'temporary failure in name resolution' in message:
                reason = 'DNS_FAILURE'
        ok = 100 <= status <= 599 and status not in (502, 503) and (expected is None or expected == status)
        if ok:
            reason = 'OK'
            break
        if status != -1:
            reason = 'HTTP_STATUS_MISMATCH'
        if attempt < 4:
            pause(2)
    return dict(name=row['name'], port=port, expected=expected, timeout=timeout,
                status=status, reason=reason, attempts=attempt, ok=ok)


def main():
    module = AnsibleModule(argument_spec=dict(sources=dict(type='list', elements='dict', required=True),
                                             port=dict(type='int', default=443), ca_path=dict(type='path')),
                           supports_check_mode=True)
    if module.check_mode:
        module.exit_json(changed=False, skipped=True)
    try:
        rows = []
        port = module.params['port']
        if not 1 <= port <= 65535:
            raise ValueError()
        for source in module.params['sources']:
            probe = dict(source.get('probe', {}))
            if 'expected_status' in probe:
                probe['expected_status'] = int(probe['expected_status'])
            probe['timeout'] = int(probe.get('timeout', 10))
            if probe['timeout'] < 1 or not 100 <= probe.get('expected_status', 200) <= 599:
                raise ValueError()
            path = probe.get('path', '/')
            if not isinstance(path, str) or not path.startswith('/') or any(ord(c) < 32 for c in path):
                raise ValueError()
            for name in source['fqdns']:
                if not isinstance(name, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9.-]{0,252}', name):
                    raise ValueError()
                addresses = source['expectedAddresses']
                if not isinstance(addresses, list) or not addresses or not all(isinstance(a, str) for a in addresses):
                    raise ValueError()
                if source.get('https', True):
                    rows.append(dict(name=name, addresses=set(addresses), probe=probe, port=port))
                if 'tcpPort' in source:
                    tcp_port = source['tcpPort']
                    if type(tcp_port) is not int or not 1 <= tcp_port <= 65535:
                        raise ValueError()
                    rows.append(dict(name=name, addresses=set(addresses), port=tcp_port, transport='tcp'))
    except (KeyError, TypeError, ValueError):
        module.fail_json(msg='SERVICE_ENDPOINT_PROBE_INPUT_INVALID')

    # Keep result order stable even when individual lookups or retries finish out of order.
    with ThreadPoolExecutor(max_workers=4) as pool:
        names = {name: pool.submit(resolved_addresses, name) for name in dict.fromkeys(row['name'] for row in rows)}
        invalid = [row['name'] for row in rows if names[row['name']].result() != row['addresses']]
    if invalid:
        module.fail_json(msg='SERVICE_ENDPOINT_DNS_UNRESOLVED', names=sorted(set(invalid)))
    # Ansible open_url installs a process-global urllib opener. Separate workers
    # keep TLS trust and redirect settings isolated between requests.
    with ProcessPoolExecutor(max_workers=4, mp_context=get_context('fork')) as pool:
        results = list(pool.map(public_probe, rows, repeat(module.params['ca_path'])))
    module.exit_json(changed=False, probes=results)


def public_probe(row, ca_path):
    if row.get('transport') != 'tcp':
        return https_probe(row, ca_path)
    timeout = 3
    for address in sorted(row['addresses']):
        try:
            with socket.create_connection((address, row['port']), timeout=timeout):
                pass
        except OSError:
            return dict(name=row['name'], port=row['port'], expected=None, timeout=timeout,
                        status=-1, reason='TCP_CONNECTION_FAILED', attempts=1, ok=False)
    return dict(name=row['name'], port=row['port'], expected=None, timeout=timeout,
                status=0, reason='OK', attempts=1, ok=True)


if __name__ == '__main__':
    main()

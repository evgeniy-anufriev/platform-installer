"""Normalize application placements into the existing endpoint hook input."""
import ipaddress
import re

try:
    from .haproxy_resolution import normalize_backend_settings
except ImportError:
    from haproxy_resolution import normalize_backend_settings


def project_endpoint_sources(rows, desired, hosts):
    sources = {}
    for row in rows:
        settings = row['settings']
        endpoint = settings.get('endpoint', {})
        if not endpoint.get('enabled', False):
            continue
        source_id, host = row['instanceId'], row['hostId']
        group_id = endpoint.get('endpoint_group')
        domain = desired.get('endpointGroups', {}).get(group_id, {}).get('address', {}).get('domain')
        protocol = endpoint.get('protocol', 'http')
        port = settings.get('ports', {}).get(endpoint.get('listener'), {}).get('published')
        if (not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', source_id) or
                not isinstance(domain, str) or protocol not in {'http', 'https'} or
                type(port) is not int or not 1 <= port <= 65535):
            raise ValueError('APPLICATION_ENDPOINT_INVALID')
        defaults = {'balance': 'roundrobin', 'check': True, 'fall': 3, 'rise': 2,
                    'ssl': protocol == 'https', 'sslVerify': 'required'}
        backend, findings = normalize_backend_settings(defaults, endpoint.get('haproxy', {}).get('backend', {}),
                                                       'applicationLibraries.' + row['libraryId'] + '.' + source_id)
        if findings or backend['ssl'] != (protocol == 'https') or (backend['ssl'] and backend.get('sslVerify') != 'required'):
            raise ValueError('APPLICATION_ENDPOINT_BACKEND_INVALID')
        probe = dict({'path': '/', 'expected_status': 200, 'timeout': 10}, **endpoint.get('probe', {}))
        if (not isinstance(probe['path'], str) or not re.fullmatch(r'/[^\s\x00-\x1f\x7f]{0,2047}', probe['path']) or
                type(probe['expected_status']) is not int or not 100 <= probe['expected_status'] <= 599 or
                type(probe['timeout']) is not int or not 1 <= probe['timeout'] <= 60):
            raise ValueError('APPLICATION_ENDPOINT_PROBE_INVALID')
        probe['validate_certs'] = True
        record = {'endpointGroup': group_id, 'endpoint': {'scope': 'deployment', 'serviceDeploymentId': source_id,
                  'endpointGroupId': group_id, 'fqdn': source_id + '.' + domain,
                  'sanDnsNames': [source_id + '.' + domain], 'wildcardDnsNames': []},
                  'settings': backend, 'probe': probe, 'targets': []}
        existing = sources.setdefault(source_id, record)
        if any(existing[key] != record[key] for key in ('endpoint', 'settings', 'probe')):
            raise ValueError('APPLICATION_HOST_ENDPOINT_CONFLICT')
        address = hosts.get(host, {}).get('ansible_host')
        try:
            parsed = ipaddress.ip_address(address)
            if parsed.version != 4:
                raise ValueError('IPv4 required by the DNS projection')
            address = str(parsed)
        except (ValueError, TypeError):
            raise ValueError('APPLICATION_ENDPOINT_ADDRESS_INVALID')
        existing['targets'].append({'hostId': host, 'address': address, 'port': port, 'serverName': host})
    for source in sources.values():
        source['targets'].sort(key=lambda target: target['hostId'])
    return sources

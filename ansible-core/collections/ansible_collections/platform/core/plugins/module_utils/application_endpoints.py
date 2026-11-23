"""Normalize application placements into the existing endpoint hook input."""
import ipaddress
import re

try:
    from .haproxy_resolution import normalize_backend_settings
except ImportError:
    from haproxy_resolution import normalize_backend_settings


def https_endpoint(settings):
    legacy = settings.get('endpoint', {})
    https = settings.get('endpoints', {}).get('https')
    if https is None:
        return legacy
    return dict(https, endpoint_group=legacy.get('endpoint_group'))


def placement_target(settings, host, hosts):
    """Use the endpoint placement's existing listener and target address."""
    endpoint = settings.get('endpoint', {})
    if endpoint.get('protocol', 'http') not in {'http', 'https'}:
        raise ValueError('APPLICATION_ENDPOINT_INVALID')
    return _listener_target(settings, host, hosts, endpoint.get('listener'))


def _listener_target(settings, host, hosts, listener):
    port = settings.get('ports', {}).get(listener, {}).get('published')
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('APPLICATION_ENDPOINT_INVALID')
    address = hosts.get(host, {}).get('ansible_host')
    if not isinstance(address, str) or not address:
        raise ValueError('APPLICATION_ENDPOINT_ADDRESS_INVALID')
    return {'hostId': host, 'address': address, 'port': port, 'serverName': host}


def public_endpoint_url(instance_id, settings, desired):
    """Shared endpoints publish HTTPS/443 independently of backend transport."""
    endpoint = https_endpoint(settings)
    domain = desired.get('endpointGroups', {}).get(endpoint.get('endpoint_group'), {}).get('address', {}).get('domain')
    if not endpoint.get('enabled') or not domain:
        raise ValueError('APPLICATION_ENDPOINT_INVALID')
    return 'https://' + instance_id + '.' + domain


def _published_target(settings, host, hosts, listener):
    target = _listener_target(settings, host, hosts, listener)
    try:
        parsed = ipaddress.ip_address(target['address'])
        if parsed.version != 4:
            raise ValueError('IPv4 required by the DNS projection')
        target['address'] = str(parsed)
    except (ValueError, TypeError):
        raise ValueError('APPLICATION_ENDPOINT_ADDRESS_INVALID')
    return target


def project_endpoint_sources(rows, desired, hosts):
    sources = {}
    for row in rows:
        settings = row['settings']
        endpoint = https_endpoint(settings)
        tcp = settings.get('endpoints', {}).get('tcp', {})
        https_enabled = endpoint.get('enabled', False)
        tcp_enabled = tcp.get('enabled', False)
        if not https_enabled and not tcp_enabled:
            continue
        source_id, host = row['instanceId'], row['hostId']
        group_id = endpoint.get('endpoint_group')
        domain = desired.get('endpointGroups', {}).get(group_id, {}).get('address', {}).get('domain')
        if (not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', source_id) or
                not isinstance(domain, str)):
            raise ValueError('APPLICATION_ENDPOINT_INVALID')
        record = {'endpointGroup': group_id, 'endpoint': {'scope': 'deployment', 'serviceDeploymentId': source_id,
                  'endpointGroupId': group_id, 'fqdn': source_id + '.' + domain,
                  'sanDnsNames': [source_id + '.' + domain], 'wildcardDnsNames': []}}
        if https_enabled:
            record.update(_https_route(row, endpoint, settings, host, hosts))
        if tcp_enabled:
            port = tcp.get('public_port')
            if type(port) is not int or not 1 <= port <= 65535:
                raise ValueError('APPLICATION_ENDPOINT_TCP_PORT_INVALID')
            record['tcp'] = {'publicPort': port, 'targets': [
                _published_target(settings, host, hosts, tcp.get('listener'))]}
        existing = sources.setdefault(source_id, record)
        if (any(existing.get(key) != record.get(key) for key in ('endpoint', 'settings', 'probe')) or
                existing.get('tcp', {}).get('publicPort') != record.get('tcp', {}).get('publicPort')):
            raise ValueError('APPLICATION_HOST_ENDPOINT_CONFLICT')
        if existing is not record:
            if https_enabled:
                existing['targets'].extend(record['targets'])
            if tcp_enabled:
                existing['tcp']['targets'].extend(record['tcp']['targets'])
    for source in sources.values():
        if 'targets' in source:
            source['targets'].sort(key=lambda target: target['hostId'])
        if 'tcp' in source:
            source['tcp']['targets'].sort(key=lambda target: target['hostId'])
    return sources


def _https_route(row, endpoint, settings, host, hosts):
    protocol = endpoint.get('protocol', 'http')
    if protocol not in {'http', 'https'}:
        raise ValueError('APPLICATION_ENDPOINT_INVALID')
    target = _published_target(settings, host, hosts, endpoint.get('listener'))
    defaults = {'balance': 'roundrobin', 'check': True, 'fall': 3, 'rise': 2,
                'ssl': protocol == 'https', 'sslVerify': 'required'}
    backend, findings = normalize_backend_settings(defaults, endpoint.get('haproxy', {}).get('backend', {}),
                                                   'applicationLibraries.' + row['libraryId'] + '.' + row['instanceId'])
    if findings or backend['ssl'] != (protocol == 'https') or (backend['ssl'] and backend.get('sslVerify') != 'required'):
        raise ValueError('APPLICATION_ENDPOINT_BACKEND_INVALID')
    probe = dict({'path': '/', 'expected_status': 200, 'timeout': 10}, **endpoint.get('probe', {}))
    if (not isinstance(probe['path'], str) or not re.fullmatch(r'/[^\s\x00-\x1f\x7f]{0,2047}', probe['path']) or
            type(probe['expected_status']) is not int or not 100 <= probe['expected_status'] <= 599 or
            type(probe['timeout']) is not int or not 1 <= probe['timeout'] <= 60):
        raise ValueError('APPLICATION_ENDPOINT_PROBE_INVALID')
    probe['validate_certs'] = True
    return {'settings': backend, 'probe': probe, 'targets': [target]}

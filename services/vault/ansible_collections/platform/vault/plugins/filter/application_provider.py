"""Bounded pure reconciliations consumed by builtin uri tasks."""
import ipaddress
import json
import re
from ansible.errors import AnsibleFilterError


def delta(response, fields, owner):
    if response.get('status') == 404:
        if response.get('json', {}).get('data'):
            raise AnsibleFilterError('APPLICATION_VAULT_DOCUMENT_OWNERSHIP_INVALID')
        return dict(method='PUT', body={'options': {'cas': 0}, 'data': dict(fields, _platform_owner=owner)}, changed=True)
    data = response['json']['data']
    if data['data'].get('_platform_owner') != owner or data['metadata'].get('deletion_time') or data['metadata'].get('destroyed'):
        raise AnsibleFilterError('APPLICATION_VAULT_DOCUMENT_OWNERSHIP_INVALID')
    changed = {k: v for k, v in fields.items() if data['data'].get(k) != v}
    return dict(method='PATCH', changed=bool(changed), body={'options': {'cas': data['metadata']['version']}, 'data': changed})


def retained_policy(response, desired, owner):
    """Retain only canonical instance KV reads, never arbitrary HCL/capabilities."""
    if response.get('status') == 404:
        return desired
    previous = response['json']['data']['policy']
    header = '# ' + owner + '\n'
    if not previous.startswith(header) or not desired.startswith(header):
        raise AnsibleFilterError('APPLICATION_VAULT_IDENTITY_OWNERSHIP_INVALID')
    identity = owner.split(':')
    if len(identity) != 4 or identity[0] != 'platform.application/v1':
        raise AnsibleFilterError('APPLICATION_VAULT_IDENTITY_OWNERSHIP_INVALID')
    project, library, instance = identity[1:]

    def reads(policy):
        result = set()
        for line in policy[len(header):].splitlines():
            if line == '# application.connection-retention/v1':
                continue
            match = re.fullmatch(r'path ("[^"\\]+") \{ capabilities = \["(read|update)"\] \}', line)
            if not match:
                raise AnsibleFilterError('APPLICATION_VAULT_POLICY_FORMAT_INVALID')
            path, capability = json.loads(match[1]), match[2]
            if path in ('auth/token/lookup-self', 'auth/token/renew-self', 'auth/token/revoke-self'):
                expected = 'read' if path.endswith('lookup-self') else 'update'
                if capability != expected:
                    raise AnsibleFilterError('APPLICATION_VAULT_POLICY_FORMAT_INVALID')
                continue
            prefix = r'[a-z][a-z0-9_.-]*/data/' + re.escape(project + '/' + library + '/')
            if (capability != 'read' or not re.fullmatch(prefix + r'(shared|' + re.escape(instance) + r'/accounts/[a-z][a-z0-9_.-]*)', path)):
                raise AnsibleFilterError('APPLICATION_VAULT_POLICY_FORMAT_INVALID')
            result.add(path)
        return result

    paths = reads(previous) | reads(desired)
    tail = ('path "auth/token/lookup-self" { capabilities = ["read"] }\n'
            'path "auth/token/renew-self" { capabilities = ["update"] }\n'
            'path "auth/token/revoke-self" { capabilities = ["update"] }\n')
    return header + '# application.connection-retention/v1\n' + ''.join('path %s { capabilities = ["read"] }\n' % json.dumps(path) for path in sorted(paths)) + tail


def cidrs(routes, bridges=None):
    try:
        networks = {'127.0.0.1/32'} | {str(ipaddress.IPv4Network(item[0]['prefsrc']+'/24', strict=False)) for item in routes}
        for placement in bridges or []:
            addresses = [address for interface in placement for address in interface['addr_info']
                         if address.get('family') == 'inet' and address.get('scope') == 'global']
            if not addresses:
                raise ValueError('Missing LXC bridge IPv4 subnet')
            for address in addresses:
                network = ipaddress.IPv4Network(address['local']+'/'+str(address['prefixlen']), strict=False)
                if network.prefixlen == 0:
                    raise ValueError('Unrestricted LXC subnet')
                networks.add(str(network))
        return sorted(networks)
    except (ValueError, KeyError, TypeError, IndexError):
        raise AnsibleFilterError('APPLICATION_VAULT_ROUTE_INVALID')


def source_cache(results, provider):
    return {provider+':'+r['item']['mount']+'/'+r['item']['document']: r['fields'] for r in results}


def document_cache(results, values, provider):
    states = {}
    for response in results:
        document = response['item']
        key = provider+':'+document['mount']+'/'+document['document']
        delta(response, values[key], document['owner'])
        states[key] = response
    return states


def role_changed(response, desired):
    if response.get('status') == 404:
        return True
    current = response['json']['data']
    for key, value in desired.items():
        existing = current.get(key)
        if isinstance(value, list):
            if key == 'token_bound_cidrs':
                # Vault serializes a /32 constraint as a bare IPv4 address.
                existing = [str(ipaddress.ip_network(item, strict=False)) for item in existing or []]
                value = [str(ipaddress.ip_network(item, strict=False)) for item in value]
            if sorted(existing or []) != sorted(value):
                return True
        elif existing != value:
            return True
    return False


def verify_fields(results, expected):
    try:
        if len(results) != len(expected):
            return False
        for result in results:
            data = result['json']['data']['data']
            if any(not isinstance(data.get(field), str) or not data[field] for field in expected[result['item']]):
                return False
        return True
    except (KeyError, TypeError):
        return False


class FilterModule:
    def filters(self):
        return {'application_vault_retained_policy': retained_policy, 'application_vault_document_cache': document_cache, 'application_vault_verify_fields': verify_fields, 'application_vault_role_changed': role_changed, 'application_vault_source_cache': source_cache, 'application_kv_delta': delta, 'application_vault_cidrs': cidrs}

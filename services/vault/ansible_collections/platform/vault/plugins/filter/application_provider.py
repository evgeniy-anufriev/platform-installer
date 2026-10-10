"""Bounded pure reconciliations consumed by builtin uri tasks."""
import ipaddress
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


def cidrs(routes):
    try:
        return sorted({'127.0.0.1/32'} | {str(ipaddress.IPv4Network(item[0]['prefsrc']+'/24', strict=False)) for item in routes})
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
        return {'application_vault_document_cache': document_cache, 'application_vault_verify_fields': verify_fields, 'application_vault_role_changed': role_changed, 'application_vault_source_cache': source_cache, 'application_kv_delta': delta, 'application_vault_cidrs': cidrs}

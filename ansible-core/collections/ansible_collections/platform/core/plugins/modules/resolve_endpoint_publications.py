#!/usr/bin/python
"""Batch the existing endpoint/DNS resolvers without changing their rules."""
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.platform.core.plugins.module_utils.service_integration_resolution import resolve_service_integrations
from ansible_collections.platform.core.plugins.module_utils.service_endpoint_resolution import resolve_service_endpoints
from ansible_collections.platform.core.plugins.module_utils.dns_resolution import resolve_dns_zones


def resolve_batch(desired_state, service_catalog, inventory_hosts, inventory_deployments,
                  endpoint_sources, source_ids):
    known = set(desired_state.get('serviceDeployments', {})) | set(endpoint_sources)
    if not source_ids or any(not isinstance(s, str) or s not in known for s in source_ids):
        raise ValueError('APPLICATION_ENDPOINT_SCOPE_INVALID')
    sources = sorted(set(source_ids))
    projections = {s: resolve_service_integrations(desired_state, [], s,
        inventory_deployments, endpoint_sources=endpoint_sources)['integrations'] for s in sources}
    with_dns = [s for s in sources if projections[s]['dnsDeployments']]
    endpoints = dict(endpoints={}, hostEndpoints={})
    dns = dict(zones={})
    if with_dns:
        endpoints = resolve_service_endpoints(desired_state, service_catalog,
            inventory_deployments=inventory_deployments, deployment_ids=with_dns, endpoint_sources=endpoint_sources)
        if endpoints['status'] != 'PASS':
            return dict(status='BLOCKED', findings=endpoints['findings'], sources=[])
        dns = resolve_dns_zones(desired_state, service_catalog, inventory_hosts, inventory_deployments,
                               True, with_dns, False, endpoint_sources=endpoint_sources)
        if dns['status'] != 'PASS':
            return dict(status='BLOCKED', findings=dns['findings'], sources=[])
    result = []
    for source in sources:
        projection = projections[source]
        names = []
        if source in with_dns:
            if source in endpoints['endpoints']:
                names.append(endpoints['endpoints'][source]['fqdn'])
            names.extend(e['fqdn'] for e in endpoints['hostEndpoints'].values()
                         if e['serviceDeploymentId'] == source)
        records = []
        for provider in projection['dnsDeployments']:
            zone = dns['zones'][provider]
            for name in names:
                matches = [r for r in zone['records'] if r['owner'] == name + '.']
                if len(matches) == 1:
                    records.append(dict(bindDeploymentId=provider, zone=zone['zone'], owner=name + '.',
                                        addresses=matches[0]['values'], ttl=zone['defaultTtl']))
        normalized = endpoint_sources.get(source, {})
        if normalized:
            names = [normalized['endpoint']['fqdn']]
        expected = sorted(set(normalized.get('expectedAddresses', [])))
        if not expected:
            owners = {n.rstrip('.') + '.' for n in names}
            expected = sorted({a for r in records if r['owner'] in owners for a in r['addresses']})
        result.append(dict(sourceId=source, projection=projection, dnsRecords=records, fqdns=names,
                           probe=normalized.get('probe', {}), expectedAddresses=expected))
    return dict(status='PASS', findings=[], sources=result)


def main():
    module = AnsibleModule(argument_spec=dict(
        desired_state=dict(type='dict', required=True), service_catalog=dict(type='dict', required=True),
        inventory_hosts=dict(type='dict', required=True), inventory_deployments=dict(type='dict', required=True),
        endpoint_sources=dict(type='dict', default={}), source_ids=dict(type='list', elements='str', required=True)),
        supports_check_mode=True)
    try:
        result = resolve_batch(**module.params)
        if result['status'] != 'PASS':
            module.fail_json(msg='APPLICATION_ENDPOINT_RESOLUTION_BLOCKED', **result)
        module.exit_json(changed=False, **result)
    except (KeyError, TypeError, ValueError):
        module.fail_json(msg='APPLICATION_ENDPOINT_SCOPE_INVALID')


if __name__ == '__main__':
    main()

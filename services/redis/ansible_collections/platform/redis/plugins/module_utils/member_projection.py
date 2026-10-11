"""Service-owned Redis allocation, shared by infrastructure and app hooks."""
import re


def project_members(instances, deployment, settings):
    result = []
    for slot, source in enumerate(sorted(instances, key=lambda item: item['id'])):
        member = dict(source, slot=slot)
        for name, base in [('redis_port', 'port'), ('sentinel_port', 'sentinel_port')]:
            port = int(settings[base]) + slot
            if not 1 <= port <= 65535:
                raise ValueError('REDIS_LISTENER_PORT_INVALID')
            member[name] = port
        member.update(instance_name=deployment + '-' + source['id'].rsplit('-', 1)[-1],
                      legacy_instance_name=re.sub(r'[^A-Za-z0-9_.-]', '_', source['id']))
        for kind in ('data', 'config', 'log'):
            if kind + '_root' in settings:
                member[kind + '_directory'] = settings[kind + '_root'] + '/' + source['id']
        result.append(member)
    return result

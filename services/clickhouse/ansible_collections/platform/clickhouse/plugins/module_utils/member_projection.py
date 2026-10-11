"""Service-owned ClickHouse host-local allocation; no target discovery."""
import hashlib


def project_members(instances, deployment, settings):
    result, ordinals = [], {}
    for slot, source in enumerate(sorted(instances, key=lambda item: item['id'])):
        ordinal = ordinals.get(source['host'], 0)
        ordinals[source['host']] = ordinal + 1
        member = dict(source, slot=slot + 1, host_ordinal=ordinal)
        for name, base in [('https_port', 'port'), ('native_port', 'native_port'),
                           ('interserver_port', 'interserver_port'),
                           ('keeper_client_port', 'keeper_client_port'),
                           ('keeper_raft_port', 'keeper_raft_port')]:
            if base not in settings:
                continue
            port = int(source['port']) if name == 'https_port' and 'port' in source else int(settings[base]) + ordinal
            if not 1 <= port <= 65535:
                raise ValueError('CLICKHOUSE_LISTENER_PORT_INVALID')
            member[name] = port
        unit_id = hashlib.sha256((deployment + '\n' + source['id']).encode()).hexdigest()
        member['unit_id'] = unit_id
        for kind in ('server', 'keeper'):
            member[kind + '_unit_name'] = 'platform-clickhouse-' + kind + '@' + deployment + '-' + source['id'].rsplit('-', 1)[-1] + '.service'
            member['legacy_' + kind + '_unit_name'] = 'platform-clickhouse-' + kind + '-' + unit_id[:16] + '.service'
        for kind in ('config', 'data', 'log'):
            if kind + '_root' in settings:
                member[kind + '_directory'] = settings[kind + '_root'] + '/' + deployment + '/' + source['id']
        result.append(member)
    return result

from ansible_collections.platform.redis.plugins.module_utils.member_projection import project_members


def application_preflight_batches(accounts):
    groups = {}
    for account in accounts:
        for target in account['candidates']:
            key = (target['hostId'], target['memberId'], target['address'], target['port'],
                   account['listener'], account['adminPasswordRef'])
            groups.setdefault(key, dict(target=target, listener=account['listener'],
                                        adminPasswordRef=account['adminPasswordRef'], accounts=[]))['accounts'].append(account)
    return [dict(group, accounts=group['accounts'][offset:offset + 100])
            for group in groups.values() for offset in range(0, len(group['accounts']), 100)]


class FilterModule:
    def filters(self):
        return {'platform_redis_members': project_members,
                'application_preflight_batches': application_preflight_batches}

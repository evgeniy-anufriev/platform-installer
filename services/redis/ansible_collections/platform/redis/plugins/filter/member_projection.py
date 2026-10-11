from ansible_collections.platform.redis.plugins.module_utils.member_projection import project_members


class FilterModule:
    def filters(self):
        return {'platform_redis_members': project_members}

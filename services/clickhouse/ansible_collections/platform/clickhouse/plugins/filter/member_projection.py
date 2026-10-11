from ansible_collections.platform.clickhouse.plugins.module_utils.member_projection import project_members


class FilterModule:
    def filters(self):
        return {'platform_clickhouse_members': project_members}

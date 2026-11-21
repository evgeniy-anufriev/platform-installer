from ansible_collections.platform.clickhouse.plugins.module_utils.member_projection import project_members


def application_preflight_jobs(inputs):
    """Share a catalog read across the scopes of one ClickHouse deployment."""
    jobs = []
    for job in inputs['jobs']:
        if job['serviceType'] != 'clickhouse':
            continue
        # Keep the existing scope limit without restricting larger deployments.
        if len(job['databases']) > 128 or len(job['accounts']) > 128:
            jobs.extend(scope for scope in inputs['libraryJobs'] + inputs['instanceJobs']
                        if scope['providerId'] == job['providerId'])
        else:
            jobs.append(job)
    return jobs


class FilterModule:
    def filters(self):
        return {'platform_clickhouse_members': project_members,
                'application_preflight_jobs': application_preflight_jobs}

"""Resolve versioned package scripts from the existing application projection."""
try:
    from .application_endpoints import placement_target
    from .application_libraries import checked_file
except ImportError:
    from application_endpoints import placement_target
    from application_libraries import checked_file


def _scalar(value):
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (str, int, float)):
        return str(value)
    raise ValueError('APPLICATION_SCRIPT_REFERENCE_INVALID')


def _instance(library, name):
    matches = [(instance_id, value) for instance_id, value in library['instances'].items()
               if value['applicationName'] == name]
    if len(matches) != 1:
        raise ValueError('APPLICATION_SCRIPT_REFERENCE_INVALID')
    return matches[0]


def _argument(argument, job, library, hosts, desired):
    if isinstance(argument, str):
        return argument
    source = argument['valueFrom']
    if source == 'applicationId':
        return job['instanceId']
    if source == 'projectId':
        return job['projectId']
    if source == 'libraryId':
        return job['libraryId']
    if source == 'targetHostId':
        return job['hostId']
    if source == 'parameter':
        name = argument['name']
        if name not in job['settings'].get('parameters', {}):
            raise ValueError('APPLICATION_SCRIPT_REFERENCE_INVALID')
        return _scalar(job['settings']['parameters'][name])
    if source in ('placement_https', 'endpoint'):
        name = argument.get('application', argument.get('name'))
        instance_id, instance = _instance(library, name)
        placement = instance['placements'].get(job['hostId'])
        if placement is None:
            raise ValueError('APPLICATION_SCRIPT_TARGET_INVALID')
        if source == 'endpoint':
            endpoint = placement.get('endpoint', {})
            group = desired.get('endpointGroups', {}).get(endpoint.get('endpoint_group'), {})
            domain = group.get('address', {}).get('domain')
            if not endpoint.get('enabled') or not domain:
                raise ValueError('APPLICATION_SCRIPT_REFERENCE_INVALID')
            return endpoint.get('protocol', 'http') + '://' + instance_id + '.' + domain
        target = placement_target(placement, job['hostId'], hosts)
        if placement.get('endpoint', {}).get('protocol') != 'https':
            raise ValueError('APPLICATION_SCRIPT_HTTPS_PLACEMENT_REQUIRED')
        return 'https://' + target['address'] + ':' + str(target['port'])
    if source == 'connection':
        connection = library['instances'][job['instanceId']]['connections'].get(argument['name'], {})
        targets = connection.get('targets', [])
        local = [target for target in targets if target['hostId'] == job['hostId']]
        target = local[0] if len(local) == 1 else targets[0] if len(targets) == 1 else None
        if target is None or 'address' not in target or 'port' not in target:
            raise ValueError('APPLICATION_SCRIPT_REFERENCE_INVALID')
        return str(target['address']) + ':' + str(target['port'])
    raise ValueError('APPLICATION_SCRIPT_REFERENCE_INVALID')


def prepare_script_jobs(root, snapshot, desired, rows, jobs):
    if not any(job.get('packageApplicationScripts') or job.get('packageLibraryScripts') for job in jobs):
        for job in jobs:
            job.pop('packageApplicationScripts', None)
            job.pop('packageLibraryScripts', None)
            job['scripts'] = []
        return jobs
    libraries = snapshot['applicationLibraries']['libraries']
    hosts = {host: {'ansible_host': value['ansibleHost']} for host, value in snapshot['hosts'].items()}
    for job in jobs:
        if 'projectId' not in job and 'project' in snapshot:
            job['projectId'] = snapshot['project']['id']
        library = libraries[job['libraryId']]
        instance = library['instances'][job['instanceId']]
        app_scripts = job.pop('packageApplicationScripts')
        lib_scripts = job.pop('packageLibraryScripts')
        if {item['id'] for item in app_scripts} & {item['id'] for item in lib_scripts}:
            raise ValueError('APPLICATION_SCRIPT_ID_CONFLICT')
        declarations = [(item, 'instance', job['applicationPackagePath']) for item in app_scripts]
        library_hosts = {host for member in library['instances'].values() for host in member['placements']}
        library_instance_for_host = min(instance_id for instance_id, member in library['instances'].items()
                                        if job['hostId'] in member['placements'])
        if job['instanceId'] == library_instance_for_host:
            declarations.extend((item, 'library', job['libraryPackagePath']) for item in lib_scripts)
        scripts = []
        for script, scope, package_path in declarations:
            eligible = sorted(instance['placements'] if scope == 'instance' else library_hosts)
            if not eligible:
                raise ValueError('APPLICATION_SCRIPT_TARGET_INVALID')
            selected = eligible[0] if script.get('execution', 'each_target') == 'once' else job['hostId']
            if job['hostId'] != selected:
                continue
            scripts.append(dict(id=script['id'], phase=script['phase'], scope=scope,
                                path=checked_file(root, package_path + '/' + script['source']),
                                argv=[_argument(value, job, library, hosts, desired) for value in script.get('argv', [])],
                                secretInputs={name: value['ref'] for name, value in script.get('secretInputs', {}).items()}))
        job['scripts'] = scripts
    return jobs

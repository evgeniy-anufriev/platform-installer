"""Resolve versioned package scripts from the existing application projection."""
import json
try:
    from .application_endpoints import placement_target, public_endpoint_url
    from .application_libraries import checked_file
    from .application_connections import active_script, script_secret_source, script_secret_reference, connection_callback
except ImportError:
    from application_endpoints import placement_target, public_endpoint_url
    from application_libraries import checked_file
    from application_connections import active_script, script_secret_source, script_secret_reference, connection_callback


def _scalar(value):
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (str, int, float)):
        return str(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    raise ValueError('APPLICATION_SCRIPT_REFERENCE_INVALID')


def _instance(library, name):
    matches = [(instance_id, value) for instance_id, value in library['instances'].items()
               if value['applicationName'] == name]
    if len(matches) != 1:
        raise ValueError('APPLICATION_SCRIPT_REFERENCE_INVALID')
    return matches[0]


def _argument(argument, job, library, hosts, desired, provider_library=None):
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
        if source == 'endpoint' and name is None:
            return public_endpoint_url(job['instanceId'], job['settings'], desired)
        instance_id, instance = _instance(library, name)
        placement = instance['placements'].get(job['hostId'])
        if placement is None:
            raise ValueError('APPLICATION_SCRIPT_TARGET_INVALID')
        if source == 'endpoint':
            return public_endpoint_url(instance_id, placement, desired)
        target = placement_target(placement, job['hostId'], hosts)
        if placement.get('endpoint', {}).get('protocol') != 'https':
            raise ValueError('APPLICATION_SCRIPT_HTTPS_PLACEMENT_REQUIRED')
        return 'https://' + target['address'] + ':' + str(target['port'])
    if source in ('connection', 'provided_connection'):
        connection = ((provider_library or library).get('providedConnections', {}).get(argument['name'], {}) if source == 'provided_connection'
                      else library['instances'][job['instanceId']]['connections'].get(argument['name'], {}))
        if 'field' in argument:
            parts = argument['field'].split('.')
            if parts[0] == 'credentials':
                credential = connection.get('credentials', {}).get(parts[1] if len(parts) > 1 else '', {})
                if (len(parts) != 4 or parts[2:] != ['source', 'value'] or credential.get('sensitive', True)
                        or credential.get('source', {}).get('kind') != 'literal'):
                    raise ValueError('APPLICATION_SCRIPT_SECRET_ARGUMENT_FORBIDDEN')
                return _scalar(credential['source']['value'])
            value = connection
            for part in parts:
                if part == 'credentials':
                    raise ValueError('APPLICATION_SCRIPT_SECRET_ARGUMENT_FORBIDDEN')
                value = value[part]
            return _scalar(value)
        if connection.get('url'):
            return connection['url']
        targets = connection.get('targets', [])
        local = [target for target in targets if target['hostId'] == job['hostId']]
        target = local[0] if len(local) == 1 else targets[0] if len(targets) == 1 else None
        if target is None or 'address' not in target or 'port' not in target:
            raise ValueError('APPLICATION_SCRIPT_REFERENCE_INVALID')
        return str(target['address']) + ':' + str(target['port'])
    if source == 'account_batch':
        return _scalar(job['accountBatch'])
    raise ValueError('APPLICATION_SCRIPT_REFERENCE_INVALID')


def prepare_script_jobs(root, snapshot, desired, rows, jobs):
    libraries = snapshot['applicationLibraries']['libraries']
    if (not any(job.get('packageApplicationScripts') or job.get('packageLibraryScripts') for job in jobs)
            and not any(connection.get('connectionProvisioner') for library in libraries.values()
                        for instance in library['instances'].values() for connection in instance.get('connections', {}).values())):
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
        app_scripts = job.pop('packageApplicationScripts', [])
        lib_scripts = job.pop('packageLibraryScripts', [])
        if {item['id'] for item in app_scripts} & {item['id'] for item in lib_scripts}:
            raise ValueError('APPLICATION_SCRIPT_ID_CONFLICT')
        declarations = [(item, 'instance', job['applicationPackagePath']) for item in app_scripts]
        for item in lib_scripts:
            eligible_instances = sorted(instance_id for instance_id, member in library['instances'].items()
                                        if job['hostId'] in member['placements'] and active_script(item, member))
            if eligible_instances and job['instanceId'] == eligible_instances[0]:
                declarations.append((item, 'library', job['libraryPackagePath']))
        scripts = []
        for script, scope, package_path in declarations:
            if not active_script(script, instance):
                continue
            eligible = sorted(instance['placements'] if scope == 'instance' else {
                host for member in library['instances'].values() if active_script(script, member)
                for host in member['placements']})
            if not eligible:
                raise ValueError('APPLICATION_SCRIPT_TARGET_INVALID')
            selected = eligible[0] if script.get('target') or script.get('execution', 'each_target') == 'once' else job['hostId']
            if job['hostId'] != selected:
                continue
            secret_inputs = {}
            for name, source in script.get('secretInputs', {}).items():
                value = script_secret_source(source, library, instance)
                if value is None and source.get('optional', False):
                    continue
                secret_inputs[name] = script_secret_reference(value)
            targets = [None]
            if script.get('target'):
                connection = instance['connections'][script['target']['connection']]
                if connection.get('serviceType') != 'application':
                    raise ValueError('APPLICATION_SCRIPT_TARGET_INVALID')
                target_hosts = sorted({item['hostId'] for item in connection['targets']})
                if not target_hosts:
                    raise ValueError('APPLICATION_SCRIPT_TARGET_INVALID')
                if script.get('execution', 'each_target') == 'once':
                    target_hosts = target_hosts[:1]
                targets = [dict(libraryId=connection['libraryId'], instanceId=connection['applicationId'],
                                hostId=host) for host in target_hosts]
            if script['phase'] == 'provider_prepare' and targets == [None]:
                raise ValueError('APPLICATION_SCRIPT_TARGET_REQUIRED')
            for target in targets:
                argument_job = dict(job, hostId=target['hostId']) if target else job
                scripts.append(dict(id=script['id'], phase=script['phase'], order=script.get('order', 0), scope=scope,
                                path=checked_file(root, package_path + '/' + script['source']),
                                argv=[_argument(value, argument_job, library, hosts, desired) for value in script.get('argv', [])],
                                secretInputs=secret_inputs, target=target, runOn=script.get('run_on', 'target'),
                                targetConnection=script.get('target', {}).get('connection'),
                                sharedInputs=[value['name'] for value in script.get('secretInputs', {}).values()
                                              if value.get('valueFrom') == 'library_secret']))
        job['scripts'] = scripts
    for job in jobs:
        library = libraries[job['libraryId']]
        instance = library['instances'][job['instanceId']]
        if job['hostId'] != min(instance['placements']):
            continue
        for alias, connection in instance.get('connections', {}).items():
            if connection.get('serviceType') != 'application' or not connection.get('connectionProvisioner'):
                continue
            provider, _, callback = connection_callback(libraries, connection)
            provider_job = min((item for item in jobs if item['libraryId'] == connection['libraryId']
                                and item['instanceId'] == connection['applicationId']), key=lambda item: item['hostId'])
            secret_inputs, shared_inputs = {}, []
            for key, source in callback.get('secretInputs', {}).items():
                value = script_secret_source(source, library, instance, provider)
                if value is None and source.get('optional', False):
                    continue
                secret_inputs[key] = script_secret_reference(value)
                if source.get('valueFrom') == 'library_secret':
                    shared_inputs.append(source['name'])
                elif source.get('valueFrom') == 'secret_binding':
                    binding = instance['secretBindings'][source['binding']]['source']
                    if 'library_secret' in binding:
                        shared_inputs.append(binding['library_secret'])
            identifier = alias + '.' + callback['id']
            if any(item['id'] == identifier for item in job['scripts']):
                raise ValueError('APPLICATION_SCRIPT_ID_CONFLICT')
            job['scripts'].append(dict(id=identifier, phase='provider_prepare', order=callback.get('order', 0),
                scope='instance', path=checked_file(root, provider_job['applicationPackagePath'] + '/' + callback['source']),
                argv=[_argument(value, dict(job, hostId=provider_job['hostId']), library, hosts, desired, provider)
                      for value in callback.get('argv', [])],
                secretInputs=secret_inputs, sharedInputs=shared_inputs, targetConnection=alias, runOn=callback.get('run_on', 'target'),
                target=dict(libraryId=connection['libraryId'], instanceId=connection['applicationId'], hostId=provider_job['hostId'])))
    return jobs

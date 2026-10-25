"""Application-provided connections from native Ansible-resolved values only."""
import copy
import hashlib
try:
    from .application_endpoints import public_endpoint_url
except ImportError:
    from application_endpoints import public_endpoint_url


def enabled(settings, name):
    return settings.get('connections', {}).get(name, {}).get('enabled', True)


def active_script(script, instance):
    if script.get('phase') in ('account_apply', 'connection_apply'):
        return False  # On-demand provider callback, never a lifecycle invocation.
    return all(name in instance.get('connections', {}) for name in script.get('requires_connections', []))


def library_script_hosts(library, instance_id, script):
    """Placements where this instance represents the library script."""
    return [host for host in sorted(library['instances'][instance_id]['placements'])
            if instance_id == min((name for name, member in library['instances'].items()
                                   if host in member['placements'] and active_script(script, member)), default=None)]


def script_secret_source(source, library, instance, provider_library=None):
    kind = source.get('valueFrom', 'runtime_secret')
    if kind == 'runtime_secret':
        return dict(kind='runtime_secret_ref', ref=source['ref'])
    if kind == 'library_secret':
        return library['sharedSecretRequirements'][source['name']]['source']
    if kind == 'connection':
        return instance['connections'][source['name']]['credentials'][source['credential']]['source']
    if kind == 'provided_connection':
        return (provider_library or library)['providedConnections'][source['name']]['credentials'][source['credential']]['source']
    if kind == 'secret_binding':
        binding = instance.get('secretBindings', {}).get(source['binding'])
        if binding is None and source.get('optional', False):
            return None
        value = binding['source']
        if 'library_secret' in value:
            return library['sharedSecretRequirements'][value['library_secret']]['source']
        return instance['credentialRequirements'][value['account']]['credentials'][value['field']]['source']
    if kind == 'account_batch':
        return None
    raise ValueError('APPLICATION_SCRIPT_REFERENCE_INVALID')


def connection_callback(libraries, connection):
    library = libraries[connection['libraryId']]
    instance = library['instances'][connection['applicationId']]
    matches = [script for script in instance.get('scripts', [])
               if script['id'] == connection['connectionProvisioner']['apply_script']
               and script['phase'] == 'connection_apply' and script.get('execution') == 'once']
    if len(matches) != 1:
        raise ValueError('APPLICATION_CONNECTION_CALLBACK_INVALID')
    return library, instance, matches[0]


def script_secret_reference(source):
    if source and source['kind'] == 'runtime_secret_ref':
        return source['ref']
    if source and source['kind'] == 'vault_ref':
        return 'pla-vault-' + hashlib.sha256(repr(sorted(source.items())).encode()).hexdigest()[:32]
    raise ValueError('APPLICATION_SCRIPT_CREDENTIAL_SOURCE_UNSUPPORTED')


def used_script_sources(libraries, selected_libraries=None, provider_libraries=()):
    """Resolve credential custody in its declaring library, including exports."""
    result = {}
    declarations = []
    for library_id, library in libraries.items():
        if selected_libraries is not None and library_id not in selected_libraries:
            for instance in (library['instances'].values() if library_id in provider_libraries else []):
                declarations.extend((library_id, library, instance, script, None)
                                    for script in library.get('scripts', []) + instance.get('scripts', [])
                                    if script['phase'] == 'integration_apply' and active_script(script, instance))
            continue
        for instance in library['instances'].values():
            declarations.extend((library_id, library, instance, script, None)
                                for script in library.get('scripts', []) + instance.get('scripts', [])
                                if active_script(script, instance))
            for connection in instance.get('connections', {}).values():
                if connection.get('serviceType') == 'application' and connection.get('connectionProvisioner'):
                    provider, _, callback = connection_callback(libraries, connection)
                    declarations.append((library_id, library, instance, callback, provider))
            for alias in instance.get('credentialRequirements', {}):
                connection = instance.get('connections', {}).get(alias, {})
                if connection.get('serviceType') != 'application' or not connection.get('accountProvisioner'):
                    continue
                owner_id = connection['libraryId']
                owner = libraries[owner_id]
                provider = owner['instances'][connection['applicationId']]
                declarations.extend((owner_id, owner, provider, script, None) for script in provider.get('scripts', [])
                                    if script['id'] == connection['accountProvisioner']['apply_script'] and script['phase'] == 'account_apply')
    for library_id, library, instance, script, provider_library in declarations:
        for source in script.get('secretInputs', {}).values():
            value = script_secret_source(source, library, instance, provider_library)
            owner = (instance['connections'][source['name']]['libraryId']
                     if source.get('valueFrom') == 'connection'
                     and instance['connections'][source['name']].get('serviceType') == 'application' else library_id)
            if provider_library and source.get('valueFrom') == 'provided_connection':
                owner = next(key for key, value in libraries.items() if value is provider_library)
            if value and value not in result.setdefault(owner, []):
                result[owner].append(value)
    return result


def provided_connections(rows, desired, hosts):
    result = {}
    for row in rows:
        library = row['libraryId']
        declarations = row.get('providedConnections', {})
        peers = [item for item in rows if item['libraryId'] == library]
        for name, declaration in declarations.items():
            matches = [item for item in peers if item['slotId'] == declaration['application']]
            if not matches:
                continue
            first = matches[0]
            endpoint = first['settings'].get('endpoint', {})
            ports = first['settings'].get('ports', {})
            group = desired.get('endpointGroups', {}).get(endpoint.get('endpoint_group'), {})
            domain = group.get('address', {}).get('domain')
            protocol = declaration['protocol']
            if (not endpoint.get('enabled') or not domain
                    or endpoint.get('listener') not in ports):
                continue
            if protocol != 'https':
                raise ValueError('APPLICATION_PROVIDED_CONNECTION_PROTOCOL_UNSUPPORTED')
            targets = []
            for peer in matches:
                ep = peer['settings'].get('endpoint', {})
                if ep != endpoint:
                    raise ValueError('APPLICATION_PROVIDED_CONNECTION_HOST_CONFLICT')
                target_port = peer['settings']['ports'][ep['listener']]['published']
                targets.append(dict(hostId=peer['hostId'], address=hosts[peer['hostId']]['ansibleHost'],
                                    port=target_port, protocol=endpoint.get('protocol', 'http')))
            value = dict(libraryId=library, applicationId=first['instanceId'], slotId=first['slotId'],
                         name=name, protocol=protocol, serviceType='application',
                         url=public_endpoint_url(first['instanceId'], first['settings'], desired),
                         parameters=copy.deepcopy(declaration.get('parameters', {})),
                         credentials=copy.deepcopy(declaration.get('credentials', {})),
                         accountProvisioner=copy.deepcopy(declaration.get('account_provisioner', {})),
                         connectionProvisioner=copy.deepcopy(declaration.get('connection_provisioner', {})),
                         startupPriority=first.get('startupPriority', 100),
                         targets=sorted(targets, key=lambda item: item['hostId']))
            previous = result.setdefault(library, {}).setdefault(name, value)
            if previous != value:
                raise ValueError('APPLICATION_PROVIDED_CONNECTION_HOST_CONFLICT')
    return result


def application_connection(binding, declaration, exports):
    reference = binding['providedConnectionRef']
    connection = copy.deepcopy(exports.get(reference['libraryId'], {}).get(reference['name']))
    if not connection or declaration.get('protocol', connection['protocol']) != connection['protocol']:
        raise ValueError('APPLICATION_PROVIDED_CONNECTION_INVALID')
    return connection


def connection_order_findings(libraries, order):
    """Explicit order/scope checks; never discover dependencies from template text."""
    findings = []
    positions = {name: index for index, name in enumerate(order)}
    for library_id, library in libraries.items():
        for instance_id, instance in library.get('instances', {}).items():
            for name, connection in instance.get('connections', {}).items():
                if connection.get('serviceType') != 'application':
                    continue
                provider = connection['libraryId']
                field = 'applicationLibraryDeployments.%s.applications.%s.connections.%s' % (
                    library_id, instance.get('slotId', instance_id), name)
                if provider == library_id:
                    valid = (connection['applicationId'] != instance_id and
                             connection['startupPriority'] < instance.get('startupPriority', 100))
                else:
                    valid = provider in positions and library_id in positions and positions[provider] < positions[library_id]
                if not valid:
                    findings.append((field, provider))
            for script in library.get('scripts', []) + instance.get('scripts', []):
                if script.get('phase') != 'provider_prepare' or not active_script(script, instance):
                    continue
                target = instance.get('connections', {}).get(script.get('target', {}).get('connection'), {})
                if target.get('serviceType') != 'application':
                    findings.append(('applicationLibraryDeployments.%s.scripts.%s' % (library_id, script['id']), library_id))
                    continue
                target_position = (positions.get(target['libraryId'], -1), target.get('startupPriority', 100))
                for alias in script.get('requires_connections', []):
                    required = instance['connections'][alias]
                    if required.get('serviceType') != 'application':
                        continue
                    if (required['libraryId'], required['applicationId']) == (target['libraryId'], target['applicationId']):
                        continue
                    position = (positions.get(required['libraryId'], -1), required.get('startupPriority', 100))
                    if position >= target_position:
                        findings.append(('applicationLibraryDeployments.%s.scripts.%s' % (library_id, script['id']), required['libraryId']))
    return findings

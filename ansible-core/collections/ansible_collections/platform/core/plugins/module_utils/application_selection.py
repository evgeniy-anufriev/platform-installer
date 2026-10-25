"""Invocation-only library selection. The complete project remains authoritative."""
import copy


def execution_scope(snapshot, library_order=None, skipped=None):
    libraries = snapshot.get('applicationLibraries', {}).get('libraries', {})
    order = sorted(libraries) if library_order is None else library_order
    skipped = [] if skipped is None else skipped
    if (not isinstance(order, list) or any(not isinstance(item, str) for item in order)
            or len(order) != len(set(order)) or set(order) != set(libraries)):
        raise ValueError('APPLICATION_LIBRARY_ORDER_INVALID')
    if (not isinstance(skipped, list) or any(not isinstance(item, str) for item in skipped)
            or len(skipped) != len(set(skipped)) or set(skipped) - set(libraries)):
        raise ValueError('APPLICATION_LIBRARY_SELECTION_INVALID')
    installed = [key for key in order if key not in skipped]
    consumers = {library_id + '/' + instance_id
                 for library_id in installed for instance_id in libraries[library_id].get('instances', {})}
    providers = set()
    for library_id in installed:
        for instance in libraries[library_id].get('instances', {}).values():
            for connection in instance.get('connections', {}).values():
                if connection.get('serviceType') == 'application':
                    owner, identity = connection['libraryId'], connection['applicationId']
                    # Connections have already been validated by the resolver. Scope
                    # projection does not introduce a second connection validator.
                    providers.add(owner + '/' + identity)
    return dict(libraryOrder=list(order), skippedLibraries=sorted(skipped),
                installLibraries=installed, consumerInstances=sorted(consumers),
                providerInstances=sorted(providers),
                providerLibraries=[key for key in order if any(item.startswith(key + '/') for item in providers)])


def scope_for(snapshot):
    return snapshot.get('applicationExecutionScope') or execution_scope(snapshot)


def scoped_snapshot(snapshot, scope):
    """Attach execution facts without removing provider definitions from the snapshot."""
    result = dict(snapshot)
    result['applicationExecutionScope'] = copy.deepcopy(scope)
    return result


def selected_rows(rows, scope):
    return [row for row in rows if row['libraryId'] in scope['installLibraries']]


def integration_consumers(snapshot, provider_library_id, desired=None):
    """Nonsecret, selected endpoint/parameter metadata for package integration hooks."""
    libraries = snapshot.get('applicationLibraries', {}).get('libraries', {})
    scope = scope_for(snapshot)
    result = []
    for library_id in scope['installLibraries']:
        for instance_id, instance in sorted(libraries[library_id].get('instances', {}).items()):
            aliases = sorted(alias for alias, connection in instance.get('connections', {}).items()
                             if connection.get('serviceType') == 'application'
                             and connection['libraryId'] == provider_library_id)
            if not aliases:
                continue
            placements = {host: {key: copy.deepcopy(placement.get(key, {}))
                                 for key in ('endpoint', 'parameters')}
                          for host, placement in sorted(instance.get('placements', {}).items())}
            if desired is not None:
                try:
                    from .application_endpoints import public_endpoint_url
                except ImportError:
                    from application_endpoints import public_endpoint_url
                for placement in placements.values():
                    if placement.get('endpoint', {}).get('enabled'):
                        placement['endpointUrl'] = public_endpoint_url(instance_id, placement, desired)
            result.append(dict(libraryId=library_id, applicationId=instance_id,
                               connections=aliases, placements=placements))
    return result

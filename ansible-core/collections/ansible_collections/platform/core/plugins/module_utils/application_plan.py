"""Target-free application descriptors; image source selection stays in execution."""
import os
try:
    from .project_validation import canonical_digest
    from .application_libraries import finding, ID
    from .application_runtime import image_requirement
    from .application_images import selected_image, registry_request
    from .schema_validation import SchemaValidator
    from .application_connections import active_script, script_secret_source, connection_order_findings, connection_callback
except ImportError:
    from project_validation import canonical_digest
    from application_libraries import finding, ID
    from application_runtime import image_requirement
    from application_images import selected_image, registry_request
    from schema_validation import SchemaValidator
    from application_connections import active_script, script_secret_source, connection_order_findings, connection_callback

OPERATIONS = ['APPLICATION_LIBRARIES_APPLY', 'APPLICATION_LIBRARIES_VERIFY']
PLAN_VERSION = 'platform.installer/plan/v1alpha4'
MANIFEST_VERSION = 'platform.installer/execution-manifest/v1alpha2'


def application_execution_model(snapshot, image_lock=None, library_order=None):
    """Consume native resolved rows via the safe projection; never merge hostvars."""
    projection = snapshot.get('applicationLibraries', {})
    libraries = projection.get('libraries', {})
    requirements, secrets, findings = [], {}, []
    selected = sorted(libraries)
    if library_order is None:
        if len(selected) > 1:
            findings.append(finding('APPLICATION_LIBRARY_ORDER_REQUIRED', 'applicationLibraryOrder'))
        library_order = selected
    if (not isinstance(library_order, list) or len(library_order) != len(selected) or
            any(not isinstance(item, str) for item in library_order) or
            len(set(library_order)) != len(library_order) or set(library_order) != set(selected)):
        findings.append(finding('APPLICATION_LIBRARY_ORDER_INVALID', 'applicationLibraryOrder'))
        library_order = selected
    images = image_lock.get('images', {}) if isinstance(image_lock, dict) else {}
    for field, provider in connection_order_findings(libraries, library_order):
        item = finding('APPLICATION_PROVIDED_CONNECTION_ORDER_REQUIRED', field)
        item['safeDetails'] = {'providerLibraryId': provider}
        findings.append(item)
    contracts = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../../../../contracts'))
    invalid_lock = bool(libraries) and bool(SchemaValidator(contracts).validate(
        image_lock or {}, os.path.join(contracts, 'artifact-source/v1alpha2/' +
        ('prepared-images.schema.json' if (image_lock or {}).get('apiVersion') == 'platform.installer/container-images/v1alpha2' else 'image-lock.schema.json'))))
    if invalid_lock:
        findings.append(finding('APPLICATION_IMAGE_LOCK_INVALID', 'artifactLock.x-container-images'))
        images = {}

    def secret(source, library_id, placements, field, purpose='APPLICATION_SECRET', provider=None, scope=None, operations=None):
        if source.get('kind') != 'runtime_secret_ref':
            return
        ref = source.get('ref')
        if not isinstance(ref, str) or not ID.fullmatch(ref):
            findings.append(finding('APPLICATION_SECRET_REF_INVALID', field))
            return
        requested_operations = list(operations or OPERATIONS)
        # A runtime reference names one value across application and script consumers.
        key = (ref, scope)
        item = secrets.get(key)
        if item is None:
            item = dict(purpose=purpose, providerDeployment=provider,
                        runtimeReference=ref, applicationLibraries=[], hosts=[],
                        operations=requested_operations)
            secrets[key] = item
        elif item['purpose'] != purpose or item['providerDeployment'] != provider:
            findings.append(finding('APPLICATION_SECRET_REF_CONFLICT', field))
            return
        # One value can be consumed by both lifecycle and Apply-only callbacks.
        # Accumulate their declared uses, preserving the canonical operation order.
        item['operations'] = [operation for operation in OPERATIONS
                              if operation in item['operations'] or operation in requested_operations]
        identity = [item['purpose'], ref] if scope is None else [item['purpose'], ref, scope]
        item['requirementRef'] = 'application-secret-' + canonical_digest(identity).split(':')[1][:32]
        item['applicationLibraries'] = sorted(set(item['applicationLibraries']) | {library_id})
        item['hosts'] = sorted(set(item['hosts']) | set(placements))

    def registry_for(reference, library_id, instance_id, host):
        try:
            image = selected_image(image_lock or {}, reference, library_id, instance_id, host)
            if image is not None and not image.get('registry'):
                return None
            return registry_request(image['registry']['reference'] if image else reference)['registry']
        except ValueError:
            return registry_request(reference)['registry']  # The image finding still blocks execution.

    for library_id, library in sorted(libraries.items()):
        library_hosts = set()
        for instance_id, instance in sorted(library.get('instances', {}).items()):
            placements = sorted(instance.get('placements', {}))
            library_hosts.update(placements)
            field = 'applicationLibraryDeployments.%s.applications.%s' % (library_id, instance.get('slotId', instance_id))
            for script in instance.get('scripts', []):
                if not active_script(script, instance):
                    continue
                for name, source in script.get('secretInputs', {}).items():
                    value = script_secret_source(source, library, instance)
                    if value:
                        secret(value, library_id, placements,
                               field + '.scripts.' + script['id'] + '.secretInputs.' + name,
                               operations=['APPLICATION_LIBRARIES_APPLY'] if script.get('phase') == 'provider_prepare' else OPERATIONS)
            for alias, connection in instance.get('connections', {}).items():
                if connection.get('serviceType') != 'application' or not connection.get('connectionProvisioner'):
                    continue
                owner, _, callback = connection_callback(libraries, connection)
                for name, source in callback.get('secretInputs', {}).items():
                    value = script_secret_source(source, library, instance, owner)
                    if value:
                        provider_source = source.get('valueFrom') == 'provided_connection'
                        secret(value, connection['libraryId'] if provider_source else library_id,
                               sorted(target['hostId'] for target in connection['targets']) if provider_source else placements,
                               field + '.connections.' + alias + '.secretInputs.' + name,
                               operations=['APPLICATION_LIBRARIES_APPLY'])
            for host in placements:
                image_name = instance['placements'][host].get('imageRequirement', instance.get('imageRequirement', {})).get('image')
                try:
                    image = selected_image(image_lock or {}, image_name, library_id, instance_id, host)
                    requirement = image_requirement(instance_id + ':' + host, image_name, image)
                    requirements.append(dict(requirement, applicationLibrary=library_id, instanceId=instance_id,
                                             hosts=[host], sourcePolicy='REPOSITORY_THEN_OFFLINE'))
                except (ValueError, KeyError, TypeError):
                    findings.append(finding('APPLICATION_IMAGE_LOCK_INVALID', field + '.placements.' + host + '.image'))
            for registry, pair in library.get('registryCredentials', {}).items():
                registry_hosts = [host for host in placements if registry_for(
                    instance['placements'][host].get('imageRequirement', instance.get('imageRequirement', {})).get('image'), library_id, instance_id, host) == registry]
                if not registry_hosts:
                    continue
                for name in ('username', 'password'):
                    secret(pair[name]['source'], library_id, registry_hosts, field + '.registry_credentials.' + registry,
                           purpose='APPLICATION_REGISTRY_' + name.upper(), scope=library_id + ':' + registry)
            for name, account in sorted(instance.get('credentialRequirements', {}).items()):
                for credential, value in sorted(account.get('credentials', {}).items()):
                    secret(value['source'], library_id, placements, field + '.accounts.' + name + '.' + credential)
                connection = instance.get('connections', {}).get(name, {})
                if connection.get('serviceType') == 'application':
                    owner_library = libraries[connection['libraryId']]
                    owner_instance = owner_library['instances'][connection['applicationId']]
                    callback_id = connection['accountProvisioner']['apply_script']
                    callbacks = [item for item in owner_instance.get('scripts', [])
                                 if item['id'] == callback_id and item['phase'] == 'account_apply']
                    if len(callbacks) != 1:
                        findings.append(finding('APPLICATION_ACCOUNT_CALLBACK_INVALID', field + '.accounts.' + name))
                    else:
                        for key, source in callbacks[0].get('secretInputs', {}).items():
                            value = script_secret_source(source, owner_library, owner_instance)
                            if value:
                                secret(value, library_id, placements, field + '.accounts.' + name + '.' + key,
                                       operations=['APPLICATION_LIBRARIES_APPLY'])
            if instance.get('agentRequired') or any(c.get('source', {}).get('kind') == 'vault_ref'
                                                   for a in instance.get('credentialRequirements', {}).values()
                                                   for c in a.get('credentials', {}).values()):
                for connection in instance.get('connections', {}).values():
                    if connection.get('serviceType') == 'vault':
                        provider = connection['deploymentRef']
                        secret(dict(kind='runtime_secret_ref', ref='vault-admin-token-' + provider),
                               library_id, placements, field + '.vault_ref',
                               purpose='APPLICATION_VAULT_ADMIN_TOKEN', provider=provider)
        for name, value in sorted(library.get('sharedSecretRequirements', {}).items()):
            secret(value['source'], library_id, library_hosts,
                   'applicationLibraryDeployments.' + library_id + '.sharedSecrets.' + name)
        for script in library.get('scripts', []):
            selected = [instance for instance in library.get('instances', {}).values() if active_script(script, instance)]
            if not selected:
                continue
            for name, source in script.get('secretInputs', {}).items():
                value = script_secret_source(source, library, selected[0])
                if value:
                    secret(value, library_id, library_hosts,
                           'applicationLibraryDeployments.' + library_id + '.scripts.' + script['id'] + '.secretInputs.' + name,
                           operations=['APPLICATION_LIBRARIES_APPLY'] if script.get('phase') == 'provider_prepare' else OPERATIONS)
    actions = []
    targets = set()
    # Reuse resolved deployment hosts: provider hooks can discover any member.
    for library in libraries.values():
        for instance in library.get('instances', {}).values():
            targets.update(instance.get('placements', {}))
            for connection in instance.get('connections', {}).values():
                for target in connection.get('targets', []):
                    targets.add(target['hostId'])
    # Shared endpoint reconcile contacts its infrastructure placements too.
    targets.update(host for host, placements in snapshot.get('topology', {}).get('placementsByHost', {}).items()
                   if placements)
    if libraries:
        for index, action in enumerate(('apply', 'verify')):
            actions.append(dict(id='applications:' + action, type=OPERATIONS[index],
                                targets=sorted(targets),
                                dependsOn=['applications:apply'] if index else [],
                                mutating=index == 0, reboot='NONE',
                                summary=action.capitalize() + ' application libraries'))
    return dict(actions=actions, artifactRequirements=requirements,
                runtimeSecretRequirements=sorted(secrets.values(), key=lambda item: item['requirementRef']),
                libraryIds=list(library_order), findings=findings,
                semanticFingerprint=canonical_digest(dict(projection=projection, imageLock={} if invalid_lock else image_lock or {}, libraryOrder=library_order)))


def application_operation(action, model):
    """Closed private descriptor for the fixed controller, without credential values."""
    return dict(operationId=action['id'], phaseId='applications', operation=action['type'],
                targets=action['targets'], applicationLibraries=model['libraryIds'],
                applicationSemanticFingerprint=model['semanticFingerprint'])

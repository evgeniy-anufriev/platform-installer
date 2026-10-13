"""Target-free application descriptors; image source selection stays in execution."""
import os
try:
    from .project_validation import canonical_digest
    from .application_libraries import finding, ID
    from .application_runtime import image_requirement
    from .schema_validation import SchemaValidator
except ImportError:
    from project_validation import canonical_digest
    from application_libraries import finding, ID
    from application_runtime import image_requirement
    from schema_validation import SchemaValidator

OPERATIONS = ['APPLICATION_LIBRARIES_APPLY', 'APPLICATION_LIBRARIES_VERIFY']
PLAN_VERSION = 'platform.installer/plan/v1alpha4'
MANIFEST_VERSION = 'platform.installer/execution-manifest/v1alpha2'


def application_execution_model(snapshot, image_lock=None):
    """Consume native resolved rows via the safe projection; never merge hostvars."""
    projection = snapshot.get('applicationLibraries', {})
    libraries = projection.get('libraries', {})
    requirements, secrets, findings = [], {}, []
    images = image_lock.get('images', {}) if isinstance(image_lock, dict) else {}
    contracts = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../../../../contracts'))
    invalid_lock = bool(libraries) and bool(SchemaValidator(contracts).validate(
        image_lock or {}, os.path.join(contracts, 'artifact-source/v1alpha2/image-lock.schema.json')))
    if invalid_lock:
        findings.append(finding('APPLICATION_IMAGE_LOCK_INVALID', 'artifactLock.x-container-images'))
        images = {}

    def secret(source, library_id, placements, field, purpose='APPLICATION_SECRET', provider=None):
        if source.get('kind') != 'runtime_secret_ref':
            return
        ref = source.get('ref')
        if not isinstance(ref, str) or not ID.fullmatch(ref):
            findings.append(finding('APPLICATION_SECRET_REF_INVALID', field))
            return
        key = 'application-secret-' + canonical_digest([purpose, ref]).split(':')[1][:32]
        item = secrets.setdefault((purpose, ref), dict(requirementRef=key, purpose=purpose,
                                            providerDeployment=provider,
                                            runtimeReference=ref, applicationLibraries=[], hosts=[],
                                            operations=list(OPERATIONS)))
        item['applicationLibraries'] = sorted(set(item['applicationLibraries']) | {library_id})
        item['hosts'] = sorted(set(item['hosts']) | set(placements))

    for library_id, library in sorted(libraries.items()):
        library_hosts = set()
        for instance_id, instance in sorted(library.get('instances', {}).items()):
            placements = sorted(instance.get('placements', {}))
            library_hosts.update(placements)
            field = 'applicationLibraryDeployments.%s.applications.%s' % (library_id, instance.get('slotId', instance_id))
            for host in placements:
                image_name = instance['placements'][host].get('imageRequirement', instance.get('imageRequirement', {})).get('image')
                try:
                    requirement = image_requirement(instance_id + ':' + host, image_name, images.get(image_name))
                    requirements.append(dict(requirement, applicationLibrary=library_id, instanceId=instance_id,
                                             hosts=[host], sourcePolicy='REPOSITORY_THEN_OFFLINE'))
                except (ValueError, KeyError, TypeError):
                    findings.append(finding('APPLICATION_IMAGE_LOCK_INVALID', field + '.placements.' + host + '.image'))
            for name, account in sorted(instance.get('credentialRequirements', {}).items()):
                for credential, value in sorted(account.get('credentials', {}).items()):
                    secret(value['source'], library_id, placements, field + '.accounts.' + name + '.' + credential)
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
                libraryIds=sorted(libraries), findings=findings,
                semanticFingerprint=canonical_digest(dict(projection=projection, imageLock={} if invalid_lock else image_lock or {})))


def application_operation(action, model):
    """Closed private descriptor for the fixed controller, without credential values."""
    return dict(operationId=action['id'], phaseId='applications', operation=action['type'],
                targets=action['targets'], applicationLibraries=model['libraryIds'],
                applicationSemanticFingerprint=model['semanticFingerprint'])

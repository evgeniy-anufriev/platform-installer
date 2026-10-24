"""Provider batch dependency projection. No product APIs, scheduling or secrets."""
import hashlib


def instance_key(library_id, instance_id):
    return library_id + '/' + instance_id


def batch_id(connection):
    return 'provider-' + hashlib.sha256(('/'.join((connection['libraryId'], connection['applicationId'], connection['name']))).encode()).hexdigest()[:24]


def prepare_integrations(snapshot, jobs):
    libraries = snapshot['applicationLibraries']['libraries']
    batches, dependencies, shared = {}, {}, {}
    for library_id, library in libraries.items():
        for app_id, instance in library['instances'].items():
            consumer = instance_key(library_id, app_id)
            for alias, connection in instance.get('connections', {}).items():
                if connection.get('serviceType') != 'application':
                    continue
                key = batch_id(connection)
                batch = batches.setdefault(key, dict(id=key, providerLibraryId=connection['libraryId'],
                    providerInstanceId=connection['applicationId'], connection=connection, accounts=[], hooks=[]))
                account = instance.get('credentialRequirements', {}).get(alias)
                if account:
                    if not connection.get('accountProvisioner'):
                        raise ValueError('APPLICATION_ACCOUNT_CAPABILITY_UNSUPPORTED')
                    credentials = account['credentials']
                    if (set(credentials) != {'username', 'password'} or credentials['username']['source']['kind'] != 'literal'
                            or credentials['password']['source']['kind'] not in ('runtime_secret_ref', 'vault_ref')):
                        raise ValueError('APPLICATION_PROVIDER_CREDENTIAL_INVALID')
                    identity = consumer + '/' + alias
                    batch['accounts'].append(dict(id=identity, libraryId=library_id, instanceId=app_id,
                        alias=alias, mode=account['mode'], username=credentials['username']['source']['value'],
                        parameters=account.get('parameters', {}), passwordSource=credentials['password']['source']))
                    dependencies.setdefault(consumer, set()).add(key)
    seen_hooks = set()
    for job in jobs:
        consumer = instance_key(job['libraryId'], job['instanceId'])
        for script in job.get('scripts', []):
            if script['phase'] != 'provider_prepare':
                continue
            # The target alias identifies one exact export, even with multiple exports per instance.
            connection = libraries[job['libraryId']]['instances'][job['instanceId']]['connections'][script['targetConnection']]
            batch = batches[batch_id(connection)]
            marker = (batch['id'], job['libraryId'], None if script['scope'] == 'library' else job['instanceId'],
                      script['id'], script['target']['hostId'])
            if marker not in seen_hooks:
                batch['hooks'].append(dict(script, consumerLibraryId=job['libraryId'], consumerInstanceId=job['instanceId']))
                seen_hooks.add(marker)
            dependencies.setdefault(consumer, set()).add(batch['id'])
            for name in script.get('sharedInputs', []):
                shared.setdefault(job['libraryId'] + '/' + name, set()).add(batch['id'])
    for batch in batches.values():
        usernames = [account['username'] for account in batch['accounts']]
        if len(set(usernames)) != len(usernames):
            raise ValueError('APPLICATION_ACCOUNT_IDENTITY_CONFLICT')
        batch['hooks'].sort(key=lambda item: (item.get('order', 0), item['scope'] != 'library', item['consumerLibraryId'], item['consumerInstanceId'], item['id']))
        batch['accounts'].sort(key=lambda item: item['id'])
    return dict(batches=sorted(batches.values(), key=lambda item: item['id']),
                dependencies={key: sorted(value) for key, value in dependencies.items()},
                sharedDependencies={key: sorted(value) for key, value in shared.items()})


def pending_instances(inputs, completed):
    return sorted(key for key, required in inputs['dependencies'].items() if set(required) - set(completed))


def ready_vault_jobs(jobs, inputs, completed, delivered):
    pending = set(pending_instances(inputs, completed))
    return [job for job in jobs if instance_key(job['libraryId'], job['instanceId']) not in pending
            and instance_key(job['libraryId'], job['instanceId']) not in delivered]


def shared_vault_jobs(jobs, inputs, completed):
    result = []
    for job in jobs:
        documents = []
        for document in job['documents']:
            fields = {name: value for name, value in document['fields'].items()
                      if not set(inputs['sharedDependencies'].get(job['libraryId'] + '/' + name, [])) - set(completed)}
            if fields:
                documents.append(dict(document, fields=fields))
        result.append(dict(job, documents=documents))
    return result

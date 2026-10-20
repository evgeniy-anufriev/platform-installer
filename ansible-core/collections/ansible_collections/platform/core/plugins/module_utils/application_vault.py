"""Target-free Vault jobs; no values, network access or Installer lifecycle."""
import hashlib
import json
import re

SEGMENT = re.compile(r'^[A-Za-z0-9_-][A-Za-z0-9_.-]{0,127}$')


def segment(value):
    if not isinstance(value, str) or not SEGMENT.fullmatch(value) or value in {'.', '..'}:
        raise ValueError('APPLICATION_VAULT_REFERENCE_INVALID')
    return value


def jaas_field(field):
    """Quote a JAAS string with native template functions, preserving Unicode/HTML."""
    expression = '.Data.data.' + field
    for source, target in [('\\', '\\\\'), ('"', '\\"'), ('\n', '\\n'), ('\r', '\\r'),
                           ('\t', '\\t'), ('\b', '\\b'), ('\f', '\\f')]:
        expression += ' | replaceAll %s %s' % (json.dumps(source), json.dumps(target))
    return '"{{ ' + expression + ' }}"'


def kv_source(source, row):
    if source.get('kind') == 'vault_ref':
        ref = row['bindings'].get(source['binding'], {}).get('deploymentRef')
        parts = source['document'].split('/')
        for part in parts:
            segment(part)
        return dict(providerId=ref, mount=segment(source['mount']), document='/'.join(parts), field=segment(source['field']))
    return None


def project_vault(rows, prepared):
    snapshot = prepared['snapshot']
    libraries = snapshot['applicationLibraries']['libraries']
    plans = prepared['pki_materialization']['materializationPlans']
    project = segment(snapshot['project']['id'])
    providers, library_jobs, instance_jobs, source_jobs = {}, [], [], []
    for library_id, library in sorted(libraries.items()):
        selected = [r for r in rows if r['libraryId'] == library_id]
        row = selected[0]
        if any(r.get('vaultRef', {}) != row.get('vaultRef', {}) for r in selected):
            raise ValueError('APPLICATION_VAULT_HOST_CONFLICT')
        active = [i for i in library['instances'].values() if i['agentRequired']]
        sources = [c['source'] for i in library['instances'].values() for a in i['credentialRequirements'].values()
                   for c in a['credentials'].values() if c['source']['kind'] == 'vault_ref']
        if not active and not sources:
            continue
        auth = row.get('vaultRef', {})
        ref = row['bindings'].get(auth.get('binding'), {}).get('deploymentRef')
        if not ref:
            raise ValueError('APPLICATION_VAULT_BINDING_REQUIRED')
        connections = [c for i in library['instances'].values() for c in i['connections'].values()
                       if c.get('deploymentRef') == ref and c.get('serviceType') == 'vault']
        if not connections or any(c != connections[0] for c in connections):
            raise ValueError('APPLICATION_VAULT_CONNECTION_INVALID')
        targets = connections[0]['targets']
        endpoint = snapshot.get('endpoints', {}).get('deployments', {}).get(ref)
        if not targets or (not endpoint and len(targets) != 1):
            raise ValueError('APPLICATION_VAULT_CONNECTION_AMBIGUOUS')
        target = targets[0]
        address = endpoint['fqdn'] if endpoint else target['address']
        if not isinstance(address, str) or not re.fullmatch(r'[A-Za-z0-9.-]+', address):
            raise ValueError('APPLICATION_VAULT_CONNECTION_INVALID')
        ca_plans = [p for p in plans if p['hostId'] == target['hostId'] and p['tlsProfileId'] == target.get('tlsProfileRef')]
        if len(ca_plans) != 1:
            raise ValueError('APPLICATION_VAULT_CA_PLAN_REQUIRED')
        # Owner contract: all published endpoints use HTTPS port 443.
        url = 'https://%s' % address if endpoint else 'https://%s:%s' % (address, target['port'])
        provider = dict(providerId=ref, url=url,
                        routeAddress=address, caHost=target['hostId'], caSource=ca_plans[0]['targetDirectory']+'/ca-chain.pem',
                        auth=auth)
        if ref in providers and providers[ref] != provider:
            raise ValueError('APPLICATION_VAULT_AUTH_CONFLICT')
        providers[ref] = provider
        for source in sources:
            location = kv_source(source, row)
            if location['providerId'] != ref:
                raise ValueError('APPLICATION_VAULT_SOURCE_PROVIDER_MISMATCH')
            password_ref = 'pla-vault-'+hashlib.sha256(repr(sorted(source.items())).encode()).hexdigest()[:32]
            entry = dict(location, passwordRef=password_ref)
            if entry not in source_jobs:
                source_jobs.append(entry)
        shared = {}
        for name, value in sorted(library['sharedSecretRequirements'].items()):
            source = value['source']
            if source['kind'] == 'pki_credential':
                profile = row['bindings'].get(source['binding'], {}).get('profileRef')
                if any(r['bindings'].get(source['binding'], {}).get('profileRef') != profile for r in selected):
                    raise ValueError('APPLICATION_VAULT_PKI_CREDENTIAL_AMBIGUOUS')
                hosts = {r['hostId'] for r in selected}
                matches = [p for p in plans if p['hostId'] in hosts and p['tlsProfileId'] == profile
                           and 'PKCS12_KEYSTORE' in p['formats']]
                if (source['credential'] != 'java_keystore_password' or len(matches) != len(hosts)
                        or len({p.get('storePasswordSecretRef') for p in matches}) != 1
                        or not matches[0].get('storePasswordSecretRef')):
                    raise ValueError('APPLICATION_VAULT_PKI_CREDENTIAL_AMBIGUOUS')
                shared[name] = dict(source=dict(kind='runtime_secret_ref', ref=matches[0]['storePasswordSecretRef']), pkiPlans=matches)
            elif source['kind'] in {'runtime_secret_ref', 'vault_ref'}:
                shared[name] = dict(source=source)
            else:
                raise ValueError('APPLICATION_VAULT_SOURCE_DEFERRED')
        mounts = {r['settings']['provisioner']['secrets']['mount'] for r in selected if
                  r['settings'].get('provisioner', {}).get('secret_bindings')}
        if len(mounts) > 1:
            raise ValueError('APPLICATION_VAULT_SHARED_MOUNT_CONFLICT')
        mount = segment(next(iter(mounts), 'secret'))
        shared_doc = '%s/%s/shared' % (project, segment(library_id))
        documents = []
        shared_locations = {}
        for name, value in shared.items():
            location = kv_source(value['source'], row)
            if location and location['providerId'] != ref:
                raise ValueError('APPLICATION_VAULT_SOURCE_PROVIDER_MISMATCH')
            if location and not any(all(entry.get(key) == value for key, value in location.items()) for entry in source_jobs):
                source_jobs.append(location)
            shared_locations[name] = location or dict(mount=mount, document=shared_doc, field=segment(name))
        writable_shared = {k: v for k, v in shared.items() if v['source']['kind'] != 'vault_ref'}
        if writable_shared:
            documents.append(dict(mount=mount, document=shared_doc, fields=writable_shared))
        library_jobs.append(dict(providerId=ref, libraryId=library_id, documents=documents))
        for instance_id, instance in sorted(library['instances'].items()):
            instance_rows = [r for r in selected if r['instanceId'] == instance_id]
            provisioner = instance_rows[0]['settings'].get('provisioner', {})
            if not instance['agentRequired']:
                continue
            locations, account_docs = {}, []
            for account_id, account in sorted(instance['credentialRequirements'].items()):
                fields = {}
                document = '%s/%s/%s/accounts/%s' % (project, library_id, segment(instance_id), segment(account_id))
                for field, credential in account['credentials'].items():
                    source = credential['source']
                    location = kv_source(source, row)
                    if location and location['providerId'] != ref:
                        raise ValueError('APPLICATION_VAULT_SOURCE_PROVIDER_MISMATCH')
                    if source['kind'] not in {'literal', 'runtime_secret_ref', 'vault_ref'}:
                        raise ValueError('APPLICATION_VAULT_SOURCE_DEFERRED')
                    locations[(account_id, field)] = location or dict(mount=mount, document=document, field=segment(field))
                    if not location:
                        fields[field] = dict(source=source)
                if fields:
                    account_docs.append(dict(mount=mount, document=document, fields=fields))
            envs, paths, read_fields = [], set(), {}
            for name, binding in sorted(instance['secretBindings'].items()):
                source = binding['source']
                location = shared_locations[source['library_secret']] if 'library_secret' in source else locations[(source['account'], source['field'])]
                path = location['mount']+'/data/'+location['document']
                paths.add(path)
                read_fields.setdefault(path, []).append(location['field'])
                if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', location['field']):
                    raise ValueError('APPLICATION_VAULT_AGENT_FIELD_INVALID')
                # Supervisor templates are keyed by contents. Distinct env names
                # reading one field need a no-output comment to remain distinct.
                contents = '{{/* %s */}}{{ with secret %s }}{{ .Data.data.%s }}{{ end }}' % (name, json.dumps(path), location['field'])
                if binding.get('format') == 'kafka_scram_jaas':
                    if (source.get('field') != 'password'
                            or instance['connections'][source['account']]['serviceType'] != 'kafka'):
                        raise ValueError('APPLICATION_VAULT_AGENT_FIELD_INVALID')
                    user = locations[(source['account'], 'username')]
                    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', user['field']):
                        raise ValueError('APPLICATION_VAULT_AGENT_FIELD_INVALID')
                    user_path = user['mount']+'/data/'+user['document']
                    paths.add(user_path)
                    read_fields.setdefault(user_path, []).append(user['field'])
                    contents = ('{{/* %s */}}org.apache.kafka.common.security.scram.ScramLoginModule required '
                                'username={{ with secret %s }}%s{{ end }} '
                                'password={{ with secret %s }}%s{{ end }};') % (
                                    name, json.dumps(user_path), jaas_field(user['field']), json.dumps(path), jaas_field(location['field']))
                envs.append(dict(name=name, contents=contents))
            identity = 'pla-'+hashlib.sha256((':'.join((project, library_id, instance_id))).encode()).hexdigest()[:32]
            owner = 'platform.application/v1:'+':'.join((project, library_id, instance_id))
            policy = '# '+owner+'\n'+''.join('path %s { capabilities = ["read"] }\n' % json.dumps(p) for p in sorted(paths))
            policy += 'path "auth/token/lookup-self" { capabilities = ["read"] }\npath "auth/token/renew-self" { capabilities = ["update"] }\n'
            policy += 'path "auth/token/revoke-self" { capabilities = ["update"] }\n'
            instance_jobs.append(dict(providerId=ref, libraryId=library_id, instanceId=instance_id,
                                     hosts=sorted(instance['placements']), documents=account_docs, identity=identity,
                                     owner=owner, policy=policy, envTemplates=envs, readFields=read_fields, mounts=sorted({p.split('/')[0] for p in paths})))
    for job in library_jobs+instance_jobs:
        for doc in job['documents']:
            doc['owner'] = 'platform.application/v1:'+':'.join((project, job['libraryId'], doc['document']))
    return dict(providers=[providers[k] for k in sorted(providers)], libraryJobs=library_jobs, instanceJobs=instance_jobs, sourceJobs=source_jobs)

"""Bounded real A8 Docker+application protocol QA; isolated project on RED OS.

Reuses the approved connection-probe binary as HTTP server, without connection inputs.
This verifies mixed orchestration only, not probe connections/security or A9.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid
import yaml
import secrets
import sys
import urllib.request
import urllib.error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--release', required=True)
    parser.add_argument('--state', required=True)
    parser.add_argument('--key', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--fresh-vault', action='store_true')
    parser.add_argument('--inputs-root', help='Existing private QA directory under .runtime/secrets')
    parser.add_argument('--providers-host', choices=('node1', 'node2'), default='node1')
    parser.add_argument('--redis-host', choices=('node1', 'node2'))
    parser.add_argument('--node2-public-key-file', help='Public host key obtained over the established trusted SSH connection')
    parser.add_argument('--scenario', action='append', choices=('success', 'repeat', 'cancel', 'apply-failure'),
                        help='Run only selected bounded cases; prior successful mixed evidence may be reused')
    args = parser.parse_args()
    redis_host = args.redis_host or args.providers_host
    release, state = Path(args.release), Path(args.state)
    state.mkdir(parents=True, mode=0o700, exist_ok=True)
    if state.stat().st_mode & 0o077:
        raise RuntimeError('QA_STATE_PERMISSIONS_INVALID')
    tools = release / 'ansible-core/tools'
    sys.path.insert(0, str(tools))
    import execution_secret_output
    manifest = yaml.safe_load((release / 'manifest.yaml').read_text())
    # Bundle manifest byte digest matches the immutable bundle admission identity.
    bundle_digest = 'sha256:' + hashlib.sha256((release / 'manifest.yaml').read_bytes()).hexdigest()
    runtime = dict(bundleDigest=bundle_digest, coreVersion=manifest['coreVersion'],
                   catalogDigest=manifest['catalogDigest'], planningProtocol='v1alpha1')
    command = ['python3', str(tools / 'execution_protocol.py'), '--state-root', str(state),
               '--runtime-release', str(release), '--controller', str(tools / 'execution_controller.py'),
               '--bundle-digest', bundle_digest]

    def call(value, extra=None):
        result = subprocess.run(command + (extra or []), input=json.dumps(value).encode(),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
        try:
            response = json.loads(result.stdout)
        except ValueError:
            raise RuntimeError('QA_PROTOCOL_RESPONSE_INVALID exit=%s' % result.returncode)
        if result.returncode or response.get('error'):
            raise RuntimeError('QA_PROTOCOL_FAILED ' + str(response.get('code', response.get('error', {}).get('code') if isinstance(response.get('error'), dict) else response.get('error'))))
        return response

    summary = dict(runtimeRelease=runtime, scenarios=[])
    capabilities = call(dict(apiVersion='platform.installer/execution-runtime/v1alpha3', operation='GetCapabilities'))
    if capabilities.get('apiVersion') != 'platform.installer/execution-capabilities/v1alpha7':
        raise RuntimeError('QA_MIXED_CAPABILITY_MISSING')
    secret_dir = Path(args.inputs_root) if args.inputs_root else Path(args.source) / '.runtime/secrets'
    if '.runtime/secrets' not in str(secret_dir.resolve()) or secret_dir.is_symlink():
        raise RuntimeError('QA_INPUT_CUSTODY_INVALID')
    secret_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
    secret_path = secret_dir / 'a8-vault-inputs.json'
    if secret_path.exists():
        if secret_path.is_symlink() or secret_path.stat().st_mode & 0o077:
            raise RuntimeError('QA_INPUT_CUSTODY_INVALID')
        saved = json.loads(secret_path.read_text())
    else:
        saved = dict(storePassword=secrets.token_urlsafe(24), marker=secrets.token_urlsafe(24), adminToken=None)
        with os.fdopen(os.open(secret_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'w') as stream:
            json.dump(saved, stream)
    store_password, marker, admin_token = saved['storePassword'], saved['marker'], saved['adminToken']
    if args.fresh_vault:
        for name in ('redisAdmin', 'redisApp'):
            saved.setdefault(name, secrets.token_urlsafe(24))
        with open(secret_path, 'w') as stream:
            json.dump(saved, stream)
    scenarios = args.scenario or (('success', 'repeat') if args.fresh_vault else ('success', 'repeat', 'cancel', 'apply-failure'))
    for scenario in scenarios:
        cancel_active = scenario == 'cancel'
        staging = 'installer-' + str(int(time.time() * 1000000))
        project = state / 'runs' / staging / 'project'
        project.mkdir(parents=True, mode=0o700)
        inventory = project / 'inventory'
        (inventory / 'group_vars/all').mkdir(parents=True)
        (inventory / 'host_vars/node1').mkdir(parents=True)
        if args.providers_host == 'node2':
            (inventory / 'host_vars/node2').mkdir(parents=True)
        desired = dict(serviceDeployments={'qa-docker': dict(serviceType='docker', mode='existing-user',
                                                             configuration=dict(accountName='platform-docker'))})
        fixture = Path(args.source) / 'examples/valid/application-runtime'
        for folder in ('application-packages', 'library-packages'):
            shutil.copytree(fixture / folder, project / folder)
        defaults = project / 'application-packages/apigateway/1.0.0/roles/application_apigateway/defaults/main.yml'
        definition = json.loads(defaults.read_text())
        definition['platform_application_definition']['defaults'].update(
            image='platform-application-connection-probe:a5-qa',
            command=['/a8-qa-nonexistent-binary'] if scenario == 'apply-failure' else ['/usr/bin/connection-probe'], config_files=[])
        defaults.write_text(json.dumps(definition))
        compose = project / 'application-packages/apigateway/1.0.0/roles/application_apigateway/templates/apigateway.compose.yml.j2'
        compose.write_text(compose.read_text().split('    volumes:')[0])
        base_vars = json.loads((fixture / 'inventory/group_vars/all/platform-installer.yml').read_text())
        library = base_vars['platform_desired_state']['applicationLibraryDeployments']['sdku']
        library['runtimeRef'] = 'qa-docker'
        library['applications']['gateway']['overrides']['ports']['http']['published'] = 28188
        if args.fresh_vault:
            for name in ('certificateAuthorities', 'certificateProfiles', 'tlsProfiles'):
                desired[name] = base_vars['platform_desired_state'][name]
            desired['serviceDeployments']['a8-vault-final'] = dict(serviceType='vault', mode='standalone',
                configuration=dict(tlsProfile='apps-tls', port=28212, clusterPort=28213,
                                   dataRoot='/data/a8-vault-protocol-final'))
            desired['serviceDeployments']['a8-redis-final'] = dict(serviceType='redis', mode='standalone',
                configuration=dict(tlsProfile='apps-tls', redisPort=28380,
                                   redisCredential={'passwordSecretRef': 'runtime:a8-redis-admin'}))
            library['bindings'] = {'secrets': {'deploymentRef': 'a8-vault-final'},
                                   'redis': {'deploymentRef': 'a8-redis-final'},
                                   'application_pki': {'profileRef': 'apps-tls'}}
            library['vault_ref'] = {'binding': 'secrets'}
            library['applications']['gateway']['overrides']['ports']['http']['published'] = 28191
            base = definition['platform_application_definition']['defaults']
            base['user'] = '1000:1000'
            base['provisioner'] = dict(type='vault-agent', mode='process-supervisor', auth={'method': 'approle'},
                approle={'bind_secret_id': False}, secrets={'mount': 'secret'},
                secret_bindings={'PROBE_VAULT_MARKER': {'source': {'library_secret': 'marker'}},
                    'REDIS_USER': {'source': {'account': 'redis', 'field': 'username'}},
                    'REDIS_PASSWORD': {'source': {'account': 'redis', 'field': 'password'}},
                    'PROBE_KEYSTORE_PASSWORD': {'source': {'library_secret': 'java_keystore_password'}}})
            base['accounts'] = {'redis': {'mode': 'managed', 'credentials': {
                'username': {'source': {'kind': 'literal', 'value': 'a8-qa-user'}},
                'password': {'source': {'kind': 'runtime_secret_ref', 'ref': 'a8-redis-app'}}},
                'grants': {'commands': ['ping', 'get', 'set', 'del'], 'keys': ['a8qa:*']}}}
            base['environment'].update(REDIS_HOST='192.168.56.102' if redis_host == 'node2' else '192.168.56.101', REDIS_PORT='28380',
                PROBE_REDIS_KEY_PREFIX='a8qa:', PROBE_KEYSTORE_PKCS12='/opt/application/pki/keystore.p12',
                PROBE_TRUSTSTORE_PKCS12='/opt/application/pki/truststore.p12')
            definition['platform_application_definition']['connections'] = {
                'vault': {'library_binding': 'secrets', 'protocol': 'https'},
                'redis': {'library_binding': 'redis', 'purpose': 'client'}}
            defaults.write_text(json.dumps(definition))
            app_manifest = project / 'application-packages/apigateway/1.0.0/application.yml'
            package = json.loads(app_manifest.read_text())
            agent = 'roles/application_apigateway/templates/agent.hcl.j2'
            package['files'].append(agent); package['render']['agent_template'] = agent
            app_manifest.write_text(json.dumps(package))
            (app_manifest.parent / agent).write_text('{{ application_runtime | platform.core.application_agent_config }}\n')
            compose.write_text(compose.read_text().replace('entrypoint: {{ application_effective.command | to_json }}',
                'entrypoint: ["/usr/bin/vault", "agent", "-config=/opt/vault/agent.hcl"]') +
                "    tmpfs:\n      - /run/probe:uid=1000,gid=1000,mode=0700\n"
                "    volumes:\n      - {{ (application_runtime.vault_path ~ ':/opt/vault:ro') | to_json }}\n"
                "      - {{ (application_runtime.pki_path ~ ':/opt/application/pki:ro') | to_json }}\n")
            lib_defaults = project / 'library-packages/sdku/1.0.0/roles/library_sdku/defaults/main.yml'
            lib = json.loads(lib_defaults.read_text())
            lib['platform_library_definition']['shared_secrets'] = {'marker': {'source': {'kind': 'runtime_secret_ref', 'ref': 'qa-marker'}},
                'java_keystore_password': {'source': {'kind': 'pki_credential', 'binding': 'application_pki', 'credential': 'java_keystore_password'}}}
            lib_defaults.write_text(json.dumps(lib))
        desired['applicationLibraryDeployments'] = {'sdku': library}
        archive = release / 'runtime/artifacts/applications/probe.tar'
        lock = dict(apiVersion='platform.installer/artifacts/v1alpha1', digest=bundle_digest,
            **{'x-container-images': dict(apiVersion='platform.installer/container-images/v1alpha1', images={
                'platform-application-connection-probe:a5-qa': dict(
                    imageId='sha256:caa73a170e7bc73ffc6a44a37360163ceb3939f6a986abba3c867094256c0f0d',
                    platform={'os': 'linux', 'architecture': 'amd64'}, archive=dict(
                        ref='runtime/artifacts/applications/probe.tar', size=archive.stat().st_size,
                        sha256='sha256:' + hashlib.sha256(archive.read_bytes()).hexdigest()))})})
        variables = dict(platform_desired_state_contract='platform.installer/project-desired-state/v3alpha1',
                         platform_desired_state=desired, platform_name_prefix='', platform_data_root_directory='/data',
                         platform_artifact_lock=lock)
        (inventory / 'group_vars/all/platform-installer.yml').write_text(json.dumps(variables))
        hosts = dict(localhost=dict(ansible_connection='local'),
                    node1=dict(ansible_host='192.168.56.101', ansible_user='platform-automation', ansible_connection='ssh',
                               ansible_pipelining=True, ansible_ssh_pipelining=True))
        if args.providers_host == 'node2':
            hosts['node2'] = dict(ansible_host='192.168.56.102', ansible_user='platform-automation', ansible_connection='ssh',
                                  ansible_pipelining=True, ansible_ssh_pipelining=True)
        (inventory / 'hosts.yml').write_text(json.dumps(dict(all=dict(hosts=hosts,
                    children=dict(platform_targets=dict(hosts={host: {} for host in hosts if host != 'localhost'}))))))
        host_vars = dict(platform_deployments={'qa-docker': {}}, platform_application_libraries={'sdku': {}},
                         platform_docker_tls_directory='/home/platform-docker/.config/docker/pki')
        if args.fresh_vault:
            providers = {'a8-vault-final': {'members': {'vault-1': {'roles': ['vault']}}}}
            redis = {'a8-redis-final': {'members': {'a8-final-redis-1': {'roles': ['redis']}}}}
            if args.providers_host == 'node2':
                if redis_host == 'node2':
                    providers.update(redis)
                else:
                    host_vars['platform_deployments'].update(redis)
                (inventory / 'host_vars/node2/platform-installer.yml').write_text(json.dumps({'platform_deployments': providers}))
            else:
                host_vars['platform_deployments'].update(providers)
                host_vars['platform_deployments'].update(redis)
        (inventory / 'host_vars/node1/platform-installer.yml').write_text(json.dumps(host_vars))
        (project / 'project.yml').write_text(json.dumps(dict(apiVersion='platform.installer/v2alpha1', kind='PlatformProject',
            metadata=dict(id='a8-vault-protocol-final' if args.fresh_vault else 'a8-mixed-protocol', name='A8 bounded mixed regression'),
            desiredStateContract='platform.installer/project-desired-state/v2alpha1',
            artifactLock=variables['platform_artifact_lock'],
            catalogLock=dict(apiVersion='platform.installer/catalog/v1alpha1', digest=manifest['catalogDigest'], services={}))))
        planned = call(dict(apiVersion='platform.installer/execution-runtime/v1alpha3', operation='BuildDeploymentPlan',
                            runId=staging, project={}, runtimeRelease=runtime,
                            deploymentOrder=['qa-docker', 'a8-vault-final', 'a8-redis-final'] if args.fresh_vault else ['qa-docker'],
                            applicationVaultSources={'a8-vault-final': 'CURRENT_RUN_BOOTSTRAP' if admin_token is None else 'RUNTIME_INPUT'} if args.fresh_vault else {}))
        plan = planned['deploymentPlan']
        if plan['status'] != 'EXECUTABLE':
            raise RuntimeError('QA_PLAN_BLOCKED ' + ','.join(x['code'] for x in plan['findings']))
        private_manifest = json.loads((project.parent / 'manifest.json').read_text())
        expected_scope = (['PKI_APPLY', 'SERVICE_APPLY', 'SERVICE_VERIFY', 'SERVICE_APPLY', 'SERVICE_VERIFY', 'SERVICE_APPLY', 'SERVICE_VERIFY'] if args.fresh_vault else
                          ['SERVICE_APPLY', 'SERVICE_VERIFY']) + ['APPLICATION_LIBRARIES_APPLY', 'APPLICATION_LIBRARIES_VERIFY']
        if args.fresh_vault and private_manifest['operations'][0]['operation'] == 'PKI_REISSUE':
            expected_scope.insert(0, 'PKI_REISSUE')
        if [op['operation'] for op in private_manifest['operations']] != expected_scope:
            raise RuntimeError('QA_UNEXPECTED_SCOPE')
        public_key = Path('/etc/ssh/ssh_host_ed25519_key.pub').read_text().split()
        approvals = [dict(hostId='node1', address='192.168.56.101', port=22,
                         keyType=public_key[0], publicKey=public_key[1])]
        if args.providers_host == 'node2':
            key = Path(args.node2_public_key_file).read_text().split()
            approvals.append(dict(hostId='node2', address='192.168.56.102', port=22,
                                  keyType=key[0], publicKey=key[1]))
        trust = dict(stagingId=staging, projectIdentity=private_manifest['projectIdentity'],
                     projectRevision=private_manifest['projectRevision'], planFingerprint=private_manifest['planFingerprint'],
                     runtimeRelease=runtime, manifestDigest=planned['executionManifestDigest'],
                     approvals=approvals if private_manifest.get('targetConnections') else [])
        call(trust, ['--stage-target-host-trust'])
        attempt = uuid.uuid4().hex
        binding = dict(startAttemptId=attempt, projectIdentity=private_manifest['projectIdentity'],
                       projectRevision=private_manifest['projectRevision'], planFingerprint=private_manifest['planFingerprint'],
                       executionManifestDigest=planned['executionManifestDigest'], runtimeRelease=runtime)
        payload = dict(apiVersion='TargetCredentialLeasePayload/v1alpha4', kind='TargetCredentialLeasePayload',
                       username='platform-automation', password=None, privateKey=Path(args.key).read_text(),
                       sudoPassword=None, pkiStorePassword=None, runtimeSecretValues={}, runtimeSecretInputs=[])
        if args.fresh_vault:
            payload['pkiStorePassword'] = store_password
            for requirement in private_manifest['applicationSecretRequirements']:
                if requirement['source'] == 'RUNTIME_INPUT':
                    payload['runtimeSecretValues'][requirement['requirementRef']] = (
                        admin_token if requirement['purpose'] == 'APPLICATION_VAULT_ADMIN_TOKEN' else
                        saved['redisApp'] if requirement['runtimeReference'] == 'a8-redis-app' else marker)
            for requirement in private_manifest['runtimeSecretRequirements']:
                if requirement['purpose'] == 'SERVICE_PASSWORD':
                    payload['runtimeSecretValues'][requirement['requirementRef']] = saved['redisAdmin']
            if admin_token:
                for requirement in private_manifest['runtimeSecretInputs']:
                    if requirement['purpose'] == 'SERVICE_ADMIN_TOKEN':
                        payload['runtimeSecretInputs'].append({key: requirement[key] for key in
                            ('requirementRef', 'purpose', 'serviceDeployment', 'operations')})
                        payload['runtimeSecretInputs'][-1]['value'] = admin_token
        lease = call(dict(binding, apiVersion='platform.installer/runtime-secret-lease/v1alpha2',
                          kind='PutRuntimeSecretLeaseRequest', requestId=uuid.uuid4().hex, payload=payload))
        del payload
        started = call(dict(binding, apiVersion='platform.installer/execution-start/v1alpha2', kind='StartExecutionRequest', leaseId=lease['leaseId']))
        run_id = started['runId']
        events, cursor, cancelled = [], 0, False
        deadline = time.monotonic() + 1800
        while time.monotonic() < deadline:
            page = call(dict(apiVersion='platform.installer/execution-runtime/v1alpha1', operation='GetEvents', runId=run_id, afterSequence=cursor, limit=512))
            events.extend(page['events']); cursor = page['nextSequence']
            if cancel_active and not cancelled and any(x['eventType'] == 'TASK_STARTED' and x.get('actionId') == 'applications:apply' for x in events):
                cancelled_response = call(dict(apiVersion='platform.installer/execution-runtime/v1alpha1', operation='CancelExecution', runId=run_id))
                if cancelled_response['run']['state'] != 'CANCELLED':
                    raise RuntimeError('QA_CANCEL_FAILED')
                cancelled = True
            observed = call(dict(apiVersion='platform.installer/execution-runtime/v1alpha1', operation='GetExecution', runId=run_id))
            if observed['run']['state'] not in ('PENDING', 'STARTING', 'RUNNING'):
                break
            time.sleep(0.25)
        expected = 'CANCELLED' if cancel_active else 'FAILED' if scenario == 'apply-failure' else 'SUCCEEDED'
        if observed['run']['state'] != expected:
            print(json.dumps(dict(runId=run_id, state=observed['run']['state'],
                                  safeEvents=events[-6:]), sort_keys=True))
            raise RuntimeError('QA_TERMINAL_' + observed['run']['state'])
        if not cancel_active and not any(e['eventType'] == 'ACTION_COMPLETED' and e.get('status') == 'SUCCESS' for e in events):
            raise RuntimeError('QA_SERVICE_EVENTS_MISSING')
        if scenario in ('success', 'repeat'):
            port = 28191 if args.fresh_vault else 28188
            try:
                response = urllib.request.urlopen('http://192.168.56.101:%s/status' % port, timeout=30)
            except urllib.error.HTTPError as error:
                response = error  # 503 is expected: connection/PKCS inputs are outside this bounded A8 fixture.
            status = json.loads(response.read())
            if args.fresh_vault and status['checks']['vaultAgent']['state'] != 'ok':
                raise RuntimeError('QA_AGENT_MARKER_MISSING')
            if args.fresh_vault and any(status['checks'][name]['state'] != 'ok' for name in ('pkcs12', 'pkcs12Client', 'redis')):
                raise RuntimeError('QA_ACCOUNT_PROVIDER_STATUS_FAILED')
        if scenario == 'apply-failure' and any(e['eventType'] == 'ACTION_STARTED' and e.get('actionId') == 'applications:verify' for e in events):
            raise RuntimeError('QA_VERIFY_STARTED_AFTER_APPLY_FAILURE')
        if args.fresh_vault and admin_token is None:
            admin_token = execution_secret_output.current_run_admin_token(
                str(state), str(state / 'runs' / run_id), 'a8-vault-protocol-final', 'a8-vault-final', run_id)
            saved['adminToken'] = admin_token
            with open(secret_path, 'w') as stream:
                json.dump(saved, stream)
        if (list((state / 'runs' / run_id).rglob('target-key-*.pem')) or
            list((state / 'runs' / run_id).glob('.runtime-secret-inputs-*.json')) or
            list((state / 'runs' / run_id).glob('.runtime-application-secret-*')) or
            any((state / 'runs' / run_id / ('.runtime-projection-' + hashlib.sha256(operation.encode()).hexdigest() + '.json')).exists()
                for operation in ('applications:apply', 'applications:verify'))):
            raise RuntimeError('QA_CREDENTIAL_CLEANUP_FAILED')
        record = dict(scenario=scenario, runId=run_id, projectRevision=private_manifest['projectRevision'],
            planFingerprint=private_manifest['planFingerprint'], manifestDigest=planned['executionManifestDigest'],
            state=observed['run']['state'], eventCount=len(events),
            actions=[dict(type=e['eventType'], operationId=e.get('actionId'), status=e.get('status')) for e in events if e['eventType'] in ('ACTION_STARTED', 'ACTION_COMPLETED')],
            changedTasks=sum(e['eventType'] == 'TASK_COMPLETED' and e.get('status') == 'CHANGED' for e in events), credentialCleanup='PASS')
        summary['scenarios'].append(record)
        Path(args.source, 'qa-a8-' + ('vault' if args.fresh_vault else 'mixed') + '-result.json').write_text(json.dumps(summary, sort_keys=True))
        print(json.dumps(record, sort_keys=True), flush=True)
        if scenario == 'repeat' and record['changedTasks']:
            raise RuntimeError('QA_REPEAT_CHANGED')
    print(json.dumps(summary, sort_keys=True))


if __name__ == '__main__':
    main()

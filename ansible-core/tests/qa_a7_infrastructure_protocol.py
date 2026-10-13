"""Owner-authorized native Docker protocol regression; run only on RED OS QA.

Uses an existing Docker account and its existing TLS directory. No app deployment,
PKI issuance, mocks, or production protocol changes. All credentials stay private.
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--release', required=True)
    parser.add_argument('--state', required=True)
    parser.add_argument('--key', required=True)
    parser.add_argument('--target-host', choices=('node1', 'node2'), default='node1')
    parser.add_argument('--public-key-file')
    args = parser.parse_args()
    release, state = Path(args.release), Path(args.state)
    state.mkdir(parents=True, mode=0o700, exist_ok=True)
    if state.stat().st_mode & 0o077:
        raise RuntimeError('QA_STATE_PERMISSIONS_INVALID')
    tools = release / 'ansible-core/tools'
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
    for index, cancel_active in enumerate((False, True)):
        staging = 'installer-' + str(int(time.time() * 1000000))
        project = state / 'runs' / staging / 'project'
        project.mkdir(parents=True, mode=0o700)
        inventory = project / 'inventory'
        (inventory / 'group_vars/all').mkdir(parents=True)
        (inventory / 'host_vars' / args.target_host).mkdir(parents=True)
        desired = dict(serviceDeployments={'qa-docker': dict(serviceType='docker', mode='existing-user',
                                                             configuration=dict(accountName='platform-docker'))})
        variables = dict(platform_desired_state_contract='platform.installer/project-desired-state/v2alpha1',
                         platform_desired_state=desired, platform_name_prefix='', platform_data_root_directory='/data',
                         platform_artifact_lock=dict(apiVersion='platform.installer/artifacts/v1alpha1', digest=bundle_digest))
        (inventory / 'group_vars/all/platform-installer.yml').write_text(json.dumps(variables))
        address = '192.168.56.102' if args.target_host == 'node2' else '192.168.56.101'
        (inventory / 'hosts.yml').write_text(json.dumps(dict(all=dict(hosts={
                    'localhost': dict(ansible_connection='local'),
                    args.target_host: dict(ansible_host=address, ansible_user='platform-automation', ansible_pipelining=True, ansible_ssh_pipelining=True)},
                    children=dict(platform_targets=dict(hosts={args.target_host: {}}))))))
        (inventory / 'host_vars' / args.target_host / 'platform-installer.yml').write_text(json.dumps(dict(
            platform_deployments={'qa-docker': {}}, platform_docker_tls_directory='/home/platform-docker/.config/docker/pki')))
        (project / 'project.yml').write_text(json.dumps(dict(apiVersion='platform.installer/v2alpha1', kind='PlatformProject',
            metadata=dict(id='a7-infra-protocol', name='A7 bounded Docker regression'),
            desiredStateContract='platform.installer/project-desired-state/v2alpha1',
            artifactLock=variables['platform_artifact_lock'],
            catalogLock=dict(apiVersion='platform.installer/catalog/v1alpha1', digest=manifest['catalogDigest'], services={}))))
        planned = call(dict(apiVersion='platform.installer/execution-runtime/v1alpha2', operation='BuildDeploymentPlan',
                            runId=staging, project={}, runtimeRelease=runtime, deploymentOrder=['qa-docker']))
        plan = planned['deploymentPlan']
        if plan['status'] != 'EXECUTABLE':
            raise RuntimeError('QA_PLAN_BLOCKED ' + ','.join(x['code'] for x in plan['findings']))
        private_manifest = json.loads((project.parent / 'manifest.json').read_text())
        if [op['operation'] for op in private_manifest['operations']] != ['SERVICE_APPLY', 'SERVICE_VERIFY']:
            raise RuntimeError('QA_UNEXPECTED_SCOPE')
        public_key = Path(args.public_key_file or '/etc/ssh/ssh_host_ed25519_key.pub').read_text().split()
        trust = dict(stagingId=staging, projectIdentity=private_manifest['projectIdentity'],
                     projectRevision=private_manifest['projectRevision'], planFingerprint=private_manifest['planFingerprint'],
                     runtimeRelease=runtime, manifestDigest=planned['executionManifestDigest'],
                     approvals=[dict(hostId=args.target_host, address=address, port=22,
                                     keyType=public_key[0], publicKey=public_key[1])])
        call(trust, ['--stage-target-host-trust'])
        attempt = uuid.uuid4().hex
        binding = dict(startAttemptId=attempt, projectIdentity=private_manifest['projectIdentity'],
                       projectRevision=private_manifest['projectRevision'], planFingerprint=private_manifest['planFingerprint'],
                       executionManifestDigest=planned['executionManifestDigest'], runtimeRelease=runtime)
        payload = dict(apiVersion='TargetCredentialLeasePayload/v1alpha4', kind='TargetCredentialLeasePayload',
                       username='platform-automation', password=None, privateKey=Path(args.key).read_text(),
                       sudoPassword=None, pkiStorePassword=None, runtimeSecretValues={}, runtimeSecretInputs=[])
        lease = call(dict(binding, apiVersion='platform.installer/runtime-secret-lease/v1alpha2',
                          kind='PutRuntimeSecretLeaseRequest', requestId=uuid.uuid4().hex, payload=payload))
        del payload
        started = call(dict(binding, apiVersion='platform.installer/execution-start/v1alpha2', kind='StartExecutionRequest', leaseId=lease['leaseId']))
        run_id = started['runId']
        events, cursor, cancelled = [], 0, False
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            page = call(dict(apiVersion='platform.installer/execution-runtime/v1alpha1', operation='GetEvents', runId=run_id, afterSequence=cursor, limit=512))
            events.extend(page['events']); cursor = page['nextSequence']
            if cancel_active and not cancelled and any(x['eventType'] == 'TASK_STARTED' for x in events):
                cancelled_response = call(dict(apiVersion='platform.installer/execution-runtime/v1alpha1', operation='CancelExecution', runId=run_id))
                if cancelled_response['run']['state'] != 'CANCELLED':
                    raise RuntimeError('QA_CANCEL_FAILED')
                cancelled = True
            observed = call(dict(apiVersion='platform.installer/execution-runtime/v1alpha1', operation='GetExecution', runId=run_id))
            if observed['run']['state'] not in ('PENDING', 'STARTING', 'RUNNING'):
                break
            time.sleep(0.25)
        expected = 'CANCELLED' if cancel_active else 'SUCCEEDED'
        if observed['run']['state'] != expected:
            print(json.dumps(dict(runId=run_id, state=observed['run']['state'],
                                  safeEvents=events[-6:]), sort_keys=True))
            raise RuntimeError('QA_TERMINAL_' + observed['run']['state'])
        if not cancel_active and not any(e['eventType'] == 'ACTION_COMPLETED' and e.get('status') == 'SUCCESS' for e in events):
            raise RuntimeError('QA_SERVICE_EVENTS_MISSING')
        if list((state / 'runs' / run_id).rglob('target-key-*.pem')) or list((state / 'runs' / run_id).glob('.runtime-secret-inputs-*.json')):
            raise RuntimeError('QA_CREDENTIAL_CLEANUP_FAILED')
        summary['scenarios'].append(dict(runId=run_id, projectRevision=private_manifest['projectRevision'],
            planFingerprint=private_manifest['planFingerprint'], manifestDigest=planned['executionManifestDigest'],
            state=observed['run']['state'], eventCount=len(events),
            actions=[dict(type=e['eventType'], operationId=e.get('actionId'), status=e.get('status')) for e in events if e['eventType'] in ('ACTION_STARTED', 'ACTION_COMPLETED')],
            changedTasks=sum(e['eventType'] == 'TASK_COMPLETED' and e.get('status') == 'CHANGED' for e in events), credentialCleanup='PASS'))
    print(json.dumps(summary, sort_keys=True))


if __name__ == '__main__':
    main()

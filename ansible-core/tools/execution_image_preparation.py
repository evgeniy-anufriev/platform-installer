"""Fixed image preparation protocol; all registry requests are Ansible tasks."""
import json
import os
import signal
import subprocess
import sys
import tempfile
import time

from execution_lifecycle import LifecycleError, digest
import execution_secret_lease as secrets
import execution_target_trust as trust

REQUEST_VERSION = 'platform.installer/execution-runtime/v1alpha6'
LEASE_VERSION = 'platform.installer/application-image-preparation-lease/v1alpha1'


def read_inputs(journal, expected=''):
    value = secrets._read(os.path.join(journal.directory, 'application-image-inputs.json'))
    if expected and digest(value) != expected:
        raise LifecycleError('APPLICATION_IMAGE_PREPARATION_STALE')
    return value


def binding(journal, inputs, release):
    return dict(preparationId=journal.run_id, inputsDigest=digest(inputs),
                projectIdentity=inputs['projectIdentity'], projectRevision=inputs['projectRevision'],
                runtimeRelease=release, descriptorSetFingerprint=inputs['descriptorSetFingerprint'])


def preparation_payload(journal, inputs, release, lease):
    """Request-lifetime lease: it cannot be attached to an execution run."""
    if time.time() > inputs.get('expiresAt', 0):
        raise LifecycleError('APPLICATION_IMAGE_LEASE_EXPIRED')
    if (not isinstance(lease, dict) or set(lease) != {'apiVersion', 'binding', 'payload', 'approvals'} or
            lease['apiVersion'] != LEASE_VERSION or lease['binding'] != binding(journal, inputs, release)):
        raise LifecycleError('APPLICATION_IMAGE_LEASE_INVALID')
    payload = json.loads(secrets._payload(lease['payload']).decode())
    if payload['apiVersion'] != secrets.TYPED_RUNTIME_SECRET_PAYLOAD_VERSION:
        raise LifecycleError('APPLICATION_IMAGE_LEASE_INVALID')
    expected = {item['requirementRef'] for item in inputs['requirements']}
    if set(payload.get('runtimeSecretValues', {})) != expected or payload.get('runtimeSecretInputs') or payload.get('pkiStorePassword'):
        raise LifecycleError('APPLICATION_IMAGE_LEASE_INVALID')
    known_hosts = trust._known_hosts({'targetConnections': inputs['targetConnections']}, lease['approvals'])
    values = {item['runtimeReference']: payload['runtimeSecretValues'][item['requirementRef']] for item in inputs['requirements']}
    return payload, known_hosts, values


def prepare(journal, value, release, runtime_release):
    inputs = read_inputs(journal, value['inputsDigest'])
    if inputs['runtimeRelease'] != runtime_release:
        raise LifecycleError('APPLICATION_IMAGE_PREPARATION_STALE')
    result_path = os.path.join(journal.directory, 'application-images.json')
    if os.path.isfile(result_path):
        return dict(status='READY', preparationDigest=digest(secrets._read(result_path)))
    if not inputs['placements']:
        result = dict(apiVersion='platform.installer/container-images/v1alpha2', placements=inputs['ready'])
        secrets._write(result_path, result)
        return dict(status='READY', preparationDigest=digest(result))
    payload, known_hosts, values = preparation_payload(journal, inputs, runtime_release, value.get('preparationLease'))
    from execution_controller import _environment
    with tempfile.TemporaryDirectory(prefix='.runtime-image-preparation-', dir=journal.directory) as temporary:
        credentials_path = os.path.join(temporary, 'credentials.json')
        credentials = {'ansible_password': payload['password']} if payload.get('password') is not None else {'privateKey': payload['privateKey']}
        if payload.get('sudoPassword') is not None:
            credentials['ansible_become_password'] = payload['sudoPassword']
        secrets._write(credentials_path, credentials)
        trust_path = os.path.join(temporary, 'known_hosts')
        descriptor = os.open(trust_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(known_hosts)
        import yaml
        with open(os.path.join(release, 'manifest.yaml'), encoding='utf-8') as stream:
            bundle = yaml.safe_load(stream)
        variables = dict(platform_application_image_inputs=inputs, platform_application_image_bundle=bundle,
                         platform_application_image_secret_values=values, platform_application_image_result_path=result_path,
                         ansible_user=payload['username'])
        variables_path = os.path.join(temporary, 'vars.json')
        secrets._write(variables_path, variables)
        command = [sys.executable, os.path.join(release, 'ansible-core/tools/run_with_runtime_credentials.py'),
                   '--credentials-file', credentials_path, '--runtime-dir', os.path.join(temporary, 'identity'), '--',
                   'ansible-playbook', '-i', os.path.join(journal.directory, 'project/inventory/hosts.yml'),
                   os.path.join(release, 'ansible-core/playbooks/applications/images/prepare.yml'), '-e', '@' + variables_path]
        environment = _environment(release, leased_private_key=bool(payload.get('privateKey')))
        environment['ANSIBLE_SSH_ARGS'] = environment['ANSIBLE_SSH_ARGS'].replace(
            '/var/lib/platform-installer/execution/known_hosts', trust_path)
        child = subprocess.Popen(command, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        def cancel(_signal, _frame):
            raise LifecycleError('APPLICATION_IMAGE_PREPARATION_CANCELLED')
        previous = {signum: signal.signal(signum, cancel) for signum in (signal.SIGTERM, signal.SIGHUP)}
        try:
            if child.wait(timeout=max(1, inputs['expiresAt'] - time.time())):
                raise LifecycleError('APPLICATION_IMAGE_PREPARATION_FAILED')
        except BaseException:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
            if os.path.isfile(result_path):
                os.unlink(result_path)
            raise
        finally:
            for signum, handler in previous.items():
                signal.signal(signum, handler)
    result = secrets._read(result_path)
    return dict(status='READY', preparationDigest=digest(result))

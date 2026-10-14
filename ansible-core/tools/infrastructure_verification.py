"""B0 bounded infrastructure evidence in the existing private execution namespace.

Local clients may cache the returned summary, but only this node's journal may
authorize reuse. No target discovery, credentials or service rules live here.
"""
import copy
import hashlib
import json
import os
import re
import stat
import tempfile
import fcntl
from contextlib import contextmanager

from execution_lifecycle import Journal, LifecycleError, digest, validate_ownership

MODES = ('FULL_PROJECT', 'APPLICATION_LIBRARIES_ONLY', 'INFRASTRUCTURE_VERIFY_ONLY')
MANIFEST_VERSION = 'platform.installer/execution-manifest/v1alpha3'
PLAN_VERSION = 'platform.installer/plan/v1alpha5'
MAX_BYTES = 16 * 1024 * 1024


def _private(path, directory=False):
    info = os.lstat(path)
    if (info.st_uid != os.geteuid() or info.st_mode & 0o077 or (not directory and info.st_nlink != 1) or
            not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))):
        raise LifecycleError('INFRA_EVIDENCE_UNAVAILABLE')


def _read(path):
    _private(os.path.dirname(path), True)
    _private(path)
    if os.stat(path).st_size > MAX_BYTES:
        raise LifecycleError('INFRA_EVIDENCE_UNAVAILABLE')
    with open(path, encoding='utf-8') as stream:
        return json.load(stream)


def _write(path, value):
    parent = os.path.dirname(path)
    _private(parent, True)
    descriptor, temporary = tempfile.mkstemp(prefix='.infra-', dir=parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, sort_keys=True, separators=(',', ':'))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _path(root, project, create=False):
    _private(root, True)
    directory = os.path.join(root, 'infrastructure-verification')
    if create:
        os.makedirs(directory, mode=0o700, exist_ok=True)
    _private(directory, True)
    return os.path.join(directory, hashlib.sha256(project.encode('utf-8')).hexdigest() + '.json')


def _index(path):
    value = _read(path)
    if (not isinstance(value, dict) or set(value) != {'schemaVersion', 'projectIdentity', 'generation', 'model', 'trust', 'verifies'} or
            value['schemaVersion'] != 1 or not isinstance(value['generation'], str) or
            not re.fullmatch(r'[a-f0-9]{32}', value['generation']) or
            not isinstance(value['trust'], dict) or len(value['trust']) > 256 or
            not isinstance(value['verifies'], dict) or len(value['verifies']) > 256 or
            any(not isinstance(ref, dict) or set(ref) != {'runId'} or not isinstance(ref['runId'], str)
                for ref in value['verifies'].values())):
        raise LifecycleError('INFRA_EVIDENCE_UNAVAILABLE')
    return value


def model(manifest):
    """Resolved service operations, not project revision or an app-path exclusion list."""
    services = [op for op in manifest['operations'] if op['operation'] in ('SERVICE_APPLY', 'SERVICE_VERIFY')]
    verifies = [op for op in services if op['operation'] == 'SERVICE_VERIFY']
    coverage = {op['serviceDeployment']: digest(op) for op in verifies}
    if not coverage or len(coverage) != len(verifies):
        raise LifecycleError('INFRA_VERIFY_COVERAGE_INCOMPLETE')
    hosts = {host for op in services for host in op.get('targets', [])}
    semantic = dict(projectIdentity=manifest['projectIdentity'], runtimeRelease=manifest['runtimeRelease'],
                    services=sorted(services, key=lambda op: op['operationId']),
                    targetConnections={host: manifest.get('targetConnections', {}).get(host) for host in sorted(hosts)},
                    artifactSourceAuthorities=manifest['artifactSourceAuthorities'],
                    pkiMaterializationPlans=manifest['pkiMaterializationPlans'])
    return dict(fingerprint=digest(semantic), coverage=coverage, hosts=sorted(hosts))


def _trust(journal, manifest, hosts):
    connections = manifest.get('targetConnections', {})
    if not connections:
        return {}
    path = os.path.join(journal.directory, 'known_hosts')
    _private(path)
    with open(path, encoding='ascii') as stream:
        lines = stream.read(65537).splitlines()
    if len(lines) > 256:
        raise LifecycleError('INFRA_EVIDENCE_UNAVAILABLE')
    by_endpoint = {}
    for line in lines:
        fields = line.split()
        if len(fields) != 3 or fields[0] in by_endpoint:
            raise LifecycleError('INFRA_EVIDENCE_UNAVAILABLE')
        by_endpoint[fields[0]] = digest(fields[1:])
    result = {}
    for host in hosts:
        connection = connections[host]
        address, port = connection['address'], connection['port']
        endpoint = address if port == 22 else '[%s]:%s' % (address, port)
        result[host] = by_endpoint[endpoint]
    return result


def summary(root, project, expected):
    """Target-free, bounded and read-only. Revalidate every source journal."""
    result = dict(status='BLOCKED', infrastructureFingerprint=expected['fingerprint'],
                  evidenceRevision=None, deployments=[], code='INFRA_VERIFY_MISSING')
    try:
        index = _index(_path(root, project))
        if index.get('projectIdentity') != project or index.get('model') != expected:
            result['code'] = 'INFRA_VERIFY_STALE'
            return result
        result['evidenceRevision'] = digest(index)
        for deployment, coverage in sorted(expected['coverage'].items()):
            ref = index.get('verifies', {}).get(deployment)
            if not ref:
                continue
            journal = Journal(root, ref['runId'])
            _private(journal.directory, True)
            source = _read(os.path.join(journal.directory, 'manifest.json'))
            metadata = validate_ownership(journal)
            status = _read(journal.status_path)
            terminal = _read(journal.result_path)
            proof = _read(os.path.join(journal.directory, 'infrastructure-verifies.json'))
            if (metadata['projectIdentity'] != project or metadata['manifestDigest'] != digest(source) or
                    status.get('state') != terminal.get('state') or
                    terminal.get('state') not in ('SUCCEEDED', 'FAILED', 'CANCELLED') or
                    source.get('infrastructureVerification', {}).get('model') != expected or
                    proof.get('generation') != index['generation'] or
                    proof.get('trust') != index.get('trust') or
                    _trust(journal, source, expected['hosts']) != index.get('trust') or
                    proof.get('verifies', {}).get(deployment) != coverage):
                raise LifecycleError('INFRA_EVIDENCE_UNAVAILABLE')
            result['deployments'].append(dict(deploymentId=deployment, sourceRunId=journal.run_id,
                                               coverageDigest=coverage, verifiedAt=terminal['completedAt']))
        if len(result['deployments']) == len(expected['coverage']):
            result.update(status='PASS', code=None)
    except FileNotFoundError:
        pass
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        result.update(status='BLOCKED', code='INFRA_EVIDENCE_UNAVAILABLE', evidenceRevision=None, deployments=[])
    return result


def assert_admission(root, manifest, run_id=None):
    binding = manifest.get('infrastructureVerification', {})
    if manifest.get('executionMode') != 'APPLICATION_LIBRARIES_ONLY':
        return
    current = summary(root, manifest['projectIdentity'], binding['model'])
    if current['status'] != 'PASS' or current['evidenceRevision'] != binding['evidenceRevision']:
        raise LifecycleError('INFRA_EVIDENCE_CHANGED')
    if run_id is not None:
        index = _index(_path(root, manifest['projectIdentity']))
        if _trust(Journal(root, run_id), manifest, binding['model']['hosts']) != index.get('trust'):
            raise LifecycleError('INFRA_EVIDENCE_CHANGED')


def validate_manifest(manifest):
    binding = manifest.get('infrastructureVerification')
    if (manifest.get('executionMode') not in MODES or not isinstance(binding, dict) or
            set(binding) != {'model', 'evidenceRevision'} or
            not isinstance(binding['model'], dict) or set(binding['model']) != {'fingerprint', 'coverage', 'hosts'}):
        raise LifecycleError('EXECUTION_MANIFEST_INVALID')
    expected = binding['model']
    coverage = expected['coverage']
    if (not isinstance(expected['hosts'], list) or len(expected['hosts']) > 256 or
            any(not isinstance(host, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}', host) for host in expected['hosts']) or
            expected['hosts'] != sorted(set(expected['hosts'])) or
            not isinstance(coverage, dict) or not 1 <= len(coverage) <= 256 or
            not isinstance(expected['fingerprint'], str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', expected['fingerprint']) or
            any(not isinstance(key, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,127}', key) or
                not isinstance(value, str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', value)
                for key, value in coverage.items())):
        raise LifecycleError('EXECUTION_MANIFEST_INVALID')
    operations = manifest['operations']
    mode = manifest['executionMode']
    if mode == 'FULL_PROJECT' and model(manifest) != expected:
        raise LifecycleError('EXECUTION_MANIFEST_INVALID')
    if mode == 'INFRASTRUCTURE_VERIFY_ONLY':
        actual = {op['serviceDeployment']: digest(op) for op in operations if op['operation'] == 'SERVICE_VERIFY'}
        if (len(actual) != len(operations) or actual != coverage or manifest['applicationSecretRequirements'] or
                manifest['runtimeSecretOutputs']):
            raise LifecycleError('EXECUTION_MANIFEST_INVALID')
    if mode == 'APPLICATION_LIBRARIES_ONLY':
        if ([op['operation'] for op in operations] != ['APPLICATION_LIBRARIES_APPLY', 'APPLICATION_LIBRARIES_VERIFY'] or
                not isinstance(binding['evidenceRevision'], str) or
                not re.fullmatch(r'sha256:[a-f0-9]{64}', binding['evidenceRevision']) or
                manifest['runtimeSecretRequirements'] or manifest['runtimeSecretInputs'] or manifest['runtimeSecretOutputs'] or
                any(item['source'] != 'RUNTIME_INPUT' for item in manifest['applicationSecretRequirements'])):
            raise LifecycleError('EXECUTION_MANIFEST_INVALID')


def tracked(root, project):
    if not project:
        return False
    try:
        return os.path.exists(_path(root, project))
    except FileNotFoundError:
        return False


@contextmanager
def _admission_lock(root):
    descriptor = os.open(os.path.join(root, '.active-runs.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        _private(os.path.join(root, '.active-runs.lock'))
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def begin(journal, manifest):
    with _admission_lock(journal.root):
        _begin(journal, manifest)


def _begin(journal, manifest):
    """Once per infrastructure run; called before its first target operation."""
    mode = manifest.get('executionMode', 'FULL_PROJECT')
    if mode == 'APPLICATION_LIBRARIES_ONLY':
        assert_admission(journal.root, manifest, journal.run_id)
        return
    marker = os.path.join(journal.directory, 'infrastructure-verifies.json')
    if os.path.exists(marker):
        return
    path = _path(journal.root, manifest['projectIdentity'], True)
    expected = manifest.get('infrastructureVerification', {}).get('model')
    try:
        index = _index(path)
    except (OSError, ValueError):
        index = None
    trust = _trust(journal, manifest, expected['hosts']) if expected else {}
    if (mode != 'INFRASTRUCTURE_VERIFY_ONLY' or not index or index.get('model') != expected or
            index.get('trust') != trust):
        index = dict(schemaVersion=1, projectIdentity=manifest['projectIdentity'], generation=os.urandom(16).hex(),
                     model=expected, trust=trust, verifies={})
        _write(path, index)
    _write(marker, dict(generation=index['generation'], trust=trust, verifies={}))


def verify_pending(journal, operation):
    """A newer attempted Verify supersedes its old success, even on crash/failure."""
    with _admission_lock(journal.root):
        path = _path(journal.root, journal.metadata()['projectIdentity'])
        index = _index(path)
        proof = _read(os.path.join(journal.directory, 'infrastructure-verifies.json'))
        if index['generation'] != proof['generation']:
            raise LifecycleError('INFRA_EVIDENCE_CHANGED')
        # A pending/failed source is deliberately not usable by summary(). Keep
        # the latest attempt reference so an older publisher cannot restore it.
        index['verifies'][operation['serviceDeployment']] = dict(runId=journal.run_id)
        _write(path, index)


def verified(journal, operation):
    try:
        stats = _read(_coverage_path(journal, operation['operationId']))
        for host in operation['targets']:
            counts = stats[host]
            if counts['ok'] < 1 or any(counts[key] for key in ('changed', 'failures', 'unreachable', 'ignored', 'rescued')):
                return False
    except (OSError, ValueError, KeyError, TypeError):
        return False
    path = os.path.join(journal.directory, 'infrastructure-verifies.json')
    proof = _read(path)
    proof['verifies'][operation['serviceDeployment']] = digest(operation)
    _write(path, proof)
    return True


def _coverage_path(journal, action_id):
    return os.path.join(journal.directory, 'verify-coverage-' + hashlib.sha256(action_id.encode('utf-8')).hexdigest() + '.json')


def record_stats(journal, action_id, stats):
    """Only bounded numeric Ansible recap counters, never task payloads."""
    manifest = _read(os.path.join(journal.directory, 'manifest.json'))
    validate_ownership(journal)
    if (manifest.get('apiVersion') != MANIFEST_VERSION or journal.status().get('state') != 'RUNNING' or
            not any(op['operationId'] == action_id and op['operation'] == 'SERVICE_VERIFY' for op in manifest['operations']) or
            not isinstance(stats, dict) or len(stats) > 257):
        raise LifecycleError('INFRA_VERIFY_COVERAGE_INCOMPLETE')
    fields = ('ok', 'changed', 'failures', 'unreachable', 'ignored', 'rescued')
    result = {}
    for host, counts in stats.items():
        if (not isinstance(host, str) or len(host) > 255 or not isinstance(counts, dict) or
                any(type(counts.get(key)) is not int or not 0 <= counts[key] <= 1000000 for key in fields)):
            raise LifecycleError('INFRA_VERIFY_COVERAGE_INCOMPLETE')
        result[host] = {key: counts[key] for key in fields}
    _write(_coverage_path(journal, action_id), result)


def publish(journal, manifest):
    with _admission_lock(journal.root):
        _publish(journal, manifest)


def before_terminal(journal, manifest, state):
    # Revoke while the run is still ACTIVE, before another Start can be admitted.
    if manifest.get('apiVersion') != MANIFEST_VERSION or state == 'SUCCEEDED':
        return
    application_started = manifest.get('executionMode') == 'APPLICATION_LIBRARIES_ONLY' or any(
        event.get('eventType') == 'ACTION_STARTED' and event.get('actionId') == 'applications:apply'
        for event in journal.events())
    if application_started:
        with _admission_lock(journal.root):
            path = _path(journal.root, manifest['projectIdentity'])
            _revoke_library_failure(journal, manifest, path, _index(path))


def _revoke_library_failure(journal, manifest, path, index):
    if manifest['executionMode'] == 'APPLICATION_LIBRARIES_ONLY':
        if digest(index) != manifest['infrastructureVerification']['evidenceRevision']:
            return
    else:
        proof = _read(os.path.join(journal.directory, 'infrastructure-verifies.json'))
        if index['generation'] != proof['generation']:
            return
    try:
        failure = _read(os.path.join(journal.directory, 'application-failure-domain.json'))
    except (OSError, ValueError):
        failure = None
    if not isinstance(failure, dict) or failure.get('domain') != 'APPLICATION_ONLY':
        index.update(generation=os.urandom(16).hex(), verifies={})
        _write(path, index)


def _publish(journal, manifest):
    """Optional derived index publication after durable terminal; never replay work."""
    if manifest.get('apiVersion') != MANIFEST_VERSION:
        return
    path = _path(journal.root, manifest['projectIdentity'])
    index = _index(path)
    status, result = _read(journal.status_path), _read(journal.result_path)
    if status.get('state') != result.get('state') or result.get('state') not in ('SUCCEEDED', 'FAILED', 'CANCELLED'):
        return
    if manifest.get('executionMode') == 'APPLICATION_LIBRARIES_ONLY':
        if result['state'] != 'SUCCEEDED':
            _revoke_library_failure(journal, manifest, path, index)
        return
    proof = _read(os.path.join(journal.directory, 'infrastructure-verifies.json'))
    if (
            index['generation'] != proof['generation'] or index['model'] != manifest['infrastructureVerification']['model']):
        return
    for deployment, coverage in proof['verifies'].items():
        if (index['model']['coverage'].get(deployment) == coverage and
                index['verifies'].get(deployment) == {'runId': journal.run_id}):
            index['verifies'][deployment] = dict(runId=journal.run_id)
    _write(path, index)


def record_application_failure(journal, application_only=False, action_id=None):
    """Called by the trusted task callback; unknown/provider failures dominate."""
    validate_ownership(journal)
    manifest = _read(os.path.join(journal.directory, 'manifest.json'))
    if (manifest.get('executionMode') not in ('APPLICATION_LIBRARIES_ONLY', 'FULL_PROJECT') or
            journal.status()['state'] != 'RUNNING' or
            (manifest.get('executionMode') == 'FULL_PROJECT' and action_id not in ('applications:apply', 'applications:verify'))):
        return
    path = os.path.join(journal.directory, 'application-failure-domain.json')
    descriptor = journal.event_lock()
    try:
        try:
            previous = _read(path)
        except FileNotFoundError:
            previous = None
        domain = 'APPLICATION_ONLY' if application_only and (previous is None or previous.get('domain') == 'APPLICATION_ONLY') else 'UNKNOWN'
        _write(path, dict(domain=domain))
    finally:
        os.close(descriptor)


def scope_plan(result, mode, root):
    """Project the already resolved full plan into a fixed B0 scope."""
    if mode not in MODES:
        raise LifecycleError('EXECUTION_MODE_UNSUPPORTED')
    result = copy.deepcopy(result)
    plan, manifest = result['deploymentPlan'], result['executionManifest']
    plan['apiVersion'] = PLAN_VERSION
    plan['executionMode'] = mode
    plan['infrastructureVerification'] = dict(status='UNKNOWN', infrastructureFingerprint=None,
        evidenceRevision=None, deployments=[], code='INFRA_EVIDENCE_UNAVAILABLE')
    if manifest is None:
        return result
    expected = model(manifest)
    observation = summary(root, manifest['projectIdentity'], expected)
    binding = dict(model=expected, evidenceRevision=observation['evidenceRevision'])
    manifest.update(apiVersion=MANIFEST_VERSION, executionMode=mode, infrastructureVerification=binding)
    manifest.setdefault('applicationSecretRequirements', [])
    if mode == 'APPLICATION_LIBRARIES_ONLY':
        if observation['status'] != 'PASS':
            plan['status'], plan['readiness'] = 'BLOCKED', 'BLOCKED'
            plan['findings'].append(dict(apiVersion='platform.installer/finding/v1alpha1', kind='Finding',
                code=observation['code'], status='BLOCKED', category='deployment-plan', field='infrastructureVerification',
                safeMessage='Infrastructure Verify evidence is missing or stale'))
            result['executionManifest'] = None
        if any(item['source'] != 'RUNTIME_INPUT' for item in manifest['applicationSecretRequirements']):
            raise LifecycleError('APPLICATION_BOOTSTRAP_PROVIDER_INVALID')
        phases = [p for p in plan['phases'] if p['id'] == 'applications']
        if not phases:
            raise LifecycleError('APPLICATION_LIBRARIES_REQUIRED')
        phases[0]['actions'][0]['dependsOn'] = []
        manifest['operations'] = [op for op in manifest['operations'] if op['operation'].startswith('APPLICATION_LIBRARIES_')]
        manifest['runtimeSecretRequirements'] = []
        manifest['runtimeSecretInputs'] = []
        manifest['runtimeSecretOutputs'] = []
        manifest['requiredCredentials'] = [{k: item[k] for k in ('requirementRef', 'purpose', 'hosts')}
                                           for item in manifest['applicationSecretRequirements']]
        manifest['runtimeSecretDescriptorSetFingerprint'] = digest(dict(serviceDescriptors=[],
            applicationDescriptors=manifest['applicationSecretRequirements']))
        manifest['artifactRequirements'] = [item for item in manifest['artifactRequirements'] if item.get('artifactType') == 'container-image']
        manifest['artifactSourceAuthorities'] = []
    elif mode == 'INFRASTRUCTURE_VERIFY_ONLY':
        phases = [p for p in plan['phases'] if p['id'] == 'services']
        phases[0]['actions'] = [a for a in phases[0]['actions'] if a['type'] == 'SERVICE_VERIFY']
        for action in phases[0]['actions']:
            action['dependsOn'] = []
        manifest['operations'] = [op for op in manifest['operations'] if op['operation'] == 'SERVICE_VERIFY']
        manifest['applicationSecretRequirements'] = []
        manifest['artifactRequirements'] = []
        manifest['artifactSourceAuthorities'] = []
        manifest['runtimeSecretOutputs'] = []
        manifest['runtimeSecretInputs'] = [item for item in manifest['runtimeSecretInputs'] if 'SERVICE_VERIFY' in item['operations']]
        # Preserve the existing typed lease declaration contract. There is no
        # Apply operation in this manifest to consume its Apply permission.
        # Verify may read existing PKI, but must never run PKI materialization.
        manifest['runtimeSecretRequirements'] = [item for item in manifest['runtimeSecretRequirements'] if item['purpose'] == 'SERVICE_PASSWORD']
        names = {item['requirementRef'] for item in manifest['runtimeSecretRequirements'] + manifest['runtimeSecretInputs']}
        manifest['requiredCredentials'] = [item for item in manifest['requiredCredentials'] if item['requirementRef'] in names]
    else:
        phases = plan['phases']
    plan['phases'] = phases
    for order, phase in enumerate(phases):
        phase['order'] = order
    plan['requiredCredentials'] = manifest['requiredCredentials']
    plan['artifactRequirements'] = manifest['artifactRequirements']
    plan['infrastructureVerification'] = observation
    fingerprint = digest(dict(previous=plan['fingerprints']['plan'], mode=mode, binding=binding, phases=phases))
    plan['fingerprints']['plan'] = manifest['planFingerprint'] = fingerprint
    plan['id'] = 'plan-' + fingerprint.split(':')[1][:24]
    result['executionManifestDigest'] = digest(manifest) if result['executionManifest'] else None
    return result

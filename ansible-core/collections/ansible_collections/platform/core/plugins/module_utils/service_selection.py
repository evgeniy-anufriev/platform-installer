"""Invocation-only service selection; provider definitions remain in the snapshot."""
import copy
try:
    from .project_validation import canonical_digest
except ImportError:
    from project_validation import canonical_digest

PLAN_VERSION = 'platform.installer/plan/v1alpha11'
MANIFEST_VERSION = 'platform.installer/execution-manifest/v1alpha8'


def execution_scope(deployments, order, skipped):
    skipped = [] if skipped is None else skipped
    if (not isinstance(skipped, list) or any(not isinstance(item, str) for item in skipped)
            or len(skipped) != len(set(skipped)) or set(skipped) - set(deployments)):
        raise ValueError('SERVICE_SELECTION_INVALID')
    return dict(serviceOrder=list(order), skippedServices=sorted(skipped),
                installServices=[key for key in order if key not in skipped])


def select_pki(materialization, selected):
    """Materialize only selected service consumers, retaining shared requests."""
    if not isinstance(materialization, dict):
        return materialization
    result = copy.deepcopy(materialization)
    requests = []
    for request in result.get('requests', []):
        request['consumers'] = [c for c in request.get('consumers', []) if c.get('deploymentId') in selected]
        if request['consumers']:
            requests.append(request)
    result['requests'] = requests
    allowed = {(r['id'], c['hostId']) for r in requests for c in r['consumers']}
    result['materializationPlans'] = [p for p in result.get('materializationPlans', [])
                                    if (p.get('requestId'), p.get('hostId')) in allowed]
    return result


def promote(result, scope):
    plan = result['deploymentPlan']
    for document, version in ((plan, PLAN_VERSION), (result.get('executionManifest'), MANIFEST_VERSION)):
        if document is not None:
            document.update(apiVersion=version, skipServiceDeployments=scope['skippedServices'], serviceExecutionScope=scope)
    fingerprint = canonical_digest(dict(previous=plan['fingerprints']['plan'], serviceExecutionScope=scope))
    plan['fingerprints']['plan'] = fingerprint
    plan['id'] = 'plan-' + fingerprint.split(':')[1][:24]
    if result.get('executionManifest'):
        result['executionManifest']['planFingerprint'] = fingerprint
    return result


def validation_prefix(manifest):
    scope = manifest['serviceExecutionScope']
    expected = execution_scope(dict.fromkeys(scope['serviceOrder']), scope['serviceOrder'], manifest['skipServiceDeployments'])
    if (scope != expected or len(scope['serviceOrder']) != len(set(scope['serviceOrder']))
            or manifest['executionMode'] != 'FULL_PROJECT' or manifest['skipInfrastructureVerify']):
        raise ValueError('SERVICE_SELECTION_INVALID')
    services = [op for op in manifest['operations'] if op['operation'] in ('SERVICE_APPLY', 'SERVICE_VERIFY')]
    if ([op['serviceDeployment'] for op in services if op['operation'] == 'SERVICE_APPLY'] != scope['installServices']
            or [op['serviceDeployment'] for op in services if op['operation'] == 'SERVICE_VERIFY'] != scope['installServices']):
        raise ValueError('SERVICE_SELECTION_MANIFEST_MISMATCH')
    if any(item.get('serviceDeployment') in scope['skippedServices'] for item in manifest['runtimeSecretInputs'] + manifest['runtimeSecretOutputs']):
        raise ValueError('SERVICE_SELECTION_MANIFEST_MISMATCH')
    result = copy.deepcopy(manifest)
    result.pop('skipServiceDeployments')
    result.pop('serviceExecutionScope')
    result['apiVersion'] = ('platform.installer/execution-manifest/v1alpha7'
                            if any(op['operation'] == 'APPLICATION_LIBRARIES_POST_INSTALL' for op in manifest['operations'])
                            else 'platform.installer/execution-manifest/v1alpha6')
    return result

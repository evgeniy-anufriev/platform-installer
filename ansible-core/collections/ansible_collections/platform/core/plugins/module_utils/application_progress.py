"""Display-only steps for the existing application Apply operation."""
try:
    from .project_validation import canonical_digest
except ImportError:
    from project_validation import canonical_digest


def describe_progress(result, scope, skip_infrastructure_verify=False):
    plan = result['deploymentPlan']
    applies = [action for phase in plan.get('phases', []) for action in phase['actions']
               if action['type'] == 'APPLICATION_LIBRARIES_APPLY']
    if not applies or 'executionMode' not in plan:
        return result
    applies[0]['progressSteps'] = [dict(id='applications:prepare', summary='Подготовить ресурсы и провайдеров')] + [
        dict(id='applications:library:' + identity, summary='Установить и проверить библиотеку ' + identity)
        for identity in scope['installLibraries']]
    plan.update(apiVersion='platform.installer/plan/v1alpha10',
                skipApplicationLibraries=scope['skippedLibraries'], applicationExecutionScope=scope,
                skipInfrastructureVerify=skip_infrastructure_verify)
    fingerprint = canonical_digest(dict(previous=plan['fingerprints']['plan'], phases=plan['phases']))
    plan['fingerprints']['plan'] = fingerprint
    plan['id'] = 'plan-' + fingerprint.split(':')[1][:24]
    if result.get('executionManifest'):
        result['executionManifest']['planFingerprint'] = fingerprint
    return result

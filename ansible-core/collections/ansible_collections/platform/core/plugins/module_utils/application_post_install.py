"""Terminal package-script operation; existing lifecycle and runner remain owners."""
import copy

OPERATION = 'APPLICATION_LIBRARIES_POST_INSTALL'
PLAN_VERSION = 'platform.installer/plan/v1alpha9'
MANIFEST_VERSION = 'platform.installer/execution-manifest/v1alpha7'
OPERATIONS = ['APPLICATION_LIBRARIES_APPLY', 'APPLICATION_LIBRARIES_VERIFY', OPERATION]


def promote(result, scope, skip_infrastructure_verify=False):
    """Use the new contracts only when the scoped plan contains the new action."""
    plan = result['deploymentPlan']
    if not any(a['type'] == OPERATION for p in plan.get('phases', []) for a in p['actions']):
        return result
    for document, version in ((plan, PLAN_VERSION), (result.get('executionManifest'), MANIFEST_VERSION)):
        if document is not None:
            document.update(apiVersion=version, skipApplicationLibraries=scope['skippedLibraries'],
                            applicationExecutionScope=scope, skipInfrastructureVerify=skip_infrastructure_verify)
    return result


def validation_prefix(manifest):
    """Validate the new terminal suffix before reusing prior infrastructure checks.

    This copy is admission-only, never dispatched or used to authorize secrets.
    The caller also validates the complete original against the v1alpha7 schema.
    """
    operations = manifest['operations']
    terminal = [item for item in operations if item['operation'] == OPERATION]
    if len(terminal) != 1 or terminal != operations[-1:] or len(operations) < 2:
        raise ValueError('APPLICATION_POST_INSTALL_ORDER_INVALID')
    last = terminal[0]
    lifecycle = OPERATIONS[:2] if operations[-2]['operation'] == OPERATIONS[1] else OPERATIONS[:1]
    if ([item['operation'] for item in operations[-len(lifecycle)-1:]] != lifecycle + [OPERATION] or
            last['operationId'] != 'applications:post-install' or
            manifest.get('executionMode') == 'INFRASTRUCTURE_VERIFY_ONLY'):
        raise ValueError('APPLICATION_POST_INSTALL_ORDER_INVALID')
    for field in ('phaseId', 'targets', 'applicationLibraries', 'applicationSemanticFingerprint', 'applicationExecutionScope'):
        if last.get(field) != operations[-2].get(field):
            raise ValueError('APPLICATION_POST_INSTALL_SCOPE_INVALID')
    result = copy.deepcopy(manifest)
    result['apiVersion'] = 'platform.installer/execution-manifest/v1alpha6'
    result['operations'] = result['operations'][:-1]
    for item in result['applicationSecretRequirements']:
        declared = item['operations']
        if not declared or declared != [op for op in OPERATIONS if op in declared]:
            raise ValueError('APPLICATION_POST_INSTALL_SECRET_SCOPE_INVALID')
        # Existing prefix admission expects lifecycle descriptors. Original exact
        # operation permissions remain in the immutable manifest and lease.
        item['operations'] = [op for op in declared if op != OPERATION] or OPERATIONS[:2]
    return result


def script_queue(jobs, library_order):
    """Resolved declarations already enforce once/each_target and library scope."""
    queue = [dict(script, libraryId=job['libraryId'], instanceId=job['instanceId'], hostId=job['hostId'])
             for job in jobs for script in job.get('scripts', []) if script['phase'] == 'post_install']
    return sorted(queue, key=lambda item: (library_order.index(item['libraryId']), item['order'], item['id'],
                                          0 if item['scope'] == 'library' else 1, item['instanceId'], item['hostId']))

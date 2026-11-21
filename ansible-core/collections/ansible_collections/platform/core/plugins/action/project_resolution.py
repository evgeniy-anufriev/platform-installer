"""Load/store a controller-private desired-derived result."""
import os
import time
from ansible.plugins.action import ActionBase
from ansible_collections.platform.core.plugins.module_utils import project_resolution as resolution


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        task_vars = task_vars or {}
        args = self._task.args
        local = task_vars.get('platform_project_resolution_local_path')
        directory = task_vars.get('platform_project_resolution_directory')
        operation = args.get('operation')
        if (not local and operation not in ('load', 'reuse_application_rows')) or (
                operation == 'reuse_application_rows' and not task_vars.get('_application_image_resolution_context')):
            return dict(changed=False, hit=False)
        try:
            started = time.monotonic()
            project = os.path.realpath(task_vars.get('platform_project_root') or os.path.dirname(task_vars['inventory_dir']))
            runtime = task_vars.get('platform_project_resolution_runtime') or {
                'source': os.path.realpath(os.path.join(os.path.dirname(__file__), '../../../../../../..'))}
            expected, documents = resolution.identity(project, runtime,
                task_vars.get('platform_installer_owned_paths', []))
            expected['controller'] = task_vars.get('inventory_hostname')
            shared_expected = dict(expected)
            context = task_vars.get('platform_plan_resolution_context')
            if context:
                expected.update(planContext=context, stagedProject=project)
            invocation = dict(identity=expected, project=project,
                              catalog=os.path.realpath(task_vars.get('platform_service_catalog_path', '')))
            if operation == 'reuse_application_rows':
                # Same Ansible operation only. Keep the normal fresh snapshot
                # after this step; image enrichment and plan proof are unchanged.
                result = task_vars.get('platform_image_snapshot', {})
                if not isinstance(result, dict) or not isinstance(result.get('snapshot'), dict):
                    return dict(changed=False, hit=False)
                snapshot = result.get('snapshot', {})
                rows = result.get('application_rows')
                findings = result.get('application_findings')
                hit = (task_vars['_application_image_resolution_context'] == invocation
                       and snapshot.get('projectRevision') == expected['revision']
                       and isinstance(rows, list)
                       and isinstance(findings, list)
                       and bool(rows or findings)
                       and all(isinstance(row, dict) for row in rows + findings))
                return dict(changed=False, hit=hit, application_rows=rows if hit else [],
                            application_findings=findings if hit else [])
            if not local:
                return dict(changed=False, hit=False, identity=expected, invocation_context=invocation)
            shared = os.path.join(directory, resolution.scope_name(project, runtime)) if directory else None
            if args.get('operation') == 'load':
                result = resolution.read(local, expected)
                source = 'request' if result is not None else 'fresh'
                if result is None:
                    result = resolution.read(shared, shared_expected)
                    if result is not None:
                        source = 'shared'
                        resolution.write(local, expected, result)
                resolution.atomic_json(local + '.metrics', dict(hit=result is not None,
                    source=source, readSeconds=round(time.monotonic() - started, 6)))
                return dict(changed=False, hit=result is not None, result=result or {},
                            identity=expected, started=started, invocation_context=invocation)
            reference = args.get('result_variable')
            if reference is not None and (reference != 'platform_project_resolution' or 'result' in args):
                raise ValueError('PROJECT_RESOLUTION_INVALID')
            result = task_vars[reference] if reference is not None else args['result']
            previous = task_vars['_project_resolution_cache']
            if (previous['identity'] != expected or
                    result['snapshot']['projectRevision'] != expected['revision']):
                raise ValueError('PROJECT_RESOLUTION_INPUT_CHANGED')
            root = os.path.realpath(os.path.join(os.path.dirname(__file__), '../../../../../../..'))
            eligible = resolution.reusable(project, documents, result, os.path.join(root, 'services'))
            if context or eligible:
                resolution.write(local, expected, result)
            if eligible and shared:
                # Only a closed desired-only result can cross requests. Local
                # results keep their stricter planContext/staging-path binding.
                resolution.write(shared, shared_expected, result)
            resolution.atomic_json(local + '.metrics', dict(hit=False, source='fresh', reusable=eligible,
                resolveSeconds=round(time.monotonic() - previous['started'], 6)))
            return dict(changed=False, hit=False)
        except (OSError, KeyError, TypeError, ValueError) as error:
            code = 'PROJECT_RESOLUTION_INPUT_CHANGED' if str(error) == 'PROJECT_RESOLUTION_INPUT_CHANGED' else 'PROJECT_RESOLUTION_INVALID'
            return dict(failed=True, changed=False, msg=code, error_code=code)

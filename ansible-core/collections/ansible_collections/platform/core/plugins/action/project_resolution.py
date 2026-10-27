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
        if not local:
            return dict(changed=False, hit=False)
        try:
            started = time.monotonic()
            project = os.path.realpath(task_vars['platform_project_root'])
            runtime = task_vars['platform_project_resolution_runtime']
            expected, documents = resolution.identity(project, runtime,
                task_vars.get('platform_installer_owned_paths', []))
            shared = os.path.join(directory, resolution.scope_name(project, runtime)) if directory else None
            if args.get('operation') == 'load':
                result = resolution.read(local, expected)
                source = 'request' if result is not None else 'fresh'
                if result is None:
                    result = resolution.read(shared, expected)
                    if result is not None:
                        source = 'shared'
                        resolution.write(local, expected, result)
                resolution.atomic_json(local + '.metrics', dict(hit=result is not None,
                    source=source, readSeconds=round(time.monotonic() - started, 6)))
                return dict(changed=False, hit=result is not None, result=result or {},
                            identity=expected, started=started)
            result = args['result']
            previous = task_vars['_project_resolution_cache']
            if (previous['identity'] != expected or
                    result['snapshot']['projectRevision'] != expected['revision']):
                raise ValueError('PROJECT_RESOLUTION_INPUT_CHANGED')
            root = os.path.realpath(os.path.join(os.path.dirname(__file__), '../../../../../../..'))
            eligible = resolution.reusable(project, documents, result, os.path.join(root, 'services'))
            if eligible:
                resolution.write(local, expected, result)
                resolution.write(shared, expected, result)
            resolution.atomic_json(local + '.metrics', dict(hit=False, source='fresh', reusable=eligible,
                resolveSeconds=round(time.monotonic() - previous['started'], 6)))
            return dict(changed=False, hit=False)
        except (OSError, KeyError, TypeError, ValueError) as error:
            code = 'PROJECT_RESOLUTION_INPUT_CHANGED' if str(error) == 'PROJECT_RESOLUTION_INPUT_CHANGED' else 'PROJECT_RESOLUTION_INVALID'
            return dict(failed=True, changed=False, msg=code, error_code=code)

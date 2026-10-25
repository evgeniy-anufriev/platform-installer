"""Controller-only preparation inputs from native Ansible rows and bundle metadata."""
import json
import os
from ansible.plugins.action import ActionBase
from ansible_collections.platform.core.plugins.module_utils.application_images import (
    registry_request, selected_image, offline_image, placement_key, normalize_image,
)
from ansible_collections.platform.core.plugins.module_utils.application_runtime import resolve_image_lock
from ansible_collections.platform.core.plugins.module_utils.application_plan import application_execution_model
from ansible_collections.platform.core.plugins.module_utils.project_validation import canonical_digest


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        values = task_vars or {}
        args = self._task.args
        try:
            root = args['project_root']
            manifest_path = os.path.join(root, 'project.yml')
            project = self._loader.load_from_file(manifest_path) if os.path.isfile(manifest_path) else {}
            lock = resolve_image_lock(values.get('platform_artifact_lock'), (project or {}).get('artifactLock'))
            snapshot = args['snapshot']
            if snapshot.get('validation', {}).get('status') != 'PASS':
                raise ValueError('APPLICATION_IMAGE_PROJECT_INVALID')
            bundle = self._loader.load_from_file(os.path.join(args['bundle_root'], 'manifest.yaml'))
            from ansible_collections.platform.core.plugins.module_utils.application_selection import execution_scope
            scope = execution_scope(snapshot, values.get('platform_execution_application_library_order'), values.get('platform_execution_skip_application_libraries'))
            placements, ready, targets = [], {}, set()
            for row in ([] if values.get('platform_execution_mode') == 'INFRASTRUCTURE_VERIFY_ONLY' else values.get('platform_application_rows', [])):
                if row['libraryId'] not in scope['installLibraries']:
                    continue
                reference = row['settings']['image']
                legacy = selected_image(lock, reference, row['libraryId'], row['instanceId'], row['hostId'])
                request = registry_request(reference, legacy)
                host = values['hostvars'][row['hostId']]
                policy = list(host.get('platform_application_approved_registries', []))
                if legacy:
                    ready[placement_key(row)] = dict(reference=reference, image=legacy)
                    continue
                candidates = [item for item in bundle.get('containerImages', [])
                              if normalize_image(item['reference']) == normalize_image(reference)]
                if request['registry'] not in policy and len(candidates) == 1:
                    ready[placement_key(row)] = dict(reference=reference, image=offline_image(bundle, reference, candidates[0]['platform']))
                    continue
                if request['registry'] not in policy and not candidates:
                    raise ValueError('APPLICATION_IMAGE_NOT_LOCKED')
                placements.append(dict(libraryId=row['libraryId'], instanceId=row['instanceId'], hostId=row['hostId'],
                                       reference=reference, request=request, legacy=legacy or {},
                                       account=snapshot['effectiveConfiguration']['services'][row['runtimeRef']]['configuration'].get('accountName', {}).get('value', ''),
                                       configDirectory=host.get('platform_application_registry_config_directory', ''),
                                       credentials=row.get('registryCredentials', {}).get(request['registry'], {})))
                targets.add(row['hostId'])
            model = application_execution_model(snapshot, lock, scope['libraryOrder'], scope['skippedLibraries'])
            needed_refs = {pair[name]['source']['ref'] for item in placements
                           for pair in [item['credentials']] if pair for name in ('username', 'password')}
            requirements = [item for item in model['runtimeSecretRequirements'] if item['purpose'].startswith('APPLICATION_REGISTRY_') and item['runtimeReference'] in needed_refs]
            connections = {host: args['connections'][host] for host in sorted(targets)}
            result = dict(projectIdentity=snapshot['project']['id'], projectRevision=snapshot['projectRevision'],
                          placements=placements, ready=ready, targetConnections=connections,
                          requirements=requirements, descriptorSetFingerprint=canonical_digest(requirements))
            return dict(changed=False, inputs=result)
        except (KeyError, TypeError, ValueError, OSError) as error:
            code = str(error)
            if not code.startswith('APPLICATION_') or not code.replace('_', '').isalnum():
                code = 'APPLICATION_IMAGE_INPUT_INVALID'
            return dict(failed=True, changed=False, error_code=code, msg=code)

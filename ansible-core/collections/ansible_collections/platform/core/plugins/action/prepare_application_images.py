"""Controller-only preparation inputs from native Ansible rows and bundle metadata."""
import json
import os
import re
from ansible.plugins.action import ActionBase
from ansible_collections.platform.core.plugins.module_utils.application_images import (
    registry_request, selected_image, offline_image, placement_key, normalize_image,
)
from ansible_collections.platform.core.plugins.module_utils.application_runtime import resolve_image_lock
from ansible_collections.platform.core.plugins.module_utils.application_plan import application_execution_model
from ansible_collections.platform.core.plugins.module_utils.project_validation import canonical_digest


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def _availability_inputs(self, args, values, snapshot):
        from ansible_collections.platform.core.plugins.module_utils.application_selection import execution_scope
        scope = execution_scope(snapshot, values.get('platform_execution_application_library_order'), values.get('platform_execution_skip_application_libraries'))
        intents, probes, targets = {}, {}, set()
        rows = [] if values.get('platform_execution_mode') == 'INFRASTRUCTURE_VERIFY_ONLY' else args.get('application_rows', values.get('platform_application_rows', []))
        for row in rows:
            if row['libraryId'] not in scope['installLibraries']:
                continue
            reference = row['settings']['image']
            request = registry_request(reference)
            policy = set(values['hostvars'][row['hostId']].get('platform_application_approved_registries', [])) | set(row.get('registryCredentials', {}))
            registry = request['registry'] in policy
            intents[placement_key(row)] = dict(reference=reference, registry=registry)
            if registry:
                probes[(row['hostId'], request['registry'])] = dict(hostId=row['hostId'], endpoint=request['endpoint'])
                targets.add(row['hostId'])
        return dict(projectIdentity=snapshot['project']['id'], projectRevision=snapshot['projectRevision'],
                    placements=list(probes.values()), ready=dict(apiVersion='platform.installer/application-image-intents/v1alpha1', placements=intents),
                    targetConnections={host: args['connections'][host] for host in sorted(targets)},
                    requirements=[], descriptorSetFingerprint=canonical_digest([]), availabilityOnly=True)

    def run(self, tmp=None, task_vars=None):
        values = task_vars or {}
        args = self._task.args
        row, stage = {}, 'project-lock'
        try:
            root = args['project_root']
            manifest_path = os.path.join(root, 'project.yml')
            project = self._loader.load_from_file(manifest_path) if os.path.isfile(manifest_path) else {}
            lock = resolve_image_lock(values.get('platform_artifact_lock'), (project or {}).get('artifactLock'))
            stage = 'project-snapshot'
            snapshot = args['snapshot']
            if snapshot.get('validation', {}).get('status') != 'PASS':
                raise ValueError('APPLICATION_IMAGE_PROJECT_INVALID')
            if values.get('platform_application_image_availability_only'):
                return dict(changed=False, inputs=self._availability_inputs(args, values, snapshot))
            stage = 'bundle-manifest'
            bundle = self._loader.load_from_file(os.path.join(args['bundle_root'], 'manifest.yaml'))
            from ansible_collections.platform.core.plugins.module_utils.application_selection import execution_scope
            scope = execution_scope(snapshot, values.get('platform_execution_application_library_order'), values.get('platform_execution_skip_application_libraries'))
            placements, ready, targets = [], {}, set()
            for row in ([] if values.get('platform_execution_mode') == 'INFRASTRUCTURE_VERIFY_ONLY' else args.get('application_rows', values.get('platform_application_rows', []))):
                if row['libraryId'] not in scope['installLibraries']:
                    continue
                reference = row['settings']['image']
                stage = 'existing-image-lock'
                legacy = selected_image(lock, reference, row['libraryId'], row['instanceId'], row['hostId'])
                stage = 'source-policy'
                request = registry_request(reference, legacy)
                host = values['hostvars'][row['hostId']]
                policy = set(host.get('platform_application_approved_registries', [])) | set(row.get('registryCredentials', {}))
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
            row, stage = {}, 'secret-requirements'
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
            stages = {
                'project-lock': 'чтение фиксации образов проекта',
                'project-snapshot': 'проверка снимка проекта',
                'bundle-manifest': 'чтение манифеста набора установки',
                'existing-image-lock': 'сопоставление ранее зафиксированного образа',
                'source-policy': 'выбор разрешённого источника образа',
                'secret-requirements': 'получение требований к секретам образов',
            }
            reasons = {
                'APPLICATION_IMAGE_NOT_LOCKED': ('Registry образа не разрешён для этого размещения; в наборе установки образ отсутствует.'
                    if stage == 'source-policy' else 'Запись фиксации размещения не соответствует выбранному образу.'),
                'APPLICATION_ARTIFACT_LOCK_CONFLICT': 'Обнаружены противоречащие друг другу фиксации образа.',
                'APPLICATION_IMAGE_REFERENCE_INVALID': 'Укажите имя образа с тегом, без SHA или @sha256.',
                'APPLICATION_IMAGE_PROJECT_INVALID': 'Снимок проекта содержит блокирующие замечания.',
                'APPLICATION_IMAGE_ARCHIVE_AMBIGUOUS': 'Найдено несколько подходящих архивов образа.',
                'APPLICATION_IMAGE_ARCHIVE_NOT_LOCKED': 'Архив образа не подтверждён компонентами набора установки.',
            }
            message = 'Этап: ' + stages[stage] + '. ' + reasons.get(code, 'Некорректные входные данные подготовки образов.')
            field = 'applicationImages'
            for key, label in (('libraryId', 'Библиотека'), ('instanceId', 'Приложение'), ('hostId', 'Узел')):
                value = row.get(key)
                if isinstance(value, str) and re.fullmatch(r'[a-zA-Z0-9_.-]{1,96}', value):
                    message += ' ' + label + ': «' + value[:48] + '».'
                    field += '.' + value[:48]
            try:
                reference = normalize_image(row.get('settings', {}).get('image'))
                message += ' Образ: «' + reference[:192] + '».'
            except (ValueError, TypeError, AttributeError):
                pass  # Invalid input text is never copied into a public diagnostic.
            finding = dict(apiVersion='platform.installer/finding/v1alpha1', kind='Finding', code=code,
                           status='BLOCKED', category='application-images', field=field, safeMessage=message[:512])
            return dict(failed=True, changed=False, error_code=code, msg=code, finding=finding)

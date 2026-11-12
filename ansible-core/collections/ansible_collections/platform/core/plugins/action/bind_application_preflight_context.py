"""Bind already resolved placement fields without re-templating each fact."""
import hashlib

from ansible.plugins.action import ActionBase
from ansible.plugins.filter.core import to_json
from ansible_collections.platform.core.plugins.filter.application_runtime import preflight_template_contexts


def placement_context(job, context, host, library_path, instance_path, pairs):
    settings = job['settings']
    digest = hashlib.sha256(to_json(pairs, separators=(',', ':')).encode('utf-8')).hexdigest()
    return {
        'application_config_digest': digest,
        'application_effective': settings,
        'application_environment': dict(settings.get('environment', {}), **context['identity_environment']),
        'application_runtime': {
            'image': settings['image'], 'connections': context['connections'], 'topics': context['topics'],
            'container_name': job['placement']['containerName'],
            'base_compose_path': library_path + '/' + job['baseFilename'], 'base_service': job['baseService'],
            'config_path': instance_path + '/config', 'vault': job.get('vault', {}),
            'application_command': settings['command'], 'vault_path': instance_path + '/vault',
            'pki_path': instance_path + '/pki',
        },
        'library_runtime': {
            'defaults': job.get('commonDefaults', {}), 'library_id': job['libraryId'],
            'host_id': host, 'connections': context['library_connections'],
        },
    }


class ActionModule(ActionBase):
    TRANSFERS_FILES = False
    _requires_connection = False

    def run(self, tmp=None, task_vars=None):
        values = task_vars or {}
        try:
            if 'application_preflight_index' in values:
                job = values['_application_preflight_job']
                context = values['_application_preflight_template_context']
            else:
                job = self._templar.template(values['application_runtime_job'])
                libraries = values['hostvars']['localhost']['application_snapshot']['snapshot']['applicationLibraries']['libraries']
                context, = preflight_template_contexts([job], libraries)
            facts = placement_context(job, context, values['inventory_hostname'],
                                      values['application_library_path'], values['application_instance_path'],
                                      values['application_config_pairs'])
        except (KeyError, TypeError, ValueError, AttributeError):
            return dict(changed=False, failed=True, msg='APPLICATION_PREFLIGHT_CONTEXT_INVALID')
        return dict(changed=False, ansible_facts=facts, _ansible_facts_cacheable=False)

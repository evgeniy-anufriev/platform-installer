"""Validate Core-owned values from the native Compose JSON projection."""
from ansible.parsing.dataloader import DataLoader
from ansible_collections.platform.core.plugins.module_utils.application_libraries import account_policies
from ansible_collections.platform.core.plugins.module_utils.application_runtime import validate_compose, validate_config_contents, selected_archive, pinned_registry_reference, agent_config, validate_agent


def selected_archive_path(root, source, offline):
    return selected_archive(root, source, offline, DataLoader().load_from_file)


def parent_paths(paths):
    result = set()
    for path in paths:
        current = ''
        for part in path.split('/'):
            if part:
                current += '/' + part
                result.add(current)
    return sorted(result)


class FilterModule(object):
    def filters(self):
        return {"application_agent_config": agent_config, "application_validate_agent": validate_agent, "application_validate_compose": validate_compose, "application_parent_paths": parent_paths,
                "application_validate_configs": validate_config_contents, "application_account_policies": account_policies,
                "application_selected_archive": selected_archive_path,
                "application_pinned_registry_reference": pinned_registry_reference}

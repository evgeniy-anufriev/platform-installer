from ansible_collections.platform.core.plugins.module_utils.application_credentials import protected_secret_files


class FilterModule:
    def filters(self):
        return {'application_protected_secret_files': protected_secret_files}

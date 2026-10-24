from ansible_collections.platform.core.plugins.module_utils.application_credentials import protected_secret_files, script_failure


class FilterModule:
    def filters(self):
        return {'application_protected_secret_files': protected_secret_files,
                'application_script_failure': script_failure}

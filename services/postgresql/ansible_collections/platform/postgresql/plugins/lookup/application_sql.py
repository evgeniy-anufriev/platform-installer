"""Render the account SQL using only its declared inputs."""
from ansible.plugins.loader import lookup_loader
from ansible.plugins.lookup import LookupBase
from ansible.template import Templar


class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        source = variables or {}
        names = (
            'platform_postgresql_application_job',
            'platform_postgresql_application_credential_files',
            'platform_postgresql_application_lock_timeout',
            'platform_postgresql_application_statement_timeout',
            'platform_application_password_updates',
            'ansible_search_path',
        )
        context = {name: self._templar.template(source[name])
                   for name in names if name in source}
        templar = Templar(loader=self._loader, variables=context)
        template = lookup_loader.get('ansible.builtin.template',
                                     loader=self._loader, templar=templar)
        return template.run(terms, variables=context, **kwargs)

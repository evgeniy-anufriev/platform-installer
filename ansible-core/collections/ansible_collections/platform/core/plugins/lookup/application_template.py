"""Use a narrow Ansible template context for self-contained placement templates."""
from ansible.plugins.loader import lookup_loader
from ansible.plugins.lookup import LookupBase
from ansible.template import Templar
from jinja2 import Environment, TemplateError, meta, nodes


PLACEMENT_VARIABLES = {
    'application_effective', 'application_environment', 'application_runtime',
    'application_parameters', 'library_runtime', 'inventory_hostname',
    'application_name', 'application_instance_id', 'application_instance_path',
    'application_project_id', 'application_config_digest',
}
FILTERS = {'default', 'dirname', 'indent', 'join', 'length', 'list', 'lower', 'replace',
           'sort', 'string', 'to_json', 'to_nice_yaml', 'trim', 'upper',
           'platform.core.application_agent_config'}


def template_names(source):
    if '#jinja2' in source:
        return None
    try:
        environment = Environment()
        for name in FILTERS:
            environment.filters.setdefault(name, str)
        tree = environment.parse(source)
        names = meta.find_undeclared_variables(tree)
    except TemplateError:
        return None
    if (names - PLACEMENT_VARIABLES - {'undef'} or
            any(tree.find_all((nodes.Include, nodes.Import, nodes.FromImport, nodes.Extends))) or
            any(item.name not in {'defined', 'undefined'} for item in tree.find_all(nodes.Test)) or
            any(item.name not in FILTERS for item in tree.find_all(nodes.Filter))):
        return None
    for call in tree.find_all(nodes.Call):
        if isinstance(call.node, nodes.Name) and call.node.name == 'undef':
            continue
        if not isinstance(call.node, nodes.Getattr) or call.node.attr not in {'get', 'items', 'values', 'keys'}:
            return None
    return names - {'undef'}


class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        variables = variables or {}
        term, = terms
        path = self.find_file_in_search_path(variables, 'templates', term)
        data, _ = self._loader._get_file_contents(path)
        names = template_names(data.decode('utf-8', errors='surrogateescape'))
        templar = self._templar
        if names is not None:
            variables = {name: templar.template(variables[name])
                         for name in names | {'ansible_search_path'} if name in variables}
            templar = Templar(loader=self._loader, variables=variables)
        lookup = lookup_loader.get('ansible.builtin.template', loader=self._loader, templar=templar)
        return lookup.run(terms, variables=variables, **kwargs)

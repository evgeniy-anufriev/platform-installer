"""Render the existing HAProxy templates once per host, without writing files."""
import json
from ansible.errors import AnsibleError
from ansible.plugins.action import ActionBase


class ActionModule(ActionBase):
    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        try:
            variables = dict(task_vars or {}, haproxy_template_path=self._task.args['template_path'])
            templar = self._templar.copy_with_new_env(available_variables=variables)
            rendered = templar.template("{{ lookup('ansible.builtin.template', haproxy_template_path) }}")
            files = json.loads(rendered) if isinstance(rendered, str) else rendered
            expected = ['10-public.cfg'] + [item['configFileName'] for item in variables['platform_haproxy_application_backends']]
            if (not isinstance(files, list) or len(set(expected)) != len(expected)
                    or [item['name'] for item in files] != expected
                    or any(not isinstance(item['content'], str) or not item['content'] for item in files)):
                raise ValueError()
            return dict(changed=False, files=files)
        except (AnsibleError, KeyError, TypeError, ValueError):
            return dict(failed=True, msg='HAPROXY_FRAGMENT_TEMPLATE_INVALID')

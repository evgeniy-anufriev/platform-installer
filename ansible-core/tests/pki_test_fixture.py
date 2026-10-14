"""Run real PKI deploy tasks with only the system trust boundary redirected."""

import grp
import os
from pathlib import Path
import pwd
import shutil
import sys

import yaml


def isolated_deploy_role(root):
    root = Path(root).resolve()
    source = Path(__file__).resolve().parents[1] / 'collections/ansible_collections/platform/core/roles/pki_deploy'
    role = root / 'roles' / 'pki_deploy'
    shutil.copytree(source, role)
    path = role / 'tasks/trust_anchors.yml'
    tasks = yaml.safe_load(path.read_text())
    system_anchors = '/etc/pki/ca-trust/source/anchors'
    for task in tasks:
        for module, field in (('ansible.builtin.file', 'path'), ('ansible.builtin.copy', 'dest')):
            if module in task:
                options = task[module]
                assert options[field].startswith(system_anchors)
                options[field] = options[field].replace(system_anchors, str(root / 'trust-anchors'), 1)
                options['owner'] = pwd.getpwuid(os.getuid()).pw_name
                options['group'] = grp.getgrgid(os.getgid()).gr_name
        if 'ansible.builtin.command' in task:
            assert task['ansible.builtin.command']['argv'] == ['update-ca-trust']
            # Exercise the actual task/register/changed_when, not the host's trust updater.
            task['ansible.builtin.command']['argv'] = [
                sys.executable, '-c',
                'from pathlib import Path; Path(%r).touch()' % str(root / 'trust-refreshed'),
            ]
    rendered = yaml.safe_dump(tasks)
    assert system_anchors not in rendered and 'update-ca-trust' not in rendered
    path.write_text(rendered)
    return str(role)

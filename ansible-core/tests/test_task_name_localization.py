"""Keep operator-visible Ansible labels Russian without inspecting resource names."""

import os
from pathlib import Path
import re
import unittest

import yaml
from yaml.nodes import MappingNode, ScalarNode, SequenceNode


ROOT = Path(__file__).resolve().parents[2]
TASK_LISTS = frozenset(('tasks', 'pre_tasks', 'post_tasks', 'handlers', 'block', 'rescue', 'always'))


def task_labels(node, task=False, role_root=False):
    if isinstance(node, ScalarNode):
        if re.search(r'ansible_failed_task\.name\s*==', node.value):
            yield node
    elif isinstance(node, SequenceNode):
        for child in node.value:
            yield from task_labels(child, task=task or role_root)
    elif isinstance(node, MappingNode):
        mapping = {key.value: value for key, value in node.value if isinstance(key, ScalarNode)}
        if task or 'hosts' in mapping or 'import_playbook' in mapping or 'block' in mapping or any(
                key.startswith(('ansible.builtin.', 'ansible.legacy.', 'platform.')) for key in mapping):
            for key in ('name', 'notify', 'listen'):
                value = mapping.get(key)
                values = value.value if isinstance(value, SequenceNode) else (value,)
                for label in values:
                    if isinstance(label, ScalarNode):
                        yield label
        for key, value in mapping.items():
            yield from task_labels(value, task=key in TASK_LISTS)


class TaskNameLocalizationTests(unittest.TestCase):
    def test_task_fragments_and_handlers_exclude_module_and_resource_names(self):
        tree = yaml.compose('''
- name: Проверить блок
  block:
    - name: Скопировать файл
      ansible.builtin.copy:
        name: machine_resource_name
        content: retained
      notify: Перезапустить службу
      loop:
        - name: compose.yml
''')
        self.assertEqual(['Проверить блок', 'Скопировать файл', 'Перезапустить службу'],
                         [label.value for label in task_labels(tree)])

    def test_owned_play_task_block_and_handler_labels_are_russian(self):
        failures = []
        count = 0
        for section in ('ansible-core', 'services', 'examples', 'config'):
            for directory, folders, filenames in os.walk(ROOT / section):
                folders[:] = [name for name in folders if name not in
                              ('_vendor', 'vendor', 'portable-source', '.runtime', '__pycache__')]
                for filename in filenames:
                    if not filename.endswith(('.yml', '.yaml')):
                        continue
                    path = Path(directory) / filename
                    relative = path.relative_to(ROOT).as_posix()
                    tree = yaml.compose(path.read_text(encoding='utf-8'))
                    for label in task_labels(tree, role_root='/tasks/' in relative or '/handlers/' in relative):
                        count += 1
                        if not re.search('[А-Яа-яЁё]', label.value):
                            failures.append('%s:%s' % (relative, label.start_mark.line + 1))
        self.assertGreater(count, 0, 'No Ansible task labels were inspected')
        self.assertEqual([], failures, 'Untranslated Ansible labels: %s' % ', '.join(failures[:20]))


if __name__ == '__main__':
    unittest.main()

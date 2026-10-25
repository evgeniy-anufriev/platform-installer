"""Run production update rendering/guards with isolated observations; no target writes."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import yaml

ROLE = Path(__file__).resolve().parents[1] / 'ansible_collections/platform/bind/roles/bind'


class ZoneBatchRuntimeTests(unittest.TestCase):
    def run_tasks(self, observations, success=True):
        if not shutil.which('ansible-playbook'):
            self.skipTest('Ansible runtime required')
        tasks = yaml.safe_load((ROLE / 'tasks/update_a_records.yml').read_text())
        selected = [task for task in tasks if task['name'] in (
            'Проверить непустую зону и уникальность владельцев записей обновления BIND',
            'Создать одно обновление зоны с наблюдаемым существованием и предварительными условиями RDATA',
            'Привязать весь запрос DNS перед его первой модификацией')]
        selected.append({'ansible.builtin.copy': {'content': '{{ _platform_bind_zone_update }}', 'dest': '{{ result_path }}'}})
        with tempfile.TemporaryDirectory() as directory:
            result_path = Path(directory) / 'update.txt'
            path = Path(directory) / 'play.yml'
            path.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False,
                                                vars=dict(platform_bind_a_records=[row['record'] for row in observations],
                                                          _platform_bind_zone_observations=observations, result_path=str(result_path)), tasks=selected)]))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(path)], capture_output=True, text=True, timeout=40)
            self.assertEqual(success, result.returncode == 0, result.stdout + result.stderr)
            return result_path.read_text() if result_path.exists() else ''

    @staticmethod
    def observed(owner, current=(), absent=False, zone='example.test', addresses=None):
        return dict(record=dict(zone=zone, owner=owner, addresses=addresses or ['192.0.2.2'], ttl=60),
                    currentAddresses=list(current), absentOwner=absent, changed=True)

    def test_one_send_covers_all_owners_and_exact_prerequisites(self):
        text = self.run_tasks([self.observed('existing.example.test.', ['192.0.2.1']),
                               self.observed('new.example.test.', absent=True),
                               self.observed('empty.example.test.')])
        self.assertEqual(1, text.splitlines().count('send'))
        self.assertIn('prereq yxrrset existing.example.test. A 192.0.2.1', text)
        self.assertIn('prereq nxdomain new.example.test.', text)
        self.assertIn('prereq nxrrset empty.example.test. A', text)
        self.assertIn('prereq nxrrset empty.example.test. CNAME', text)
        self.assertEqual(3, text.count('update delete '))

    def test_duplicate_owner_and_mixed_zones_fail_before_mutation(self):
        row = self.observed('one.example.test.')
        self.run_tasks([row, row], False)
        self.run_tasks([row, self.observed('two.other.test.', zone='other.test')], False)

    def test_thirty_owners_fit_and_oversize_is_rejected(self):
        rows = [self.observed('app%d.example.test.' % number, absent=True) for number in range(30)]
        self.assertEqual(30, self.run_tasks(rows).count('update delete '))
        self.run_tasks([self.observed('large.example.test.', addresses=['192.0.2.2'] * 1500)], False)

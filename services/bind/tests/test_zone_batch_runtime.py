"""Run production update rendering/guards with isolated observations; no target writes."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest
import yaml

ROLE = Path(__file__).resolve().parents[1] / 'ansible_collections/platform/bind/roles/bind'


class ZoneBatchRuntimeTests(unittest.TestCase):
    def test_base_records_nested_includes_and_repeat(self):
        executable = shutil.which('ansible-playbook')
        if not executable:
            self.skipTest('Ansible runtime required')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dig = root / 'dig'
            dig.write_text('#!/bin/sh\nprintf "REAL_DIG_STUB\\n" >> "$BIND_TEST_CALLS"\n'
                           'printf ";; status: NOERROR\\n;; flags: qr aa;\\n%s 60 IN A 192.0.2.2\\n" "$2"\n')
            dig.chmod(0o755)
            records = [dict(type='A', owner=name + '.example.test.', values=['192.0.2.2'])
                       for name in ('first', 'second')]
            include = {'ansible.builtin.include_tasks': str(ROLE / 'tasks/update_base_zone_records.yml')}
            tasks = [include, include, {'ansible.builtin.assert': {'that': [
                '_platform_bind_zone_observations | length == 1',
                '_platform_bind_zone_observations[0].record.owner == "second.example.test."',
                'not _platform_bind_zone_observations[0].changed']}}]
            play = [dict(hosts='localhost', connection='local', gather_facts=False,
                         vars=dict(platform_bind_base_zone=dict(value=dict(
                             zone='example.test', defaultTtl=60, records=records))), tasks=tasks)]
            source = root / 'play.yml'
            source.write_text(yaml.safe_dump(play))
            calls = root / 'calls'
            result = subprocess.run([executable, '-i', 'localhost,', str(source)],
                                    env=dict(os.environ, PATH=str(root) + os.pathsep + os.environ['PATH'],
                                             BIND_TEST_CALLS=str(calls)),
                                    capture_output=True, text=True, timeout=90)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual(4, len(calls.read_text().splitlines()))
            self.assertIn('changed=0', result.stdout)

    def run_tasks(self, observations, success=True):
        if not shutil.which('ansible-playbook'):
            self.skipTest('Ansible runtime required')
        tasks = yaml.safe_load((ROLE / 'tasks/update_a_records.yml').read_text())
        selected = [task for task in tasks if task['name'] in (
            'Проверка непустой зоны и уникальности владельцев обновляемых записей BIND',
            'Создание одного обновления зоны с проверками наличия записей и исходных RDATA',
            'Привязка всего запроса DNS перед его первой модификацией')]
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

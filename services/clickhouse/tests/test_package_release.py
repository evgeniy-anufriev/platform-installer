"""Exercise existing role comparisons/templates through native Ansible, no install."""
import copy
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[3]
TASKS = Path(__file__).resolve().parents[1] / 'ansible_collections/platform/clickhouse/roles/clickhouse_tls/tasks'


class ClickHousePackageReleaseTests(unittest.TestCase):
    def probe(self, release, legacy=False):
        def tasks(name):
            return yaml.safe_load((TASKS / (name + '.yml')).read_text())

        names = ['clickhouse-common-static', 'clickhouse-server', 'clickhouse-client']
        version = '26.9.1'
        identity = 'clickhouse-server-' + version + '-' + release + '.x86_64'
        variables = dict(platform_clickhouse_package_version=version, platform_clickhouse_mode='raft-ha',
                         clickhouse_package_id='clickhouse-server',
                         _platform_clickhouse_installed_packages=dict(stdout_lines=[name + '\t' + version + '-' + release + '.x86_64' for name in names]),
                         _platform_clickhouse_stock_unit_owner=dict(rc=0, stdout=identity),
                         _platform_clickhouse_keeper_binary_owner=dict(stdout=identity))
        if not legacy:
            variables.update(platform_clickhouse_package_releases=dict.fromkeys(names, release), platform_clickhouse_package_architecture='x86_64')
        selected = [copy.deepcopy(tasks('preflight')[2])]
        selected += [copy.deepcopy(task) for task in tasks('packages') if task.get('ansible.builtin.assert')]
        selected += [copy.deepcopy(task) for task in tasks('stock_unit') if task.get('ansible.builtin.assert', {}).get('fail_msg') == 'CLICKHOUSE_STOCK_UNIT_OWNERSHIP_UNCONFIRMED' and 'rc == 0' in str(task)]
        install = tasks('install_package')
        repository = next(task for task in install if 'ansible.builtin.dnf' in task and 'name' in task['ansible.builtin.dnf'] and isinstance(task['ansible.builtin.dnf']['name'], str) and 'clickhouse_package_id }}-' in task['ansible.builtin.dnf']['name'])
        copied = next(task for task in install if 'ansible.builtin.copy' in task)
        selected += [dict(name='Render actual install inputs without installing', **{'ansible.builtin.set_fact': dict(
            qa_package=repository['ansible.builtin.dnf']['name'], qa_destination=copied['ansible.builtin.copy']['dest'])}),
            {'ansible.builtin.assert': {'that': ["qa_package == 'clickhouse-server-%s-%s'" % (version, release),
                "qa_destination.endswith('clickhouse-server-%s-%s.x86_64.rpm')" % (version, release)]}}]
        with tempfile.TemporaryDirectory(prefix='qa-clickhouse-release-') as temporary:
            play = Path(temporary) / 'probe.yml'
            play.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False, vars=variables, tasks=selected)], sort_keys=False))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(play)],
                env=dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg')),
                capture_output=True, text=True, timeout=60)
        self.assertEqual(0, result.returncode, (result.stdout + result.stderr)[-2200:])

    def test_release_two_in_existing_install_and_ownership_checks(self):
        self.probe('2')

    def test_manual_legacy_release_one_defaults(self):
        self.probe('1', legacy=True)


if __name__ == '__main__':
    unittest.main()

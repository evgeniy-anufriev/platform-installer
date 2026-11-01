"""Native Ansible scheduling and real timeout process tests in isolated paths."""
import copy
import getpass
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[3]
SERVICE = ROOT / 'services/postgresql'
ROLE = SERVICE / 'ansible_collections/platform/postgresql/roles/postgresql'


@unittest.skipUnless(shutil.which('ansible-playbook'), 'RED OS Ansible required')
class FailoverOrderRuntimeTests(unittest.TestCase):
    def run_order(self, monitor='node3', fail_monitor=False, limit=None, standalone=False):
        with tempfile.TemporaryDirectory(prefix='pg-monitor-order-') as folder:
            base = Path(folder)
            fixture_role = base / 'collections/ansible_collections/platform/postgresql/roles/postgresql/tasks'
            fixture_role.mkdir(parents=True)
            # Replace service effects only. The actual apply play scheduling,
            # role invocation, group_by and fatal barrier run unchanged.
            fixture_role.joinpath('main.yml').write_text(yaml.safe_dump([
                {'ansible.builtin.assert': {'that': "not (inventory_hostname == qa_monitor and qa_fail_monitor)"}},
                {'ansible.builtin.assert': {'that': "qa_standalone or inventory_hostname == qa_monitor or lookup('file', qa_root ~ '/monitor-ready', errors='ignore') == qa_monitor"}},
                {'ansible.builtin.copy': {'content': '{{ inventory_hostname }}', 'dest': '{{ qa_root }}/monitor-ready'},
                 'when': 'not qa_standalone and inventory_hostname == qa_monitor'},
                {'ansible.builtin.copy': {'content': 'done', 'dest': '{{ qa_root }}/{{ inventory_hostname }}'}}
            ], sort_keys=False))
            plays = [copy.deepcopy(p) for p in yaml.safe_load((SERVICE / 'playbooks/apply.yml').read_text())
                     if 'hosts' in p]
            for play in plays:
                play['become'] = False
                play['gather_facts'] = False
            base.joinpath('play.yml').write_text(yaml.safe_dump(plays, sort_keys=False))
            inventory = {'all': {'vars': {
                'ansible_connection': 'local', 'qa_root': str(base), 'qa_monitor': monitor,
                'qa_fail_monitor': fail_monitor, 'qa_standalone': standalone,
                'platform_postgresql_instances': [] if standalone else [
                    dict(host=h, roles=['monitor' if h == monitor else 'database'])
                    for h in ('node1', 'node2', 'node3')]},
                'children': {'platform_targets': {'hosts': {h: {} for h in ('node1', 'node2', 'node3')}}}}}
            base.joinpath('inventory.yml').write_text(yaml.safe_dump(inventory, sort_keys=False))
            args = ['ansible-playbook', '-i', str(base / 'inventory.yml'), str(base / 'play.yml')]
            if limit:
                args += ['--limit', limit]
            result = subprocess.run(args, env=dict(os.environ,
                ANSIBLE_COLLECTIONS_PATH=str(base / 'collections') + ':' + str(ROOT / 'ansible-core/collections')),
                capture_output=True, text=True, timeout=60)
            self.assertEqual(not fail_monitor, result.returncode == 0, (result.stdout + result.stderr)[-2600:])
            expected = set() if fail_monitor else set(limit.split(',') if limit else ['node1', 'node2', 'node3'])
            self.assertEqual(expected, {h for h in ('node1', 'node2', 'node3') if (base / h).exists()})

    def test_monitor_precedes_data_at_every_inventory_position(self):
        for monitor in ('node3', 'node1', 'node2'):
            with self.subTest(monitor=monitor):
                self.run_order(monitor=monitor)

    def test_monitor_failure_stops_subsequent_data_plays(self):
        self.run_order(fail_monitor=True)

    def test_limit_does_not_apply_unselected_data_host(self):
        self.run_order(limit='node1,node3')

    def test_standalone_retains_serial_application(self):
        self.run_order(standalone=True)

    def test_create_commands_bound_and_terminate_hung_processes(self):
        production = yaml.safe_load((ROLE / 'tasks/pg_auto_failover.yml').read_text())
        creates = [p for p in production if p.get('register') in (
            'platform_postgresql_pg_autoctl_create_monitor', 'platform_postgresql_pg_autoctl_create_postgres')]
        with tempfile.TemporaryDirectory(prefix='pg-create-timeout-') as folder:
            base = Path(folder)
            binary = base / 'pg_autoctl'
            binary.write_text('#!/usr/bin/python3\nimport os, pathlib, signal, time\n'
                              'pathlib.Path(os.environ["QA_PID"]).write_text(str(os.getpid()))\n'
                              'if os.getenv("QA_IGNORE_TERM") == "1": signal.signal(signal.SIGTERM, signal.SIG_IGN)\n'
                              'time.sleep(60)\n')
            binary.chmod(0o755)
            for create in creates:
                with self.subTest(create=create['register']):
                    task = copy.deepcopy(create)
                    task.pop('become_user')
                    task['environment']['QA_PID'] = str(base / 'pid')
                    task['environment']['QA_IGNORE_TERM'] = '1' if 'monitor' in create['register'] else '0'
                    variables = dict(platform_postgresql_pg_autoctl_create_timeout=1,
                        platform_postgresql_binary_directory=str(base), platform_postgresql_data_directory=str(base / 'data'),
                        _platform_postgresql_member_port=15432, _platform_postgresql_member=dict(address='127.0.0.1', roles=['monitor', 'database']),
                        platform_postgresql_user=getpass.getuser(), platform_postgresql_failover_auth='scram-sha-256',
                        _platform_postgresql_tls_directory=str(base), _platform_postgresql_monitor_uri='postgres://test@localhost/test',
                        platform_postgresql_pgpass_file=str(base / 'synthetic-passfile'),
                        platform_postgresql_pg_autoctl_pg_version={'stat': {'exists': False}})
                    play = [dict(hosts='localhost', connection='local', gather_facts=False, vars=variables, tasks=[task])]
                    base.joinpath('timeout.yml').write_text(yaml.safe_dump(play))
                    started = time.monotonic()
                    result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(base / 'timeout.yml')],
                        env=dict(os.environ, PATH=str(base) + ':' + os.environ['PATH']),
                        capture_output=True, text=True, timeout=25)
                    self.assertNotEqual(0, result.returncode)
                    self.assertLess(time.monotonic() - started, 20)
                    self.assertTrue((base / 'pid').exists(), result.stdout[-1500:])
                    pid = int((base / 'pid').read_text())
                    self.assertFalse(Path('/proc/' + str(pid)).exists(), 'timed-out pg_autoctl still running')
                    (base / 'pid').unlink()

            # Existing slot-convergence retries still work for ordinary failures.
            binary.write_text('#!/usr/bin/python3\nimport os, pathlib, sys\n'
                              'p=pathlib.Path(os.environ["QA_PID"])\n'
                              'n=int(p.read_text())+1 if p.exists() else 1\np.write_text(str(n))\n'
                              'sys.exit(1 if n == 1 else 0)\n')
            variables['platform_postgresql_pg_autoctl_create_timeout'] = 10
            base.joinpath('timeout.yml').write_text(yaml.safe_dump([dict(hosts='localhost', connection='local',
                gather_facts=False, vars=variables, tasks=[task])]))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(base / 'timeout.yml')],
                env=dict(os.environ, PATH=str(base) + ':' + os.environ['PATH']),
                capture_output=True, text=True, timeout=25)
            self.assertEqual(0, result.returncode, result.stdout[-1800:])
            self.assertEqual('2', (base / 'pid').read_text())


if __name__ == '__main__':
    unittest.main()

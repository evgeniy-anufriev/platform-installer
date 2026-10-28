import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[3]
ROLE = ROOT / 'services/clickhouse/ansible_collections/platform/clickhouse/roles/application_provider'


@unittest.skipUnless(shutil.which('ansible-playbook'), 'Ansible required')
class TableRenderRuntimeTests(unittest.TestCase):
    def test_native_action_parity_and_timing_for_24_tables(self):
        with tempfile.TemporaryDirectory(prefix='table-batch-timing-') as folder:
            root = Path(folder)
            actions, callbacks = root / 'actions', root / 'callbacks'
            actions.mkdir()
            callbacks.mkdir()
            fixtures = Path(__file__).parent / 'fixtures'
            shutil.copyfile(fixtures / 'prepare_tables_before_batch.py', actions / 'prepare_legacy_tables.py')
            timing = root / 'timing.json'
            callback = '''import json, time
from ansible.plugins.callback import CallbackBase
class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'aggregate'
    CALLBACK_NAME = 'render_timing'
    CALLBACK_NEEDS_ENABLED = True
    def v2_playbook_on_task_start(self, task, is_conditional):
        self.started = time.monotonic()
    def v2_runner_on_ok(self, result):
        name = result._task.get_name()
        if name not in ('Legacy render', 'Batch render'):
            return
        self.times = getattr(self, 'times', {})
        self.times[name] = round(time.monotonic() - self.started, 4)
        with open(TIMING_PATH, 'w') as stream:
            json.dump(self.times, stream)
'''.replace('TIMING_PATH', repr(str(timing)))
            (callbacks / 'render_timing.py').write_text(callback)
            job = dict(mode='standalone', databases=[dict(name='analytics', tables=[
                dict(name='records_' + str(i), engine='MergeTree', columns=[dict(name='id', type='UInt64')],
                     order_by='id', settings={'index_granularity': 8192}) for i in range(24)])])
            tasks = [dict(name='Legacy render', prepare_legacy_tables=dict(job=job, phase='preflight',
                          template_path=str(fixtures / 'application-table-before-batch.sql.j2')), register='old', no_log=True),
                     dict(name='Batch render', **{'platform.clickhouse.prepare_application_tables': dict(job=job,
                          phase='preflight', template_path=str(ROLE / 'templates/application-tables.json.j2'))},
                          register='batch', no_log=True),
                     {'ansible.builtin.assert': {'that': ['old.tables == batch.tables', 'batch.tables | length == 24']}}]
            play = root / 'play.yml'
            play.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False, tasks=tasks)]))
            env = dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
                ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections') + ':' + str(ROOT / 'services/clickhouse'),
                ANSIBLE_ACTION_PLUGINS=str(actions), ANSIBLE_CALLBACK_PLUGINS=str(callbacks),
                ANSIBLE_CALLBACKS_ENABLED='render_timing')
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(play)], env=env,
                                    capture_output=True, text=True, timeout=90)
            self.assertEqual(0, result.returncode, (result.stdout + result.stderr)[-2500:])
            measured = json.loads(timing.read_text())
            self.assertEqual({'Legacy render', 'Batch render'}, set(measured))
            # Timing is evidence, not a flaky correctness threshold.
            print('CLICKHOUSE_RENDER_BENCHMARK ' + json.dumps(measured, sort_keys=True))

    def test_batch_matches_existing_lookup_and_accounts_does_not_render(self):
        for mode in ('standalone', 'raft-ha'):
            with self.subTest(mode=mode):
                self.compare_render(mode)

    def compare_render(self, mode):
        with tempfile.TemporaryDirectory(prefix='table-render-') as folder:
            root = Path(folder)
            table = dict(name='ev`ents', engine='MergeTree', columns=[dict(name='id', type='UInt64')], order_by='tuple()')
            if mode == 'raft-ha':
                table.update(engine='ReplicatedMergeTree', replicationPath='/tables/{shard}/events',
                    columns=[dict(name='id', type='UInt64', codec='Delta, ZSTD')],
                    indexes=[dict(name='by_id', expression='id', type='minmax', granularity=1)],
                    settings={'index_granularity': 8192, 'comment': "a'b", 'enable_mixed_granularity_parts': True})
            job = dict(mode=mode, databases=[dict(name='da`ta', tables=[table, dict(table, name='second')]),
                dict(name='second_db', tables=[dict(table, name='other')]), dict(name='empty', tables=[])])
            template = str(Path(__file__).parent / 'fixtures/application-table-before-batch.sql.j2')
            tasks = [{'platform.clickhouse.prepare_application_tables': {'job': '{{ platform_clickhouse_application_job }}', 'phase': 'resources', 'template_path': str(ROLE / 'templates/application-tables.json.j2')}, 'register': 'batch'},
                {'ansible.builtin.set_fact': {'legacy': []}},
                {'ansible.builtin.set_fact': {'legacy': "{{ legacy + [{'database': item.0.name, 'definition': item.1, 'sql': lookup('ansible.builtin.template', table_template_path)}] }}"},
                 'loop': '{{ platform_clickhouse_application_job.databases | subelements("tables") }}'},
                {'ansible.builtin.assert': {'that': ['batch.tables == legacy', 'not batch.changed']}},
                {'ansible.builtin.set_fact': {'single': []}},
                {'ansible.builtin.set_fact': {'single': "{{ single + [lookup('ansible.builtin.template', single_template_path)] }}"},
                 'loop': '{{ platform_clickhouse_application_job.databases | subelements("tables") }}'},
                {'ansible.builtin.assert': {'that': ['single == (legacy | map(attribute="sql") | list)']}},
                {'platform.clickhouse.prepare_application_tables': {'job': {'databases': [{'tables': [{'invalid': 'not rendered'}]}]}, 'phase': 'accounts'}, 'register': 'accounts'},
                {'ansible.builtin.assert': {'that': ['accounts.tables == []', 'not accounts.changed']}}]
            play = root / 'play.yml'
            play.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False,
                vars=dict(platform_clickhouse_application_job=job, table_template_path=template,
                          single_template_path=str(ROLE / 'templates/application-table.sql.j2')), tasks=tasks)]))
            env = dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
                ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections') + ':' + str(ROOT / 'services/clickhouse'))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(play)], env=env,
                                    capture_output=True, text=True, timeout=90)
            self.assertEqual(0, result.returncode, result.stdout[-3500:] + result.stderr[-1000:])

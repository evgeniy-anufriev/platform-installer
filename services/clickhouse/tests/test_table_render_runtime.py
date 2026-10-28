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
            job = dict(mode=mode, databases=[dict(name='da`ta', tables=[table, dict(table, name='second')])])
            template = str(ROLE / 'templates/application-table.sql.j2')
            tasks = [{'platform.clickhouse.prepare_application_tables': {'job': '{{ platform_clickhouse_application_job }}', 'phase': 'resources', 'template_path': template}, 'register': 'batch'},
                {'ansible.builtin.set_fact': {'legacy': []}},
                {'ansible.builtin.set_fact': {'legacy': "{{ legacy + [{'database': item.0.name, 'definition': item.1, 'sql': lookup('ansible.builtin.template', table_template_path)}] }}"},
                 'loop': '{{ platform_clickhouse_application_job.databases | subelements("tables") }}'},
                {'ansible.builtin.assert': {'that': ['batch.tables == legacy', 'not batch.changed']}},
                {'platform.clickhouse.prepare_application_tables': {'job': {'databases': [{'tables': [{'invalid': 'not rendered'}]}]}, 'phase': 'accounts'}, 'register': 'accounts'},
                {'ansible.builtin.assert': {'that': ['accounts.tables == []', 'not accounts.changed']}}]
            play = root / 'play.yml'
            play.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False,
                vars=dict(platform_clickhouse_application_job=job, table_template_path=template), tasks=tasks)]))
            env = dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
                ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections') + ':' + str(ROOT / 'services/clickhouse'))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(play)], env=env,
                                    capture_output=True, text=True, timeout=90)
            self.assertEqual(0, result.returncode, result.stdout[-3500:] + result.stderr[-1000:])

"""Desired resolution identity, conservative reuse and fresh enrichment."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ansible-core/collections'))
from ansible_collections.platform.core.plugins.module_utils import project_resolution as reuse
from ansible_collections.platform.core.plugins.action.project_resolution import ActionModule


class ProjectResolutionTests(unittest.TestCase):
    def result(self, revision='sha256:revision'):
        return dict(snapshot={'projectRevision': revision}, pki_materialization={},
                    application_image_lock={}, execution_configuration={}, execution_connections={})

    def test_supported_expressions_and_unconfirmed_context_fall_back(self):
        for text in ('plain', '{{ library_instance_id }}', '{{ hostvars[node].ansible_host }}',
                     '{{ values | default({}) | combine(other) }}'):
            self.assertTrue(reuse.pure_templates(text), text)
        for text in ("{{ lookup('env', 'TOKEN') }}", "{{ query('pipe', 'command') }}",
                     '{{ now() }}', '{{ values | random }}', '{{ value | external_filter }}',
                     '{{ ansible_env.HOME }}', '{{ inventory_dir }}', '{{ vars[name] }}'):
            self.assertFalse(reuse.pure_templates(text), text)

    def test_changed_identity_cannot_reuse_and_corruption_is_not_hidden(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder, 'result.json'))
            expected = dict(revision='sha256:revision', runtime={'bundleDigest': 'a'})
            self.assertIsNone(reuse.read(path, expected))
            reuse.write(path, expected, self.result())
            self.assertEqual(self.result(), reuse.read(path, expected))
            self.assertIsNone(reuse.read(path, dict(expected, runtime={'bundleDigest': 'b'})))
            value = json.loads(Path(path).read_text())
            value['result']['execution_connections'] = {'host': {'address': 'changed'}}
            Path(path).write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, 'PROJECT_RESOLUTION_INVALID'):
                reuse.read(path, expected)

    def test_runtime_credentials_outside_resolution_are_never_serialized(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder, 'result.json'))
            value = dict(self.result(), runtime_secrets={'token': 'synthetic-private-marker'})
            reuse.write(path, {'revision': 'sha256:revision'}, value)
            self.assertNotIn('synthetic-private-marker', Path(path).read_text())

    def test_enrichment_does_not_mutate_saved_base(self):
        base = self.result()
        before = copy.deepcopy(base)
        prepared = {'placements': {}}
        enriched = reuse.enrich(base, prepared)
        self.assertEqual(prepared, enriched['application_image_lock'])
        self.assertEqual(before, base)

    def test_absolute_staging_paths_are_not_reused_across_requests(self):
        with tempfile.TemporaryDirectory() as folder:
            value = self.result()
            value['execution_configuration'] = {'path': folder + '/private-source'}
            self.assertFalse(reuse.reusable(folder, [], value, '/nonexistent'))

    def test_package_inventory_and_defaults_mutations_change_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'inventory/group_vars/all').mkdir(parents=True)
            (root / 'inventory/hosts.yml').write_text('all: {}\n')
            path = root / 'inventory/group_vars/all/vars.yml'
            path.write_text('setting: one\n')
            first, _ = reuse.identity(folder, {'bundle': 'a'})
            path.write_text('setting: two\n')
            second, _ = reuse.identity(folder, {'bundle': 'a'})
            self.assertNotEqual(first, second)
            self.assertNotEqual(second, reuse.identity(folder, {'bundle': 'b'})[0])

    def test_unknown_version_is_a_miss_and_atomic_parallel_writes_remain_valid(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder, 'result.json'))
            expected = {'revision': 'sha256:revision'}
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lambda _: reuse.write(path, expected, self.result()), range(20)))
            self.assertEqual(self.result(), reuse.read(path, expected))
            envelope = json.loads(Path(path).read_text())
            envelope['version'] = 'future-version'
            Path(path).write_text(json.dumps(envelope))
            self.assertIsNone(reuse.read(path, expected))
            self.assertEqual(['result.json'], [p.name for p in Path(folder).iterdir()])

    def test_indirect_dynamic_filters_and_external_defaults_disable_reuse(self):
        for text in ("{{ values | map('external_filter') }}",
                     "{{ values | selectattr('name', test_name) }}",
                     "{{ hostvars[node]['ansible_env'] }}"):
            self.assertFalse(reuse.pure_templates(text), text)
        with tempfile.TemporaryDirectory() as folder:
            defaults = Path(folder, 'services/example/defaults')
            defaults.mkdir(parents=True)
            (defaults / 'main.yml').write_text("value: \"{{ lookup('env', 'EXTERNAL') }}\"\n")
            self.assertFalse(reuse.reusable('/unrelated/project', [], self.result(),
                                           str(Path(folder, 'services'))))

    def test_store_rejects_project_mutation_after_load(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder, 'project')
            (root / 'inventory').mkdir(parents=True)
            source = root / 'inventory/hosts.yml'
            source.write_text('all: {}\n')
            action = ActionModule.__new__(ActionModule)
            action._task = SimpleNamespace(args={'operation': 'load'})
            variables = dict(platform_project_root=str(root),
                platform_project_resolution_local_path=str(Path(folder, 'result.json')),
                platform_project_resolution_runtime={'bundle': 'a'})
            loaded = action.run(task_vars=variables)
            source.write_text('all: {hosts: {node1: {}}}\n')
            action._task.args = dict(operation='store', result=self.result(loaded['identity']['revision']))
            result = action.run(task_vars=dict(variables, _project_resolution_cache=loaded))
            self.assertTrue(result['failed'])
            self.assertEqual('PROJECT_RESOLUTION_INPUT_CHANGED', result['error_code'])
            self.assertFalse(Path(variables['platform_project_resolution_local_path']).exists())


if __name__ == '__main__':
    unittest.main()

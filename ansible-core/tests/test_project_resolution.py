"""Desired resolution identity, conservative reuse and fresh enrichment."""
import copy
import json
import os
import shutil
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
    def local_package(self, root):
        source = root / 'application-packages/demo/1.0.0/roles/application_demo/defaults/main.yml'
        source.parent.mkdir(parents=True)
        asset = root / 'application-packages/demo/1.0.0/assets/client.json.j2'
        asset.parent.mkdir()
        asset.write_text('{"id": "{{ application_instance_id }}"}')
        source.write_text("client: \"{{ lookup('ansible.builtin.template', "
                          "(application_job.application.defaultsPath | dirname) ~ "
                          "'/../../../assets/client.json.j2', convert_data=false) | from_json }}\"\n")
        (root / 'inventory').mkdir()
        (root / 'inventory/hosts.yml').write_text('all: {}\n')
        (root / 'project.yml').write_text('metadata: {id: project-fixture}\n')
        return source, asset

    def test_local_package_lookup_is_transitive_and_bounded_to_hashed_closure(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder, 'project')
            source, asset = self.local_package(root)
            first, documents = reuse.identity(str(root), {'bundle': 'a'})
            check = lambda: reuse.reusable(str(root), documents, self.result(), '/nonexistent')
            self.assertTrue(check())
            asset.write_text("{{ lookup('env', 'EXTERNAL') }}")
            self.assertFalse(check())
            self.assertNotEqual(first, reuse.identity(str(root), {'bundle': 'a'})[0])
            asset.write_text('{"id": "{{ application_instance_id }}"}')
            self.assertFalse(reuse.reusable(str(root), [d for d in documents if '/assets/' not in d['logicalPath']],
                                            self.result(), '/nonexistent'))
            for expression in (
                    "lookup(plugin, path)", "lookup('env', 'EXTERNAL')",
                    "lookup('ansible.builtin.file', '/etc/hostname')",
                    "lookup('ansible.builtin.file', platform_project_root ~ '/../external.json')",
                    "lookup('ansible.builtin.file', platform_project_root ~ '/missing.json')",
                    "hostvars[node].get('ansible_env')", "other.get('key')",
                    "platform_project_root | hash", "application_job | hash",
                    "application_job.application.defaultsPath | basename",
                    "application_job.application | hash", "hostvars | to_json | hash",
                    "application_job.get('platform_execution_mode')", "platform_execution_mode",
                    "application_job['instance'].get('x')", # subscript method contexts are not proved
                    ):
                source.write_text('{{ ' + expression + ' }}')
                self.assertFalse(check(), expression)
            outside = Path(folder, 'outside')
            outside.mkdir()
            os.symlink(outside, root / 'untracked')
            source.write_text("{{ lookup('ansible.builtin.file', platform_project_root ~ '/untracked/../application-packages/demo/1.0.0/assets/client.json.j2') }}")
            self.assertFalse(check())
            source.write_text("{{ lookup('ansible.builtin.template', (application_job.application.defaultsPath | dirname) ~ '/../../../assets/client.json.j2') }}")
            asset.unlink()
            external = Path(folder, 'outside.json')
            external.write_text('{}')
            os.symlink(external, asset)
            self.assertFalse(check())

    def test_proved_dictionary_and_local_list_calls_only(self):
        contexts = dict(project='/project', source='/project/defaults.yml', documents=())
        for text in ("{{ (_application_shared.defaults.parameters | default({})).get('KEY', []) }}",
                     "{% set members=[] %}{% for placement in application_placements %}"
                     "{% set _=members.append(placement.address) %}{% endfor %}{{ members | join(',') }}"):
            self.assertTrue(reuse.pure_templates(text, **contexts), text)
        for text in ("{{ application_connections.get('x') }}", "{{ object.append(value) }}",
                     "{% set application_job={} %}{{ application_job.get('x') }}",
                     "{% set members=[] %}{% set members=hostvars %}{{ members.append(1) }}",
                     "{% set members=[] %}{% for members in application_placements %}{{ members.append(1) }}{% endfor %}",
                     "{{ application_job.get('platform_execution_mode') }}"):
            self.assertFalse(reuse.pure_templates(text, **contexts), text)

    def test_current_szi_and_five_sdku_packages_have_closed_template_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for family, packages in (
                    ('szi', ('keycloak', 'grant-access', 'grant-access-audit', 'grant-access-front', 'nginx')),
                    ('sdku', ('sdku-telemechanics', 'sdku-vtor', 'sdku-knp', 'sdku-status-calculation', 'sdku-tank-farm'))):
                library = ROOT / 'examples' / family / 'library-packages' / family
                shutil.copytree(library, root / 'library-packages' / family)
                for package in packages:
                    source = ROOT / 'examples' / family / 'application-packages' / package
                    shutil.copytree(source, root / 'application-packages' / package)
            _, documents = reuse.identity(str(root), {'bundle': 'a'})
            self.assertTrue(reuse.reusable(str(root), documents, self.result(), str(ROOT / 'services')))

    def test_yaml_escaping_is_checked_after_decoding_without_rendering(self):
        self.assertTrue(reuse._pure_document("value: '{{ application_instance_id | replace(''-'', ''_'') }}'"))
        self.assertFalse(reuse._pure_document("value: '{{ lookup(''env'', ''EXTERNAL'') }}'"))

    def test_dynamic_inventory_is_not_a_closed_input_and_executable_mode_changes_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder, 'project')
            self.local_package(root)
            inventory = root / 'inventory/hosts.yml'
            first, documents = reuse.identity(str(root), {'bundle': 'a'})
            os.chmod(inventory, 0o700)
            second, documents = reuse.identity(str(root), {'bundle': 'a'})
            self.assertNotEqual(first, second)
            self.assertFalse(reuse.reusable(str(root), documents, self.result(), '/nonexistent'))
            os.chmod(inventory, 0o600)
            inventory.write_text('plugin: external.inventory\n')
            _, documents = reuse.identity(str(root), {'bundle': 'a'})
            self.assertFalse(reuse.reusable(str(root), documents, self.result(), '/nonexistent'))

    def test_closed_result_crosses_plan_requests_but_external_inputs_do_not(self):
        with tempfile.TemporaryDirectory() as folder:
            first_root = Path(folder, 'first')
            source, asset = self.local_package(first_root)
            shared = str(Path(folder, 'shared'))
            action = ActionModule.__new__(ActionModule)
            variables = dict(platform_project_root=str(first_root),
                platform_project_resolution_local_path=str(Path(folder, 'first-result.json')),
                platform_project_resolution_directory=shared,
                platform_project_resolution_runtime={'bundle': 'a'},
                platform_plan_resolution_context='plan-one')
            def load_store(values):
                action._task = SimpleNamespace(args={'operation': 'load'})
                loaded = action.run(task_vars=values)
                self.assertFalse(loaded.get('failed'), loaded)
                if not loaded['hit']:
                    action._task.args = dict(operation='store', result=self.result(loaded['identity']['revision']))
                    stored = action.run(task_vars=dict(values, _project_resolution_cache=loaded))
                    self.assertFalse(stored.get('failed'), stored)
                return loaded
            self.assertFalse(load_store(variables)['hit'])
            second_root = Path(folder, 'second')
            shutil.copytree(first_root, second_root)
            second = dict(variables, platform_project_root=str(second_root),
                platform_plan_resolution_context='different-plan-context',
                platform_project_resolution_local_path=str(Path(folder, 'second-result.json')))
            self.assertTrue(load_store(second)['hit'])
            # A descriptor request has no plan context; selectors affect the
            # planner, not the allowlisted desired-only resolver inputs.
            third = dict(second, platform_project_resolution_local_path=str(Path(folder, 'descriptor.json')))
            third.pop('platform_plan_resolution_context')
            self.assertTrue(load_store(third)['hit'])
            for key, value in (('platform_execution_mode', 'APPLICATION_LIBRARIES_ONLY'),
                               ('platform_execution_deployment_order', ['other']),
                               ('platform_execution_application_library_order', ['lib']),
                               ('platform_execution_skip_application_libraries', ['lib']),
                               ('platform_execution_application_vault_sources', {'vault': 'RUNTIME_INPUT'})):
                changed = dict(third, **{key: value},
                    platform_project_resolution_local_path=str(Path(folder, key + '.json')))
                self.assertTrue(load_store(changed)['hit'], key)
            changed = dict(third, inventory_hostname='other-controller',
                platform_project_resolution_local_path=str(Path(folder, 'other-controller.json')))
            self.assertFalse(load_store(changed)['hit'])
            Path(second_root, asset.relative_to(first_root)).write_text("{{ lookup('env', 'EXTERNAL') }}")
            self.assertFalse(load_store(third)['hit'])
            fourth = dict(third, platform_project_resolution_local_path=str(Path(folder, 'external-repeat.json')))
            self.assertFalse(load_store(fourth)['hit'])

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

    def test_role_findings_round_trip_without_becoming_a_public_snapshot_field(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder, 'result.json'))
            expected = dict(revision='sha256:revision', runtime={'bundleDigest': 'a'})
            value = self.result()
            value['application_rows'] = []
            value['application_findings'] = [{'code': 'APPLICATION_INPUT_INVALID', 'status': 'BLOCKED'}]
            reuse.write(path, expected, value)
            self.assertEqual(value, reuse.read(path, expected))
            self.assertNotIn('application_findings', value['snapshot'])

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

    def test_store_by_reference_preserves_identity_and_rejects_ambiguous_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder, 'project')
            (root / 'inventory').mkdir(parents=True)
            (root / 'inventory/hosts.yml').write_text('all: {}\n')
            action = ActionModule.__new__(ActionModule)
            action._task = SimpleNamespace(args={'operation': 'load'})
            variables = dict(platform_project_root=str(root),
                platform_project_resolution_local_path=str(Path(folder, 'result.json')),
                platform_project_resolution_runtime={'bundle': 'a'})
            loaded = action.run(task_vars=variables)
            variables.update(_project_resolution_cache=loaded,
                             platform_project_resolution=self.result(loaded['identity']['revision']))
            action._task.args = dict(operation='store', result_variable='platform_project_resolution')
            result = action.run(task_vars=variables)
            self.assertFalse(result.get('failed', False), result)
            for args in ({'result_variable': 'other'},
                         {'result_variable': 'platform_project_resolution', 'result': {}}):
                action._task.args = dict(operation='store', **args)
                self.assertTrue(action.run(task_vars=variables)['failed'])
            (root / 'inventory/hosts.yml').write_text('all: {hosts: {node1: {}}}\n')
            action._task.args = dict(operation='store', result_variable='platform_project_resolution')
            self.assertEqual('PROJECT_RESOLUTION_INPUT_CHANGED', action.run(task_vars=variables)['error_code'])

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

    def test_image_rows_are_reused_only_in_the_same_invocation_context(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder, 'project')
            (root / 'inventory').mkdir(parents=True)
            source = root / 'inventory/hosts.yml'
            source.write_text('all: {}\n')
            variables = dict(platform_project_root=str(root),
                platform_service_catalog_path=str(Path(folder, 'catalog.yml')),
                platform_project_resolution_runtime={'bundle': 'a'})
            action = ActionModule.__new__(ActionModule)
            action._task = SimpleNamespace(args={'operation': 'reuse_application_rows'})
            self.assertFalse(action.run(task_vars=variables)['hit'])
            action._task.args = {'operation': 'load'}
            loaded = action.run(task_vars=variables)
            result = self.result(loaded['identity']['revision'])
            result['snapshot']['applicationLibraries'] = {'status': 'PASS'}
            result['application_rows'] = [{'instanceId': 'probe'}]
            result['application_findings'] = []
            variables.update(_application_image_resolution_context=loaded['invocation_context'],
                             platform_image_snapshot=result)
            action._task.args = {'operation': 'reuse_application_rows'}
            reused = action.run(task_vars=variables)
            self.assertTrue(reused['hit'])
            self.assertEqual(result['application_rows'], reused['application_rows'])
            for key, value in (
                ('platform_project_resolution_runtime', {'bundle': 'b'}),
                ('platform_service_catalog_path', str(Path(folder, 'other.yml'))),
                ('platform_plan_resolution_context', 'new-plan'),
            ):
                with self.subTest(key=key):
                    self.assertFalse(action.run(task_vars=dict(variables, **{key: value}))['hit'])
            blocked = copy.deepcopy(result)
            blocked['snapshot']['applicationLibraries']['status'] = 'BLOCKED'
            blocked['application_findings'] = [{'code': 'APPLICATION_INPUT_INVALID', 'status': 'BLOCKED'}]
            reused = action.run(task_vars=dict(variables, platform_image_snapshot=blocked))
            self.assertTrue(reused['hit'])
            self.assertEqual(blocked['application_findings'], reused['application_findings'])
            for invalid in (None, {}, dict(result, application_rows=[]), dict(result, application_rows=['invalid'])):
                self.assertFalse(action.run(task_vars=dict(variables, platform_image_snapshot=invalid))['hit'])
            legacy = dict(result)
            legacy.pop('application_findings')
            self.assertFalse(action.run(task_vars=dict(variables, platform_image_snapshot=legacy))['hit'])
            source.write_text('all: {hosts: {node1: {}}}\n')
            self.assertFalse(action.run(task_vars=variables)['hit'])
            self.assertFalse(Path(folder, 'result.json').exists())


if __name__ == '__main__':
    unittest.main()

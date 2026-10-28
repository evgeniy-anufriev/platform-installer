"""Native script phase dispatch and context-free delivery/repeat proof."""
import copy
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
TASKS = ROOT / 'ansible-core/playbooks/applications/tasks'


@unittest.skipUnless(shutil.which('ansible-playbook'), 'native Ansible required')
class ScriptDispatchRuntimeTests(unittest.TestCase):
    def run_play(self, root, tasks, variables=None, success=True, role_path=None,
                 hosts='localhost', inventory='localhost,'):
        play = root / 'play.yml'
        play.write_text(yaml.safe_dump([dict(hosts=hosts, connection='local', gather_facts=False,
            vars=variables or {}, tasks=tasks)], sort_keys=False))
        result = subprocess.run(['ansible-playbook', '-i', inventory, str(play)],
            env=dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections'),
                     **({'ANSIBLE_ROLES_PATH': str(role_path)} if role_path else {})),
            capture_output=True, text=True, timeout=120)
        self.assertEqual(success, result.returncode == 0, (result.stdout + result.stderr)[-3500:])
        self.assertNotIn('private-probe-value', result.stdout + result.stderr)
        return result

    def test_manual_outer_default_loop_keeps_each_job_context(self):
        with tempfile.TemporaryDirectory(prefix='script-caller-loop-') as folder:
            root = Path(folder)
            script = root / 'loop.sh'
            script.write_text('#!/bin/sh\nset -eu\nprintf "%s\\n" "$1" >> "$PWD/seen"\n'
                              'printf \'{"status":"ok","changed":false}\\n\'\n')
            jobs = [dict(id=name, path=str(script), workingDirectory=str(root),
                         account=pwd.getpwuid(os.getuid()).pw_name, argv=[name], secretInputs={})
                    for name in ('first', 'second')]
            self.run_play(root, [{'ansible.builtin.include_role': {'name': 'platform.core.package_script'},
                'loop': jobs, 'vars': {'platform_script_job': '{{ item }}'}}])
            self.assertEqual(['first', 'second'], (root / 'seen').read_text().splitlines())

    def test_empty_phases_do_not_enter_runtime_and_active_phases_keep_order(self):
        library = yaml.safe_load((TASKS / 'ordered-library.yml').read_text())
        instance = yaml.safe_load((TASKS / 'instance-placement.yml').read_text())
        def phase(source, scope, selected):
            return copy.deepcopy(next(t for t in source
                if t.get('ansible.builtin.include_role', {}).get('tasks_from') == 'run_scripts'
                and t['vars']['application_script_scope'] == scope
                and t['vars']['application_script_phase'] == selected))
        with tempfile.TemporaryDirectory(prefix='script-dispatch-') as folder:
            root = Path(folder)
            script = root / 'phase.sh'
            script.write_text('#!/bin/sh\nset -eu\nprintf "%s\\n" "$1" >> "$PWD/seen"\n'
                              'printf \'{"status":"ok","changed":false}\\n\'\n')
            scripts = [dict(id=scope + '-' + p, path=str(script), phase=p, scope=scope,
                            argv=[scope + '-' + p], secretInputs={})
                       for scope in ('library', 'instance') for p in ('before_start', 'after_ready')]
            jobs = [dict(libraryId='sample', instanceId='active', account=pwd.getpwuid(os.getuid()).pw_name,
                         instancePath=str(root), scripts=scripts),
                    dict(libraryId='sample', instanceId='empty', scripts=[])]
            tasks = [phase(library, 'library', 'before_start'),
                     phase(instance, 'instance', 'before_start'),
                     phase(instance, 'instance', 'after_ready'),
                     phase(library, 'library', 'after_ready')]
            self.run_play(root, tasks, dict(platform_application_preflight_jobs=jobs,
                application_library_id='sample', application_library_runtime_jobs=jobs,
                application_instance_runtime_jobs=jobs, platform_application_secret_files={}))
            self.assertEqual(['library-before_start', 'instance-before_start',
                              'instance-after_ready', 'library-after_ready'], (root / 'seen').read_text().splitlines())
            self.assertFalse((root / '.scripts/.secrets').exists())

    def test_ordered_library_passes_only_its_placements_to_each_instance(self):
        with tempfile.TemporaryDirectory(prefix='ordered-script-selection-') as folder:
            root = Path(folder)
            roles = root / 'roles/probe_runtime/tasks'
            roles.mkdir(parents=True)
            # External container actions are observations; production ordering,
            # conditions, set_fact and include-task variables remain unchanged.
            for step in ('apply_library', 'apply_instance', 'image_delivery', 'run_scripts', 'activate_instance', 'verify_container'):
                observation = "{{ seen + [{'step': '" + step + "', 'library': application_library_id, 'instance': application_runtime_job.instanceId | default('library')}] }}"
                (roles / (step + '.yml')).write_text(yaml.safe_dump([
                    {'ansible.builtin.set_fact': {'seen': observation}}]))
            for file in ('ordered-library.yml', 'ordered-instance.yml', 'instance-placement.yml'):
                source = yaml.safe_load((TASKS / file).read_text())
                for task in source:
                    role = task.get('ansible.builtin.include_role', {})
                    if role.get('name') == 'platform.core.application_runtime':
                        role['name'] = 'probe_runtime'
                (root / file).write_text(yaml.safe_dump(source, sort_keys=False))
            jobs = [dict(libraryId=lib, instanceId=name, startupPriority=priority, scripts=[])
                    for lib, name, priority in [('a', 'second', 20), ('b', 'other', 1), ('a', 'first', 10)]]
            variables = dict(seen=[], platform_application_preflight_jobs=jobs,
                platform_endpoint_sources={}, platform_application_completed_batches=[],
                application_selection={'scope': {'installLibraries': ['a', 'b'], 'skippedLibraries': [], 'providerLibraries': []}},
                application_runtime_inputs=dict(jobs=jobs, integrationScripts=[], integrations=dict(batches=[], dependencies={})))
            tasks = [{'ansible.builtin.set_fact': variables},
                     {'ansible.builtin.include_tasks': str(root / 'ordered-library.yml'),
                      'loop': ['a', 'b'], 'loop_control': {'loop_var': 'application_library_id'}},
                     {'ansible.builtin.copy': {'content': '{{ seen | to_json }}', 'dest': str(root / 'seen.json')}}]
            self.run_play(root, tasks, variables, role_path=root / 'roles')
            seen = json.loads((root / 'seen.json').read_text())
            self.assertEqual([('a', 'first'), ('a', 'second'), ('b', 'other')],
                [(row['library'], row['instance']) for row in seen if row['step'] == 'activate_instance'])
            self.assertEqual([('a', 'second'), ('a', 'first'), ('b', 'other')],
                [(row['library'], row['instance']) for row in seen if row['step'] == 'image_delivery'])
            self.assertFalse(any(row['step'] == 'run_scripts' for row in seen))

    def test_preparation_once_per_invocation_with_late_dependencies(self):
        library = yaml.safe_load((ROOT / 'ansible-core/collections/ansible_collections/platform/core/roles/application_runtime/tasks/apply_library.yml').read_text())
        placement = yaml.safe_load((TASKS / 'instance-placement.yml').read_text())
        with tempfile.TemporaryDirectory(prefix='application-preparation-') as folder:
            root = Path(folder)
            probe = root / 'prepare.yml'
            probe.write_text(yaml.safe_dump([{'ansible.builtin.set_fact': {
                'prepared': '{{ prepared + [application_runtime_job.instanceId] }}'}}]))
            initial = copy.deepcopy(library[-2]['block'][-1])
            initial['ansible.builtin.include_tasks'] = str(probe)
            deferred = copy.deepcopy(placement[0])
            del deferred['ansible.builtin.include_role']
            deferred['ansible.builtin.include_tasks'] = str(probe)
            jobs = [dict(libraryId='sample', instanceId=name) for name in ('early', 'late')]
            variables = dict(prepared=[], application_library_id='sample',
                platform_application_preflight_jobs=jobs, application_instance_runtime_jobs=jobs,
                platform_application_completed_batches=['previous'], application_runtime_inputs=dict(integrations=dict(
                    dependencies={'sample/early': ['previous'], 'sample/late': ['next']})))
            tasks = [{'ansible.builtin.set_fact': variables}, library[0], initial, library[-1],
                     {'ansible.builtin.assert': {'that': "application_prepared_instance_ids == ['early']"}},
                     {'ansible.builtin.set_fact': {'platform_application_completed_batches': ['previous', 'next']}},
                     deferred,
                     {'ansible.builtin.assert': {'that': "prepared == ['early', 'late']"}},
                     # Another operation must prepare both again, despite retained host facts.
                     library[0], initial, library[-1], deferred,
                     {'ansible.builtin.assert': {'that': "prepared == ['early', 'late', 'early', 'late']"}}]
            self.run_play(root, tasks, variables)

    def test_coordination_keeps_endpoint_hosts_without_local_placements(self):
        with tempfile.TemporaryDirectory(prefix='application-coordination-') as folder:
            root = Path(folder)
            source = yaml.safe_load((TASKS / 'ordered-instance.yml').read_text())
            endpoint = root / 'endpoint.yml'
            endpoint.write_text(yaml.safe_dump([{'ansible.builtin.copy': {
                'content': 'endpoint', 'dest': str(root / 'endpoint-{{ inventory_hostname }}')}}]))
            placement = root / 'instance-placement.yml'
            placement.write_text(yaml.safe_dump([{'ansible.builtin.copy': {
                'content': 'placement', 'dest': str(root / 'placement-{{ inventory_hostname }}')}}]))
            for task in source:
                path = task.get('ansible.builtin.include_tasks')
                if path == 'instance-placement.yml':
                    task['ansible.builtin.include_tasks'] = str(placement)
                elif path and 'apply-source' in path:
                    task['ansible.builtin.include_tasks'] = str(endpoint)
                elif path:  # provider/Vault side effects are outside this scheduling proof
                    task['ansible.builtin.include_tasks'] = str(root / 'noop.yml')
            (root / 'noop.yml').write_text('[]')
            batch = dict(providerLibraryId='sample', providerInstanceId='one')
            context = {'ansible.builtin.set_fact': dict(platform_application_completed_batches=[],
                application_runtime_inputs=dict(integrations=dict(dependencies={}, batches=[batch]))),
                'delegate_to': 'localhost', 'delegate_facts': True, 'run_once': True}
            variables = dict(application_library_id='sample', application_instance_id='one',
                application_instance_runtime_jobs="{{ [{'instanceId': 'one'}] if inventory_hostname == 'node2' else [] }}")
            self.run_play(root, [context] + source + [{'ansible.builtin.assert': {
                'that': 'application_ready_provider_batches | length == 1'}}], variables,
                hosts='all', inventory='node1,node2,node3,')
            self.assertEqual(['placement-node2'], [path.name for path in root.glob('placement-*')])
            self.assertEqual(3, len(list(root.glob('endpoint-*'))))

    def test_shared_delivery_coordinator_remembers_only_successful_fields(self):
        with tempfile.TemporaryDirectory(prefix='application-shared-delta-') as folder:
            root = Path(folder)
            roles = root / 'roles/probe_vault/tasks'
            roles.mkdir(parents=True)
            for step in ('preflight', 'library', 'instance'):
                (roles / (step + '.yml')).write_text(yaml.safe_dump([{
                    'ansible.builtin.set_fact': {'seen': "{{ seen + [{'step': '" + step + "', 'fields': platform_vault_application_job.documents[0].fields | list}] }}"},
                    'delegate_facts': False}]))
            source = yaml.safe_load((TASKS / 'deliver-ready.yml').read_text())
            for task in source:
                if 'ansible.builtin.include_role' in task:
                    task['ansible.builtin.include_role']['name'] = 'probe_vault'
            (root / 'deliver.yml').write_text(yaml.safe_dump(source, sort_keys=False))
            variables = dict(seen=[], platform_application_completed_batches=[], platform_application_delivered_instances=[],
                platform_application_delivered_shared_fields=[], application_runtime_inputs=dict(integrations=dict(
                    dependencies={}, sharedDependencies={'sample/late': ['ready']})),
                application_vault_inputs=dict(instanceJobs=[], libraryJobs=[dict(providerId='vault', libraryId='sample',
                    documents=[dict(mount='secret', document='shared', fields={'early': {}, 'late': {}})])]))
            for name in ('vault_runtime', 'vault_values', 'vault_documents', 'vault_identities', 'secret_files'):
                variables['platform_application_' + name] = {}
            variables['platform_application_secret_root'] = str(root)
            call = {'ansible.builtin.include_tasks': str(root / 'deliver.yml')}
            tasks = [{'ansible.builtin.set_fact': variables}, call, call, {'ansible.builtin.set_fact': {'platform_application_completed_batches': ['ready']}},
                     call, call, {'ansible.builtin.assert': {'that': [
                         "seen | map(attribute='step') | list == ['preflight', 'library', 'preflight', 'library']",
                         "seen | map(attribute='fields') | list == [['early'], ['early'], ['late'], ['late']]",
                         'platform_application_delivered_shared_fields | length == 2']}}]
            self.run_play(root, tasks, variables, role_path=root / 'roles')

    def test_copy_batch_preserves_inputs_and_repeat_changed_zero(self):
        with tempfile.TemporaryDirectory(prefix='script-delivery-') as folder:
            root = Path(folder)
            one, two = root / 'one', root / 'two'
            one.write_text('private-probe-value')
            two.write_text('second-synthetic-value')
            script = root / 'probe.sh'
            script.write_text('#!/bin/sh\nset -eu\n'
                '[ "$(cat "$PLATFORM_SCRIPT_SECRET_FIRST_FILE")" = private-probe-value ]\n'
                '[ "$(cat "$PLATFORM_SCRIPT_SECRET_SECOND_FILE")" = second-synthetic-value ]\n'
                '[ "$(stat -c %a "$PLATFORM_SCRIPT_SECRET_FIRST_FILE")" = 600 ]\n'
                '[ "$(stat -c %a "$PLATFORM_SCRIPT_BATCH_FILE")" = 600 ]\n'
                '[ ! -e "$PWD/.scripts/.secrets/probe/stale" ]\n'
                'cp "$PLATFORM_SCRIPT_BATCH_FILE" "$PWD/observed.json"\n'
                'changed=false\nif [ ! -f "$PWD/created" ]; then touch "$PWD/created"; changed=true; fi\n'
                'printf \'{"status":"ok","changed":%s}\\n\' "$changed"\n')
            invocations = [['first', '; touch must-not-exist'], ['second', 'line\nbreak']]
            job = dict(id='probe', path=str(script), account=pwd.getpwuid(os.getuid()).pw_name,
                       workingDirectory=str(root), argv=[], secretInputs={'first': 'one', 'second': 'two'},
                       invocations=invocations)
            call = {'ansible.builtin.include_role': {'name': 'platform.core.package_script'},
                    'vars': dict(platform_script_job=job, platform_script_secret_files={'one': str(one), 'two': str(two)})}
            stale = root / '.scripts/.secrets/probe'
            stale.mkdir(parents=True)
            (stale / 'stale').write_text('obsolete')
            self.run_play(root, [call])
            repeated = self.run_play(root, [call])
            self.assertIn('changed=0', repeated.stdout)
            self.assertEqual(invocations, json.loads((root / 'observed.json').read_text()))
            self.assertFalse((root / 'must-not-exist').exists())
            self.assertFalse(stale.exists())
            bad = copy.deepcopy(call)
            bad['vars']['platform_script_job']['path'] = str(root / 'missing.sh')
            self.run_play(root, [bad], success=False)
            self.assertFalse(stale.exists())

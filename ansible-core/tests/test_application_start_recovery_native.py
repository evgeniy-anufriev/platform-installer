"""Exercise production activation tasks with a deterministic Docker CLI boundary."""
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
CORE = ROOT / 'ansible-core'
TASKS = CORE / 'collections/ansible_collections/platform/core/roles/application_runtime/tasks/activate_instance.yml'


@unittest.skipUnless(shutil.which('ansible-playbook'), 'native Ansible required')
class ApplicationStartRecoveryTests(unittest.TestCase):
    def test_per_host_includes_preserve_other_hosts_after_recovery(self):
        for mode, failing_host, legacy in [('success', 'node3', False),
                                           ('recover', 'node3', False),
                                           ('recover', 'node2', False),
                                           ('fail', 'node3', False),
                                           ('recover', 'node3', True)]:
            with self.subTest(mode=mode, failing_host=failing_host, legacy=legacy), tempfile.TemporaryDirectory() as folder:
                work = Path(folder)
                for host in ('node2', 'node3'):
                    (work / host).mkdir()
                cli = work / 'docker'
                cli.write_text('''#!/usr/bin/env python3
import json,os,sys,pathlib
p=pathlib.Path(os.environ['PROBE_DIR']);a=sys.argv[1:];host=os.environ['PROBE_HOST']
with (p/'calls').open('a') as f:f.write(json.dumps(a)+'\\n')
app=a[-1].split('-')[0] if a[:2]==['container','inspect'] else a[-1]
if a[:2]==['container','inspect']:
 print(json.dumps([{'Id':app+('new' if (p/(app+'-recreated')).exists() else 'old'),'Image':'sha256:probe','Config':{'Labels':{'platform.installer.project':'p','platform.installer.library':'l','platform.installer.instance':app,'platform.installer.host':host}},'State':{'Running':True}}]))
elif a[:2]==['compose','up']:
 failing=host==os.environ['PROBE_FAIL_HOST'] and app=='first'
 if '--force-recreate' in a:
  if failing and os.environ['PROBE_MODE']=='fail':sys.exit(2)
  (p/(app+'-recreated')).touch()
 elif failing and os.environ['PROBE_MODE']!='success':sys.exit(1)
else:sys.exit(3)
''')
                cli.chmod(0o755)
                tasks_path = TASKS
                if legacy:
                    tasks = yaml.safe_load(TASKS.read_text())
                    tasks[1]['block'][0].pop('any_errors_fatal', None)
                    tasks[2]['ansible.builtin.include_tasks'] = str(TASKS.parent / 'verify.yml')
                    tasks_path = work / 'legacy.yml'
                    tasks_path.write_text(yaml.safe_dump(tasks))
                job = dict(account=pwd.getpwuid(os.getuid()).pw_name,
                           dockerEnvironment=dict(PATH=str(work)+':'+os.environ['PATH'],
                                                  PROBE_DIR=str(work)+'/{{ inventory_hostname }}',
                                                  PROBE_HOST='{{ inventory_hostname }}',
                                                  PROBE_FAIL_HOST=failing_host, PROBE_MODE=mode),
                           composeArgv=['docker', 'compose'], instanceId="{{ qa_item.split('/')[1] }}",
                           projectId='p', libraryId='l', hostId='{{ inventory_hostname }}',
                           instancePath=str(work), placement=dict(containerName="{{ qa_item.split('/')[1] }}-{{ inventory_hostname }}"),
                           authority=dict(requirement=dict(imageId='sha256:probe')),
                           settings=dict(readiness=dict(mode='container', retries=1, delay=0)))
                inner = work / 'instance.yml'
                inner.write_text(yaml.safe_dump([{'ansible.builtin.include_tasks': str(tasks_path),
                                                 'vars': {'application_runtime_job': job}}]))
                stages = [{'ansible.builtin.include_tasks': str(inner),
                           'loop': ["{{ inventory_hostname }}/"+instance],
                           'loop_control': {'loop_var': 'qa_item'}} for instance in ('first', 'second')]
                stages.append({'ansible.builtin.copy': {'content': 'continued',
                               'dest': str(work)+'/{{ inventory_hostname }}/continued', 'mode': '0600'}})
                play = [dict(hosts='all', gather_facts=False, any_errors_fatal=True,
                             vars={'ansible_python_interpreter': shutil.which('python3')},
                             tasks=[{'block': stages, 'always': [{'ansible.builtin.debug': {'msg': 'QA_CLEANUP'}}]}])]
                probe = work / 'play.yml'
                probe.write_text(yaml.safe_dump(play))
                result = subprocess.run(['ansible-playbook', '-i', 'node2,node3,',
                                         '-e', 'ansible_connection=local', str(probe)],
                                        env=dict(os.environ, ANSIBLE_CONFIG=str(CORE/'ansible.cfg'),
                                                 ANSIBLE_COLLECTIONS_PATH=str(CORE/'collections')),
                                        capture_output=True, text=True, timeout=180)
                continued = {h for h in ('node2', 'node3') if (work/h/'continued').exists()}
                expected = {'node3'} if legacy else (set() if mode == 'fail' else {'node2', 'node3'})
                self.assertEqual(expected, continued, result.stdout+result.stderr)
                self.assertEqual(mode == 'fail' or legacy, result.returncode != 0, result.stdout+result.stderr)
                calls = {h: [json.loads(line) for line in (work/h/'calls').read_text().splitlines()]
                         for h in ('node2', 'node3') if (work/h/'calls').exists()}
                if mode == 'fail':
                    self.assertFalse(any(a[:2] == ['compose', 'up'] and a[-1] == 'second'
                                         for rows in calls.values() for a in rows))
                elif not legacy:
                    for host in ('node2', 'node3'):
                        ups = [a for a in calls[host] if a[:2] == ['compose', 'up']]
                        self.assertEqual(3 if mode == 'recover' and host == failing_host else 2, len(ups))
                        self.assertEqual(1 if mode == 'recover' and host == failing_host else 0,
                                         sum('--force-recreate' in a for a in ups))

    def test_start_recreate_and_unrecoverable_failure(self):
        for mode in ('success', 'recover', 'fail'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                work = Path(folder)
                cli = work / 'docker'
                cli.write_text('''#!/usr/bin/env python3
import json,os,sys,pathlib
p=pathlib.Path(os.environ['PROBE_DIR']); a=sys.argv[1:]
with (p/'calls').open('a') as f:f.write(json.dumps(a)+'\\n')
recreated=(p/'recreated').exists()
if a[:2]==['container','inspect']:
 print(json.dumps([{'Id':'new' if recreated else 'old','Image':'sha256:probe','Config':{'Labels':{'platform.installer.project':'p','platform.installer.library':'l','platform.installer.instance':'app','platform.installer.host':'h'}},'State':{'Running':True}}]))
elif a[:2]==['compose','up']:
 if '--force-recreate' in a:
  if os.environ['PROBE_MODE']=='fail':sys.exit(2)
  (p/'recreated').touch()
 elif os.environ['PROBE_MODE']!='success':sys.exit(1)
else:sys.exit(3)
''', encoding='utf-8')
                cli.chmod(0o755)
                job = dict(account=pwd.getpwuid(os.getuid()).pw_name,
                           dockerEnvironment=dict(PATH=str(work)+':'+os.environ['PATH'],
                                                  PROBE_DIR=str(work), PROBE_MODE=mode),
                           composeArgv=['docker', 'compose'], instanceId='app', projectId='p',
                           libraryId='l', hostId='h', instancePath=str(work),
                           placement=dict(containerName='app-h'),
                           authority=dict(requirement=dict(imageId='sha256:probe')),
                           settings=dict(readiness=dict(mode='container', retries=1, delay=0)))
                play = [dict(hosts='localhost', connection='local', gather_facts=False,
                             vars=dict(application_runtime_job=job),
                             tasks=[{'ansible.builtin.include_tasks': str(TASKS)}])]
                probe = work / 'play.yml'
                probe.write_text(yaml.safe_dump(play), encoding='utf-8')
                result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(probe)],
                                        env=dict(os.environ, ANSIBLE_CONFIG=str(CORE/'ansible.cfg'),
                                                 ANSIBLE_COLLECTIONS_PATH=str(CORE/'collections')),
                                        capture_output=True, text=True, timeout=90)
                calls = [json.loads(line) for line in (work/'calls').read_text().splitlines()]
                ups = [args for args in calls if args[:2] == ['compose', 'up']]
                self.assertEqual(1 if mode == 'success' else 2, len(ups), result.stdout+result.stderr)
                self.assertNotIn('--force-recreate', ups[0])
                for args in ups:
                    self.assertEqual('app', args[-1])
                    self.assertIn('--no-deps', args)
                    self.assertEqual('never', args[args.index('--pull')+1])
                if mode != 'success':
                    self.assertIn('--force-recreate', ups[1])
                self.assertEqual(mode == 'fail', result.returncode != 0, result.stdout+result.stderr)
                inspections = [args for args in calls if args[:2] == ['container', 'inspect']]
                self.assertEqual(1 if mode == 'fail' else 2, len(inspections))
                if mode == 'success':
                    self.assertIn('changed=0', result.stdout)
                elif mode == 'recover':
                    self.assertIn('changed=1', result.stdout)
                    self.assertIn('rescued=1', result.stdout)

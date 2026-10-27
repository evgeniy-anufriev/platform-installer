"""Exercise the production wait with real BIND peers in a private network namespace."""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
ROLE = ROOT / 'services/bind/ansible_collections/platform/bind/roles/bind'


class BindReadinessTests(unittest.TestCase):
    def test_wait_is_after_service_start_and_record_updates(self):
        tasks = yaml.safe_load((ROLE / 'tasks/start.yml').read_text())
        self.assertEqual('readiness.yml', tasks[-1]['ansible.builtin.include_tasks'])
        self.assertIn('update_base_zone_records.yml', [t.get('ansible.builtin.include_tasks') for t in tasks[:-1]])

    @unittest.skipUnless(os.environ.get('PLATFORM_TEST_NATIVE_BIND_READINESS') == '1', 'explicit native BIND QA')
    def test_cold_secondary_waits_then_repeat_is_unchanged(self):
        result = self.native('cold')
        self.assertGreater(result['first']['attempts'][0], 1)
        self.assertEqual(0, result['first']['failed'])
        self.assertEqual(0, result['first']['changed'])
        self.assertEqual([1], result['repeat']['attempts'])
        self.assertEqual(0, result['repeat']['changed'])

    @unittest.skipUnless(os.environ.get('PLATFORM_TEST_NATIVE_BIND_READINESS') == '1', 'explicit native BIND QA')
    def test_active_secondary_without_zone_fails_after_bounded_wait(self):
        result = self.native('unavailable')
        self.assertGreater(result['first']['failed'], 0)
        self.assertEqual(0, result['first']['changed'])

    def native(self, mode):
        process = subprocess.Popen(['unshare', '--net', sys.executable, str(Path(__file__).resolve()), '--fixture', mode],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=180)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            self.fail('isolated BIND fixture timed out')
        self.assertEqual(0, process.returncode, stderr + stdout)
        return json.loads(stdout.strip().splitlines()[-1])


def fixture(mode):
    subprocess.run(['ip', 'link', 'set', 'lo', 'up'], check=True)
    subprocess.run(['ip', 'address', 'add', '127.0.0.2/8', 'dev', 'lo'], check=True)
    processes, logs = [], []
    cancel = threading.Event()
    worker = None
    with tempfile.TemporaryDirectory(prefix='bind-readiness-') as directory:
        work = Path(directory)
        zone = 'readiness.test'
        (work / 'primary.zone').write_text(
            '$TTL 1\n@ IN SOA ns.readiness.test. hostmaster.readiness.test. (1 1 1 300 1)\n'
            '@ IN NS ns.readiness.test.\nns IN A 127.0.0.2\n')
        for name, address, body in [
            ('primary', '127.0.0.2', 'type primary; file "primary.zone"; allow-transfer { 127.0.0.1; }; also-notify { 127.0.0.1; };'),
            ('secondary', '127.0.0.1', 'type secondary; primaries { 127.0.0.2; }; file "secondary.zone";')]:
            (work / (name + '.conf')).write_text(
                'options { directory "%s"; listen-on { %s; }; listen-on-v6 { none; }; '
                'notify-source %s; transfer-source %s; recursion no; dnssec-validation no; querylog yes; pid-file "%s.pid"; session-keyfile "%s.session"; }; '
                'controls {}; zone "%s" { %s };' % (work, address, address, address, name, name, zone, body))

        callbacks = work / 'callbacks'
        callbacks.mkdir()
        (callbacks / 'readiness_result.py').write_text('''import json
from ansible.plugins.callback import CallbackBase
class CallbackModule(CallbackBase):
 CALLBACK_VERSION=2.0
 CALLBACK_TYPE='stdout'
 CALLBACK_NAME='readiness_result'
 def __init__(self):
  super().__init__(); self.attempts=[]
 def capture(self,result):
  if result._task.name == 'Ожидание авторитетного SOA из локального BIND':
   self.attempts.extend(r.get('attempts',1) for r in result._result.get('results',[]))
 def v2_runner_on_ok(self,result): self.capture(result)
 def v2_runner_on_failed(self,result,ignore_errors=False): self.capture(result)
 def v2_playbook_on_stats(self,stats):
  rows=[stats.summarize(h) for h in stats.processed]
  print('QA_RESULT='+json.dumps({'attempts':self.attempts,'changed':sum(r['changed'] for r in rows),'failed':sum(r['failures']+r['unreachable'] for r in rows)}))
''')
        defaults = yaml.safe_load((ROLE / 'defaults/main.yml').read_text())
        play = [{'name': 'BIND readiness native QA', 'hosts': 'localhost', 'gather_facts': False,
                 'vars': {'platform_bind_resolved_zones': {'qa-bind': {'zone': zone}},
                          'platform_deployments': {'qa-bind': {}},
                          'ansible_remote_tmp': str(work / 'remote-tmp'),
                          'platform_bind_readiness_retries': 2 if mode == 'unavailable' else defaults['platform_bind_readiness_retries'],
                          'platform_bind_readiness_delay': 1},
                 'tasks': [{'name': 'Production BIND readiness', 'ansible.builtin.include_tasks': str(ROLE / 'tasks/readiness.yml')}]}]
        (work / 'play.yml').write_text(yaml.safe_dump(play))

        def start(name):
            output = open(work / (name + '.log'), 'w')
            logs.append(output)
            processes.append(subprocess.Popen(['/usr/sbin/named', '-g', '-u', 'root', '-c', str(work / (name + '.conf'))],
                                              cwd=work, stdout=output, stderr=subprocess.STDOUT))

        def delayed_primary():
            while not cancel.wait(0.05):
                if 'query: readiness.test IN SOA' in (work / 'secondary.log').read_text():
                    if not cancel.wait(2):
                        start('primary')
                    return

        def query():
            env = dict(os.environ, ANSIBLE_STDOUT_CALLBACK='readiness_result', ANSIBLE_CALLBACK_PLUGINS=str(callbacks),
                       ANSIBLE_LOCAL_TEMP=str(work / 'ansible-tmp'))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', '-c', 'local', str(work / 'play.yml')],
                                    env=env, capture_output=True, text=True, timeout=120)
            matches = [line.removeprefix('QA_RESULT=') for line in result.stdout.splitlines() if line.startswith('QA_RESULT=')]
            if not matches:
                raise RuntimeError(result.stderr + result.stdout)
            return json.loads(matches[-1])

        try:
            start('secondary')
            for _ in range(100):
                with socket.socket() as probe:
                    if probe.connect_ex(('127.0.0.1', 53)) == 0:
                        break
                time.sleep(0.05)
            else:
                raise RuntimeError((work / 'secondary.log').read_text())
            if mode == 'cold':
                worker = threading.Thread(target=delayed_primary)
                worker.start()
            first = query()
            if mode == 'cold' and first['failed']:
                raise RuntimeError('Cold secondary did not become ready: ' + json.dumps(first) + '\n' + (work / 'secondary.log').read_text() + '\n' + ((work / 'primary.log').read_text() if (work / 'primary.log').exists() else 'PRIMARY_NOT_STARTED'))
            repeat = query() if mode == 'cold' and not first['failed'] else None
            print(json.dumps({'first': first, 'repeat': repeat}))
        finally:
            cancel.set()
            if worker:
                worker.join()
            for process in processes:
                process.terminate()
            for process in processes:
                process.wait(timeout=10)
            for output in logs:
                output.close()


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--fixture':
        fixture(sys.argv[2])
    else:
        unittest.main()

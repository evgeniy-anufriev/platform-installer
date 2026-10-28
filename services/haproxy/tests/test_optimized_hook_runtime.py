"""Exercise the generic partial hook on real HAProxy in isolated directories."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[3]

@unittest.skipUnless(getattr(os, 'geteuid', lambda: -1)() == 0 and shutil.which('ansible-playbook')
                     and shutil.which('haproxy') and shutil.which('openssl'), 'isolated native root fixtures')
class OptimizedHookRuntimeTests(unittest.TestCase):
    def test_one_endpoint(self):
        self.optimized_publication(1)

    def test_five_endpoints(self):
        self.optimized_publication(5)

    def test_twenty_endpoints(self):
        self.optimized_publication(20)

    def optimized_publication(self, count):
        with tempfile.TemporaryDirectory(prefix='qa-haproxy-batch-', dir='/var/tmp') as folder:
            root = Path(folder)
            active, candidate = root / 'active', root / 'active/.candidate'
            conf, pki = active / 'conf.d', root / 'pki'
            conf.mkdir(parents=True, mode=0o750)
            pki.mkdir(mode=0o750)
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                '-subj', '/CN=localhost', '-keyout', str(pki / 'key.pem'), '-out', str(pki / 'cert.pem')],
                check=True, capture_output=True)
            (pki / 'haproxy.pem').write_bytes((pki / 'cert.pem').read_bytes() + (pki / 'key.pem').read_bytes())
            (pki / 'haproxy.pem').chmod(0o640)
            (active / 'haproxy.cfg').write_text('global\n    maxconn 128\ndefaults\n    mode http\n'
                '    timeout connect 1s\n    timeout client 1s\n    timeout server 1s\n')
            (conf / '10-public.cfg').write_text('frontend old\n    bind 127.0.0.1:19345\n    http-request return status 503\n')
            for name in ['20-local-stats.cfg', '90-stats-backends.cfg']:
                (conf / name).write_text('# unchanged provider configuration\n')
            for number in range(40):
                (conf / ('30-backend-neighbor-%s-public.cfg' % number)).write_text(
                    'backend neighbor%s\n    server local 127.0.0.1:9\n' % number)
            (conf / 'custom fragment.cfg').write_text('# unrelated custom fragment\n')
            for path in conf.iterdir():
                path.chmod(0o640)
            (active / 'haproxy.cfg').chmod(0o640)
            shutil.copytree(conf, candidate / 'conf.d')
            shutil.copy2(active / 'haproxy.cfg', candidate / 'haproxy.cfg')
            source_name = '30-backend-qa-source-public.cfg'
            backend = dict(configFileName=source_name, backendName='app-qa', targetDeploymentId='qa-source',
                providerHostIds=['localhost'], settings=dict(balance='roundrobin', ssl=False, check=False),
                targets=[dict(serverName='local', address='127.0.0.1', port=9)])
            backends = [dict(backend, configFileName=(source_name if n == 0 else f'30-backend-source-{n}-public.cfg'),
                             backendName=f'app-{n}', targetDeploymentId=('qa-source' if n == 0 else f'source-{n}'))
                        for n in range(count)]
            source_ids = [b['targetDeploymentId'] for b in backends]
            values = dict(platform_haproxy_config_directory=str(active), platform_haproxy_main_config=str(active / 'haproxy.cfg'),
                platform_haproxy_conf_directory=str(conf), platform_haproxy_candidate_directory=str(candidate),
                platform_haproxy_pki_directory=str(pki), platform_haproxy_binary=shutil.which('haproxy'),
                platform_haproxy_public_port=19346, platform_haproxy_partial_deployment_ids=source_ids,
                _platform_haproxy_partial_ids=source_ids, platform_deployments={'qa-proxy': {}},
                platform_desired_state={'endpointGroups': {'qa': {'address': {'domain': 'example.internal'}}}},
                platform_haproxy_runtime_projection={'backends': {'backends': {'qa-proxy': backends}}})
            environment = dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
                ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections') + ':' + str(ROOT / 'services/haproxy'))
            inventory = root / 'inventory.yml'
            inventory.write_text(yaml.safe_dump({'all': {'children': {'platform_targets': {'hosts': {
                'localhost': {'ansible_host': '127.0.0.1', 'ansible_connection': 'local'}}}}}}))
            def invoke(tasks):
                path = root / 'play.yml'
                path.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False,
                                                    vars=values, tasks=tasks)]))
                return subprocess.run(['ansible-playbook', '-i', str(inventory), str(path)],
                    env=environment, capture_output=True, text=True, timeout=180)
            def role(part):
                return {'ansible.builtin.include_role': {'name': 'platform.haproxy.haproxy', 'tasks_from': part}}
            untouched = {p.name: p.read_bytes() for p in conf.iterdir() if p.name != '10-public.cfg'}
            legacy_seconds = None
            if count == 20:
                saved = root / 'initial-active'
                shutil.copytree(active, saved)
                started = time.monotonic()
                legacy = invoke([role('prepare'), role('activate')])
                legacy_seconds = time.monotonic() - started
                self.assertEqual(0, legacy.returncode, (legacy.stdout + legacy.stderr)[-4000:])
                legacy_bytes = {p.name: p.read_bytes() for p in conf.iterdir()}
                shutil.rmtree(active)
                shutil.copytree(saved, active)
            started = time.monotonic()
            first = invoke([role('partial_candidate'), role('activate')])
            cold_seconds = time.monotonic() - started
            self.assertEqual(0, first.returncode, first.stdout[-5000:] + first.stderr[-1000:])
            self.assertTrue((conf / source_name).exists())
            self.assertEqual({p.name for p in conf.iterdir()}, {p.name for p in (candidate / 'conf.d').iterdir()})
            self.assertIn('Проверка полного графа-кандидата HAProxy', first.stdout)
            self.assertEqual(1, first.stdout.count('TASK [platform.haproxy.haproxy : Пакетное копирование сохраняемых фрагментов в кандидат HAProxy]'))
            for name, contents in untouched.items():
                self.assertEqual(contents, (conf / name).read_bytes())
                self.assertEqual(contents, (candidate / 'conf.d' / name).read_bytes())
            if legacy_seconds is not None:
                self.assertEqual(legacy_bytes, {p.name: p.read_bytes() for p in conf.iterdir()})
                print(f'HOOK_BASELINE endpoints={count} legacy_cold={legacy_seconds:.3f}s optimized_cold={cold_seconds:.3f}s', flush=True)
            def fingerprint():
                return {str(p.relative_to(active)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in [active / 'haproxy.cfg', *conf.iterdir()]}
            before = fingerprint()
            candidate_mtime = (candidate / 'conf.d' / source_name).stat().st_mtime_ns
            started = time.monotonic()
            repeated = invoke([role('partial_candidate'), role('activate'), role('partial_reload')])
            repeat_seconds = time.monotonic() - started
            self.assertEqual(0, repeated.returncode, repeated.stdout[-4000:] + repeated.stderr[-1000:])
            self.assertIn('changed=0', repeated.stdout)
            self.assertEqual(before, fingerprint())
            self.assertEqual({p.name for p in conf.iterdir()}, {p.name for p in (candidate / 'conf.d').iterdir()})
            self.assertEqual(candidate_mtime, (candidate / 'conf.d' / source_name).stat().st_mtime_ns)
            self.assertNotIn('TASK [platform.haproxy.haproxy : Пакетная запись выбранных фрагментов в кандидат HAProxy]', repeated.stdout)
            print(f'HOOK_BENCH endpoints={count} cold={cold_seconds:.3f}s repeat={repeat_seconds:.3f}s', flush=True)
            if count == 1:
                pem = pki / 'haproxy.pem'
                original_pem = pem.read_bytes()
                pem.write_text('invalid TLS material')
                invalid_tls = invoke([role('partial_candidate'), role('activate')])
                self.assertNotEqual(0, invalid_tls.returncode)
                self.assertEqual(before, fingerprint())
                self.assertEqual(candidate_mtime, (candidate / 'conf.d' / source_name).stat().st_mtime_ns)
                pem.write_bytes(original_pem)
            self.assertEqual(1, first.stdout.count('TASK [platform.haproxy.haproxy : Пакетная запись выбранных фрагментов в кандидат HAProxy]'))
            self.assertEqual(1, first.stdout.count('TASK [platform.haproxy.haproxy : Пакетная установка проверенных фрагментов HAProxy]'))
            backends[0]['backendName'] = 'invalid backend name'
            invalid = invoke([role('partial_candidate'), role('activate')])
            self.assertNotEqual(0, invalid.returncode)
            self.assertIn('Проверка полного графа-кандидата HAProxy', invalid.stdout)
            self.assertEqual(before, fingerprint())

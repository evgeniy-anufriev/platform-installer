"""Real candidate validation/publication in disposable root-owned directories."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[3]
ROLE = ROOT / 'services/haproxy/ansible_collections/platform/haproxy/roles/haproxy'


class PartialHookContractTests(unittest.TestCase):
    def test_batch_uses_native_remote_copy_without_per_file_copy_loop(self):
        tasks = yaml.safe_load((ROLE / 'tasks/partial_copy.yml').read_text())
        copies = [t for t in tasks if 'ansible.builtin.copy' in t]
        self.assertEqual(2, len(copies))
        self.assertTrue(all(t['ansible.builtin.copy']['remote_src'] for t in copies))
        self.assertTrue(all('loop' not in t for t in copies))
        self.assertFalse(any('ansible.builtin.command' in t or 'ansible.builtin.shell' in t for t in tasks))
    def test_hook_prepares_once_and_keeps_cluster_phase_barriers(self):
        plays = yaml.safe_load((ROOT / 'services/haproxy/playbooks/integrate.yml').read_text())
        self.assertEqual(['partial_prepare', 'activate', 'partial_reload'],
                         [p['roles'][0]['tasks_from'] for p in plays])
        self.assertTrue(all(p['any_errors_fatal'] for p in plays))
        tasks = yaml.safe_load((ROOT / 'services/integrations/tasks/apply-source.yml').read_text())
        phases = [t['ansible.builtin.include_role'].get('tasks_from') for t in tasks
                  if t.get('ansible.builtin.include_role', {}).get('name') == 'platform.haproxy.haproxy']
        self.assertEqual(['partial_prepare', 'activate', 'partial_reload', 'endpoint_verify'], phases)
        prepare = yaml.safe_load((ROLE / 'tasks/partial_prepare.yml').read_text())
        self.assertEqual(['resolve.yml', 'partial_candidate.yml'],
                         [t['ansible.builtin.include_tasks'] for t in prepare if 'ansible.builtin.include_tasks' in t])


@unittest.skipUnless(getattr(os, 'geteuid', lambda: -1)() == 0 and shutil.which('ansible-playbook')
                     and shutil.which('haproxy') and shutil.which('openssl'), 'isolated root/Ansible/HAProxy/OpenSSL required')
class PartialBatchRuntimeTests(unittest.TestCase):
    def test_remote_directory_copy_keeps_only_the_exact_retained_names(self):
        with tempfile.TemporaryDirectory(prefix='qa-haproxy-copy-', dir='/var/tmp') as folder:
            root = Path(folder)
            source, candidate = root / 'source', root / 'candidate'
            source.mkdir()
            (candidate / 'conf.d').mkdir(parents=True)
            kept = {'10-public.cfg', '20-local-stats.cfg', '90-stats-backends.cfg',
                    '30-backend-neighbor-public.cfg', 'custom fragment.cfg'}
            selected = '30-backend-selected-public.cfg'
            for name in kept | {selected}:
                (source / name).write_text('# ' + name + '\n')
            (source / 'extra-directory').mkdir()
            (source / 'extra-directory/unused').write_text('not in candidate')
            outside = root / 'outside'
            outside.write_text('untouched')
            (source / 'extra-link').symlink_to(outside)
            main = root / 'haproxy.cfg'
            main.write_text('# main\n')
            values = dict(platform_haproxy_conf_directory=str(source),
                platform_haproxy_candidate_directory=str(candidate), platform_haproxy_main_config=str(main),
                _platform_haproxy_partial_source_files=[selected],
                _platform_haproxy_prior_backend_capture={'previousInventory': [
                    {'name': selected}, {'name': '30-backend-neighbor-public.cfg'}]},
                _platform_haproxy_third_party_fragments={'files': [{'path': str(source / 'custom fragment.cfg')}]})
            play = root / 'play.yml'
            play.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False,
                vars=values, tasks=[{'ansible.builtin.include_role': {
                    'name': 'platform.haproxy.haproxy', 'tasks_from': 'partial_copy'}}])]))
            environment = dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
                ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections') + ':' + str(ROOT / 'services/haproxy'))
            for _ in range(2):
                result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(play)], env=environment,
                    capture_output=True, text=True, timeout=90)
                self.assertEqual(0, result.returncode, result.stdout[-2500:] + result.stderr[-800:])
                self.assertIn('changed=0', result.stdout)
                self.assertEqual(kept, {p.name for p in (candidate / 'conf.d').iterdir()})
                self.assertEqual('untouched', outside.read_text())
                self.assertTrue((source / selected).exists())
                self.assertTrue((source / 'extra-directory/unused').exists())
                self.assertTrue((source / 'extra-link').is_symlink())

    def test_many_fragments_repeat_and_invalid_candidate_never_publishes(self):
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
            values = dict(platform_haproxy_config_directory=str(active), platform_haproxy_main_config=str(active / 'haproxy.cfg'),
                platform_haproxy_conf_directory=str(conf), platform_haproxy_candidate_directory=str(candidate),
                platform_haproxy_pki_directory=str(pki), platform_haproxy_binary=shutil.which('haproxy'),
                platform_haproxy_public_port=19346, platform_haproxy_partial_deployment_id='qa-source',
                _platform_haproxy_partial_ids=['qa-source'], platform_deployments={'qa-proxy': {}},
                platform_desired_state={'endpointGroups': {'qa': {'address': {'domain': 'example.internal'}}}},
                platform_haproxy_runtime_projection={'backends': {'backends': {'qa-proxy': [backend]}}})
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
            first = invoke([role('prepare'), role('activate')])
            self.assertEqual(0, first.returncode, first.stdout[-5000:] + first.stderr[-1000:])
            self.assertTrue((conf / source_name).exists())
            self.assertEqual({p.name for p in conf.iterdir()}, {p.name for p in (candidate / 'conf.d').iterdir()})
            self.assertIn('Проверка полного графа-кандидата HAProxy', first.stdout)
            self.assertEqual(1, first.stdout.count('TASK [platform.haproxy.haproxy : Пакетное копирование сохраняемых фрагментов в кандидат HAProxy]'))
            for name, contents in untouched.items():
                self.assertEqual(contents, (conf / name).read_bytes())
                self.assertEqual(contents, (candidate / 'conf.d' / name).read_bytes())
            def fingerprint():
                return {str(p.relative_to(active)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in [active / 'haproxy.cfg', *conf.iterdir()]}
            before = fingerprint()
            repeated = invoke([role('prepare'), role('activate'), role('partial_reload')])
            self.assertEqual(0, repeated.returncode, repeated.stdout[-4000:] + repeated.stderr[-1000:])
            self.assertIn('changed=0', repeated.stdout)
            self.assertEqual(before, fingerprint())
            self.assertEqual({p.name for p in conf.iterdir()}, {p.name for p in (candidate / 'conf.d').iterdir()})
            backend['backendName'] = 'invalid backend name'
            invalid = invoke([role('prepare'), role('activate')])
            self.assertNotEqual(0, invalid.returncode)
            self.assertIn('Проверка полного графа-кандидата HAProxy', invalid.stdout)
            self.assertEqual(before, fingerprint())

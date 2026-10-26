"""Actual deferred Ansible delivery against a disposable TLS KV/AppRole fixture."""
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile
import threading
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[3]
DELIVERY = ROOT / 'ansible-core/playbooks/applications/tasks/deliver-ready.yml'


@unittest.skipUnless(shutil.which('ansible-playbook') and shutil.which('openssl'), 'native Ansible/OpenSSL required')
class VaultDeliveryRuntimeTests(unittest.TestCase):
    def test_network_key_isolates_provider_route_host_and_bridge(self):
        source = ROOT / 'services/vault/ansible_collections/platform/vault/roles/application_provider/tasks/instance.yml'
        key_task = next(t for t in yaml.safe_load(source.read_text())
                        if t.get('name') == 'Определение ключа обнаружения сетей выбранных размещений Vault')
        with tempfile.TemporaryDirectory(prefix='qa-vault-network-key-') as directory:
            root = Path(directory)
            tasks = [{'ansible.builtin.set_fact': {'keys': []}}]
            cases = [('p', 'first.invalid', 'localhost'), ('p', 'other.invalid', 'localhost'),
                     ('other', 'first.invalid', 'localhost'), ('p', 'first.invalid', 'other-host')]
            for provider, route, host in cases:
                variables = dict(key_task['vars'], platform_vault_application_job=dict(providerId=provider, hosts=[host]),
                                 platform_application_vault_runtime={provider: {'routeAddress': route}})
                tasks.extend([dict(key_task, vars=variables),
                              {'ansible.builtin.set_fact': {'keys': '{{ keys + [application_vault_network_key] }}'}}])
            tasks.append({'ansible.builtin.set_fact': {'platform_docker_lxc_bridge': 'different-bridge'}})
            tasks.extend([dict(key_task, vars=dict(key_task['vars'],
                platform_vault_application_job=dict(providerId='p', hosts=['localhost']),
                platform_application_vault_runtime={'p': {'routeAddress': 'first.invalid'}})),
                {'ansible.builtin.assert': {'that': [
                    'keys | unique | length == 4', 'application_vault_network_key not in keys']}}])
            play, inventory = root / 'probe.yml', root / 'inventory.yml'
            play.write_text(yaml.safe_dump([dict(hosts='localhost', gather_facts=False, tasks=tasks)], sort_keys=False))
            inventory.write_text(yaml.safe_dump({'all': {'hosts': {
                'localhost': {'ansible_connection': 'local'}, 'other-host': {'ansible_connection': 'local'}}}}))
            result = subprocess.run(['ansible-playbook', '-i', str(inventory), str(play)],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(0, result.returncode, (result.stdout + result.stderr)[-1500:])

    def exercise(self, *, race=False, foreign=False, repeat=True):
        with tempfile.TemporaryDirectory(prefix='qa-vault-delivery-') as directory:
            root = Path(directory)
            secret_root = root / 'secrets'
            secret_root.mkdir(mode=0o700)
            password_file = secret_root / 'password-input'
            password_file.write_text('fixture-password')
            password_file.chmod(0o600)
            cert, key = secret_root / 'vault-p-ca.pem', root / 'key.pem'
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                            '-keyout', str(key), '-out', str(cert), '-subj', '/CN=localhost',
                            '-addext', 'subjectAltName=IP:127.0.0.1'], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            state = dict(kv={}, policies={}, roles={}, gets=Counter(), writes=0, race=race, conflicts=0)
            if foreign:
                state['kv']['lib/first/accounts/db'] = dict(version=1, data={'_platform_owner': 'foreign'})

            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *args):
                    pass

                def handle_request(self):
                    if self.headers.get('X-Vault-Token') != 'fixture-token':
                        self.send_error(403)
                        return
                    path = self.path.removeprefix('/v1/')
                    body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))) or b'{}')
                    status, result = 200, {}
                    if self.command == 'GET':
                        state['gets'][path] += 1
                    if path.startswith('secret/data/'):
                        name = path.removeprefix('secret/data/')
                        current = state['kv'].get(name)
                        if self.command == 'GET':
                            if current:
                                result = {'data': {'data': current['data'], 'metadata': {
                                    'version': current['version'], 'deletion_time': '', 'destroyed': False}}}
                            else:
                                status = 404
                        elif state['race']:
                            state['race'] = False
                            state['kv'][name] = dict(version=1, data={'_platform_owner': 'fixture', 'neighbor': 'keep'})
                            status, result = 400, {'errors': ['check-and-set parameter did not match the current version']}
                            state['conflicts'] += 1
                        elif body['options']['cas'] != (current['version'] if current else 0):
                            status, result = 400, {'errors': ['check-and-set parameter did not match the current version']}
                        else:
                            data = dict(current['data']) if current and self.command == 'PATCH' else {}
                            data.update(body['data'])
                            state['kv'][name] = dict(version=(current['version'] if current else 0) + 1, data=data)
                            state['writes'] += 1
                    elif path.startswith('sys/policies/acl/'):
                        identity = path.split('/')[-1]
                        if self.command == 'GET':
                            if identity in state['policies']:
                                result = {'data': {'policy': state['policies'][identity]}}
                            else:
                                status = 404
                        else:
                            state['policies'][identity] = body['policy']
                            status = 204
                    elif path.startswith('auth/approle/role/'):
                        parts = path.split('/')
                        identity = parts[3]
                        if path.endswith('/role-id'):
                            result = {'data': {'role_id': 'role-' + identity}}
                        elif self.command == 'GET':
                            if identity in state['roles']:
                                result = {'data': state['roles'][identity]}
                            else:
                                status = 404
                        else:
                            state['roles'][identity] = body
                            status = 204
                    else:
                        status = 404
                    encoded = json.dumps(result).encode()
                    self.send_response(status)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(encoded)))
                    self.end_headers()
                    self.wfile.write(encoded)

                do_GET = do_PUT = do_PATCH = do_POST = handle_request

            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(str(cert), str(key))
            server.socket = context.wrap_socket(server.socket, server_side=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                bin_dir = root / 'bin'
                bin_dir.mkdir()
                stub = ('#!/usr/bin/python3\nimport json,pathlib,sys\n'
                        'p=pathlib.Path(' + repr(str(root / 'network-calls')) + ')\n'
                        'with p.open("a") as s:s.write(pathlib.Path(sys.argv[0]).name+"\\n")\n'
                        'if pathlib.Path(sys.argv[0]).name=="getent": print("198.51.100.4 STREAM fixture")\n'
                        'elif "route" in sys.argv: print(json.dumps([{"prefsrc":"192.0.2.3"}]))\n'
                        'else: print(json.dumps([{"addr_info":[{"family":"inet","scope":"global","local":"10.0.3.1","prefixlen":24}]}]))\n')
                for name in ['ip', 'getent']:
                    (bin_dir / name).write_text(stub)
                    (bin_dir / name).chmod(0o700)
                jobs = [dict(providerId='p', libraryId='lib', instanceId=name, identity='id-' + name,
                             owner='fixture', hosts=['localhost'], policy='# fixture\n', documents=[
                                 dict(mount='secret', document='lib/' + name + '/accounts/db', owner='fixture',
                                      fields={'password': {'source': {'kind': 'runtime_secret_ref', 'ref': 'password-input'}}})])
                        for name in ['first', 'second']]
                provider = dict(url='https://127.0.0.1:' + str(server.server_port), routeAddress='fixture.invalid',
                                token='fixture-token', mounts={'secret/': {'type': 'kv', 'options': {'version': '2'}}})
                facts = dict(platform_application_vault_runtime={'p': provider}, platform_application_vault_values={},
                             platform_application_vault_documents={}, platform_application_vault_identities={},
                             platform_application_secret_files={'password-input': str(password_file)}, platform_application_secret_root=str(secret_root),
                             platform_application_completed_batches=[], platform_application_delivered_instances=[],
                             application_vault_inputs=dict(libraryJobs=[], instanceJobs=jobs),
                             application_runtime_inputs={'integrations': {'dependencies': {}, 'sharedDependencies': {}}})
                play = root / 'probe.yml'
                play.write_text(yaml.safe_dump([
                    dict(hosts='localhost', gather_facts=False, tasks=[{'ansible.builtin.set_fact': facts}]),
                    dict(hosts='coordinator', gather_facts=False,
                         environment={'PATH': str(bin_dir) + ':' + os.environ['PATH']},
                         tasks=[{'ansible.builtin.include_tasks': str(DELIVERY)}])], sort_keys=False))
                inventory = root / 'inventory.yml'
                inventory.write_text(yaml.safe_dump({'all': {'hosts': {
                    'localhost': {'ansible_connection': 'local'}, 'coordinator': {'ansible_connection': 'local'}}}}))
                for _ in range(2 if repeat and not foreign else 1):
                    result = subprocess.run(['ansible-playbook', '-i', str(inventory), str(play)],
                                            env=dict(os.environ, ANSIBLE_COLLECTIONS_PATH=(
                                                str(ROOT / 'ansible-core/collections') + ':' + str(ROOT / 'services/vault'))),
                                            capture_output=True, text=True, timeout=120)
                    self.assertEqual(not foreign, result.returncode == 0, (result.stdout + result.stderr)[-3000:])
                    self.assertNotIn('fixture-password', result.stdout + result.stderr)
                if foreign:
                    self.assertEqual(0, state['writes'])
                    return
                self.assertEqual(2, state['writes'])
                self.assertEqual(1 if race else 0, state['conflicts'])
                self.assertEqual(2 if repeat else 1, state['gets']['secret/data/lib/second/accounts/db'])
                self.assertEqual((2 if repeat else 1) + (1 if race else 0),
                                 state['gets']['secret/data/lib/first/accounts/db'])
                self.assertEqual(6 if repeat else 3, len((root / 'network-calls').read_text().splitlines()))
                self.assertEqual(['10.0.3.0/24', '127.0.0.1/32', '192.0.2.0/24'], state['roles']['id-first']['token_bound_cidrs'])
                if race:
                    self.assertEqual('keep', state['kv']['lib/first/accounts/db']['data']['neighbor'])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_deferred_delivery_reads_each_document_once_and_reuses_networks(self):
        self.exercise()

    def test_cas_conflict_retains_unrelated_fields_and_retries_once(self):
        self.exercise(race=True, repeat=False)

    def test_foreign_document_stops_before_any_write(self):
        self.exercise(foreign=True, repeat=False)

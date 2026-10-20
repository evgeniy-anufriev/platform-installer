"""Real Ansible URI tasks against an isolated HTTPS registry metadata fixture."""
import base64
import hashlib
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

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which('ansible-playbook') and shutil.which('openssl'), 'native Ansible/openssl required')
class ApplicationRegistryNativeTests(unittest.TestCase):
    def run_registry(self, bearer=False, corrupt=False, anonymous=False, duplicate=False, standalone=False):
        config = json.dumps(dict(os='linux', architecture='amd64', rootfs=dict(type='layers', diff_ids=[]))).encode()
        image_id = 'sha256:' + hashlib.sha256(config).hexdigest()
        manifest = json.dumps(dict(schemaVersion=2, mediaType='application/vnd.oci.image.manifest.v1+json',
                                   config=dict(digest=image_id, size=len(config)), layers=[])).encode()
        requests = []
        basic = 'Basic ' + base64.b64encode(b'sentinel-registry-login-7362:sentinel-registry-password-8362').decode()
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(self.path)
                auth = self.headers.get('Authorization')
                if self.path.startswith('/auth'):
                    self.send_response(200 if auth == basic else 401)
                    self.send_header('Content-Type', 'application/json'); self.end_headers()
                    self.wfile.write(b'{"token":"fixture-token"}'); return
                if auth != ('Bearer fixture-token' if bearer else None if anonymous else basic):
                    self.send_response(401)
                    if bearer:
                        self.send_header('WWW-Authenticate', 'Bearer realm="https://localhost:%d/auth",service="fixture"' % self.server.server_port)
                    self.end_headers(); return
                self.send_response(200)
                self.send_header('Content-Type', 'application/json'); self.end_headers()
                self.wfile.write((b'{}' if corrupt else config) if '/blobs/' in self.path else manifest)
            def log_message(self, *args):
                pass
        with tempfile.TemporaryDirectory(prefix='platform-registry-native-') as tmp:
            root = Path(tmp)
            key, ca = root / 'key.pem', root / 'ca.pem'
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=localhost',
                            '-addext', 'subjectAltName=DNS:localhost', '-days', '1', '-keyout', str(key), '-out', str(ca)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); tls.load_cert_chain(ca, key)
            server.socket = tls.wrap_socket(server.socket, server_side=True)
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            authority = 'localhost:%d' % server.server_port
            reference = authority + '/app:latest'
            pair = {name: dict(source=dict(kind='runtime_secret_ref', ref='fixture-' + name)) for name in ('username', 'password')}
            variables = dict(platform_application_approved_registries=[authority],
                platform_application_image_secret_values={'fixture-username': 'sentinel-registry-login-7362', 'fixture-password': 'sentinel-registry-password-8362'},
                platform_application_image_bundle=dict(containerImages=[], components=[]), platform_application_image_preparations={},
                application_image_input=dict(libraryId='fixture', instanceId='app-fixture', hostId='localhost', reference=reference,
                    request=dict(registry=authority, endpoint=authority, repository='app', version='latest', digest=''),
                    legacy={}, account='', configDirectory='', credentials={} if anonymous else pair))
            result_path = root / 'result.json'
            play = [dict(name='Read registry metadata with real Ansible tasks', hosts='all', gather_facts=True,
                         gather_subset=['!all', 'min'], vars=variables,
                         module_defaults={'ansible.builtin.uri': dict(ca_path=str(ca))},
                         tasks=[{'ansible.builtin.include_role': dict(name='platform.core.prepare_application_images')},
                                {'ansible.builtin.copy': dict(content='{{ platform_application_image_preparations | to_json }}', dest=str(result_path))}])]
            if duplicate:
                play[0]['tasks'].insert(1, {'ansible.builtin.include_role': dict(name='platform.core.prepare_application_images')})
            if standalone:
                play = yaml.safe_load((ROOT / 'ansible-core/playbooks/application-images-prepare.yml').read_text())
                for item in play:
                    item['module_defaults'] = {'ansible.builtin.uri': dict(ca_path=str(ca))}
                variables['platform_application_image_inputs'] = dict(
                    targetConnections={'localhost': dict(address='127.0.0.1', port=22)},
                    placements=[variables['application_image_input']], ready={})
                variables['platform_application_image_result_path'] = str(result_path)
                vars_path = root / 'vars.json'; vars_path.write_text(json.dumps(variables)); vars_path.chmod(0o600)
            play_path = root / 'play.yml'; play_path.write_text(yaml.safe_dump(play))
            environment = dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
                               ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'ansible-core/collections'))
            try:
                argv = ['ansible-playbook', '-i', 'localhost,', '-c', 'local', str(play_path)]
                if standalone:
                    argv.extend(['-vvv', '-e', '@' + str(vars_path)])
                result = subprocess.run(argv,
                                        env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=90)
            finally:
                server.shutdown(); server.server_close(); thread.join()
            if corrupt:
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(result_path.exists())
                self.assertTrue(any('/blobs/' in path for path in requests))
            else:
                self.assertEqual(result.returncode, 0, result.stdout[-4000:])
                records = json.loads(result_path.read_text())
                image = (records['placements'] if standalone else records)['fixture:app-fixture:localhost']['image']
                self.assertEqual(image['imageId'], image_id)
                self.assertEqual(image['registry']['manifestDigest'], 'sha256:' + hashlib.sha256(manifest).hexdigest())
                self.assertNotIn('archive', image)
                if duplicate:
                    self.assertEqual(sum('/manifests/' in path for path in requests), 1)
                    self.assertEqual(sum('/blobs/' in path for path in requests), 1)
            self.assertFalse(any('/layers/' in path for path in requests))
            if standalone:
                for sentinel in ('sentinel-registry-login-7362', 'sentinel-registry-password-8362', 'fixture-token', basic.split(' ', 1)[1]):
                    self.assertNotIn(sentinel, result.stdout)

    def test_target_side_basic_auth_without_docker(self):
        self.run_registry()

    def test_target_side_bearer_auth_without_docker(self):
        self.run_registry(bearer=True)

    def test_target_side_anonymous_without_docker_or_account(self):
        self.run_registry(anonymous=True)

    def test_registry_config_integrity_failure_does_not_select_fallback(self):
        self.run_registry(corrupt=True)

    def test_repeated_target_placements_reuse_the_same_registry_observation(self):
        self.run_registry(duplicate=True)

    def test_verbose_standalone_success_does_not_expose_registry_values(self):
        self.run_registry(standalone=True)

    def test_verbose_standalone_failure_does_not_expose_registry_values(self):
        self.run_registry(standalone=True, corrupt=True)

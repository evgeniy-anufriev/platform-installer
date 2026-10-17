"""Real production HTTPS target probe: address pinning, SNI and trust on one connection."""
from pathlib import Path
import http.server
import json
import os
import shutil
import ssl
import subprocess
import sys
import time
import tempfile
import threading
import unittest
import yaml

ROLE = Path(__file__).resolve().parents[1] / 'ansible_collections/platform/haproxy/roles/haproxy'


class BackendHTTPSProbeTests(unittest.TestCase):
    def test_http_diagnostics_keep_request_and_response_private(self):
        if not shutil.which('ansible-playbook'):
            self.skipTest('Native Ansible required')
        core = Path(__file__).resolve().parents[3] / 'ansible-core'
        sys.path.insert(0, str(core / 'tools'))
        from execution_lifecycle import Journal, digest
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.startswith('/timeout'):
                    time.sleep(2)
                status = 503 if self.path.startswith('/failure') else 302 if self.path.startswith('/redirect') else 200
                self.send_response(status)
                self.send_header('Set-Cookie', 'SENSITIVE_COOKIE_SENTINEL')
                self.send_header('Location', '/SENSITIVE_REDIRECT_SENTINEL')
                self.end_headers()
                try:
                    self.wfile.write(b'SENSITIVE_BODY_SENTINEL')
                except BrokenPipeError:
                    pass
            def log_message(self, *args):
                pass
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory(prefix='platform-http-probe-') as directory:
                root = Path(directory)
                cases = [('/ok', 'OK', 200, 0, None),
                         ('/failure', 'HTTP_STATUS_MISMATCH', 503, 2, None),
                         ('/redirect', 'HTTP_STATUS_MISMATCH', 302, 2, None),
                         ('/timeout', 'TIMEOUT', -1, 2, None)]
                cases += [(path, reason, status, rc, scope)
                          for path, reason, status, rc, _ in cases[:2] for scope in ('play', 'block')]
                for index, (path, reason, actual, expected_rc, suppression) in enumerate(cases):
                    backend = {'endpoint': {'fqdn': 'SENSITIVE_HOST_SENTINEL'},
                        'private_note': 'SENSITIVE_ITEM_SENTINEL', 'settings': {'ssl': False},
                        'probe': {'path': path + '?token=SENSITIVE_QUERY_SENTINEL',
                                  'expected_status': 200, 'timeout': 1},
                        'targets': [{'address': '127.0.0.1', 'port': server.server_port}]}
                    play = [{'hosts': 'localhost', 'connection': 'local', 'gather_facts': False,
                        'vars': {'platform_haproxy_application_backends': [backend]},
                        'tasks': [{'ansible.builtin.include_tasks': str(ROLE / 'tasks/check_targets.yml')}]}]
                    if suppression == 'play':
                        play[0]['no_log'] = True
                    elif suppression == 'block':
                        play[0]['tasks'] = [{'block': play[0]['tasks'], 'no_log': True}]
                    run_id = 'http-probe-%d' % index
                    journal = Journal(str(root / 'state'), run_id)
                    manifest = {'projectIdentity': 'http-probe', 'planFingerprint': 'sha256:' + 'a' * 64,
                                'runtimeRelease': {'bundleDigest': 'sha256:' + 'c' * 64}, 'operations': []}
                    journal.initialize({'runId': run_id, 'projectIdentity': 'http-probe',
                        'planFingerprint': manifest['planFingerprint'], 'manifestDigest': digest(manifest),
                        'runtimeRelease': 'sha256:' + 'c' * 64, 'unit': 'platform-installer-run-%s.service' % run_id})
                    manifest_path = Path(journal.directory) / 'manifest.json'
                    manifest_path.write_text(json.dumps(manifest))
                    manifest_path.chmod(0o600)
                    journal.transition('RUNNING', 'running')
                    env = dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(core / 'collections'),
                        ANSIBLE_CALLBACKS_ENABLED='platform.core.execution_events_json',
                        PLATFORM_EXECUTION_STATE_ROOT=str(root / 'state'), PLATFORM_EXECUTION_RUN_ID=run_id)
                    (root / 'qa.yml').write_text(yaml.safe_dump(play))
                    result = subprocess.run(['ansible-playbook', '-vvv', '-i', 'localhost,', str(root / 'qa.yml')],
                                            capture_output=True, text=True, timeout=35, env=env)
                    output = result.stdout + result.stderr
                    self.assertEqual(expected_rc, result.returncode, output)
                    diagnostic = 'expected=200; actual=%d; timeout=1s; reason=%s' % (actual, reason)
                    events = journal.events()
                    self.assertTrue(any(event['eventType'] == 'TASK_COMPLETED' for event in events), output)
                    diagnostics = [event for event in events if event['eventType'] == 'DIAGNOSTIC'
                                   and event['safeMessage'].startswith('HTTP backend ')]
                    if suppression:
                        self.assertNotIn(diagnostic, output)
                        self.assertEqual([], diagnostics)
                    else:
                        self.assertIn(diagnostic, output)
                        self.assertEqual(1, len(diagnostics), output)
                        self.assertIn(diagnostic, diagnostics[0]['safeMessage'])
                    output += json.dumps(events)
                    for secret in ('COOKIE', 'REDIRECT', 'BODY', 'HOST', 'ITEM', 'QUERY'):
                        self.assertNotIn('SENSITIVE_' + secret + '_SENTINEL', output)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_verified_sni_response_and_negative_trust_identity(self):
        if not all(shutil.which(tool) for tool in ('ansible-playbook', 'openssl', 'curl')):
            self.skipTest('Native Ansible/OpenSSL/curl required')
        with tempfile.TemporaryDirectory(prefix='platform-a6-https-') as directory:
            root = Path(directory)
            fqdn = 'apigateway-sdku.apps.test'
            for name in ('server', 'wrong'):
                subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                    '-keyout', str(root / (name + '.key')), '-out', str(root / (name + '.pem')),
                    '-days', '1', '-subj', '/CN=' + fqdn, '-addext', 'subjectAltName=DNS:' + fqdn],
                    check=True, capture_output=True)
            class Handler(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    self.send_response(200 if getattr(self.connection, 'matched_sni', False) else 421)
                    self.send_header('Content-Length', str(len(b'SENSITIVE_RESPONSE_SENTINEL')))
                    self.end_headers()
                    self.wfile.write(b'SENSITIVE_RESPONSE_SENTINEL')
                def log_message(self, *args):
                    pass
            server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(str(root / 'server.pem'), str(root / 'server.key'))
            context.set_servername_callback(lambda sock, name, ctx: setattr(sock, 'matched_sni', name == fqdn))
            server.socket = context.wrap_socket(server.socket, server_side=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for certificate, hostname, expected in [('server', fqdn, 0), ('wrong', fqdn, 2),
                                                        ('server', 'wrong.apps.test', 2)]:
                    (root / '02-ca-chain.pem').write_bytes((root / (certificate + '.pem')).read_bytes())
                    backend = {'targetDeploymentId': 'apigateway-sdku', 'endpoint': {'fqdn': hostname},
                        'expectedServerName': hostname, 'settings': {'ssl': True},
                        'probe': {'path': '/status', 'expected_status': 200, 'timeout': 3},
                        'targets': [{'address': '127.0.0.1', 'port': server.server_port, 'serverName': 'node1'}]}
                    play = [{'hosts': 'localhost', 'connection': 'local', 'gather_facts': False,
                        'vars': {'platform_haproxy_pki_directory': str(root),
                                 'platform_haproxy_application_backends': [backend]},
                        'tasks': [{'ansible.builtin.include_tasks': str(ROLE / 'tasks/check_targets.yml')}]}]
                    (root / 'qa.yml').write_text(yaml.safe_dump(play))
                    result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(root / 'qa.yml')],
                                            capture_output=True, text=True, timeout=35)
                    diagnostic = ''
                    if result.returncode != expected:
                        check = subprocess.run(['curl', '--silent', '--noproxy', '*', '--max-time', '3',
                            '--cacert', str(root / '02-ca-chain.pem'), '--resolve',
                            hostname + ':' + str(server.server_port) + ':127.0.0.1', '--output', '/dev/null',
                            '--write-out', '%{http_code}', 'https://' + hostname + ':' + str(server.server_port) + '/status'],
                            capture_output=True, text=True)
                        diagnostic = ' fixture curl rc=' + str(check.returncode) + ' status=' + check.stdout
                    self.assertEqual(expected, result.returncode, result.stdout + result.stderr + diagnostic)
                    self.assertNotIn('SENSITIVE_RESPONSE_SENTINEL', result.stdout + result.stderr)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

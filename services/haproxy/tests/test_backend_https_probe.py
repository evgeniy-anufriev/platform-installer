"""Real production HTTPS target probe: address pinning, SNI and trust on one connection."""
from pathlib import Path
import http.server
import shutil
import ssl
import subprocess
import tempfile
import threading
import unittest
import yaml

ROLE = Path(__file__).resolve().parents[1] / 'ansible_collections/platform/haproxy/roles/haproxy'


class BackendHTTPSProbeTests(unittest.TestCase):
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

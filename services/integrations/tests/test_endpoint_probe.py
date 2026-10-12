import http.server
import json
import os
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import unittest
import yaml


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
TASK_FILE = os.path.join(ROOT, "services", "integrations", "tasks", "probe-endpoint.yml")


class _StatusHandler(http.server.BaseHTTPRequestHandler):
    status_code = 200

    def do_GET(self):
        self.send_response(self.status_code)
        self.end_headers()

    def log_message(self, _format, *_args):
        return


class EndpointProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ansible_playbook = shutil.which("ansible-playbook")
        cls.openssl = shutil.which("openssl")
        if not cls.ansible_playbook or not cls.openssl:
            raise unittest.SkipTest("ansible-playbook and openssl are required for the integration probe test")

        cls.temp_dir = tempfile.TemporaryDirectory(prefix="platform-endpoint-probe-")
        cert_path = os.path.join(cls.temp_dir.name, "server.pem")
        key_path = os.path.join(cls.temp_dir.name, "server-key.pem")
        subprocess.run(
            [cls.openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes",
             "-keyout", key_path, "-out", cert_path, "-days", "1",
             "-subj", "/CN=localhost", '-addext', 'subjectAltName=DNS:localhost'],
            check=True, capture_output=True, text=True,
        )
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _StatusHandler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)
        cls.server.socket = context.wrap_socket(cls.server.socket, server_side=True)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.port = cls.server.server_address[1]
        cls.ca_path = cert_path

    def test_verified_application_external_dns_without_project_bind(self):
        with open(os.path.join(ROOT, 'services/integrations/playbooks/apply-endpoint.yml')) as stream:
            tasks = yaml.safe_load(stream)[-1]['tasks']
        tasks.insert(0, {'ansible.builtin.set_fact': {
            'platform_endpoint_probe_expected_addresses': ['127.0.0.1']}})
        play = [{'hosts': 'localhost', 'connection': 'local', 'gather_facts': False,
            'vars': {'platform_service_integration_projection': {'haproxyDeployments': ['qa-haproxy'], 'dnsDeployments': []},
                '_platform_integration_source_id': 'localhost',
                '_platform_integration_source_fqdns': ['localhost'], '_platform_integration_probe_port_override': self.port,
                '_platform_integration_probe': {'path': '/status', 'expected_status': 200, 'timeout': 3, 'validate_certs': True},
                'platform_endpoint_ca_path': self.ca_path}, 'tasks': tasks}]
        play[0]['tasks'][-1]['ansible.builtin.include_tasks'] = TASK_FILE
        path = os.path.join(self.temp_dir.name, 'external-dns.yml')
        with open(path, 'w') as stream:
            yaml.safe_dump(play, stream)
        for status, expected in [(200, 0), (503, 2)]:
            _StatusHandler.status_code = status
            result = subprocess.run([self.ansible_playbook, '-i', 'localhost,', path],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(expected, result.returncode, result.stdout + result.stderr)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "server"):
            cls.server.shutdown()
            cls.server.server_close()
            cls.server_thread.join(timeout=5)
        if hasattr(cls, "temp_dir"):
            cls.temp_dir.cleanup()

    def run_probe(self, hostname="localhost", port=None, expected_addresses=None):
        if port is None:
            port = self.port
        if expected_addresses is None:
            expected_addresses = ['127.0.0.1']
        playbook = """---
- name: Exercise the production endpoint probe tasks
  hosts: localhost
  connection: local
  gather_facts: false
  vars:
    _platform_integration_source_id: localhost
    _platform_integration_source_fqdns: [%(hostname)s]
    _platform_integration_probe_port_override: %(port)d
    platform_endpoint_probe_expected_addresses: %(addresses)s
  tasks:
    - ansible.builtin.include_tasks: %(task_file)s
""" % {
        "hostname": json.dumps(hostname),
        "addresses": json.dumps(expected_addresses),
            "port": port,
            "task_file": json.dumps(TASK_FILE.replace(os.sep, "/")),
        }
        playbook_path = os.path.join(self.temp_dir.name, "probe.yml")
        with open(playbook_path, "w", encoding="utf-8") as handle:
            handle.write(playbook)
        return subprocess.run(
            [self.ansible_playbook, "-i", "localhost,", "-c", "local", playbook_path],
            capture_output=True, text=True, timeout=30,
        )

    def test_accepts_any_http_status_except_502_and_503(self):
        for status in (200, 401, 404, 500):
            with self.subTest(status=status):
                _StatusHandler.status_code = status
                result = self.run_probe()
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rejects_gateway_error_statuses(self):
        for status in (502, 503):
            with self.subTest(status=status):
                _StatusHandler.status_code = status
                result = self.run_probe()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("SERVICE_ENDPOINT_UNAVAILABLE", result.stdout + result.stderr)

    def test_rejects_unresolvable_endpoint_name(self):
        result = self.run_probe("endpoint-does-not-exist.invalid")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SERVICE_ENDPOINT_DNS_UNRESOLVED", result.stdout + result.stderr)

    def test_rejects_resolved_endpoint_without_an_http_response(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            closed_port = sock.getsockname()[1]
        result = self.run_probe(port=closed_port)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SERVICE_ENDPOINT_UNAVAILABLE", result.stdout + result.stderr)

    def test_rejects_external_dns_that_points_away_from_expected_endpoint(self):
        result = self.run_probe(expected_addresses=['127.0.0.2'])
        self.assertNotEqual(0, result.returncode)
        self.assertIn('SERVICE_ENDPOINT_DNS_UNRESOLVED', result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

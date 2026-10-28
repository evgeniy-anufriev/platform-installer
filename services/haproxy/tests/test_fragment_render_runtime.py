"""Byte parity against ansible.builtin.template, including final newlines."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'services/haproxy/ansible_collections/platform/haproxy/roles/haproxy/templates'


class FragmentRenderRuntimeTests(unittest.TestCase):
    def test_native_batch_matches_original_frontend_and_backend_files(self):
        with tempfile.TemporaryDirectory(prefix='qa-haproxy-render-') as directory:
            root = Path(directory)
            backends = [dict(configFileName='30-backend-vault-public.cfg', backendName='vault-apps',
                            settings=dict(balance='roundrobin', ssl=True, sslVerify='required', check=True,
                                          fall=3, rise=2, timeoutConnect='2s', timeoutServer='5s', maxconn=42,
                                          checkInterval='1s', httpCheck=dict(method='GET', path='/health', expectedStatus=200)),
                            expectedServerName='vault.apps.test',
                            targets=[dict(serverName='node1', address='192.0.2.1', port=8200)]),
                        dict(configFileName='30-backend-clickhouse-public.cfg', backendName='clickhouse-apps',
                             settings=dict(balance='leastconn', ssl=False, check=False),
                             targets=[dict(serverName='node2', address='192.0.2.2', port=8123)])]
            variables = dict(platform_haproxy_application_backends=backends,
                             platform_haproxy_public_port=8443, platform_haproxy_pki_directory='/etc/qa/pki',
                             platform_desired_state={'endpointGroups': {
                                 'apps': {'address': {'domain': 'apps.example.test'}},
                                 'nested': {'address': {'domain': 'sub.apps.example.test'}}}})
            tasks = [
                {'platform.haproxy.render_fragments': {'template_path': str(TEMPLATES / 'partial-fragments.json.j2')}, 'register': 'batch'},
                {'ansible.builtin.template': {'src': str(TEMPLATES / '10-public.cfg.j2'), 'dest': str(root / '10-public.cfg')}},
                {'ansible.builtin.template': {'src': str(TEMPLATES / '30-application-backend.cfg.j2'),
                    'dest': str(root) + '/{{ item.configFileName }}'}, 'loop': '{{ platform_haproxy_application_backends }}',
                 'vars': {'platform_haproxy_application_backend': '{{ item }}'}},
                {'ansible.builtin.slurp': {'src': str(root) + '/{{ item.name }}'}, 'loop': '{{ batch.files }}', 'register': 'originals'},
                {'ansible.builtin.assert': {'that': ['(item.content | b64decode) == item.item.content']}, 'loop': '{{ originals.results }}'}]
            path = root / 'test.yml'
            path.write_text(yaml.safe_dump([dict(hosts='localhost', connection='local', gather_facts=False,
                                               vars=variables, tasks=tasks)], sort_keys=False))
            env = dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(ROOT / 'services/haproxy'))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(path)], env=env,
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(0, result.returncode, (result.stdout + result.stderr)[-4000:])

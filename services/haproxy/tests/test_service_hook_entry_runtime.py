"""Parse real Vault/ClickHouse entrypoints; observe dispatch without service mutations."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[3]


@unittest.skipUnless(shutil.which('ansible-playbook'), 'native Ansible required')
class ServiceHookEntryTests(unittest.TestCase):
    def exercise(self, service, verify=False, failed_prepare=False, empty=False):
        with tempfile.TemporaryDirectory(prefix='qa-service-hook-entry-') as folder:
            root = Path(folder)

            def write(path, value):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(yaml.safe_dump(value, sort_keys=False))

            # These production entrypoints are copied verbatim. Only their external
            # infrastructure/service side effects and resolved inputs are fixtures.
            for path in (f'services/{service}/playbooks/apply.yml',
                         'services/integrations/playbooks/apply-endpoint.yml',
                         'services/haproxy/playbooks/integrate.yml'):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / path, target)
            for path in ('ansible-core/playbooks/validate-infrastructure.yml',
                         'ansible-core/playbooks/pki-apply.yml',
                         'services/bind/playbooks/integrate.yml'):
                write(path, [dict(hosts='localhost', gather_facts=False, tasks=[])])

            provider_hosts = [] if empty else ['node1', 'node2']
            source_id = 'qa-' + service
            write('services/integrations/tasks/resolve-source.yml', [
                {'ansible.builtin.assert': {'that': [
                    "hostvars['node3'].fixture_service_applied == '" + service + "'",
                    "platform_execution_service_deployment == '" + source_id + "'"]}},
                {'ansible.builtin.set_fact': dict(
                    platform_service_integration_projection=dict(haproxyHosts=provider_hosts,
                        haproxyDeployments=['qa-proxy'] if provider_hosts else []),
                    _platform_integration_source_id=source_id,
                    platform_bind_source_dns_records=[], _platform_integration_source_fqdns=[],
                    _platform_integration_probe={})}])
            write('services/integrations/tasks/probe-endpoint.yml', [
                {'ansible.builtin.fail': {'msg': 'Unexpected external probe in dispatch fixture'}}])

            collection = 'collections/ansible_collections/platform'
            service_role = 'vault_tls' if service == 'vault' else 'clickhouse_tls'
            write(f'{collection}/{service}/roles/{service_role}/tasks/main.yml', [
                {'ansible.builtin.set_fact': {'fixture_service_applied': service}}])
            hook = f'{collection}/haproxy/roles/haproxy/tasks'
            write(hook + '/main.yml', [{'ansible.builtin.fail': {
                'msg': 'FULL_HAPROXY_MAIN_MUST_NOT_RUN'}}])
            expected_phase = dict(partial_prepare='prepare', activate='activate', partial_reload='start')
            for entry in ('partial_prepare', 'activate', 'partial_reload', 'endpoint_verify'):
                conditions = ["inventory_hostname in ['node1', 'node2']",
                              "platform_haproxy_partial_deployment_id == '" + source_id + "'"]
                if entry in expected_phase:
                    conditions.append("platform_haproxy_phase == '" + expected_phase[entry] + "'")
                if entry == 'activate':
                    conditions += ["hostvars[item].fixture_prepared | default(false)"]
                if entry == 'partial_reload':
                    conditions += ["hostvars[item].fixture_activated | default(false)"]
                if entry == 'endpoint_verify':
                    conditions += ['not (fixture_prepared | default(false))',
                                   'not (fixture_activated | default(false))']
                tasks = [{'ansible.builtin.assert': {'that': conditions}, 'loop': provider_hosts}]
                if entry == 'partial_prepare' and failed_prepare:
                    tasks.append({'ansible.builtin.fail': {'msg': 'SYNTHETIC_CANDIDATE_REJECTED'},
                                  'when': "inventory_hostname == 'node2'"})
                if entry in ('partial_prepare', 'activate'):
                    fact = 'fixture_prepared' if entry == 'partial_prepare' else 'fixture_activated'
                    tasks.append({'ansible.builtin.set_fact': {fact: True}})
                tasks.append({'ansible.builtin.copy': {'content': source_id,
                    'dest': str(root / (entry + '-{{ inventory_hostname }}'))}})
                write(hook + '/' + entry + '.yml', tasks)

            write('inventory.yml', {'all': {'vars': {'ansible_connection': 'local',
                'ansible_become': False, 'platform_execution_service_deployment': source_id,
                'platform_endpoint_verify_only': verify}, 'children': {'platform_targets': {
                    'hosts': {host: {} for host in ('node1', 'node2', 'node3')}}},
                'hosts': {'localhost': {}}}})
            result = subprocess.run(['ansible-playbook', '-i', str(root / 'inventory.yml'),
                str(root / f'services/{service}/playbooks/apply.yml')],
                env=dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(root / 'collections')),
                capture_output=True, text=True, timeout=90)
            output = result.stdout + result.stderr
            self.assertEqual(not failed_prepare, result.returncode == 0, output[-5000:])
            self.assertNotIn('FULL_HAPROXY_MAIN_MUST_NOT_RUN', output)
            observed = {p.name for p in root.iterdir() if p.is_file() and p.name != 'inventory.yml'}
            if failed_prepare:
                self.assertIn('SYNTHETIC_CANDIDATE_REJECTED', output)
                self.assertFalse(any(name.startswith(('activate-', 'partial_reload-')) for name in observed))
            else:
                phases = [] if empty else (['endpoint_verify'] if verify else list(expected_phase))
                self.assertEqual({phase + '-' + host for phase in phases for host in provider_hosts}, observed)

    def test_vault_apply_entry(self):
        self.exercise('vault')

    def test_clickhouse_apply_entry(self):
        self.exercise('clickhouse')

    def test_vault_endpoint_verify_entry(self):
        self.exercise('vault', verify=True)

    def test_clickhouse_endpoint_verify_entry(self):
        self.exercise('clickhouse', verify=True)

    def test_failed_candidate_on_one_host_blocks_all_activation(self):
        self.exercise('vault', failed_prepare=True)

    def test_empty_provider_scope_never_enters_haproxy(self):
        self.exercise('clickhouse', empty=True)

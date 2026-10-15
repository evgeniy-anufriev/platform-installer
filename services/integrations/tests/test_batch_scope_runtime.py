"""Native read-only tests of production batch projections and policy isolation."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[3]
TASKS = ROOT / 'services/integrations/tasks'
HAP = ROOT / 'services/haproxy/ansible_collections/platform/haproxy/roles/haproxy/tasks'


class BatchScopeRuntimeTests(unittest.TestCase):
    def test_production_main_guard_after_actual_scope_normalization(self):
        main = yaml.safe_load((HAP / 'main.yml').read_text())
        normalize = dict(main[0])
        normalize['ansible.builtin.include_tasks'] = str(HAP / 'partial_scope.yml')
        guard = next(task for task in main if task.get('name') ==
                     'Require valid HAProxy phase and canonical desired state')
        baseline = dict(platform_haproxy_phase='prepare', platform_desired_state={},
                        platform_deployments={}, platform_haproxy_full_reconcile=False)
        for scope in ({'platform_haproxy_partial_deployment_ids': ['app-one', 'app-two']},
                      {'platform_haproxy_partial_deployment_id': 'app-one'}, {}):
            self.run_tasks([normalize, guard], {**baseline, **scope})
        for scope in ({'platform_haproxy_partial_deployment_ids': []},
                      {'platform_haproxy_partial_deployment_id': 'app-one',
                       'platform_haproxy_partial_deployment_ids': ['app-two']}):
            self.run_tasks([normalize, guard], {**baseline, **scope}, False)

    def run_tasks(self, tasks, variables, success=True):
        if not shutil.which('ansible-playbook'):
            self.skipTest('Ansible runtime required')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.yml'
            path.write_text(yaml.safe_dump([{'hosts': 'localhost', 'connection': 'local',
                                            'gather_facts': False, 'vars': variables, 'tasks': tasks}]))
            result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(path)],
                                    capture_output=True, text=True, timeout=45)
        self.assertEqual(success, result.returncode == 0, result.stdout + result.stderr)

    def test_partial_plural_singleton_and_empty_fail_closed(self):
        tasks = yaml.safe_load((HAP / 'partial_scope.yml').read_text())
        self.run_tasks(tasks + [{'ansible.builtin.assert': {'that': ['_platform_haproxy_partial_ids == ["app-one", "app-two"]']}}],
                       {'platform_haproxy_partial_deployment_ids': ['app-two', 'app-one'], 'platform_haproxy_full_reconcile': False})
        for variables in ({'platform_haproxy_partial_deployment_ids': []},
                          {'platform_haproxy_partial_deployment_ids': ['app-one'], 'platform_haproxy_partial_deployment_id': 'app-two'},
                          {'platform_haproxy_partial_deployment_ids': ['../escape']},
                          {'platform_haproxy_partial_deployment_ids': ['app-one'], 'platform_haproxy_full_reconcile': True}):
            self.run_tasks(tasks, {'platform_haproxy_full_reconcile': False, **variables}, False)

    def test_union_preserves_provider_groups_and_detects_dns_conflicts(self):
        tasks = yaml.safe_load((TASKS / 'resolve-selected-sources.yml').read_text())[-2:]
        rows = [dict(sourceId='app-one', projection=dict(haproxyHosts=['node1'], haproxyDeployments=['hp1'], dnsDeployments=['dns1']),
                     dnsRecords=[dict(bindDeploymentId='dns1', owner='app.test.', addresses=['192.0.2.1'], ttl=60)]),
                dict(sourceId='app-two', projection=dict(haproxyHosts=['node2'], haproxyDeployments=['hp2'], dnsDeployments=['dns1']),
                     dnsRecords=[dict(bindDeploymentId='dns1', owner='other.test.', addresses=['192.0.2.2'], ttl=120)])]
        self.run_tasks(tasks + [{'ansible.builtin.assert': {'that': [
            'platform_service_integration_projection.haproxyHosts == ["node1", "node2"]',
            'platform_bind_source_dns_records | length == 2']}}], {'_platform_integration_selected_sources': rows})
        rows[1]['dnsRecords'][0]['owner'] = 'app.test.'
        self.run_tasks(tasks, {'_platform_integration_selected_sources': rows}, False)

    def test_each_sequential_probe_retains_its_own_policy(self):
        bind = yaml.safe_load((TASKS / 'probe-selected-source.yml').read_text())[0]
        first = dict(fqdns=['one.test'], probe=dict(timeout=2, expected_status=200, validate_certs=True), expectedAddresses=['192.0.2.1'])
        second = dict(fqdns=['two.test'], probe=dict(timeout=7, expected_status=204, validate_certs=False), expectedAddresses=['192.0.2.2'])
        checks = [{'ansible.builtin.assert': {'that': ['_platform_integration_probe == _platform_selected_probe.probe',
                                                      'platform_endpoint_probe_expected_addresses == _platform_selected_probe.expectedAddresses',
                                                      '_platform_integration_source_fqdns == _platform_selected_probe.fqdns']}}]
        tasks = []
        for row in (first, second):
            tasks.extend([{'ansible.builtin.set_fact': {'_platform_selected_probe': row}}, bind, checks[-1]])
        self.run_tasks(tasks, {})

import unittest
import copy
import subprocess
import tempfile
from pathlib import Path

import yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar

ROLE = Path(__file__).resolve().parents[1] / 'ansible_collections/platform/postgresql/roles/postgresql'


class ClientHBATests(unittest.TestCase):
    def test_subnet_is_tls_scram_and_follows_specific_ha_rules(self):
        template = (ROLE / 'templates/pg_hba.conf.j2').read_text(encoding='utf-8')
        variables = {'platform_postgresql_user': 'postgres',
                     'platform_postgresql_admin_superuser': {'username': 'platform_admin'},
                     'platform_postgresql_monitor_credential': {'username': 'autoctl_node'},
                     'platform_postgresql_replication_credential': {'username': 'replicator'},
                     'platform_postgresql_failover_auth': 'scram-sha-256',
                     'platform_postgresql_instances': [{'address': '192.168.56.101', 'roles': ['monitor']}],
                     '_platform_postgresql_client_subnet': '192.168.56.0/24'}
        for mode in ['standalone', 'pg_auto_failover']:
            rendered = Templar(loader=DataLoader(), variables=dict(variables, platform_postgresql_mode=mode)).template(template)
            rule = 'hostssl all all 192.168.56.0/24 scram-sha-256'
            self.assertEqual(rendered.count(rule), 1)
            self.assertNotIn('host all all 192.168.56.0/24', rendered)
            if mode == 'pg_auto_failover':
                self.assertLess(rendered.index('hostssl postgres pgautofailover_monitor'), rendered.index(rule))
                self.assertLess(rendered.index('hostssl replication replicator'), rendered.index(rule))

    def test_production_tasks_select_member_network_not_default_route_or_fixed_prefix(self):
        tasks = yaml.safe_load((ROLE / 'tasks/client_subnet.yml').read_text(encoding='utf-8'))
        primary = {'address': '192.168.56.102', 'network': '192.168.56.0', 'prefix': '24'}
        secondary = {'address': '192.168.56.111', 'network': '192.168.56.111', 'prefix': '32'}
        facts = {'interfaces': ['wan', 'lan'],
                 'all_networks': {'ipv4': ['10.2.1.10', '192.168.56.102']},
                 'default_ipv4': {'address': '10.2.1.10'},
                 'wan': {'ipv4': {'address': '10.2.1.10', 'network': '10.2.0.0', 'prefix': '16'}},
                 'lan': {'ipv4': primary, 'ipv4_secondaries': [secondary]}}
        cases = [('192.168.56.102', facts, '192.168.56.0/24', 0),
                 ('10.2.1.10', facts, '10.2.0.0/16', 0),
                 ('192.168.56.111', facts, '192.168.56.111/32', 0),
                 ('192.168.99.1', facts, None, 2)]
        ambiguous = copy.deepcopy(facts)
        ambiguous['other'] = {'ipv4': primary}
        cases.append(('192.168.56.102', ambiguous, None, 2))
        invalid = copy.deepcopy(facts)
        invalid['lan']['ipv4']['prefix'] = '24\nhost all all all trust'
        cases.append(('192.168.56.102', invalid, None, 2))
        with tempfile.TemporaryDirectory(prefix='platform-postgresql-subnet-') as directory:
            path = Path(directory) / 'test.yml'
            for address, fixture, expected, code in cases:
                with self.subTest(address=address, expected=expected):
                    selected = copy.deepcopy(tasks)
                    if expected:
                        selected.append({'ansible.builtin.assert': {'that': "_platform_postgresql_client_subnet == '" + expected + "'"}})
                    play = [{'hosts': 'localhost', 'connection': 'local', 'gather_facts': False,
                             'vars': {'ansible_facts': fixture, '_platform_postgresql_local_members': [{'address': address}]},
                             'tasks': selected}]
                    path.write_text(yaml.safe_dump(play), encoding='utf-8')
                    result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(path)],
                                            capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                    if code:
                        self.assertIn('POSTGRES_CLIENT_SUBNET_UNAVAILABLE', result.stdout)

    def test_extra_networks_preserve_tls_scram_and_do_not_duplicate_default(self):
        template = (ROLE / 'templates/pg_hba.conf.j2').read_text(encoding='utf-8')
        variables = {'platform_postgresql_user': 'postgres',
                     'platform_postgresql_admin_superuser': {'username': 'platform_admin'},
                     'platform_postgresql_mode': 'standalone',
                     '_platform_postgresql_client_subnet': '192.168.56.0/24',
                     'platform_postgresql_client_cidrs': ['10.0.3.0/24', '192.168.56.0/24', '10.0.3.0/24']}
        rendered = Templar(loader=DataLoader(), variables=variables).template(template)
        self.assertEqual(rendered.count('hostssl all all 10.0.3.0/24 scram-sha-256'), 1)
        self.assertEqual(rendered.count('hostssl all all 192.168.56.0/24 scram-sha-256'), 1)
        self.assertNotIn('host all all 10.0.3.0/24', rendered)

    def test_role_rejects_invalid_client_networks_before_mutation(self):
        task = yaml.safe_load((ROLE / 'tasks/validate.yml').read_text(encoding='utf-8'))[0]
        variables = {'platform_postgresql_mode': 'standalone',
                     'platform_postgresql_deployment_id': 'qa-postgresql',
                     'platform_postgresql_advanced_config': {},
                     'platform_postgresql_admin_superuser': {'username': 'admin', 'passwordSecretRef': 'qa-ref'},
                     'platform_postgresql_secret_files': {'qa-ref': '/private/runtime-file'}}
        cases = [([], 0), (['10.0.3.0/24'], 0), ('10.0.3.0/24', 2),
                 (['999.0.3.0/24'], 2), (['10.0.3.0/33'], 2),
                 (['10.0.3.0/24\nhost all all all trust'], 2), ([None], 2)]
        with tempfile.TemporaryDirectory(prefix='platform-postgresql-cidrs-') as directory:
            path = Path(directory) / 'test.yml'
            for cidrs, expected in cases:
                with self.subTest(cidrs=cidrs):
                    play = [{'hosts': 'localhost', 'connection': 'local', 'gather_facts': False,
                             'vars': dict(variables, platform_postgresql_client_cidrs=cidrs), 'tasks': [task]}]
                    path.write_text(yaml.safe_dump(play), encoding='utf-8')
                    result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(path)],
                                            capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, expected, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()

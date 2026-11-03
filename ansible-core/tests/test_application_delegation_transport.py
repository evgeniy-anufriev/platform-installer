"""Native routing proof without running provider commands or changing services.

Keep transport declarations from production tasks/apply blocks, replace their
payload with reading a controller-only public marker, and delegate to a closed
SSH port. Accidental local execution succeeds at reading the marker and fails
the assertion; correct SSH execution is unreachable. Local operations must
still read the marker even when their caller uses SSH.
"""
import copy
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
APPLICATIONS = ROOT / 'ansible-core/playbooks/applications'


def tasks_in(nodes):
    for node in nodes:
        yield node
        for section in ('block', 'rescue', 'always'):
            yield from tasks_in(node.get(section, []))


def load(path):
    return yaml.safe_load(path.read_text(encoding='utf-8'))


@unittest.skipUnless(shutil.which('ansible-playbook'), 'native Ansible required')
class ApplicationDelegationTransportTests(unittest.TestCase):
    def run_probes(self, cases, parent_connection='local', target_connection=None):
        with tempfile.TemporaryDirectory(prefix='application-transport-') as directory:
            work = Path(directory)
            marker = work / 'controller-only-public-marker'
            marker.write_text('public-routing-probe')
            config = work / 'ansible.cfg'
            config.write_text('[defaults]\nretry_files_enabled = False\n')
            inventory = work / 'hosts.ini'
            inventory.write_text('localhost ansible_connection=local\n'
                                 'origin ansible_host=127.0.0.1 ansible_port=1\n'
                                 'node1 ansible_host=127.0.0.1 ansible_port=1' +
                                 (' ansible_connection=' + target_connection if target_connection else '') + '\n')
            leaf = {'name': 'Read controller-only marker',
                    'ansible.builtin.slurp': {'src': str(marker)},
                    'register': 'transport_probe', 'ignore_unreachable': True}
            role = work / 'roles/transport_probe/tasks'
            role.mkdir(parents=True)
            (role / 'main.yml').write_text(yaml.safe_dump([leaf]))
            tasks = []
            for label, transport, remote, included in cases:
                if included:
                    task = {'name': label, 'ansible.builtin.include_role': {
                        'name': 'transport_probe', 'apply': transport}}
                else:
                    task = dict(copy.deepcopy(leaf), name=label, **transport)
                tasks.extend([task, {'name': 'Check routing: ' + label,
                    'ansible.builtin.assert': {'that': [
                        'transport_probe.unreachable | default(false) | bool' if remote else
                        'not (transport_probe.unreachable | default(false) | bool)',
                        'transport_probe.content is not defined' if remote else
                        "transport_probe.content | b64decode == 'public-routing-probe'"]}}])
            play = work / 'probe.yml'
            play.write_text(yaml.safe_dump([dict(hosts='origin', connection=parent_connection,
                gather_facts=False, vars=dict(application_provider_script_host='node1',
                    application_provider_script=dict(runOn='target')),
                tasks=tasks)], sort_keys=False))
            env = {key: value for key, value in os.environ.items() if not key.startswith('ANSIBLE_')}
            env.update(ANSIBLE_CONFIG=str(config), ANSIBLE_STDOUT_CALLBACK='default',
                       ANSIBLE_ROLES_PATH=str(work / 'roles'))
            result = subprocess.run(['ansible-playbook', '-i', str(inventory), str(play), '--timeout', '2'],
                env=env, capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-8000:])

    def test_remote_provider_and_image_tasks_never_read_controller_file(self):
        files = sorted((ROOT / 'services/postgresql/ansible_collections/platform/postgresql/roles/application_provider/tasks').glob('*.yml'))
        files += [ROOT / ('services/' + suffix) for suffix in (
            'vault/ansible_collections/platform/vault/roles/application_provider/tasks/networks.yml',
            'redis/ansible_collections/platform/redis/roles/application_provider/tasks/account_scope.yml',
            'clickhouse/ansible_collections/platform/clickhouse/roles/application_provider/tasks/scope.yml')]
        files += [APPLICATIONS / 'images/availability.yml', APPLICATIONS / 'tasks/provider-script.yml']
        cases = []
        for path in files:
            nodes = load(path)
            if path.name == 'availability.yml':
                nodes = nodes[0]['tasks']
            for task in tasks_in(nodes):
                if 'delegate_to' not in task:
                    continue
                # The probe isolates transport, not domain host/loop resolution.
                transport = {'delegate_to': 'node1'}
                if 'connection' in task:
                    transport['connection'] = task['connection']
                cases.append((str(path.relative_to(ROOT)) + ': ' + task.get('name', ''), transport, True, False))
        self.assertEqual(len(cases), 25)
        self.run_probes(cases)

    def test_remote_include_apply_uses_ssh(self):
        paths = [ROOT / ('services/kafka/ansible_collections/platform/kafka/roles/kafka_kraft/tasks/' + name)
                 for name in ('application_accounts.yml', 'application_topics.yml')]
        paths.append(APPLICATIONS / 'images/placement.yml')
        cases = []
        for path in paths:
            task = next(task for task in tasks_in(load(path))
                        if any('apply' in task.get(key, {}) for key in ('ansible.builtin.include_role', 'ansible.builtin.include_tasks')))
            include = task.get('ansible.builtin.include_role', task.get('ansible.builtin.include_tasks'))
            transport = copy.deepcopy(include['apply'])
            transport['delegate_to'] = 'node1'
            cases.append((str(path.relative_to(ROOT)), transport, True, True))
        script = next(task for task in tasks_in(load(APPLICATIONS / 'tasks/provider-script.yml'))
                      if 'ansible.builtin.include_role' in task)
        cases.append(('Target provider script', script['ansible.builtin.include_role']['apply'], True, True))
        default_target = copy.deepcopy(script['ansible.builtin.include_role']['apply'])
        for key, value in default_target.items():
            if isinstance(value, str):
                default_target[key] = value.replace('application_provider_script.runOn', 'application_provider_script.missing')
        cases.append(('Provider script defaults to target', default_target, True, True))
        self.run_probes(cases)

    def test_inventory_can_explicitly_select_local_connection(self):
        source = ROOT / 'services/postgresql/ansible_collections/platform/postgresql/roles/application_provider/tasks/discover.yml'
        task = next(task for task in load(source) if 'delegate_to' in task)
        self.run_probes([('Explicit inventory connection', dict(delegate_to='node1', connection=task['connection']), False, False)],
                        target_connection='local')

    def test_execution_node_scripts_and_controller_delivery_stay_local(self):
        script = next(task for task in tasks_in(load(APPLICATIONS / 'tasks/provider-script.yml'))
                      if 'ansible.builtin.include_role' in task)
        transport = copy.deepcopy(script['ansible.builtin.include_role']['apply'])
        # Bind only the existing runOn input; retain actual conditional expressions.
        for key, value in transport.items():
            if isinstance(value, str):
                transport[key] = value.replace('application_provider_script.runOn', "'execution_node'")
        cases = [('Execution Node provider script', transport, False, True)]
        for task in tasks_in(load(APPLICATIONS / 'tasks/deliver-ready.yml')):
            include = task.get('ansible.builtin.include_role', {})
            if include.get('apply', {}).get('delegate_to') == 'localhost':
                cases.append((task['name'], include['apply'], False, True))
        self.assertEqual(len(cases), 4)
        self.run_probes(cases, parent_connection='ssh')

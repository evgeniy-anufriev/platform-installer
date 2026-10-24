"""Run real project resolution and production rendering without Apply or target SSH.

Execute on the Execution Node with --project pointing at a disposable QA copy.
Only temporary files and `docker compose config` are used. No Docker daemon,
credentials, API endpoints or deployment planner are called.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[2]
ROLE = ROOT / 'ansible-core/collections/ansible_collections/platform/core/roles/application_runtime'


def production_tasks(path, names):
    tasks = yaml.safe_load(path.read_text())
    selected = [task for task in tasks if task.get('name') in names]
    if len(selected) != len(names):
        raise RuntimeError('QA_PRODUCTION_TASK_SELECTION_INVALID')
    return selected


def build_play(folder):
    names = {
        'Bind the reserved digest and template context',
        'Render allowlisted Agent configuration without secret values',
        'Bind nonsecret Agent configuration to container reconciliation digest',
        'Require the closed Agent supervisor profile and exact child command',
        'Render expected Compose and library bytes using native Ansible templates',
        'Require the shared env to remain bounded and nonsecret',
    }
    render = production_tasks(ROLE / 'tasks/preflight.yml', names)
    configs = production_tasks(ROLE / 'tasks/preflight.yml', {
        'Render declared configuration files into private memory',
        'Read declared source files without text conversion',
        'Require bounded nonsecret rendered config contents before any file write',
    })
    for task in configs:
        if task.get('ansible.builtin.include_tasks') == 'source_config.yml':
            task['ansible.builtin.include_tasks'] = str(ROLE / 'tasks/source_config.yml')
    check = production_tasks(ROLE / 'tasks/apply_instance.yml', {
        'Parse effective Compose without startup or image mutation',
        'Check only Core-projected Compose values',
    })
    initial = {'name': 'QA Bind isolated paths to the real runtime job', 'ansible.builtin.set_fact': {
        'application_project_id': '{{ application_runtime_job.projectId }}',
        'application_name': '{{ application_runtime_job.applicationName }}',
        'application_instance_id': '{{ application_runtime_job.instanceId }}',
        'application_parameters': '{{ application_runtime_job.settings.parameters | default({}) }}',
        'application_library_path': '{{ qa_root }}/{{ inventory_hostname }}/{{ application_runtime_job.libraryId }}',
        'application_instance_path': '{{ qa_root }}/{{ inventory_hostname }}/{{ application_runtime_job.libraryId }}/{{ application_runtime_job.instanceId }}',
        'application_config_pairs': [], 'application_config_contents': [], 'application_docker_environment': {},
    }, 'no_log': True}
    materialize = [
        {'name': 'QA Create only isolated render directory', 'ansible.builtin.file': {
            'path': '{{ application_instance_path }}', 'state': 'directory', 'mode': '0700'}},
        {'name': 'QA Write rendered fixture bytes', 'ansible.builtin.copy': {
            'content': '{{ item.content }}', 'dest': '{{ item.path }}', 'mode': '0600'},
         'loop': [
             {'path': '{{ application_instance_path }}/compose.yml', 'content': '{{ application_compose_content }}'},
             {'path': '{{ application_library_path }}/{{ application_runtime_job.baseFilename }}', 'content': '{{ application_base_content }}'},
             {'path': '{{ application_library_path }}/.env', 'content': '{{ application_env_content }}'},
         ], 'no_log': True},
        {'name': 'QA Bind exact production Compose/Core check inputs', 'ansible.builtin.set_fact': {
            'application_runtime_job': "{{ application_runtime_job | combine({'instancePath': application_instance_path, 'configDigest': application_config_digest, 'dockerEnvironment': {}, 'composeArgv': ['docker', 'compose', '--project-name', application_runtime_job.placement.composeProject, '--project-directory', application_instance_path, '--env-file', application_library_path ~ '/.env', '-f', application_instance_path ~ '/compose.yml']}) }}",
        }, 'no_log': True},
    ]
    assertions = [
        {'name': 'QA Require grant Java truststore password to come from Agent', 'ansible.builtin.assert': {
            'that': [
                "'JAVA_KEYSTORE_PASSWORD' in application_agent_content",
                "'JAVA_KEYSTORE_PASSWORD' not in application_runtime_job.settings.environment",
                "application_runtime_job.settings.command[0:2] == ['/bin/sh', '/opt/application/config/start-java.sh']",
                "application_runtime_job.settings.environment.KEYCLOAK_CLIENT_ID == 'admin-cli'",
                "application_runtime_job.settings.environment.APIPROVIDER_CLIENT_ID == 'grant-access'",
                "'javax.net.ssl.trustStorePassword=$JAVA_KEYSTORE_PASSWORD' in (application_config_contents | selectattr('destination', 'equalto', 'start-java.sh') | map(attribute='content') | first | b64decode)",
            ], 'fail_msg': 'QA_JAVA_TRUSTSTORE_AGENT_BINDING_INVALID'},
         'when': "application_runtime_job.instanceId == 'grant-access'", 'no_log': True},
        {'name': 'QA Require every resolved endpoint to use its verified status resource', 'ansible.builtin.assert': {
            'that': [
                "hostvars['localhost'].platform_endpoint_sources[application_runtime_job.instanceId].probe.path == qa_probe_paths[application_runtime_job.instanceId]",
                "hostvars['localhost'].platform_endpoint_sources[application_runtime_job.instanceId].probe.expected_status == 200",
            ], 'fail_msg': 'QA_APPLICATION_ENDPOINT_PROBE_INVALID'},
         'vars': {'qa_probe_paths': {'keycloak': '/realms/master/.well-known/openid-configuration',
                                   'grant-access': '/actuator/health', 'grant-access-audit': '/',
                                   'grant-access-front': '/', 'nginx': '/server-status'}}, 'no_log': True},
        {'name': 'QA Require nginx listener to follow its effective port', 'ansible.builtin.assert': {
            'that': "('listen ' ~ (application_runtime_job.settings.ports['port-1'].container | string) ~ ' ssl') in (application_config_contents | selectattr('destination', 'equalto', 'scada-lawellet.conf') | map(attribute='content') | first)",
            'fail_msg': 'QA_NGINX_LISTENER_PORT_DIVERGED'},
         'when': "application_runtime_job.instanceId == 'nginx'", 'no_log': True},
        {'name': 'QA Require concrete Hazelcast IP addresses before process startup', 'ansible.builtin.assert': {
            'that': [
                "'${' not in application_runtime_job.settings.environment.HZ_NETWORK_PUBLICADDRESS",
                "'${' not in application_runtime_job.settings.environment.HZ_NETWORK_JOIN_TCPIP_MEMBERS",
                "application_runtime_job.settings.environment.HZ_NETWORK_PUBLICADDRESS == (hostvars[inventory_hostname].ansible_host ~ ':' ~ (application_runtime_job.settings.ports['port-2'].published | string))",
                "application_runtime_job.settings.environment.HZ_NETWORK_PORT | int == application_runtime_job.settings.ports['port-2'].container | int",
            ], 'fail_msg': 'QA_HAZELCAST_ADDRESS_UNRESOLVED'},
         'when': "application_runtime_job.instanceId == 'grant-access'", 'no_log': True},
        {'name': 'QA Require healthcheck to follow the same effective container port', 'ansible.builtin.assert': {
            'that': "('localhost:' ~ (application_runtime_job.settings.ports[qa_listener].container | string) ~ '/') in ((application_compose_config.stdout | from_json).services[application_runtime_job.instanceId].healthcheck.test | join(' '))",
            'fail_msg': 'QA_HEALTHCHECK_PORT_DIVERGED'},
         'vars': {'qa_listener': "{{ 'port-5' if application_runtime_job.instanceId == 'keycloak' else 'port-1' }}"},
         'when': "application_runtime_job.instanceId in ['keycloak', 'grant-access', 'grant-access-audit']", 'no_log': True},
        {'name': 'QA Record only nonsensitive successful render results', 'ansible.builtin.set_fact': {
            'qa_results': "{{ qa_results + [{'host': inventory_hostname, 'instance': application_runtime_job.instanceId, 'config': (application_compose_config.stdout | from_json), 'agent': application_agent_content, 'files': application_config_contents}] }}"}, 'no_log': True},
    ]
    trust_check = assertions.pop(0)
    for index, condition in enumerate(trust_check['ansible.builtin.assert']['that']):
        assertions.insert(index, {
            'name': 'QA Grant Java truststore condition ' + str(index + 1),
            'ansible.builtin.assert': {'that': condition, 'fail_msg': 'QA_JAVA_TRUSTSTORE_AGENT_BINDING_INVALID'},
            'when': trust_check['when'], 'no_log': True})
    tasks_file = folder / 'render-instance.yml'
    bind_job = {'name': 'QA Bind real resolved runtime job', 'ansible.builtin.set_fact': {
        'application_runtime_job': '{{ qa_source_job }}'}, 'no_log': True}
    tasks_file.write_text(yaml.safe_dump([bind_job, initial] + configs + render + materialize + check + assertions))
    report = folder / 'render-results.json'
    play = [
        {'import_playbook': str(ROOT / 'ansible-core/playbooks/application-libraries-resolve-runtime.yml')},
        {'hosts': 'platform_targets', 'gather_facts': False, 'become': False,
         'vars': {'qa_root': str(folder / 'render'), 'role_path': str(ROLE)},
         'tasks': [
             {'ansible.builtin.set_fact': {'qa_results': []}},
             {'ansible.builtin.include_tasks': str(tasks_file),
              'loop': "{{ hostvars['localhost'].application_runtime_inputs.jobs | selectattr('hostId', 'equalto', inventory_hostname) | list }}",
              'loop_control': {'loop_var': 'qa_source_job'}, 'no_log': True},
         ]},
        {'hosts': 'localhost', 'connection': 'local', 'gather_facts': False,
         'tasks': [{'ansible.builtin.copy': {
             'dest': str(report), 'mode': '0600',
             'content': "{{ groups['platform_targets'] | map('extract', hostvars, 'qa_results') | flatten | to_json }}"}, 'no_log': True}]},
    ]
    path = folder / 'play.yml'
    path.write_text(yaml.safe_dump(play))
    return path, report


def run(project, prepared, folder):
    play, report = build_play(folder)
    inputs = folder / 'images.json'
    inputs.write_text(json.dumps({'platform_prepared_application_images': prepared}))
    collections = [ROOT / 'ansible-core/collections'] + [p for p in (ROOT / 'services').iterdir() if (p / 'ansible_collections').is_dir()]
    command = ['ansible-playbook', '-i', str(project / 'inventory/hosts.yml'), str(play),
               '-e', '@' + str(inputs), '-e', 'ansible_connection=local',
               '-e', 'platform_project_root=' + str(project),
               '-e', 'platform_service_catalog_path=' + str(ROOT / 'examples/catalog/service-catalog.yml'),
               '-e', 'platform_contracts_root=' + str(ROOT / 'contracts')]
    result = subprocess.run(command, capture_output=True, text=True, timeout=360,
        env=dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'ansible-core/ansible.cfg'),
                 ANSIBLE_COLLECTIONS_PATH=':'.join(map(str, collections)), ANSIBLE_STDOUT_CALLBACK='default'))
    if result.returncode:
        # No arbitrary exception, rendered configuration or private stdout is emitted.
        codes = sorted(set(re.findall(r'\b(?:APPLICATION|QA)_[A-Z0-9_]+\b', result.stdout + result.stderr)))
        fatal = result.stdout.find('fatal:')
        failed = [match.group(1) for match in re.finditer(r'TASK \[([^\]\n]+)\]', result.stdout)
                  if match.start() < fatal]
        return None, {'codes': codes, 'lastTask': failed[-1] if failed else 'NATIVE_PLAY_FAILED'}
    return json.loads(report.read_text()), None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--prepared-images', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    prepared = json.loads(args.prepared_images.read_text(encoding='utf-8-sig'))
    evidence = []
    with tempfile.TemporaryDirectory(prefix='szi-native-render-') as directory:
        base = Path(directory)
        project = base / 'project'
        shutil.copytree(args.project, project, ignore=shutil.ignore_patterns('bundle', '.runtime'))
        # Explicitly test the current authored SZI packages against the supplied QA inventory.
        for kind in ('application-packages', 'library-packages'):
            shutil.copytree(ROOT / 'examples/szi' / kind, project / kind, dirs_exist_ok=True)
        cases = ('baseline', 'repeat', 'overrides', 'legacy_escaped', 'legacy_compose')
        for mode in cases:
            if mode == 'overrides':
                path = project / 'inventory/group_vars/all/platform-installer.yml'
                data = yaml.safe_load(path.read_text())
                apps = data['platform_desired_state']['applicationLibraryDeployments']['szi']['applications']
                for name, container, published in [('keycloak', 18051, 20411), ('grant-access', 18011, 28011), ('grant-access-audit', 18031, 28031), ('nginx', 28443, 30543)]:
                    apps[name].setdefault('overrides', {}).setdefault('ports', {})['port-1'] = {'container': container, 'published': published}
                apps['keycloak']['overrides']['ports']['port-5'] = {'container': 19000, 'published': 29000}
                apps['grant-access']['overrides']['ports']['port-2'] = {'container': 15701, 'published': 25701}
                path.write_text(yaml.safe_dump(data))
            elif mode.startswith('legacy_'):
                path = project / 'application-packages/grant-access/1.0.0/roles/application_grant-access/defaults/main.yml'
                data = yaml.safe_load(path.read_text())
                environment = data['platform_application_definition']['defaults']['environment']
                marker = '$$' if mode == 'legacy_escaped' else '$'
                environment['HZ_NETWORK_PUBLICADDRESS'] = marker + '{SERVER_2_IP}:25701'
                environment['HZ_NETWORK_JOIN_TCPIP_MEMBERS'] = marker + '{SERVER_2_IP}:25701,' + marker + '{SERVER_3_IP}:25701'
                path.write_text(yaml.safe_dump(data))
            folder = base / mode
            folder.mkdir()
            rows, error = run(project, prepared, folder)
            if mode.startswith('legacy_'):
                expected = ('QA Require concrete Hazelcast IP addresses before process startup'
                            if mode == 'legacy_escaped' else 'Check only Core-projected Compose values')
                if error and error['lastTask'] == expected:
                    evidence.append(dict(case=mode, status='PASS', rejectedBy=expected))
                    continue
                evidence.append(dict(case=mode, status='FAIL', codes=['QA_HISTORICAL_REGRESSION_NOT_REJECTED'],
                                     lastTask=error['lastTask'] if error else 'UNEXPECTED_SUCCESS'))
                break
            if error:
                evidence.append(dict(case=mode, status='FAIL', **error))
                break
            if len(rows) != 10 or len({(r['host'], r['instance']) for r in rows}) != 10:
                evidence.append(dict(case=mode, status='FAIL', codes=['QA_PLACEMENT_COUNT_INVALID']))
                break
            # Paths belong to the isolated fixture; normalize only those paths for repeat comparison.
            normalized = json.dumps(rows, sort_keys=True).replace(str(folder / 'render'), 'QA_RENDER_ROOT')
            if mode == 'baseline':
                baseline = normalized
            elif mode == 'repeat' and normalized != baseline:
                evidence.append(dict(case=mode, status='FAIL', codes=['QA_RENDER_REPEAT_DIVERGED']))
                break
            evidence.append(dict(case=mode, status='PASS', placements=len(rows)))
    args.report.write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence))
    return 0 if len(evidence) == len(cases) and all(row['status'] == 'PASS' for row in evidence) else 1


if __name__ == '__main__':
    raise SystemExit(main())

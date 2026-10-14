"""Explicit A9 fixture preparation only; no provider, Docker or endpoint mutations."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import yaml

ROOT = Path(__file__).resolve().parents[2]


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--release', type=Path, required=True)
    parser.add_argument('--key', required=True)
    parser.add_argument('--known-hosts', required=True)
    args = parser.parse_args()
    if args.project.exists():
        raise RuntimeError('A9_FIXTURE_ALREADY_EXISTS')
    args.project.mkdir(parents=True)
    shutil.copytree(args.baseline / 'inventory', args.project / 'inventory')
    if (args.baseline / 'project.yml').is_file():
        shutil.copyfile(args.baseline / 'project.yml', args.project / 'project.yml')
    for name in ('application-packages', 'library-packages'):
        shutil.copytree(ROOT / 'examples/valid/application-runtime' / name, args.project / name)
    group_path = args.project / 'inventory/group_vars/all/platform-installer.yml'
    group = yaml.safe_load(group_path.read_text())
    group['platform_desired_state_contract'] = 'platform.installer/project-desired-state/v3alpha1'
    desired = group['platform_desired_state']
    if desired.get('applicationLibraryDeployments'):
        raise RuntimeError('A9_EXISTING_LIBRARY_SCOPE')
    refs = {'postgres': 'qa-postgresql', 'redis': 'qa-redis', 'sentinel': 'qa-redis',
            'clickhouse': 'qa-clickhouse', 'kafka': 'qa-kafka-structure', 'vault': 'qa-vault-consumer'}
    if not set(refs.values()) | {'qa-docker'} <= set(desired['serviceDeployments']):
        raise RuntimeError('A9_BASELINE_PROVIDER_MISSING')
    pg_configuration = desired['serviceDeployments']['qa-postgresql'].setdefault('configuration', {})
    pg_configuration['clientCidrs'] = list(dict.fromkeys(pg_configuration.get('clientCidrs', []) + ['10.0.3.0/24']))
    image = 'platform-application-connection-probe:a5-qa'
    archive = args.release / 'runtime/artifacts/applications/probe.tar'
    manifest_digest = 'sha256:' + hashlib.sha256((args.release / 'manifest.yaml').read_bytes()).hexdigest()
    sha = hashlib.sha256()
    with archive.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            sha.update(chunk)
    group['platform_artifact_lock'] = {'apiVersion': 'platform.installer/artifacts/v1alpha1',
        'digest': manifest_digest, 'x-container-images': {
            'apiVersion': 'platform.installer/container-images/v1alpha1', 'images': {image: {
                'imageId': 'sha256:caa73a170e7bc73ffc6a44a37360163ceb3939f6a986abba3c867094256c0f0d',
                'platform': {'os': 'linux', 'architecture': 'amd64'}, 'archive': {
                    'ref': 'runtime/artifacts/applications/probe.tar', 'size': archive.stat().st_size,
                    'sha256': 'sha256:' + sha.hexdigest()}}}}}
    defaults_path = args.project / 'application-packages/apigateway/1.0.0/roles/application_apigateway/defaults/main.yml'
    definition = yaml.safe_load(defaults_path.read_text())['platform_application_definition']
    definition['connections'] = {alias: {'library_binding': alias,
        'purpose': 'sentinel' if alias == 'sentinel' else 'client'} for alias in refs}
    parameters = {alias: {'user': '{{ application_instance_id }}',
                         'password_ref': '{{ application_instance_id }}-' + alias + '-password'}
                  for alias in ('postgres', 'redis', 'sentinel', 'clickhouse')}
    accounts = {alias: {'mode': 'managed', 'credentials': {
        'username': {'source': {'kind': 'literal', 'value': '{{ application_parameters.' + alias + '.user }}'}},
        'password': {'source': {'kind': 'runtime_secret_ref', 'ref': '{{ application_parameters.' + alias + '.password_ref }}'}}}}
        for alias in parameters}
    accounts['postgres']['databaseRef'] = 'database'
    accounts['redis']['grants'] = {'commands': ['ping', 'get'], 'keys': ['{{ application_instance_id }}:*']}
    accounts['sentinel']['grants'] = {'commands': ['ping', 'sentinel|get-master-addr-by-name']}
    accounts['clickhouse'].update(databaseRef='analytics', grants=[{
        'databaseRef': 'analytics', 'tables': ['*'], 'privileges': ['SELECT', 'INSERT']}])
    bindings = {}
    for alias, prefix in [('postgres', 'PG'), ('redis', 'REDIS_'), ('sentinel', 'SENTINEL_'), ('clickhouse', 'CLICKHOUSE_')]:
        for field, suffix in [('username', 'USER'), ('password', 'PASSWORD')]:
            bindings[prefix + suffix] = {'source': {'account': alias, 'field': field}}
    bindings.update(PROBE_VAULT_MARKER={'source': {'account': 'postgres', 'field': 'username'}},
                    PROBE_KEYSTORE_PASSWORD={'source': {'library_secret': 'java_keystore_password'}},
                    PROBE_TRUSTSTORE_PASSWORD={'source': {'library_secret': 'java_keystore_password'}})
    definition['defaults'].update(image=image, command=['/usr/bin/connection-probe'], user='1000:1000',
        parameters=parameters, accounts=accounts, config_files=[], environment={
            'PROBE_PORT': '8080', 'PROBE_KEYSTORE_PKCS12': '/opt/application/pki/keystore.p12',
            'PROBE_TRUSTSTORE_PKCS12': '/opt/application/pki/truststore.p12'},
        provisioner={'type': 'vault-agent', 'mode': 'process-supervisor', 'auth': {'method': 'approle'},
                     'approle': {'bind_secret_id': False}, 'secrets': {'mount': 'secret'}, 'secret_bindings': bindings})
    write(defaults_path, {'platform_application_definition': definition})
    app = defaults_path.parents[3]
    package_path = app / 'application.yml'
    package = yaml.safe_load(package_path.read_text())
    agent = 'roles/application_apigateway/templates/agent.hcl'
    package['files'].append(agent)
    package['render']['agent_template'] = agent
    write(package_path, package)
    (app / agent).write_text('{{ application_runtime | platform.core.application_agent_config }}\n')
    compose = app / package['render']['compose_template']
    content = compose.read_text().replace('entrypoint: {{ application_effective.command | to_json }}',
        'entrypoint: ["/usr/bin/vault", "agent", "-config=/opt/vault/agent.hcl"]')
    content = content[:content.index('    volumes:')] + '''    tmpfs:
      - /run/probe:uid=1000,gid=1000,mode=0700
    volumes:
      - {{ (application_runtime.vault_path ~ ':/opt/vault:ro') | to_json }}
      - {{ (application_runtime.pki_path ~ ':/opt/application/pki:ro') | to_json }}
'''
    compose.write_text(content)
    base = '''services:
  base:
    environment:
      REQUEST_TIMEOUT_MS: ${REQUEST_TIMEOUT_MS}
      SERVER_ID: ${SERVER_ID}
      PGHOST: {{ library_runtime.connections.postgres.targets[0].address | to_json }}
      PGPORT: {{ library_runtime.connections.postgres.targets[0].port | string | to_json }}
      REDIS_HOST: {{ library_runtime.connections.redis.targets[0].address | to_json }}
      REDIS_PORT: {{ library_runtime.connections.redis.targets[0].port | string | to_json }}
      REDIS_TARGETS: {{ (library_runtime.connections.redis.targets | map(attribute='address') | zip(library_runtime.connections.redis.targets | map(attribute='port') | map('string')) | map('join', ':') | join(',')) | to_json }}
      SENTINEL_HOST: {{ library_runtime.connections.sentinel.targets[0].address | to_json }}
      SENTINEL_PORT: {{ library_runtime.connections.sentinel.targets[0].port | string | to_json }}
      SENTINEL_MASTER_NAME: {{ library_runtime.connections.sentinel.masterName | to_json }}
      CLICKHOUSE_URL: {{ ('https://' ~ library_runtime.connections.clickhouse.targets[0].address ~ ':' ~ library_runtime.connections.clickhouse.targets[0].port) | to_json }}
      KAFKA_TARGETS: {{ (library_runtime.connections.kafka.targets | map(attribute='address') | zip(library_runtime.connections.kafka.targets | map(attribute='port') | map('string')) | map('join', ':') | join(',')) | to_json }}
'''
    # The full-services Kafka baseline has brokers/controllers, without Registry.
    # Keep that existing scope explicit when newer role defaults enable Registry.
    desired['serviceDeployments']['qa-kafka-structure'].setdefault('configuration', {})['schemaRegistryEnabled'] = False
    desired['applicationLibraryDeployments'] = {}
    for index, library in enumerate(('sdku', 'cspa')):
        lib_path = args.project / ('library-packages/' + library + '/1.0.0')
        defaults = lib_path / ('roles/library_' + library + '/defaults/main.yml')
        data = yaml.safe_load(defaults.read_text())
        data['platform_library_definition']['connection_defaults'] = {'kafka': {'connectionRef': 'SSL'}}
        data['platform_library_definition']['shared_secrets'] = {'java_keystore_password': {
            'source': {'kind': 'pki_credential', 'binding': 'application_pki', 'credential': 'java_keystore_password'}}}
        write(defaults, data)
        lib_manifest = yaml.safe_load((lib_path / 'library.yml').read_text())
        (lib_path / lib_manifest['render']['base_compose_template']).write_text(base)
        desired['applicationLibraryDeployments'][library] = {
            'libraryRef': library + '@1.0.0', 'runtimeRef': 'qa-docker', 'vault_ref': {'binding': 'vault'},
            'bindings': dict({alias: {'deploymentRef': ref} for alias, ref in refs.items()},
                             application_pki={'profileRef': 'qa-tls-profile'}),
            'resources': {
                'database': {'kind': 'postgresql.database', 'mode': 'managed', 'binding': 'postgres',
                             'parameters': {'name': 'a9_' + library}},
                'analytics': {'kind': 'clickhouse.database', 'mode': 'managed', 'binding': 'clickhouse',
                              'parameters': {'name': 'a9_' + library}}},
            'applications': {'gateway': {'overrides': {
                'parameters': {alias: {'user': 'a9_' + library, 'password_ref': 'a9-' + library + '-' + alias}
                               for alias in parameters},
                'environment': {'PGDATABASE': 'a9_' + library},
                'ports': {'http': {'container': 8080, 'published': 28480 + index}},
                'endpoint': {'enabled': True, 'endpoint_group': 'qa-shared-endpoint', 'listener': 'http',
                             'protocol': 'http', 'probe': {'path': '/status', 'expected_status': 200, 'timeout': 10}}}}}}
    write(group_path, group)
    project_manifest = args.project / 'project.yml'
    if project_manifest.exists():
        metadata = yaml.safe_load(project_manifest.read_text())
        metadata['artifactLock'] = copy.deepcopy(group['platform_artifact_lock'])
        write(project_manifest, metadata)
    inventory_path = args.project / 'inventory/hosts.yml'
    inventory = yaml.safe_load(inventory_path.read_text())
    inventory['all'].setdefault('hosts', {})['localhost'] = {'ansible_connection': 'local'}
    def bind_hosts(node):
        for name, host in node.get('hosts', {}).items():
            if name in ('node1', 'node2', 'node3'):
                host.update(ansible_connection='ssh', ansible_user='platform-automation',
                            ansible_private_key_file=args.key,
                            ansible_ssh_common_args='-o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=' + shlex.quote(args.known_hosts))
        for child in node.get('children', {}).values():
            bind_hosts(child)
    bind_hosts(inventory['all'])
    write(inventory_path, inventory)
    for host in ('node1', 'node2', 'node3'):
        path = args.project / ('inventory/host_vars/' + host + '/platform-installer.yml')
        data = yaml.safe_load(path.read_text())
        data['platform_application_libraries'] = {'sdku': {}, 'cspa': {}} if host == 'node1' else {'sdku': {}} if host == 'node2' else {}
        write(path, data)
    print(json.dumps({'project': str(args.project), 'libraries': ['sdku', 'cspa'],
                      'placements': 3, 'bundleDigest': manifest_digest}))


if __name__ == '__main__':
    main()

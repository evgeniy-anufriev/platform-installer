"""Bind compact placement inputs and publish checked results in host scope."""
import hashlib
import os
import re
import stat
import subprocess
from pathlib import Path

from ansible.plugins.action import ActionBase
from ansible.plugins.filter.core import to_json
from jinja2 import Environment, TemplateError, meta, nodes
from ansible_collections.platform.core.plugins.action.bind_application_preflight_context import placement_context
from ansible_collections.platform.core.plugins.filter.application_runtime import preflight_source_jobs
from ansible_collections.platform.core.plugins.filter.artifact_source import resolve_artifact_source
from ansible_collections.platform.core.plugins.lookup.application_template import template_names
from ansible_collections.platform.core.plugins.module_utils.application_runtime import validate_agent, validate_config_contents
from ansible_collections.platform.core.plugins.modules.application_source_file import identity, read_source


RUNTIME_ROLE = Path(__file__).resolve().parents[2] / 'roles/application_runtime'


def docker_accounts(discoveries, config):
    result = {}
    for key, discovery in discoveries.items():
        uid, home, info = discovery['uid'], discovery['home'], discovery['info']
        run = f'/run/user/{uid}'
        arch = info['Architecture']
        if ('rootless' not in ' '.join(info['SecurityOptions']) or
                info['Swarm']['LocalNodeState'] != 'inactive' or
                arch not in {'x86_64', 'aarch64', 'amd64', 'arm64'}):
            raise ValueError('APPLICATION_RUNTIME_DAEMON_INVALID')
        result[discovery['account']] = {
            'application_discovery_key': key,
            'application_uid': uid, 'application_home': home,
            'application_image_platform': {
                'os': info['OSType'], 'architecture': {'x86_64': 'amd64', 'aarch64': 'arm64'}.get(arch, arch),
            },
            'application_docker_environment': {
                'HOME': home, 'XDG_RUNTIME_DIR': run, 'DOCKER_HOST': f'unix://{run}/docker.sock',
                'DOCKER_CONFIG': config or home + '/.docker',
            },
        }
    return result


def source_configs(job):
    return [row for row in job['configs'] if 'source' in row] + [
        row for directory in job.get('directoryConfigs', []) for row in directory.get('members', [])]


def archive_record(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as archive:
        before = os.fstat(archive.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError('APPLICATION_CONFIG_SOURCE_INVALID')
        digest = hashlib.sha256()
        for chunk in iter(lambda: archive.read(1024 * 1024), b''):
            digest.update(chunk)
        archive.seek(0)
        result = subprocess.run(['tar', '-tzf', '-'], stdin=archive, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, check=False)
        if result.returncode or identity(os.fstat(archive.fileno())) != identity(before):
            raise ValueError('APPLICATION_CONFIG_SOURCE_INVALID')
        return dict(identity=list(identity(before)), sha256=digest.hexdigest())


def collect_assets(jobs):
    jobs = list(jobs)
    paths = dict.fromkeys(row['path'] for job in jobs for row in source_configs(job))
    archives = dict.fromkeys(row['path'] for job in jobs for row in job.get('archiveConfigs', []))
    return dict(files={path: read_source(path, with_identity=True) for path in paths},
                archives={path: archive_record(path) for path in archives})


def isolated_config_template(source):
    if '#jinja2' in source:
        return False
    environment = Environment()
    for name in ('dict2items', 'to_json'):
        environment.filters[name] = str
    tree = environment.parse(source)
    inputs = {'inventory_hostname', 'application_parameters', 'application_name', 'application_runtime_job',
              'application_instance_id', 'application_instance_path', 'application_project_id', 'hostvars'}
    reads = {node.name for node in tree.find_all(nodes.Name) if node.ctx == 'load'}
    if ((meta.find_undeclared_variables(tree) & reads) - inputs or
            any(tree.find_all((nodes.Include, nodes.Import, nodes.FromImport, nodes.Extends))) or
            any(node.name not in {'defined', 'undefined'} for node in tree.find_all(nodes.Test)) or
            any(node.name not in {'dict2items', 'to_json', 'default', 'selectattr', 'map', 'first'}
                for node in tree.find_all(nodes.Filter))):
        return False
    controller_refs = set()
    for attribute in tree.find_all(nodes.Getattr):
        item = attribute.node
        if (attribute.attr in {'application_snapshot', 'platform_endpoint_sources'} and
                isinstance(item, nodes.Getitem) and isinstance(item.node, nodes.Name) and
                item.node.name == 'hostvars' and isinstance(item.arg, nodes.Const) and item.arg.value == 'localhost'):
            controller_refs.add(id(item.node))
    if any(node.name == 'hostvars' and id(node) not in controller_refs for node in tree.find_all(nodes.Name)):
        return False
    macros = {node.name for node in tree.find_all(nodes.Macro)}
    for call in tree.find_all(nodes.Call):
        if isinstance(call.node, nodes.Name) and call.node.name in macros | {'namespace'}:
            continue
        if not isinstance(call.node, nodes.Getattr) or call.node.attr not in {'values', 'items', 'get', 'keys', 'update'}:
            return False
    return True


def needs_native_render(jobs, rows):
    safe_by_path = {}

    def safe(path, config=False):
        key = path, config
        if key not in safe_by_path:
            try:
                text = Path(path).read_text(encoding='utf-8')
                safe_by_path[key] = isolated_config_template(text) if config else template_names(text) is not None
            except (OSError, UnicodeError, TemplateError):
                safe_by_path[key] = False
        return safe_by_path[key]

    for job, row in zip(jobs, rows):
        if (not row['env_key'] or not safe(job['appTemplate']) or
                (not row['base_key'] and not safe(job['baseTemplate'])) or
                (job['agentTemplate'] and not safe(job['agentTemplate']))):
            return True
        if any('template' in config and not safe(config['path'], config=True) for config in job['configs']):
            return True
    return False


def validate_library_projection(jobs):
    libraries = {}
    for job in jobs:
        shared = tuple(job[field] for field in ('libraryPath', 'baseContent', 'envContent'))
        if libraries.setdefault(job['libraryId'], shared) != shared:
            raise ValueError('APPLICATION_LIBRARY_HOST_PROJECTION_CONFLICT')


def asset_record(records, path):
    record = records[path]
    if list(identity(os.stat(path, follow_symlinks=False))) != record['identity']:
        raise ValueError('APPLICATION_CONFIG_SOURCE_INVALID')
    return record


def image_source(job, platform, host, probe=None):
    authority = job['authority']
    probe = probe or {}
    rc = 0 if probe.get('rc') == 0 else (
        2 if not authority['repository'].get('reference') or
        re.search('manifest unknown|no such manifest', probe.get('stderr', '')) else 1)
    source = resolve_artifact_source(authority, authority['requirement'], host, platform, probe.get('stdout', ''), rc)
    if source['source'] == 'BLOCKED':
        raise ValueError(source['reason'])
    return source


def image_sources(jobs, accounts, host):
    sources, groups = {}, {}
    for index, job in enumerate(jobs):
        platform = accounts[job['account']]['application_image_platform']
        repository = job['authority']['repository']
        if not repository.get('reference'):
            sources[str(index)] = image_source(job, platform, host)
            continue
        scope = {key: job[key] for key in ('account', 'projectId', 'libraryId', 'authority')}
        scope['registryCredentials'] = job.get('registryCredentials', {})
        key = to_json([repository, job['account'], job['projectId'], job['libraryId'],
                       scope['registryCredentials'], platform], sort_keys=True)
        group = groups.setdefault(key, dict(job=scope, indices=[]))
        group['indices'].append(index)
    return sources, list(groups.values())


class ActionModule(ActionBase):
    TRANSFERS_FILES = False
    _requires_connection = False

    def render_placement(self, values, job, row, paths, account, index):
        source = values['_application_preflight_sources'][str(index)]
        assets = values['hostvars'].raw_get('localhost')['_application_preflight_assets']
        root, instance = paths['root'], paths['instance_path']
        archive_path = None
        if source['source'] == 'OFFLINE_BUNDLE':
            archive_path = values.get('platform_execution_bundle_root', '').rstrip('/') + '/' + job['authority']['offlineBundle']['ref']
        configs, checksums = [], {}
        variables = dict(values, **account)
        variables.update(application_runtime_job=job, application_project_id=job['projectId'],
                         application_name=job['applicationName'], application_instance_id=job['instanceId'],
                         application_parameters=job['settings'].get('parameters', {}),
                         application_root=root, application_library_path=root, application_instance_path=instance,
                         application_image_source=source, application_selected_archive_path=archive_path,
                         application_config_contents=configs, application_archive_pairs=[], application_archive_checksums=checksums)
        with self._templar.set_temporary_context(available_variables=variables):
            for config in job['configs']:
                if 'template' in config:
                    variables['application_config'] = config
                    content = self._templar.template("{{ lookup('ansible.builtin.template', application_config.path, convert_data=False) }}")
                    configs.append(dict(destination=config['destination'], content=content,
                                        sha256=hashlib.sha256(content.encode('utf-8')).hexdigest(),
                                        mode=config.get('mode', '0644')))
            variables.pop('application_config', None)
            for config in source_configs(job):
                path = config['path']
                record = asset_record(assets['files'], path)
                configs.append(dict(destination=config['destination'], path=path, content=record['content'],
                                    encoding=record['encoding'], sha256=record['sha256'], mode=config.get('mode', '0644')))
            for archive in job.get('archiveConfigs', []):
                checksum = asset_record(assets['archives'], archive['path'])['sha256']
                checksums[archive['destination']] = checksum
                variables['application_archive_pairs'].append([archive['destination'], checksum])
            validate_config_contents(configs)
            pairs = [[record['destination'], record['sha256']] for record in configs]
            pairs.extend(variables['application_archive_pairs'])
            pairs.sort(key=lambda pair: pair[0].lower())
            variables['application_config_pairs'] = pairs
            variables.update(placement_context(job, row['template_context'], values['inventory_hostname'], root, instance, pairs))
            agent = ''
            if job['agentTemplate']:
                agent = self._templar.template("{{ lookup('platform.core.application_template', application_runtime_job.agentTemplate) }}")
                validate_agent(agent, variables['application_runtime'])
                variables['application_config_digest'] = hashlib.sha256(
                    to_json([variables['application_config_digest'], hashlib.sha256(agent.encode('utf-8')).hexdigest()]).encode('utf-8')).hexdigest()
            variables['application_agent_content'] = agent
            compose = self._templar.template("{{ lookup('platform.core.application_template', application_runtime_job.appTemplate) }}")
            base_cache = values['_application_shared_base']
            env_cache = values['_application_shared_env']
            base_key, env_key = row['base_key'], row['env_key']
            facts = {}
            if base_key in base_cache:
                base = base_cache[base_key]
            else:
                base = self._templar.template("{{ lookup('ansible.builtin.template', application_runtime_job.baseTemplate) }}")
                if base_key:
                    facts['_application_shared_base'] = dict(base_cache, **{base_key: base})
            if env_key in env_cache:
                env = env_cache[env_key]
            else:
                env = self._templar.template("{{ lookup('ansible.builtin.template', role_path ~ '/templates/library.env.j2') }}")
                validate_config_contents([{'content': env}])
                if env_key:
                    facts['_application_shared_env'] = dict(env_cache, **{env_key: env})
        facts['_application_preflight_result_' + str(index)] = {
            'uid': account['application_uid'], 'home': account['application_home'], 'root': root,
            'instancePath': instance, 'libraryPath': root, 'dockerEnvironment': account['application_docker_environment'],
            'source': source, 'configContents': configs, 'configDigest': variables['application_config_digest'],
            'archiveChecksums': checksums, 'archivePath': archive_path, 'composeContent': compose,
            'baseContent': base, 'agentContent': agent, 'envContent': env,
            'composeArgv': ['docker', 'compose', '--project-name', job['placement']['composeProject'],
                            '--project-directory', instance, '--env-file', root + '/.env', '-f', instance + '/compose.yml'],
        }
        return facts

    def run(self, tmp=None, task_vars=None):
        values = task_vars or {}
        operation = self._task.args.get('operation')
        try:
            if operation == 'assets':
                local = values['hostvars'].raw_get('localhost')
                targets = set(values['groups'].get('platform_targets', values['groups']['all']))
                rows = [row for host, placements in local['_application_preflight_inputs'].items()
                        if host in targets for row in placements]
                jobs = preflight_source_jobs(values['hostvars'], [row['index'] for row in rows])
                # Native templates can observe facts from other placements or hosts.
                native = needs_native_render(jobs, rows)
                facts = {'_application_preflight_native': native,
                         '_application_preflight_assets': {} if native else collect_assets(jobs)}
            elif operation == 'accounts':
                accounts = docker_accounts(values['application_runtime_discoveries'],
                                           values.get('platform_application_registry_config_directory', ''))
                jobs = preflight_source_jobs(values['hostvars'], [row['index'] for row in values['application_host_jobs']])
                native = values['hostvars']['localhost']['_application_preflight_native']
                sources, groups = ({}, []) if native else image_sources(jobs, accounts, values['inventory_hostname'])
                facts = {'_application_preflight_accounts': accounts, '_application_preflight_sources': sources,
                         '_application_preflight_registry_groups': groups}
            elif operation == 'registry':
                rows = values['application_host_jobs']
                indices = values['application_registry_group']['indices']
                jobs = preflight_source_jobs(values['hostvars'], [rows[index]['index'] for index in indices])
                sources = dict(values['_application_preflight_sources'])
                for index, job in zip(indices, jobs):
                    account = values['_application_preflight_accounts'][job['account']]
                    sources[str(index)] = image_source(job, account['application_image_platform'],
                                                       values['inventory_hostname'], values['application_registry_probe'])
                facts = {'_application_preflight_sources': sources}
            elif operation == 'placements':
                facts = {}
                # Keep shared render facts visible to subsequent placements on this host.
                role_path = str(RUNTIME_ROLE)
                context = dict(values, role_path=role_path, ansible_search_path=[
                    role_path, *(path for path in values.get('ansible_search_path', []) if path != role_path),
                ])
                rows = values['application_host_jobs']
                jobs = preflight_source_jobs(values['hostvars'], [row['index'] for row in rows])
                for index, (row, raw_job) in enumerate(zip(rows, jobs)):
                    context['application_preflight_index'] = index
                    with self._templar.set_temporary_context(available_variables=context):
                        job = self._templar.template(raw_job)
                    account = values['_application_preflight_accounts'][row['account']]
                    placement = self.render_placement(context, job, row, values['_application_path_checks'][index],
                                                      account, index)
                    facts.update(placement)
                    context.update(placement)
            elif operation == 'bind':
                index = values['application_preflight_index']
                row = values['application_host_jobs'][index]
                paths = values['_application_path_checks'][index]
                job, = self._templar.template(preflight_source_jobs(values['hostvars'], [row['index']]))
                account = values['_application_preflight_accounts'][row['account']]
                if account['application_image_platform']['os'] != job['authority']['requirement']['platform']['os']:
                    raise ValueError('APPLICATION_RUNTIME_DAEMON_INVALID')
                facts = dict(account, _application_preflight_job=job,
                             _application_preflight_template_context=row['template_context'],
                             _application_base_render_key=row['base_key'], _application_env_render_key=row['env_key'],
                             application_project_id=job['projectId'], application_name=job['applicationName'],
                             application_instance_id=job['instanceId'], application_parameters=job['settings'].get('parameters', {}),
                             application_root=paths['root'], application_library_path=paths['root'],
                             application_instance_path=paths['instance_path'], application_config_contents=[],
                             application_archive_pairs=[], application_archive_checksums={})
            elif operation == 'publish':
                indices = [row['index'] for row in values['application_host_jobs']]
                jobs = preflight_source_jobs(values['hostvars'], indices)
                checked = [dict(job, **values['_application_preflight_result_' + str(index)])
                           for index, job in enumerate(jobs)]
                validate_library_projection(checked)
                facts = {
                    'platform_application_preflight_jobs': checked,
                    'application_host_offline_archives': [job['authority']['offlineBundle'] for job in checked
                                                         if job['source']['source'] == 'OFFLINE_BUNDLE'],
                }
            else:
                raise ValueError('APPLICATION_PREFLIGHT_CONTEXT_INVALID')
        except ValueError as error:
            code = str(error) if str(error) in {
                'APPLICATION_RUNTIME_DAEMON_INVALID', 'APPLICATION_LIBRARY_HOST_PROJECTION_CONFLICT',
            } else 'APPLICATION_PREFLIGHT_CONTEXT_INVALID'
            return dict(changed=False, failed=True, msg=code)
        except OSError:
            return dict(changed=False, failed=True, msg='APPLICATION_CONFIG_SOURCE_INVALID')
        except (KeyError, TypeError, AttributeError, IndexError):
            return dict(changed=False, failed=True, msg='APPLICATION_PREFLIGHT_CONTEXT_INVALID')
        return dict(changed=False, ansible_facts=facts, _ansible_facts_cacheable=False)

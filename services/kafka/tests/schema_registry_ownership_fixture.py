"""Generate isolated RED OS production-task ownership regression cases."""
import copy
import json
import sys
from pathlib import Path
import yaml


def task(name, module, arguments, **extra):
    return dict(name=name, **{module: arguments}, **extra)


def generate(workspace):
    root = Path(workspace).resolve()
    assert root.parent == Path('/var/tmp') and root.name.startswith('platform-installer-qa-')
    role = root / 'services/kafka/ansible_collections/platform/kafka/roles/kafka_kraft'
    sys.path.insert(0, str(root / 'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils'))
    from kafka_schema_registry import registry_projection
    defaults = yaml.safe_load((role / 'defaults/main.yml').read_text())
    member_tasks = yaml.safe_load((role / 'tasks/schema_registry_member.yml').read_text())
    preparation = []
    for name in ('Recheck Registry root ownership before member preparation', 'Prepare Registry-owned member directories', 'Mark each new Registry member root independently'):
        item = copy.deepcopy(next(entry for entry in member_tasks if entry.get('name') == name))
        if 'ansible.builtin.include_tasks' in item:
            item['ansible.builtin.include_tasks'] = str(role / 'tasks' / item['ansible.builtin.include_tasks'])
        preparation.append(item)
    plays = []
    cases = ('foreign-absent', 'foreign-owned', 'wrong-marker', 'marker-symlink', 'logs-symlink', 'fresh-owned-clear')
    for case in cases:
        base = root / ('ownership-' + case)
        member = dict(id='probe-1', deployment_id='sr-d01-' + case, host='node2', roles=['broker'], node_id=1901,
                      listeners={'SSL': dict(port=49094, purpose='interBroker', securityProtocol='SSL')})
        projection = registry_projection([member], name='sr-d01-guard', config_root=str(base/'config'), log_root=str(base/'logs'))
        assert not projection['findings']
        instance = projection['instances'][0]
        assert all(Path(path).is_relative_to(base) for path in instance['managed_paths'])
        logs = instance['log_directory']
        config = instance['config_directory']
        setup = [task('Require synthetic unit absent', 'ansible.builtin.stat', dict(path=instance['unit_path'], follow=False), register='unit_before'),
                 task('Refuse unrelated unit', 'ansible.builtin.assert', dict(that=['not unit_before.stat.exists'])),
                 task('Create isolated case root', 'ansible.builtin.file', dict(path=str(base), state='directory', mode='0755')),
                 task('Write neighboring sentinel', 'ansible.builtin.copy', dict(dest=str(base/'neighbor.txt'), content='preserve neighbor\n', mode='0644'))]
        if case != 'fresh-owned-clear':
            if case == 'logs-symlink':
                setup += [task('Create isolated symlink target', 'ansible.builtin.file', dict(path=str(base/'neighbor-dir'), state='directory', mode='0755')),
                          task('Create logs parent', 'ansible.builtin.file', dict(path=str(Path(logs).parent), state='directory', mode='0755')),
                          task('Create unsafe log symlink', 'ansible.builtin.file', dict(path=logs, src=str(base/'neighbor-dir'), state='link'))]
            else:
                setup += [task('Create foreign root-owned logs', 'ansible.builtin.file', dict(path=logs, state='directory', owner='root', group='root', mode='0755'))]
            setup += [task('Create harmless foreign file', 'ansible.builtin.copy', dict(dest=logs+'/foreign.txt', content='foreign test file\n', owner='root', mode='0644')),
                      task('Capture logs before operation', 'ansible.builtin.stat', dict(path=logs, follow=False), register='logs_before'),
                      task('Capture foreign file before operation', 'ansible.builtin.stat', dict(path=logs+'/foreign.txt', checksum_algorithm='sha256'), register='file_before')]
        if case == 'foreign-owned':
            setup += [task('Create owned config', 'ansible.builtin.file', dict(path=config, state='directory', owner='schema-registry', group='schema-registry', mode='0700')),
                      task('Create owned config marker', 'ansible.builtin.copy', dict(dest=config+'/ownership-marker', content=instance['ownership_marker']+'\n', owner='root', group='root', mode='0644')),
                      task('Create inert owned unit fixture', 'ansible.builtin.copy', dict(dest=instance['unit_path'], content=instance['ownership_marker']+'\n[Unit]\nDescription=SR-D01 inert QA fixture\n', owner='root', mode='0644'))]
        if case == 'wrong-marker':
            setup += [task('Create wrong ownership marker', 'ansible.builtin.copy', dict(dest=logs+'/ownership-marker', content='wrong-owner\n', owner='root', mode='0644'))]
        if case == 'marker-symlink':
            setup += [task('Create correct marker outside log root', 'ansible.builtin.copy', dict(dest=str(base/'marker-target'), content=instance['ownership_marker']+'\n', owner='root', mode='0644')),
                      task('Create unsafe ownership marker symlink', 'ansible.builtin.file', dict(path=logs+'/ownership-marker', src=str(base/'marker-target'), state='link'))]
        body = [task('Run production Registry preflight', 'ansible.builtin.include_tasks', str(role/'tasks/schema_registry_validate.yml'))]
        if case == 'fresh-owned-clear':
            body += preparation
            body += [task('Validate newly owned production roots', 'ansible.builtin.include_tasks', str(role/'tasks/schema_registry_validate.yml')),
                     task('Remove owned roots using production clear', 'ansible.builtin.include_tasks', str(role/'tasks/schema_registry_clear.yml')),
                     task('Inspect cleared roots', 'ansible.builtin.stat', dict(path='{{ item }}'), loop=instance['ownership_paths'], register='cleared'),
                     task('Require all owned roots removed', 'ansible.builtin.assert', dict(that=['not item.stat.exists']), loop='{{ cleared.results }}')]
        else:
            expected_code = 'SCHEMA_REGISTRY_PATH_UNSAFE' if case == 'logs-symlink' else 'SCHEMA_REGISTRY_DIRECTORY_OWNERSHIP_UNKNOWN_OR_REMOVAL_REQUIRED'
            refusal = "'" + expected_code + "' in (ansible_failed_result.results | default([]) | map(attribute='msg') | select('defined') | list) or ansible_failed_result.msg == '" + expected_code + "'"
            body = [dict(name='Require preflight refusal', block=body + [task('Fail if preflight accepted foreign roots', 'ansible.builtin.fail', dict(msg='OWNERSHIP_TEST_UNEXPECTED_ACCEPTANCE'))],
                         rescue=[task('Require expected ownership refusal', 'ansible.builtin.assert', dict(that=[refusal]))])]
            body += [dict(name='Require independent Clear refusal', block=[task('Invoke production clear with unsafe roots', 'ansible.builtin.include_tasks', str(role/'tasks/schema_registry_clear.yml')),
                                                                          task('Fail if clear accepted foreign roots', 'ansible.builtin.fail', dict(msg='OWNERSHIP_TEST_UNEXPECTED_CLEAR'))],
                          rescue=[task('Require expected clear refusal', 'ansible.builtin.assert', dict(that=[refusal]))]),
                     task('Inspect preserved log path', 'ansible.builtin.stat', dict(path=logs, follow=False), register='logs_after'),
                     task('Inspect preserved foreign file', 'ansible.builtin.stat', dict(path=logs+'/foreign.txt', checksum_algorithm='sha256'), register='file_after'),
                     task('Require foreign ownership permissions and content unchanged', 'ansible.builtin.assert', dict(that=['logs_before.stat.uid == logs_after.stat.uid', 'logs_before.stat.gid == logs_after.stat.gid', 'logs_before.stat.mode == logs_after.stat.mode', 'file_before.stat.checksum == file_after.stat.checksum', 'file_before.stat.mode == file_after.stat.mode', 'file_before.stat.uid == file_after.stat.uid']))]
        body += [task('Inspect neighboring sentinel', 'ansible.builtin.stat', dict(path=str(base/'neighbor.txt')), register='neighbor'),
                 task('Require neighboring fixture preserved', 'ansible.builtin.assert', dict(that=['neighbor.stat.exists'])),
                 task('Write public regression verdict', 'ansible.builtin.copy', dict(dest=str(root/('ownership-'+case+'.json')), content=json.dumps(dict(case=case, verdict='PASS', neighbor='PRESERVED'))+'\n', owner='platform-automation', mode='0644'))]
        if case == 'foreign-owned':
            body = [dict(name='Check owned config and unit with foreign logs', block=body, always=[task('Remove only inert QA-created unit', 'ansible.builtin.file', dict(path=instance['unit_path'], state='absent'))])]
        variables = dict(platform_kafka_phase='full', platform_kafka_schema_registry_enabled=True,
                         platform_kafka_schema_registry_name='sr-d01-guard', platform_kafka_schema_registry_config_directory=str(base/'config'),
                         platform_kafka_schema_registry_log_directory=str(base/'logs'), platform_kafka_clean_install=False, platform_kafka_verify_only=False,
                         platform_kafka_advanced_config={}, _platform_kafka_instances=[member], _platform_kafka_broker_instances=[member], registry_instance=instance)
        plays.append(dict(name='Ownership regression '+case, hosts='platform_targets', become=True, gather_facts=False, vars=(defaults|variables), tasks=setup+body))
    (root/'ownership-tests.yml').write_text(yaml.safe_dump(plays, sort_keys=False))
    (root/'ownership-inventory.ini').write_text('[platform_targets]\nnode2 ansible_connection=local\n')
    print('Generated six isolated production-task ownership regression cases')


if __name__ == '__main__':
    generate(sys.argv[1])

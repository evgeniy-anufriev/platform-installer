import json
import shutil
import sys
from pathlib import Path
import yaml

root = Path(sys.argv[1]).resolve()
assert root.parent == Path('/var/tmp') and root.name.startswith('platform-installer-qa-')
role = root / 'services/kafka/ansible_collections/platform/kafka/roles/kafka_kraft'
sys.path.insert(0, str(root / 'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils'))
from kafka_schema_registry import registry_projection
prepare = next(task for task in yaml.safe_load((role / 'tasks/schema_registry_member.yml').read_text())
               if task.get('name') == 'Prepare Registry-owned member directories')
plays = []
for case in ('absent-config', 'owned-config'):
    base = root / ('sr-d01-' + case)
    assert base.resolve().parent == root and base.name in ('sr-d01-absent-config', 'sr-d01-owned-config')
    if base.exists():
        shutil.rmtree(base)
    member = dict(id='probe-1', deployment_id='sr-d01-' + case, host='node2', roles=['broker'], node_id=1901,
                  listeners={'SSL': dict(port=49094, purpose='interBroker', securityProtocol='SSL')})
    projection = registry_projection([member], name='sr-d01-probe', config_root=str(base / 'config'), log_root=str(base / 'logs'))
    assert not projection['findings']
    instance = projection['instances'][0]
    assert all(Path(path).is_relative_to(base) for path in instance['managed_paths'])
    tasks = [
        dict(name='Create isolated foreign log directory', **{'ansible.builtin.file': dict(path=instance['log_directory'], state='directory', owner='root', group='root', mode='0755')}),
        dict(name='Create harmless foreign file', **{'ansible.builtin.copy': dict(dest=instance['log_directory']+'/foreign.txt', content='SR-D01 harmless QA fixture\n', mode='0644')}),
        dict(name='Create neighboring preservation sentinel', **{'ansible.builtin.copy': dict(dest=str(base/'neighbor.txt'), content='must survive\n', mode='0644')}),
        dict(name='Require absent synthetic unit', **{'ansible.builtin.stat': dict(path=instance['unit_path'], follow=False)}, register='probe_unit'),
        dict(name='Refuse to touch an existing unit', **{'ansible.builtin.assert': dict(that=['not probe_unit.stat.exists'])}),
    ]
    if case == 'owned-config':
        tasks += [dict(name='Create owned config fixture', **{'ansible.builtin.file': dict(path=instance['config_directory'], state='directory', owner='schema-registry', group='schema-registry', mode='0700')}),
                  dict(name='Create matching config ownership marker', **{'ansible.builtin.copy': dict(dest=instance['config_directory']+'/ownership-marker', content=instance['ownership_marker']+'\n', owner='root', group='root', mode='0644')})]
    tasks += [
        dict(name='Run complete production Registry preflight', **{'ansible.builtin.include_tasks': str(role/'tasks/schema_registry_validate.yml')}),
        dict(name='Record foreign logs before production preparation', **{'ansible.builtin.stat': dict(path=instance['log_directory'])}, register='logs_before'),
        prepare,
        dict(name='Record logs after production preparation', **{'ansible.builtin.stat': dict(path=instance['log_directory'])}, register='logs_after'),
        dict(name='Confirm unauthorized ownership and permissions change reproduced', **{'ansible.builtin.assert': dict(that=["logs_before.stat.pw_name == 'root'", "logs_before.stat.mode == '0755'", "logs_after.stat.pw_name == 'schema-registry'", "logs_after.stat.mode == '0700'"])}),
        dict(name='Run production clear only on isolated fixture paths', **{'ansible.builtin.include_tasks': str(role/'tasks/schema_registry_clear.yml')}),
        dict(name='Inspect foreign file after production clear', **{'ansible.builtin.stat': dict(path=instance['log_directory']+'/foreign.txt')}, register='foreign_after'),
        dict(name='Inspect neighboring fixture', **{'ansible.builtin.stat': dict(path=str(base/'neighbor.txt'))}, register='neighbor_after'),
        dict(name='Confirm foreign deletion reproduced and neighbor preserved', **{'ansible.builtin.assert': dict(that=['not foreign_after.stat.exists','neighbor_after.stat.exists'])}),
        dict(name='Write safe reproduction result', **{'ansible.builtin.copy': dict(dest=str(root/('sr-d01-'+case+'.json')), content=json.dumps(dict(case=case, preflight='PASSED_FOREIGN_LOGS', applyTask='CHANGED_FOREIGN_OWNER_AND_MODE', clearTasks='DELETED_FOREIGN_FILE', neighbor='PRESERVED'))+'\n', owner='platform-automation', mode='0644')}),
    ]
    variables = dict(platform_kafka_phase='full', platform_kafka_schema_registry_enabled=True,
                     platform_kafka_schema_registry_name='sr-d01-probe', platform_kafka_schema_registry_config_directory=str(base/'config'),
                     platform_kafka_schema_registry_log_directory=str(base/'logs'), platform_kafka_clean_install=False,
                     platform_kafka_verify_only=False, platform_kafka_advanced_config={},
                     _platform_kafka_instances=[member], _platform_kafka_broker_instances=[member], registry_instance=instance)
    plays.append(dict(name='Reproduce SR-D01 '+case, hosts='platform_targets', become=True, gather_facts=False,
                      vars=(yaml.safe_load((role/'defaults/main.yml').read_text()) | variables), tasks=tasks))
(root/'sr-d01-probe.yml').write_text(yaml.safe_dump(plays, sort_keys=False))
(root/'sr-d01-inventory.ini').write_text('[platform_targets]\nnode2 ansible_connection=local\n')
print('Generated two isolated production-task cases; no credential material involved')
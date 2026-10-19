import sys, json, pathlib, yaml
from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar
from ansible.plugins.loader import init_plugin_loader
init_plugin_loader()

root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root/'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils'))
from application_libraries import load_package, prepare, CONTRACT
from schema_validation import SchemaValidator

package_root = root/'examples/sdku'
load = lambda p: yaml.safe_load(pathlib.Path(p).read_text())
validator = SchemaValidator(str(root/'contracts'))
entries = json.loads((package_root/'import-catalog.json').read_text())
packages = {}
for entry in entries:
    try:
        p = load_package(str(package_root), entry['name']+'@'+entry['version'], entry['kind'], load, validator)
    except ValueError:
        print(json.dumps({'status':'BLOCKED','package':entry['name'],
            'reason':'Core rejected the package. No validation was skipped.'}))
        sys.exit(2)
    assert p['digest'] == entry['digest'], ('digest', entry['name'])
    packages[(entry['kind'],entry['name'])] = p
example = load(package_root/'configuration/group_vars.yml.example')
membership = load(package_root/'configuration/host_vars.yml.example')['platform_application_libraries']
prepared = prepare(str(package_root), example['platform_desired_state'], {'example-host': membership}, CONTRACT, load, str(root/'contracts'))
assert not prepared['findings'], prepared['findings']
library = packages[('library','sdku')]
common = library['definition'].get('defaults', {})
base = str(package_root/'library-packages/sdku/1.0.0'/library['render']['base_compose_template'])
rendered = []
base_contents = set()
jobs = [dict(application={'definition': {'defaults': {'ports': p['definition']['defaults'].get('ports', {})}}},
             libraryId='sdku-main', slotId=n, hostId='example-host',
             slot={'overrides': {}}, instance={'overrides': {}}, hostOverride={})
        for (kind, n), p in packages.items() if kind == 'application']
for (kind,name), package in packages.items():
    if kind != 'application': continue
    settings = package['definition']['defaults']
    params = settings.get('parameters', {})
    if not params.get('database_name'):
        params['database_name'] = 'fixture_database'
    for key,value in params.items():
        if isinstance(value, str) and (not value or 'platform_desired_state' in value):
            params[key] = 'example.invalid'
    for key,value in params.get('mount_sources', {}).items():
        if not value: params['mount_sources'][key] = '/tmp/sdku-fixture'
    variables = dict(application_name=name, application_instance_id=name+'-sdku-main', application_parameters=params,
        application_topics={'kafka': {ref: dict(resourceId=ref, name=value['name'])
                            for ref, value in library['definition']['resource_defaults']['kafka']['topics'].items()}},
        application_databases={'postgres': {ref: dict(resourceId=ref, name=value['name'])
                              for ref, value in library['definition']['resource_defaults']['postgresql']['databases'].items()},
                              'clickhouse': {'history': dict(resourceId='history', name='sdku_main')}},
        library_instance_id='sdku-main', application_job=next(j for j in jobs if j['slotId'] == name),
        _application_inputs={'jobs': jobs}, groups={'all': ['example-host']},
        hostvars={'example-host': {'ansible_host': 'example.invalid'}},
        sdku_start_commands={name:'/fixture/unavailable-command'}, application_project_id='fixture', application_config_digest='0'*64,
        application_runtime_job={'baseTemplate':base},
        library_runtime={'library_id':'sdku-main','host_id':'example-host','defaults':common,'connections':{key:{'targets':[{'hostId':'example-host','address':'example.invalid','port':12345}]} for key in library['definition'].get('connections',{})}},
        application_runtime={'image':settings['image'],'container_name':name+'-sdku-main-example-host','base_compose_path':'/tmp/.base_compose.yml','base_service':'base','vault_path':'/tmp/vault','pki_path':'/tmp/pki', 'config_path':'/tmp/config', 'connections':{key:{'targets':[{'address':'example.invalid','port':12345}]} for key in package['definition'].get('connections',{})}})
    templar=Templar(loader=DataLoader(),variables=variables)
    settings=templar.template(settings)
    env=dict(common.get('environment', {}) if library['definition']['slots'][name].get('inherit_defaults', True) else {})
    env.update(settings.get('environment',{}))
    variables.update(application_effective=settings,application_environment=env)
    templar.available_variables=variables
    path=package_root/'application-packages'/name/'1.0.0'/package['render']['compose_template']
    try:
        result=yaml.safe_load(templar.template(path.read_text()))
        shared=yaml.safe_load(templar.template(pathlib.Path(base).read_text()))
        base_contents.add(json.dumps(shared, sort_keys=True))
        service=result['services'][name+'-sdku-main']
        assert service['image']==settings['image']
        assert 'environment' in service
        for name in ('KAFKA_BOOTSTRAP_SERVERS', 'SPRING_KAFKA_BOOTSTRAP_SERVERS',
                     'REDIS_ADDRESS', 'TN_SCADA_REDIS_ADDRESS', 'SPRING_KAFKA_SCHEMA_REGISTRY_URL'):
            assert name not in service['environment'], (package['name'], name)
            assert name in shared['services']['backend']['environment'], name
        rendered.append(name)
    except Exception:
        print('RENDER_FAILED', name)
        raise
assert len(base_contents) == 1, 'Library base depends on consumer'
print(json.dumps({'packageSchemasAndDigests':len(packages),'prepareJobs':len(prepared['jobs']),'syntheticComposeRenders':len(rendered),'sharedBaseVariants':len(base_contents),'realTargetExecution':False}))

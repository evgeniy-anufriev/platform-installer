"""Actual target-free Core protocol: image override -> bundle -> prepared plan."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ansible-core/tools'))
from execution_lifecycle import Journal
import execution_protocol
sys.path.insert(0, str(ROOT / 'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils'))
from schema_validation import SchemaValidator
SPEC = importlib.util.spec_from_file_location('image_protocol_builder', ROOT / 'ansible-core/tools/build_execution_runtime_bundle.py')
BUILDER = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(BUILDER)


class SelectionRequestContractTests(unittest.TestCase):
    def test_canonical_requests_and_protocol_agree_on_project_and_phase_fields(self):
        digest = 'sha256:' + 'a' * 64
        base = dict(apiVersion=execution_protocol.SELECTION_REQUEST_VERSION, runId='installer-contract-123456',
                    runtimeRelease=dict(bundleDigest=digest, catalogDigest=digest, coreVersion='0.1.0', planningProtocol='v1alpha1'))
        selection = dict(executionMode='FULL_PROJECT', deploymentOrder=['docker'], skipInfrastructureVerify=False,
                         applicationLibraryOrder=['provider', 'consumer'], skipApplicationLibraries=['provider'])
        build = dict(base, **selection, operation='BuildDeploymentPlan', project='/var/tmp/fixture/project',
                     applicationVaultSources={}, applicationImagePreparation=digest)
        describe = dict(base, **selection, operation='PrepareApplicationImages', phase='DESCRIBE')
        prepare = dict(base, operation='PrepareApplicationImages', phase='PREPARE', inputsDigest=digest)
        validator = SchemaValidator(str(ROOT / 'contracts'))
        def check(value, valid):
            filename = 'build-deployment-plan' if value['operation'] == 'BuildDeploymentPlan' else 'prepare-application-images'
            findings = validator.validate(value, str(ROOT / ('contracts/execution-runtime/v1alpha7/' + filename + '.schema.json')))
            self.assertEqual(valid, not findings, str(findings))
            with patch('sys.stdin', io.StringIO(json.dumps(value))):
                if valid:
                    self.assertEqual(value, execution_protocol.request())
                else:
                    with self.assertRaises(execution_protocol.LifecycleError):
                        execution_protocol.request()
        for value in (build, describe, prepare):
            check(value, True)
        for invalid in (dict(build, project={}), dict(build, project=''),
                        {key: value for key, value in describe.items() if key != 'applicationLibraryOrder'},
                        dict(describe, inputsDigest=digest), dict(prepare, skipApplicationLibraries=[]),
                        {key: value for key, value in prepare.items() if key != 'inputsDigest'}):
            check(invalid, False)


@unittest.skipUnless(shutil.which('ansible-playbook'), 'native Ansible required')
class ApplicationImageProtocolTests(unittest.TestCase):
    def test_saved_image_override_plans_from_automatic_bundle_metadata_without_targets(self):
        with tempfile.TemporaryDirectory(prefix='platform-image-protocol-') as tmp:
            root = Path(tmp)
            runtime = root / 'input'; (runtime / 'artifacts').mkdir(parents=True)
            reference = 'fixture.example/app:qa'
            config = json.dumps(dict(os='linux', architecture='amd64', rootfs=dict(type='layers', diff_ids=[]))).encode()
            manifest = json.dumps([dict(Config='config.json', RepoTags=[reference], Layers=[])]).encode()
            with tarfile.open(runtime / 'artifacts/app.tar', 'w') as stream:
                for name, data in [('config.json', config), ('manifest.json', manifest)]:
                    entry = tarfile.TarInfo(name); entry.size = len(data); stream.addfile(entry, io.BytesIO(data))
            release = root / 'release'
            BUILDER.build(release, runtime, 'image-protocol-fixture', '0.1.0', ['redos:8.0:x86_64'], [(reference, 'artifacts/app.tar')])
            bundle = yaml.safe_load((release / 'manifest.yaml').read_text())
            bundle_digest = 'sha256:' + hashlib.sha256((release / 'manifest.yaml').read_bytes()).hexdigest()
            runtime_release = dict(bundleDigest=bundle_digest, catalogDigest=bundle['catalogDigest'], coreVersion=bundle['coreVersion'], planningProtocol='v1alpha1')
            state = root / 'state'; state.mkdir(mode=0o700)
            run_id = 'installer-123456789012345'
            journal = Journal(str(state), run_id)
            project = Path(journal.directory) / 'project'
            shutil.copytree(ROOT / 'examples/valid/application-runtime', project)
            variables_path = project / 'inventory/group_vars/all/platform-installer.yml'
            variables = yaml.safe_load(variables_path.read_text())
            variables['platform_artifact_lock'].pop('x-container-images')
            variables['platform_artifact_lock']['digest'] = bundle_digest
            variables['platform_application_approved_registries'] = []
            for library in variables['platform_desired_state']['applicationLibraryDeployments'].values():
                library['applications']['gateway']['overrides']['image'] = reference
            variables_path.write_text(yaml.safe_dump(variables, sort_keys=False))
            definitions = yaml.safe_load((release / 'catalog/service-catalog.yml').read_text())['definitions']
            (project / 'project.yml').write_text(yaml.safe_dump(dict(
                apiVersion='platform.installer/v2alpha1', kind='PlatformProject',
                metadata=dict(id='application-image-qa', name='Application image QA'),
                desiredStateContract='platform.installer/project-desired-state/v2alpha1',
                artifactLock=variables['platform_artifact_lock'],
                catalogLock=dict(apiVersion='platform.installer/catalog/v1alpha1', digest=bundle['catalogDigest'],
                                 services={name: dict(definitionVersion=value['metadata']['version'], digest=value['x-definitionDigest'])
                                           for name, value in definitions.items()}))))
            command = [sys.executable, str(release / 'ansible-core/tools/execution_protocol.py'),
                       '--state-root', str(state), '--runtime-release', str(release),
                       '--controller', str(release / 'ansible-core/tools/execution_controller.py'), '--bundle-digest', bundle_digest]
            base = dict(apiVersion='platform.installer/execution-runtime/v1alpha6', runId=run_id, runtimeRelease=runtime_release)
            def call(value):
                request = dict(base, **value)
                if request['apiVersion'] == execution_protocol.SELECTION_REQUEST_VERSION and request['operation'] != 'GetCapabilities':
                    name = 'build-deployment-plan' if request['operation'] == 'BuildDeploymentPlan' else 'prepare-application-images'
                    findings = SchemaValidator(str(ROOT / 'contracts')).validate(request,
                        str(ROOT / ('contracts/execution-runtime/v1alpha7/' + name + '.schema.json')))
                    self.assertFalse(findings, str(findings))
                result = subprocess.run(command, input=json.dumps(request), text=True, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, timeout=90)
                response = json.loads(result.stdout)
                self.assertEqual(result.returncode, 0, str(response))
                return response
            description = call(dict(operation='PrepareApplicationImages', phase='DESCRIBE',
                                    executionMode='FULL_PROJECT', deploymentOrder=['docker'], skipInfrastructureVerify=False))
            self.assertEqual(description['inputs']['placements'], [])
            self.assertEqual(description['inputs']['targetConnections'], {})
            self.assertEqual(len(description['inputs']['ready']), 3)
            prepared = call(dict(operation='PrepareApplicationImages', phase='PREPARE', inputsDigest=description['inputsDigest']))
            planned = call(dict(operation='BuildDeploymentPlan', project=str(project),
                                executionMode='FULL_PROJECT', deploymentOrder=['docker'], skipInfrastructureVerify=False,
                                applicationLibraryOrder=sorted(variables['platform_desired_state']['applicationLibraryDeployments']),
                                applicationVaultSources={}, applicationImagePreparation=prepared['preparationDigest']))
            plan = planned['deploymentPlan']
            self.assertEqual(plan['apiVersion'], 'platform.installer/plan/v1alpha7')
            self.assertEqual(plan['status'], 'EXECUTABLE', str(plan.get('findings')))
            requirements = [item for item in plan['artifactRequirements'] if item.get('artifactType') == 'container-image']
            self.assertEqual(len(requirements), 3)
            self.assertEqual({item['imageId'] for item in requirements}, {'sha256:' + hashlib.sha256(config).hexdigest()})
            # Same real Core call with invocation selection, without target contacts.
            libraries = sorted(variables['platform_desired_state']['applicationLibraryDeployments'])
            base['apiVersion'] = 'platform.installer/execution-runtime/v1alpha7'
            capability = call(dict(operation='GetCapabilities'))
            self.assertEqual('platform.installer/execution-capabilities/v1alpha12', capability['apiVersion'])
            self.assertEqual('ApplicationPostInstall/v1alpha1', capability['applicationPostInstall']['protocol'])
            # Real resolver -> planner -> manifest admission with a skipped provider.
            # Provider package has its own connection callback and integration hook.
            libraries = ['sdku', 'cspa']
            provider_package = project / 'application-packages/apigateway/1.0.1'
            shutil.copytree(project / 'application-packages/apigateway/1.0.0', provider_package)
            def edit(path, update):
                data = yaml.safe_load(path.read_text()); update(data)
                path.write_text(yaml.safe_dump(data, sort_keys=False))
            edit(provider_package / 'roles/application_apigateway/defaults/main.yml',
                 lambda data: data['platform_application_definition'].update(version='1.0.1'))
            (provider_package / 'assets').mkdir()
            (provider_package / 'assets/probe.sh').write_text('#!/bin/sh\nexit 0\n')
            def scripts(data):
                data.update(apiVersion='platform.installer/application-package/v1alpha2', version='1.0.1')
                data['files'].append('assets/probe.sh')
                data['scripts'] = [dict(id=name, source='assets/probe.sh', phase=phase, execution='once',
                    secretInputs={'token': dict(valueFrom='provided_connection', name='sso', credential='token')})
                    for name, phase in [('client', 'connection_apply'), ('routes', 'integration_apply')]]
            edit(provider_package / 'application.yml', scripts)
            edit(project / 'library-packages/sdku/1.0.0/roles/library_sdku/defaults/main.yml',
                 lambda data: (data['platform_library_definition']['slots']['gateway'].update(applicationRef='apigateway@1.0.1'),
                    data['platform_library_definition'].update(provided_connections={'sso': dict(application='gateway', protocol='https',
                        credentials={'token': {'source': {'kind': 'runtime_secret_ref', 'ref': 'provider-token'}}},
                        connection_provisioner={'apply_script': 'client'})})))
            edit(project / 'library-packages/cspa/1.0.0/roles/library_cspa/defaults/main.yml',
                 lambda data: data['platform_library_definition'].update(connections={'sso': {
                     'library_binding': 'sso', 'protocol': 'https', 'purpose': 'client'}}))
            edit(project / 'application-packages/apigateway/1.0.0/roles/application_apigateway/defaults/main.yml',
                 lambda data: data['platform_application_definition'].update(connections=['sso']))
            desired = variables['platform_desired_state']
            desired['endpointGroups'] = {'apps': {'address': {'domain': 'apps.example.test', 'wildcard': False}}}
            desired['applicationLibraryDeployments']['sdku']['applications']['gateway']['overrides']['endpoint'] = {
                'enabled': True, 'listener': 'http', 'protocol': 'http', 'endpoint_group': 'apps'}
            desired['applicationLibraryDeployments']['cspa']['bindings']['sso'] = {
                'providedConnectionRef': {'libraryId': 'sdku', 'name': 'sso'}}
            variables_path.write_text(yaml.safe_dump(variables, sort_keys=False))
            selection = dict(executionMode='FULL_PROJECT', deploymentOrder=['docker'], skipInfrastructureVerify=False,
                             applicationLibraryOrder=libraries, skipApplicationLibraries=libraries[:1])
            snapshot_path = root / 'selection-snapshot.json'
            snapshot_environment = dict(os.environ, ANSIBLE_CONFIG=str(release / 'ansible-core/ansible.cfg'),
                ANSIBLE_COLLECTIONS_PATH=str(release / 'ansible-core/collections'),
                ANSIBLE_CALLBACKS_ENABLED='platform.core.project_snapshot_json',
                PLATFORM_PROJECT_SNAPSHOT_OUTPUT=str(snapshot_path))
            snapshot_result = subprocess.run(['ansible-playbook', '-i', str(project / 'inventory/hosts.yml'),
                str(release / 'ansible-core/playbooks/project-snapshot-machine.yml'),
                '-e', 'platform_project_root=' + str(project),
                '-e', 'platform_service_catalog_path=' + str(release / 'catalog/service-catalog.yml')],
                env=snapshot_environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=90)
            self.assertEqual(0, snapshot_result.returncode, 'Synthetic snapshot command failed')
            selection_snapshot = json.loads(snapshot_path.read_text())
            self.assertEqual('PASS', selection_snapshot['validation']['status'], str(selection_snapshot['validation']))
            description = call(dict(selection, operation='PrepareApplicationImages', phase='DESCRIBE'))
            self.assertTrue(all(not key.startswith(libraries[0] + '/') for key in description['inputs']['ready']))
            prepared = call(dict(operation='PrepareApplicationImages', phase='PREPARE', inputsDigest=description['inputsDigest']))
            selected = call(dict(selection, operation='BuildDeploymentPlan', project=str(project),
                                 applicationVaultSources={}, applicationImagePreparation=prepared['preparationDigest']))
            self.assertEqual('platform.installer/plan/v1alpha8', selected['deploymentPlan']['apiVersion'])
            self.assertEqual(libraries[:1], selected['deploymentPlan']['skipApplicationLibraries'])
            self.assertEqual(libraries[1:], selected['deploymentPlan']['applicationExecutionScope']['installLibraries'])
            manifest_path = Path(journal.directory) / 'manifest.json'
            selected_manifest = json.loads(manifest_path.read_text())
            requirements = selected_manifest['applicationSecretRequirements']
            self.assertTrue(requirements)
            self.assertEqual({'provider-token'}, {item['runtimeReference'] for item in requirements})
            self.assertTrue(all(item['operations'] == ['APPLICATION_LIBRARIES_APPLY'] for item in requirements))
            from execution_controller import validate_application_manifest
            validate_application_manifest(selected_manifest)
            combined_scope = json.loads(json.dumps(selected_manifest))
            combined_scope['applicationSecretRequirements'][0]['operations'] = [
                'APPLICATION_LIBRARIES_APPLY', 'APPLICATION_LIBRARIES_VERIFY']
            validate_application_manifest(combined_scope)
            for operations in (['UNKNOWN_OPERATION'], ['APPLICATION_LIBRARIES_VERIFY']):
                invalid_manifest = json.loads(json.dumps(selected_manifest))
                invalid_manifest['applicationSecretRequirements'][0]['operations'] = operations
                with self.assertRaises(Exception) as raised:
                    validate_application_manifest(invalid_manifest)
                self.assertIn('EXECUTION_MANIFEST_INVALID', str(raised.exception))
            stale = dict(selection, operation='BuildDeploymentPlan', project=str(project),
                         skipApplicationLibraries=[], applicationVaultSources={}, applicationImagePreparation=prepared['preparationDigest'])
            rejected = subprocess.run(command, input=json.dumps(dict(base, **stale)), text=True,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
            self.assertNotEqual(0, rejected.returncode)
            self.assertIn('APPLICATION_IMAGE_PREPARATION_STALE', rejected.stdout)
            self.assertNotIn('x-container-images', yaml.safe_load(variables_path.read_text())['platform_artifact_lock'])
            # A failed/stale handle never produces an alternative executable plan.
            invalid = dict(base, operation='BuildDeploymentPlan', project=str(project), executionMode='FULL_PROJECT',
                           deploymentOrder=['docker'], skipInfrastructureVerify=False, applicationVaultSources={},
                           applicationImagePreparation='sha256:' + 'f' * 64)
            rejected = subprocess.run(command, input=json.dumps(invalid), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            self.assertNotEqual(rejected.returncode, 0)

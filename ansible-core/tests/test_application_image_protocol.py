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

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ansible-core/tools'))
from execution_lifecycle import Journal
SPEC = importlib.util.spec_from_file_location('image_protocol_builder', ROOT / 'ansible-core/tools/build_execution_runtime_bundle.py')
BUILDER = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(BUILDER)


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
                result = subprocess.run(command, input=json.dumps(dict(base, **value)), text=True, stdout=subprocess.PIPE,
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
                                applicationVaultSources={}, applicationImagePreparation=prepared['preparationDigest']))
            plan = planned['deploymentPlan']
            self.assertEqual(plan['apiVersion'], 'platform.installer/plan/v1alpha7')
            self.assertEqual(plan['status'], 'EXECUTABLE', str(plan.get('findings')))
            requirements = [item for item in plan['artifactRequirements'] if item.get('artifactType') == 'container-image']
            self.assertEqual(len(requirements), 3)
            self.assertEqual({item['imageId'] for item in requirements}, {'sha256:' + hashlib.sha256(config).hexdigest()})
            self.assertNotIn('x-container-images', yaml.safe_load(variables_path.read_text())['platform_artifact_lock'])
            # A failed/stale handle never produces an alternative executable plan.
            invalid = dict(base, operation='BuildDeploymentPlan', project=str(project), executionMode='FULL_PROJECT',
                           deploymentOrder=['docker'], skipInfrastructureVerify=False, applicationVaultSources={},
                           applicationImagePreparation='sha256:' + 'f' * 64)
            rejected = subprocess.run(command, input=json.dumps(invalid), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            self.assertNotEqual(rejected.returncode, 0)

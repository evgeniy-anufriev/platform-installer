"""Native Ansible A7 acceptance on RED OS; no target mutations or credential values."""
import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import yaml

REPO = Path(__file__).resolve().parents[2]


class NativeApplicationPlanQA(unittest.TestCase):
    def test_redis_provider_reuses_infrastructure_prefix_and_override_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            playbook = Path(directory) / 'roots.yml'
            role = REPO / 'services/redis/ansible_collections/platform/redis/roles'
            plays = []
            for prefix in ('', 'platform', 'qa'):
                plays.append(dict(hosts='localhost', connection='local', gather_facts=False,
                    vars={'platform_name_prefix': prefix}, tasks=[
                        {'ansible.builtin.include_vars': {'file': str(role / 'redis_tls/defaults/main.yml')}},
                        {'ansible.builtin.set_fact': {'infrastructure_root': '{{ platform_redis_config_root }}'}},
                        {'ansible.builtin.include_vars': {'file': str(role / 'application_provider/defaults/main.yml')}},
                        {'ansible.builtin.assert': {'that': ['platform_redis_config_root == infrastructure_root']}}]))
            playbook.write_text(yaml.safe_dump(plays))
            for extra in ([], ['-e', 'platform_redis_config_root=/tmp/explicit-redis-root']):
                result = subprocess.run(['ansible-playbook', '-i', 'localhost,', str(playbook)] + extra,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
                self.assertEqual(0, result.returncode, 'Native provider/infrastructure root policy mismatch')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='a7-native-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'project'
        shutil.copytree(REPO / 'examples/valid/application-runtime', self.root)
        self.vars_path = self.root / 'inventory/group_vars/all/platform-installer.yml'
        self.variables = json.loads(self.vars_path.read_text())
        raw_catalog = yaml.safe_load((REPO / 'examples/catalog/service-catalog.yml').read_text())
        catalog = raw_catalog.get('platform_service_catalog', raw_catalog)
        self.catalog = catalog
        manifest = dict(apiVersion='platform.installer/v2alpha1', kind='PlatformProject',
                        metadata={'id': 'a7-native', 'name': 'A7 native target-free fixture'},
                        desiredStateContract='platform.installer/project-desired-state/v2alpha1',
                        catalogLock={'apiVersion': 'platform.installer/catalog/v1alpha1', 'digest': catalog['digest'], 'services': {}},
                        artifactLock=self.variables['platform_artifact_lock'])
        (self.root / 'project.yml').write_text(json.dumps(manifest))

    def run_core(self, operation):
        self.vars_path.write_text(json.dumps(self.variables))
        self.variables['platform_execution_runtime_release'] = dict(
            bundleDigest='sha256:' + 'a' * 64, coreVersion='a7-current-source',
            catalogDigest=self.catalog['digest'], planningProtocol='v1alpha1')
        self.variables['platform_execution_deployment_order'] = sorted(self.variables['platform_desired_state']['serviceDeployments'])
        self.variables['platform_execution_state_root'] = self.tmp.name
        self.vars_path.write_text(json.dumps(self.variables))
        output = Path(self.tmp.name) / (operation + '.json')
        manifest = Path(self.tmp.name) / 'private-manifest.json'
        config = dict(plan=('deployment-plan-machine.yml', 'deployment_plan_json', 'PLATFORM_DEPLOYMENT_PLAN_OUTPUT'),
                      snapshot=('project-snapshot-machine.yml', 'project_snapshot_json', 'PLATFORM_PROJECT_SNAPSHOT_OUTPUT'),
                      descriptors=('runtime-secret-descriptors.yml', 'runtime_secret_descriptors_json', 'PLATFORM_RUNTIME_SECRET_DESCRIPTORS_OUTPUT'))[operation]
        env = dict(os.environ, ANSIBLE_CONFIG=str(REPO / 'ansible-core/ansible.cfg'),
                   ANSIBLE_COLLECTIONS_PATH=str(REPO / 'ansible-core/collections'),
                   ANSIBLE_CALLBACKS_ENABLED='platform.core.' + config[1],
                   PLATFORM_EXECUTION_MANIFEST_OUTPUT=str(manifest))
        env[config[2]] = str(output)
        command = ['ansible-playbook', '-i', str(self.root / 'inventory/hosts.yml'),
                   str(REPO / 'ansible-core/playbooks' / config[0]),
                   '-e', 'platform_project_root=' + str(self.root),
                   '-e', 'platform_service_catalog_path=' + str(REPO / 'examples/catalog/service-catalog.yml')]
        completed = subprocess.run(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
        if completed.returncode:
            # Metadata-only error: never include raw resolved variables or Ansible stdout.
            self.fail('Native Core operation failed (exit %s)' % completed.returncode)
        self.assertNotIn(b'changed=1', completed.stdout)
        self.assertTrue(output.is_file(), 'Missing structured callback output')
        return json.loads(output.read_text()), manifest

    def test_native_application_plan_has_no_deferred_integration_blocker(self):
        plan, manifest = self.run_core('plan')
        self.assertEqual('platform.installer/plan/v1alpha4', plan['apiVersion'])
        self.assertNotIn('APPLICATION_COMMON_PLAN_INTEGRATION_REQUIRED', [f['code'] for f in plan['findings']])
        self.assertEqual(plan['status'] == 'EXECUTABLE', manifest.exists())
        self.assertTrue(any(r.get('artifactType') == 'container-image' for r in plan['artifactRequirements']))

    def test_native_snapshot_has_origins_and_current_image_requirement(self):
        value, _ = self.run_core('snapshot')
        self.assertEqual('PASS', value['validation']['status'])
        instance = value['applicationLibraries']['libraries']['sdku']['instances']['apigateway-sdku']
        self.assertEqual('container-image', instance['imageRequirement']['artifactType'])
        self.assertEqual('ANSIBLE', instance['placements']['node1']['origin']['resolution'])
        self.assertNotIn('DEFERRED_TO_A2_1', json.dumps(value))

    def test_native_no_secrets_or_agent_needs_no_application_inputs(self):
        value, _ = self.run_core('descriptors')
        self.assertEqual('BuildRuntimeSecretDescriptors/v1alpha3', value['apiVersion'])
        self.assertEqual([], value['applicationInputs'])

    def test_native_empty_libraries_preserves_infrastructure_snapshot(self):
        self.variables['platform_desired_state']['applicationLibraryDeployments'] = {}
        value, _ = self.run_core('snapshot')
        self.assertEqual('platform.installer/project-snapshot/v1alpha1', value['apiVersion'])
        self.assertNotIn('applicationLibraries', value)

    def test_native_empty_libraries_preserves_legacy_plan(self):
        self.variables['platform_desired_state']['applicationLibraryDeployments'] = {}
        value, _ = self.run_core('plan')
        self.assertEqual('platform.installer/plan/v1alpha2', value['apiVersion'])
        self.assertNotIn('APPLICATION_COMMON_PLAN_INTEGRATION_REQUIRED', [f['code'] for f in value['findings']])


if __name__ == '__main__':
    unittest.main()

import importlib.util
import copy
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1] / "collections" / "ansible_collections" / "platform" / "core" / "plugins" / "module_utils"
for dependency in ("kafka_identity", "identity_persistence"):
    dependency_spec = importlib.util.spec_from_file_location(dependency, ROOT / (dependency + ".py"))
    dependency_module = importlib.util.module_from_spec(dependency_spec)
    import sys
    sys.modules[dependency] = dependency_module
    dependency_spec.loader.exec_module(dependency_module)
spec = importlib.util.spec_from_file_location("managed_kafka_materialization", ROOT / "managed_kafka_materialization.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ManagedKafkaMaterializationTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('ansible-playbook'), 'Ansible runtime required')
    def test_native_playbook_uses_role_default_for_omitted_quorum_mode(self):
        repository = Path(__file__).resolve().parents[2]
        service = repository / 'services/kafka'
        source = next(p for p in yaml.safe_load((service / 'playbooks/apply.yml').read_text())
                      if p.get('name') == 'Подготовка идентификаторов кластера и узлов Kafka')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            defaults = root / 'ansible_collections/platform/kafka/roles/kafka_kraft/defaults/main.yml'
            defaults.parent.mkdir(parents=True)
            defaults.write_bytes((service / 'ansible_collections/platform/kafka/roles/kafka_kraft/defaults/main.yml').read_bytes())
            (root / 'playbooks').mkdir()
            path = root / 'hosts.yml'
            inventory = {'all': {'hosts': {
                'localhost': {'ansible_connection': 'local'},
                'node1': {'platform_deployments': {'k': {'members': {'c': {'roles': ['controller']}}}}}},
                'children': {'platform_targets': {'hosts': {'node1': {}}}}}}
            path.write_text(yaml.safe_dump(inventory))
            variables = dict(platform_desired_state={'serviceDeployments': {'k': {'serviceType': 'kafka'}}},
                platform_kafka_inventory_path=str(path), platform_generated_state_path=str(root / 'state.yml'),
                platform_project_id='p', qa_discovery={'node1': [
                    dict(deploymentId='k', memberId='c', state='UNINITIALIZED')]})
            play = copy.deepcopy(source)
            play['vars'] = variables
            play['tasks'].insert(0, {'ansible.builtin.set_fact': {
                'platform_kafka_discovery_by_host': '{{ qa_discovery }}'}})
            play_path = root / 'playbooks/probe.yml'
            for repeat in (False, True):
                play_path.write_text(yaml.safe_dump([play], sort_keys=False))
                result = subprocess.run(['ansible-playbook', '-i', str(path), str(play_path)],
                    env=dict(os.environ, ANSIBLE_COLLECTIONS_PATH=str(repository / 'ansible-core/collections')),
                    capture_output=True, text=True, timeout=60)
                self.assertEqual(0, result.returncode, (result.stdout + result.stderr)[-2000:])
                state = yaml.safe_load((root / 'state.yml').read_text())['platform_generated_state']['serviceDeployments']['k']
                self.assertEqual({}, state.get('members', {}))
                if repeat:
                    self.assertEqual(before, (root / 'state.yml').read_bytes())
                else:
                    before = (root / 'state.yml').read_bytes()
                    variables['qa_discovery']['node1'] = [dict(
                        deploymentId='k', memberId='c', state='INITIALIZED',
                        clusterId=state['identity']['clusterId'], directoryId='assigned-by-storage')]

    def test_static_fresh_then_initialized_repeat_without_state_rewrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            desired = {'serviceDeployments': {'k': {'serviceType': 'kafka'}}}
            inventory = {'all': {'hosts': {'n': {'platform_deployments': {'k': {'members': {'c': {'roles': ['controller']}}}}}}}}
            path = root / 'hosts.yml'
            state_path = root / 'platform-state.yml'
            path.write_text(yaml.safe_dump(inventory))
            fresh = {'n': [{'deploymentId': 'k', 'memberId': 'c', 'state': 'UNINITIALIZED'}]}
            first = module.materialize_ansible_kafka(desired, path, state_path, fresh, 'p',
                lambda _: b'a' * 16, default_quorum_mode='static')
            cluster = first['stateDocument']['platform_generated_state']['serviceDeployments']['k']['identity']['clusterId']
            before = state_path.read_bytes()
            observed = {'n': [{'deploymentId': 'k', 'memberId': 'c', 'state': 'INITIALIZED',
                              'clusterId': cluster, 'directoryId': 'kafka-generated'}]}
            repeated = module.materialize_ansible_kafka(desired, path, state_path, observed, 'p',
                lambda _: self.fail('repeat generated an identity'), default_quorum_mode='static')
            self.assertEqual('PASS', repeated['status'])
            self.assertFalse(repeated['changed'])
            self.assertEqual(before, state_path.read_bytes())

    def test_static_repeat_preserves_old_generated_state_and_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inventory = {'all': {'hosts': {'n': {'platform_deployments': {'k': {'members': {'c': {'roles': ['controller']}}}}}}}}
            desired = {'serviceDeployments': {'k': {'serviceType': 'kafka', 'configuration': {'quorumMode': 'static'}}}}
            path, state_path = root / 'hosts.yml', root / 'platform-state.yml'
            path.write_text(yaml.safe_dump(inventory))
            state_path.write_text(yaml.safe_dump({'platform_generated_state': {
                'apiVersion': 'platform.installer/generated-state/v1alpha1', 'kind': 'PlatformGeneratedState',
                'metadata': {'projectId': 'p'}, 'serviceDeployments': {'k': {
                    'identity': {'clusterId': 'cluster'}, 'members': {'c': {'identity': {'directoryId': 'old-generated'}}}}}}}))
            before = (path.read_bytes(), state_path.read_bytes())
            result = module.materialize_ansible_kafka(desired, path, state_path,
                {'n': [{'deploymentId': 'k', 'memberId': 'c', 'state': 'INITIALIZED', 'clusterId': 'cluster', 'directoryId': 'disk'}]}, 'p')
            self.assertEqual('PASS', result['status'])
            self.assertFalse(result['changed'])
            self.assertEqual(before, (path.read_bytes(), state_path.read_bytes()))

    def test_ansible_native_generate_persist_reload_and_noop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            desired = {"serviceDeployments": {"k": {"serviceType": "kafka", "identity": {}}}}
            inventory = {"all": {"hosts": {"n": {"platform_deployments": {"k": {"members": {"c": {"roles": ["controller"], "configuration": {"nodeId": 1}}}}}}}}}
            (root / "hosts.yml").write_text(yaml.safe_dump(inventory, sort_keys=False), encoding="utf-8")
            group_vars = root / "group_vars" / "all"
            host_vars = root / "host_vars"
            group_vars.mkdir(parents=True)
            host_vars.mkdir()
            opaque_group = group_vars / "custom.yml"
            opaque_host = host_vars / "n.yml"
            opaque_group.write_text("company_custom: '{{ untouched }}'\n", encoding="utf-8")
            opaque_host.write_text("host_custom:\n  nested: true\n", encoding="utf-8")
            opaque_before = (opaque_group.read_bytes(), opaque_host.read_bytes())
            discovery = {"n": [{"deploymentId": "k", "memberId": "c", "state": "UNINITIALIZED"}]}
            values = iter([b"a" * 16, b"b" * 16])
            first = module.materialize_ansible_kafka(desired, root / "hosts.yml", root / "platform-state.yml", discovery, "p", lambda _: next(values))
            self.assertTrue(first["changed"])
            state = first["stateDocument"]["platform_generated_state"]
            self.assertIn("clusterId", state["serviceDeployments"]["k"]["identity"])
            self.assertIn("directoryId", state["serviceDeployments"]["k"]["members"]["c"]["identity"])
            before = (root / "hosts.yml").read_bytes()
            second = module.materialize_ansible_kafka(desired, root / "hosts.yml", root / "platform-state.yml", discovery, "p", lambda _: (_ for _ in ()).throw(AssertionError("regenerated")))
            self.assertFalse(second["changed"])
            self.assertEqual(before, (root / "hosts.yml").read_bytes())
            self.assertEqual(opaque_before, (opaque_group.read_bytes(), opaque_host.read_bytes()))

    def test_ansible_native_materialization_reads_canonical_host_vars_members(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            desired = {"serviceDeployments": {"k": {"serviceType": "kafka", "identity": {}}}}
            inventory = {"all": {"hosts": {"n": {"ansible_host": "192.0.2.10"}}}}
            (root / "hosts.yml").write_text(yaml.safe_dump(inventory, sort_keys=False), encoding="utf-8")
            host_vars = root / "host_vars" / "n"
            host_vars.mkdir(parents=True)
            (host_vars / "platform-installer.yml").write_text(yaml.safe_dump({
                "platform_deployments": {"k": {"members": {"c": {"roles": ["controller"], "configuration": {"nodeId": 1}}}}}
            }, sort_keys=False), encoding="utf-8")
            result = module.materialize_ansible_kafka(
                desired,
                root / "hosts.yml",
                root / "platform-state.yml",
                {"n": [{"deploymentId": "k", "memberId": "c", "state": "UNINITIALIZED"}]},
                "p",
                lambda _: b"a" * 16,
            )
            self.assertTrue(result["changed"])
            state = result["stateDocument"]["platform_generated_state"]
            self.assertIn("directoryId", state["serviceDeployments"]["k"]["members"]["c"]["identity"])

    def test_installer_managed_host_document_precedes_legacy_flat_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            desired = {"serviceDeployments": {"k": {"serviceType": "kafka", "identity": {}}}}
            inventory = {"all": {"hosts": {"n": {"ansible_host": "192.0.2.10"}}}}
            (root / "hosts.yml").write_text(yaml.safe_dump(inventory, sort_keys=False), encoding="utf-8")
            host_vars = root / "host_vars"
            managed = host_vars / "n"
            managed.mkdir(parents=True)
            (host_vars / "n.yml").write_text(yaml.safe_dump({
                "platform_deployments": {"k": {"members": {"legacy": {"roles": ["controller"]}}}}
            }, sort_keys=False), encoding="utf-8")
            (managed / "platform-installer.yml").write_text(yaml.safe_dump({
                "platform_deployments": {"k": {"members": {"managed": {"roles": ["controller"], "configuration": {"nodeId": 1}}}}}
            }, sort_keys=False), encoding="utf-8")
            result = module.materialize_ansible_kafka(
                desired, root / "hosts.yml", root / "platform-state.yml",
                {"n": [{"deploymentId": "k", "memberId": "managed", "state": "UNINITIALIZED"}]},
                "p", lambda _: b"a" * 16,
            )
            self.assertEqual("PASS", result["status"])
            members = result["stateDocument"]["platform_generated_state"]["serviceDeployments"]["k"]["members"]
            self.assertEqual(["managed"], sorted(members))

    def test_generate_persist_reload_and_noop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = {"desiredState": {"serviceDeployments": {"k": {"serviceType": "kafka", "identity": {}}}}}
            inventory = {"all": {"hosts": {"n": {"platform_deployments": {"k": {"members": {"c": {"roles": ["controller"], "configuration": {"nodeId": 1}, "identity": {}}}}}}}}}
            (root / "project.yml").write_text(yaml.safe_dump(project, sort_keys=False), encoding="utf-8")
            (root / "hosts.yml").write_text(yaml.safe_dump(inventory, sort_keys=False), encoding="utf-8")
            values = iter([b"a" * 16, b"b" * 16])
            first = module.materialize_managed_kafka(root / "project.yml", root / "hosts.yml", {"n": {"k": {"c": {"state": "UNINITIALIZED"}}}}, lambda _: next(values))
            self.assertTrue(first["changed"])
            self.assertIn("clusterId", first["project"]["desiredState"]["serviceDeployments"]["k"]["identity"])
            second = module.materialize_managed_kafka(root / "project.yml", root / "hosts.yml", {"n": {"k": {"c": {"state": "UNINITIALIZED"}}}}, lambda _: (_ for _ in ()).throw(AssertionError("regenerated")))
            self.assertFalse(second["changed"])


if __name__ == "__main__":
    unittest.main()

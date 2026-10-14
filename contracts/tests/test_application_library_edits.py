import copy
import sys
import unittest
from pathlib import Path

CONTRACTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTRACTS.parent / 'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils'))
from schema_validation import SchemaValidator


class ApplicationLibraryEditTests(unittest.TestCase):
    def validate(self, value):
        return SchemaValidator(str(CONTRACTS)).validate(value, str(CONTRACTS / 'project-edit/v1alpha11/schema.json'))

    def command(self, operation):
        return dict(apiVersion='platform.installer/edit-command/v1alpha11', kind='EditCommand',
                    baseProjectRevision='sha256:' + 'a' * 64, operation=operation, deploymentId='sdku')

    def test_create_and_partial_update(self):
        value = self.command('CreateApplicationLibraryDeployment')
        value['entity'] = dict(libraryRef='sdku@1.0.0', runtimeRef='docker-main')
        self.assertEqual([], self.validate(value))
        del value['entity']['runtimeRef']
        self.assertTrue(self.validate(value))
        value['operation'] = 'UpdateApplicationLibraryDeployment'
        self.assertEqual([], self.validate(value))

    def test_slot_placement_and_reset(self):
        for operation, fields in (
            ('SetApplicationLibrarySlot', dict(entityId='gateway', entity=dict(overrides={}))),
            ('SetApplicationLibraryPlacement', dict(hostId='node1', placement={})),
            ('RemoveApplicationLibraryOverride', dict(entityId='gateway', property='parameters', setting='timeout')),
            ('SetApplicationLibraryOverride', dict(hostId='node1', property='ports', setting='http', value=dict(container=8080, published=28480))),
        ):
            value = self.command(operation)
            value.update(fields)
            self.assertEqual([], self.validate(value), operation)

    def test_closed_paths_and_scopes(self):
        value = self.command('RemoveApplicationLibraryOverride')
        value.update(entityId='gateway', property='parameters', setting='timeout')
        for fields in (dict(value='forbidden'), dict(hostId='node1'), dict(deploymentId='../sdku'),
                       dict(playbook='arbitrary.yml')):
            invalid = copy.deepcopy(value)
            invalid.update(fields)
            self.assertTrue(self.validate(invalid), fields)

    def test_old_v10_contract_retained_without_new_semantics(self):
        value = dict(apiVersion='platform.installer/edit-command/v1alpha10', kind='EditCommand',
                     baseProjectRevision='sha256:' + 'a' * 64, operation='DeleteServiceDeployment', deploymentId='kafka-main')
        self.assertEqual([], self.validate(value))
        value['operation'] = 'DeleteApplicationLibraryDeployment'
        self.assertTrue(self.validate(value))


if __name__ == '__main__':
    unittest.main()

"""The opt-in contract does not silently change older package versions."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils'))
from schema_validation import SchemaValidator


class ProviderBatchContractTests(unittest.TestCase):
    def setUp(self):
        self.validator = SchemaValidator(str(ROOT / 'contracts'))
        self.manifest = json.loads((ROOT / 'examples/szi/application-packages/keycloak/1.0.0/application.yml').read_text())

    def errors(self, manifest, version='v1alpha4'):
        return self.validator.validate(manifest, str(ROOT / 'contracts/application-libraries' / version / 'package.schema.json'))

    def test_new_manifest_accepts_explicit_batch(self):
        self.assertEqual([], self.errors(self.manifest))

    def test_old_versions_do_not_accept_batch(self):
        for version in ['v1alpha1', 'v1alpha2', 'v1alpha3']:
            manifest = copy.deepcopy(self.manifest)
            manifest['apiVersion'] = 'platform.installer/application-package/' + version
            self.assertTrue(self.errors(manifest, version))

    def test_invalid_phases_execution_and_nonboolean_opt_in_are_rejected(self):
        for overrides in [dict(phase='before_start'), dict(phase='account_apply'),
                          dict(execution='each_target'), dict(batch='true')]:
            manifest = copy.deepcopy(self.manifest)
            script = next(s for s in manifest['scripts'] if s.get('batch'))
            script.update(overrides)
            self.assertTrue(self.errors(manifest))

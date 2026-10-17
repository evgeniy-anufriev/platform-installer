import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'ansible-core/collections/ansible_collections/platform/core/plugins/module_utils'))
from schema_validation import SchemaValidator


class ApplicationCreateGrantContractTests(unittest.TestCase):
    def test_current_and_previous_privilege_contract(self):
        settings = json.loads((ROOT/'contracts/application-libraries/v1alpha1/settings.schema.json').read_text())
        rights = settings['$defs']['account']['properties']['databaseAccess']['items']['properties']['privileges']
        previous = copy.deepcopy(rights)
        previous['maxItems'] = 4
        previous['items']['enum'].remove('CREATE')
        rights['$id'] = 'https://platform.installer.test/create-grant/current'
        previous['$id'] = 'https://platform.installer.test/create-grant/previous'
        with tempfile.TemporaryDirectory() as directory:
            current_path, old_path = Path(directory)/'current.json', Path(directory)/'previous.json'
            current_path.write_text(json.dumps(rights))
            old_path.write_text(json.dumps(previous))
            validator = SchemaValidator(directory)
            for policy in [['CREATE'], ['CREATE','SELECT','INSERT','UPDATE','DELETE']]:
                self.assertEqual([], validator.validate(policy, str(current_path)))
                self.assertTrue(validator.validate(policy, str(old_path)))
            self.assertEqual([], validator.validate(['SELECT','INSERT','UPDATE','DELETE'], str(old_path)))
            self.assertTrue(validator.validate(['CREATE','CREATE'], str(current_path)))
            self.assertTrue(validator.validate(['TRUNCATE'], str(current_path)))

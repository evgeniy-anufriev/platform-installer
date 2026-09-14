import sys
import unittest
from pathlib import Path

import yaml


CONTRACTS = Path(__file__).resolve().parents[1]
REPOSITORY = CONTRACTS.parent
MODULE_UTILS = REPOSITORY / "ansible-core" / "collections" / "ansible_collections" / "platform" / "core" / "plugins" / "module_utils"
sys.path.insert(0, str(MODULE_UTILS))

from schema_validation import SchemaValidator


class ApplicationConfigContractTests(unittest.TestCase):
    def test_repository_config_conforms_to_published_schema(self):
        with (REPOSITORY / "config" / "application.yml").open(encoding="utf-8") as source:
            config = yaml.safe_load(source)
        schema = CONTRACTS / "application-config" / "v1alpha1" / "schema.json"
        self.assertEqual([], SchemaValidator(str(CONTRACTS)).validate(config, str(schema)))


if __name__ == "__main__":
    unittest.main()

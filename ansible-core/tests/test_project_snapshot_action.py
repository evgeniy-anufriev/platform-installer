import sys
import tempfile
import unittest
from pathlib import Path


COLLECTIONS = Path(__file__).resolve().parents[1] / "collections"
sys.path.insert(0, str(COLLECTIONS))

from ansible_collections.platform.core.plugins.action.project_snapshot import ActionModule


class ProjectSnapshotActionTests(unittest.TestCase):
    def test_published_catalog_service_reference_resolves_inside_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog = root / "catalog" / "service-catalog.yml"
            schema = root / "services" / "kafka" / "configuration.schema.json"
            catalog.parent.mkdir(parents=True)
            schema.parent.mkdir(parents=True)
            catalog.write_text("definitions: {}\n", encoding="utf-8")
            schema.write_text("{}\n", encoding="utf-8")
            action = object.__new__(ActionModule)
            self.assertEqual(
                str(schema.resolve()),
                action._catalog_reference(str(root.resolve()), str(catalog.resolve()), "../../services/kafka/configuration.schema.json"),
            )


if __name__ == "__main__":
    unittest.main()

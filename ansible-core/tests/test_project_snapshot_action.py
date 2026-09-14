import sys
import tempfile
import unittest
from pathlib import Path


COLLECTIONS = Path(__file__).resolve().parents[1] / "collections"
sys.path.insert(0, str(COLLECTIONS))

from ansible_collections.platform.core.plugins.action.project_snapshot import ActionModule, snapshot_host, validate_host_desired_values
from ansible_collections.platform.core.plugins.module_utils.schema_validation import SchemaValidator


class ProjectSnapshotActionTests(unittest.TestCase):
    def test_server_type_is_projected_without_becoming_identity(self):
        self.assertEqual(
            {"ansibleHost": "192.0.2.10", "type": "infra"},
            snapshot_host({"ansible_host": "192.0.2.10", "platform_host": {"type": "infra"}}, "node1"),
        )
        self.assertEqual({"ansibleHost": "node1"}, snapshot_host({}, "node1"))

    def test_host_type_validation_is_deterministic_and_contextual(self):
        class Validator:
            def validate(self, value, schema_path):
                self.schema_path = schema_path
                return [] if value.get("type") == "infra" else [{"code": "SCHEMA_VALIDATION_FAILED", "field": "/type"}]

        validator = Validator()
        findings = validate_host_desired_values(
            validator,
            "/contracts/project/v2alpha1/host-desired-vars.schema.json",
            {"node/b": {"platform_host": {"type": "INVALID"}}, "node-a": {"platform_host": {"type": "infra"}}},
            ["node/b", "node-a"],
        )
        self.assertEqual([{"code": "SCHEMA_VALIDATION_FAILED", "field": "/hosts/node~1b/platform_host/type"}], findings)
        self.assertTrue(validator.schema_path.endswith("host-desired-vars.schema.json"))

    def test_host_type_uses_portable_grammar_not_application_list(self):
        contracts = Path(__file__).resolve().parents[2] / "contracts"
        validator = SchemaValidator(str(contracts))
        schema = contracts / "project" / "v2alpha1" / "host-desired-vars.schema.json"
        self.assertEqual([], validate_host_desired_values(validator, str(schema), {"node1": {"platform_host": {"type": "scada"}}}, ["node1"]))
        findings = validate_host_desired_values(validator, str(schema), {"node1": {"platform_host": {"type": "INVALID TYPE"}}}, ["node1"])
        self.assertEqual(1, len(findings))
        self.assertEqual("/hosts/node1/platform_host/type", findings[0]["field"])

    def test_provenance_does_not_parse_ansible_config_as_yaml(self):
        action = object.__new__(ActionModule)
        loaded = []

        def load(path, required=False):
            del required
            loaded.append(path)
            return {"platform_desired_state": {"serviceDeployments": {}}}

        action._load = load
        documents = [
            {"logicalPath": "ansible.cfg", "revisionIncluded": True},
            {"logicalPath": "inventory/group_vars/all/platform-installer.yml", "revisionIncluded": True},
        ]
        desired, placements = action._provenance_sources("/project", documents, ["node1"])
        self.assertEqual("inventory/group_vars/all/platform-installer.yml", desired)
        self.assertEqual({"node1": None}, placements)
        self.assertEqual(["/project/inventory/group_vars/all/platform-installer.yml"], loaded)

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

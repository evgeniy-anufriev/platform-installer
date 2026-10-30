import importlib.util
import json
import os
import sys
import tempfile
import unittest


ROOT = os.path.join(os.path.dirname(__file__), "..", "collections", "ansible_collections", "platform", "core", "plugins", "module_utils")
sys.path.insert(0, ROOT)


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


load("project_validation", "project_validation.py")
load("service_integration_resolution", "service_integration_resolution.py")
SNAPSHOT = load("project_snapshot", "project_snapshot.py")
SCHEMA = load("schema_validation", "schema_validation.py")


class ProjectSnapshotTests(unittest.TestCase):
    def test_standalone_vault_secret_output_does_not_enter_project_revision(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "inventory"))
            for logical, content in {
                "project.yml": b"metadata: {id: project-test}\n",
                "inventory/hosts.yml": b"all: {hosts: {}}\n",
            }.items():
                path = os.path.join(root, *logical.split("/"))
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as stream:
                    stream.write(content)
            _, before = SNAPSHOT.project_documents(root)
            secret = os.path.join(root, "secrets", "vault-standalone", "root-token")
            os.makedirs(os.path.dirname(secret), mode=0o700)
            with open(secret, "wb") as stream:
                stream.write(b"standalone-test-token\n")
            _, after = SNAPSHOT.project_documents(root)
            self.assertEqual(before, after)

    def test_revision_uses_raw_bytes_and_excludes_generated_state(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "inventory", "group_vars", "all"))
            paths = {
                "project.yml": b"name: p\n",
                "inventory/hosts.yml": b"all: {}\n",
                "inventory/group_vars/all/platform.yml": b"value: 1\n",
                SNAPSHOT.GENERATED_PATH: b"generated: 1\n",
            }
            for logical, content in paths.items():
                absolute = os.path.join(root, *logical.split("/"))
                os.makedirs(os.path.dirname(absolute), exist_ok=True)
                with open(absolute, "wb") as stream:
                    stream.write(content)
            documents, first = SNAPSHOT.project_documents(root)
            same_documents, same_revision = SNAPSHOT.project_documents(root)
            self.assertEqual(first, same_revision)
            self.assertEqual(documents, same_documents)
            self.assertEqual(sorted(item["logicalPath"] for item in documents), [item["logicalPath"] for item in documents])
            with open(os.path.join(root, "inventory", "group_vars", "all", "platform-state.yml"), "wb") as stream:
                stream.write(b"generated: 2\n")
            generated_documents, generated_change = SNAPSHOT.project_documents(root)
            self.assertEqual(first, generated_change)
            with open(os.path.join(root, "project.yml"), "ab") as stream:
                stream.write(b"# comment\n")
            changed_documents, canonical_change = SNAPSHOT.project_documents(root)
            self.assertNotEqual(first, canonical_change)
            changed_paths = [
                before["logicalPath"] for before, after in zip(generated_documents, changed_documents)
                if before["digest"] != after["digest"]
            ]
            self.assertEqual(["project.yml"], changed_paths)
            generated = next(item for item in documents if item["logicalPath"] == SNAPSHOT.GENERATED_PATH)
            self.assertFalse(generated["revisionIncluded"])
            self.assertEqual("GENERATED_READ_ONLY", generated["ownership"])

    def test_redaction_preserves_references_but_not_secret_values(self):
        value = SNAPSHOT.redact({
            "password": "plain", "storePasswordSecretRef": "runtime:store",
            "nested": {"private_key": "key"},
        })
        self.assertEqual("[REDACTED]", value["password"])
        self.assertEqual("runtime:store", value["storePasswordSecretRef"])
        self.assertEqual("[REDACTED]", value["nested"]["private_key"])

    def test_snapshot_is_deterministic_partial_and_has_provenance(self):
        documents = [{"logicalPath": "inventory/group_vars/all/platform.yml", "digest": "sha256:" + "a" * 64,
                      "ownership": "INSTALLER_OWNED", "revisionIncluded": True}]
        catalog = {"digest": "sha256:" + "b" * 64, "definitions": {"kafka": {
            "metadata": {"version": "1", "displayName": "Kafka"}, "modes": {"one": {}},
            "capabilities": [], "configuration": {}, "x-definitionDigest": "sha256:" + "c" * 64,
        }}}
        state = {"serviceDeployments": {"kafka-main": {"serviceType": "kafka"}}}
        topology = {"status": "PASS", "resolvedTopology": state, "findings": []}
        configuration = {"status": "PASS", "findings": [], "services": {"kafka-main": {
            "serviceType": "kafka", "configuration": {
                "port": {"state": "RESOLVED", "source": "ROLE_DEFAULT", "value": 9092},
                "mode": {"state": "RESOLVED", "source": "DEPLOYMENT_OVERRIDE", "value": "one"},
            }, "members": {},
        }}}
        passed = {"status": "PASS", "findings": []}
        args = ("p", "P", documents, "sha256:" + "d" * 64, catalog, {}, state,
                topology, configuration, passed, dict(passed, requests=[]), dict(passed, backends={}),
                dict(passed, zones={}), "inventory/group_vars/all/platform.yml",
                {"kafka": "services/kafka/defaults/main.yml"})
        first = SNAPSHOT.build_project_snapshot(*args)
        second = SNAPSHOT.build_project_snapshot(*args)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        settings = first["effectiveConfiguration"]["services"]["kafka-main"]["configuration"]
        self.assertEqual("OVERRIDE", settings["port"]["editPolicy"])
        self.assertEqual("FUTURE_EDITABLE", settings["mode"]["editPolicy"])
        contracts = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "..", "contracts"))
        schema_path = os.path.join(contracts, "project-snapshot", "v1alpha1", "schema.json")
        self.assertEqual([], SCHEMA.SchemaValidator(contracts).validate(first, schema_path))
        blocked = dict(passed, status="BLOCKED", findings=[{
            "code": "X", "status": "BLOCKED", "field": "serviceDeployments.kafka-main",
            "safeMessage": "blocked",
        }])
        partial_args = list(args)
        partial_args[7] = blocked
        partial = SNAPSHOT.build_project_snapshot(*partial_args)
        self.assertTrue(partial["partial"])
        self.assertEqual("PARTIAL", partial["status"])

        warning = {"code": "RUNTIME_SECRET_REFERENCE_REQUIRED", "status": "WARNING",
                   "field": "serviceDeployments.kafka-main.configuration.adminCredential",
                   "safeMessage": "Required service credential reference must be saved before planning"}
        warning_args = list(args)
        warning_args[8] = dict(configuration, findings=[warning])
        warned = SNAPSHOT.build_project_snapshot(*warning_args)
        self.assertEqual("PASS", warned["status"])
        self.assertFalse(warned["partial"])
        self.assertEqual("PASS", warned["validation"]["status"])
        self.assertEqual(0, warned["validation"]["summary"]["blocked"])
        self.assertEqual(1, warned["validation"]["summary"]["warning"])
        self.assertEqual([warning], warned["findings"])
        self.assertEqual("REQUIRES_PREPARATION", warned["readiness"]["services"]["kafka-main"]["status"])
        self.assertEqual([], SCHEMA.SchemaValidator(contracts).validate(warned, schema_path))
        warning_args[7] = blocked
        mixed = SNAPSHOT.build_project_snapshot(*warning_args)
        self.assertEqual("PARTIAL", mixed["status"])
        self.assertEqual(1, mixed["validation"]["summary"]["blocked"])
        self.assertEqual(1, mixed["validation"]["summary"]["warning"])
        self.assertEqual("BLOCKED", mixed["readiness"]["services"]["kafka-main"]["status"])

        unknown_args = list(args)
        unknown_args[13] = None
        unknown = SNAPSHOT.build_project_snapshot(*unknown_args)
        unknown_mode = unknown["effectiveConfiguration"]["services"]["kafka-main"]["configuration"]["mode"]
        self.assertEqual({"kind": "UNKNOWN"}, unknown_mode["physicalOrigin"])
        self.assertEqual("READ_ONLY_UNRESOLVED", unknown_mode["editPolicy"])


if __name__ == "__main__":
    unittest.main()

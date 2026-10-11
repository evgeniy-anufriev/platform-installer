import json
import sys
import tempfile
import unittest
from collections import UserDict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ansible-core" / "collections"))
sys.path.insert(0, str(ROOT / "ansible-core" / "tools"))

from ansible_collections.platform.core.plugins.action.project_snapshot import _safe_configuration_preview
from ansible_collections.platform.core.plugins.module_utils.service_configuration_preview import ordinary_presentation_value
from build_execution_runtime_bundle import write_ui_static_defaults


class ServiceConfigurationPreviewTests(unittest.TestCase):
    def test_core_projection_keeps_ordinary_values_and_excludes_secret_objects(self):
        revision = "sha256:" + "a" * 64
        catalog = {"definitions": {"vault": {"configuration": {"settings": {
            "port": {"kind": "MANAGED", "type": "integer", "validation": {"minimum": 1, "maximum": 65535}, "ui": {}},
            "accountName": {"kind": "MANAGED", "type": "string", "validation": {"minLength": 1, "maxLength": 64}, "ui": {}},
            "credential": {"kind": "MANAGED", "type": "object", "schema": {"type": "object"}, "ui": {"x-runtimeSecretRequirement": {"requirementRef": "secret"}}},
        }}}}}
        configuration = {"services": {"vault-main": {
            "serviceType": "vault",
            "configuration": {"port": {"state": "RESOLVED", "source": "ROLE_DEFAULT", "value": 8200},
                              "accountName": {"state": "RESOLVED", "source": "DEPLOYMENT_OVERRIDE", "value": "vault-user"},
                              "credential": {"state": "RESOLVED", "source": "DEPLOYMENT_OVERRIDE", "value": {"passwordSecretRef": "runtime:secret"}}},
            "members": {"vault-1": {"configuration": {"port": {"state": "RESOLVED", "source": "MEMBER_OVERRIDE", "value": 8201}}}},
        }}}
        result = _safe_configuration_preview(configuration, catalog, revision)
        self.assertEqual(8200, result["services"]["vault-main"]["configuration"]["port"]["value"])
        self.assertEqual("vault-user", result["services"]["vault-main"]["configuration"]["accountName"]["value"])
        self.assertEqual(8201, result["services"]["vault-main"]["members"]["vault-1"]["port"]["value"])
        self.assertNotIn("credential", result["services"]["vault-main"]["configuration"])
        self.assertNotIn("runtime:secret", json.dumps(result))

    def test_dynamic_and_oversized_values_are_not_exposed(self):
        catalog = {"definitions": {"test": {"configuration": {"settings": {
            "name": {"kind": "MANAGED", "type": "string", "validation": {"minLength": 1, "maxLength": 4096}, "ui": {}}
        }}}}}
        configuration = {"services": {"deployment": {"serviceType": "test", "members": {}, "configuration": {
            "name": {"state": "DEFERRED", "source": "RUNTIME_DEFERRED", "expression": "{{ secret_value }}"}
        }}}}
        result = _safe_configuration_preview(configuration, catalog, "sha256:" + "a" * 64)
        entry = result["services"]["deployment"]["configuration"]["name"]
        self.assertEqual({"state": "DEFERRED", "source": "RUNTIME_DEFERRED"}, entry)
        self.assertNotIn("secret_value", json.dumps(result))
        configuration["services"]["deployment"]["configuration"]["name"] = {"state": "RESOLVED", "source": "ROLE_DEFAULT", "value": "x" * 4097}
        self.assertNotIn("value", _safe_configuration_preview(configuration, catalog, "sha256:" + "a" * 64)["services"]["deployment"]["configuration"]["name"])

    def test_effective_data_directories_follow_project_root_and_colocation(self):
        catalog = {"definitions": {"redis": {
            "x-dataDirectoryProjection": {
                "deploymentSetting": "dataRoot",
                "memberSetting": "dataDirectory",
                "rootVariable": "platform_data_root_directory",
                "appendMemberIdWhenCoLocated": True,
            },
            "configuration": {"settings": {
                "dataRoot": {"kind": "MANAGED", "type": "string", "validation": {"minLength": 1, "maxLength": 255}, "ui": {}},
                "dataDirectory": {"kind": "MANAGED", "type": "string", "validation": {"minLength": 1, "maxLength": 255}, "ui": {}},
            }},
        }}}
        deferred = {"state": "DEFERRED", "source": "RUNTIME_DEFERRED"}
        configuration = {"services": {"qa-redis": {
            "serviceType": "redis",
            "configuration": {"dataRoot": deferred},
            "members": {
                "redis-a": {"variableContext": {"hostId": "node1"}, "configuration": {"dataDirectory": deferred}},
                "redis-b": {"variableContext": {"hostId": "node1"}, "configuration": {"dataDirectory": deferred}},
                "redis-c": {"variableContext": {"hostId": "node2"}, "configuration": {"dataDirectory": deferred}},
            },
        }}}
        result = _safe_configuration_preview(
            configuration, catalog, "sha256:" + "a" * 64,
            {"node1": {"platform_data_root_directory": "/data"}, "node2": {"platform_data_root_directory": "/data"}},
        )["services"]["qa-redis"]
        self.assertEqual("/data/qa-redis", result["configuration"]["dataRoot"]["value"])
        self.assertEqual("/data/qa-redis/redis-a", result["members"]["redis-a"]["dataDirectory"]["value"])
        self.assertEqual("/data/qa-redis/redis-b", result["members"]["redis-b"]["dataDirectory"]["value"])
        self.assertEqual("/data/qa-redis", result["members"]["redis-c"]["dataDirectory"]["value"])
        self.assertEqual("DEFERRED", configuration["services"]["qa-redis"]["configuration"]["dataRoot"]["state"])

    def test_effective_data_directories_accept_ansible_hostvars_mapping(self):
        catalog = {"definitions": {"clickhouse": {
            "x-dataDirectoryProjection": {
                "deploymentSetting": "dataRoot",
                "memberSetting": "dataDirectory",
                "rootVariable": "platform_data_root_directory",
                "appendMemberIdWhenCoLocated": True,
            },
            "configuration": {"settings": {
                "dataRoot": {"kind": "MANAGED", "type": "string", "validation": {"minLength": 1, "maxLength": 255}, "ui": {}},
                "dataDirectory": {"kind": "MANAGED", "type": "string", "validation": {"minLength": 1, "maxLength": 255}, "ui": {}},
            }},
        }}}
        deferred = {"state": "DEFERRED", "source": "RUNTIME_DEFERRED"}
        configuration = {"services": {"qa-clickhouse": {
            "serviceType": "clickhouse",
            "configuration": {"dataRoot": deferred},
            "members": {
                "clickhouse-1": {"variableContext": {"hostId": "node1"}, "configuration": {"dataDirectory": deferred}},
            },
        }}}

        # HostVars and HostVarsVars are mapping proxies in Ansible; UserDict
        # exercises that contract without requiring an Ansible runtime here.
        hostvars = UserDict({"node1": UserDict({"platform_data_root_directory": "/data"})})
        result = _safe_configuration_preview(
            configuration, catalog, "sha256:" + "a" * 64, hostvars,
        )["services"]["qa-clickhouse"]

        self.assertEqual("/data/qa-clickhouse", result["configuration"]["dataRoot"]["value"])
        self.assertEqual("/data/qa-clickhouse", result["members"]["clickhouse-1"]["dataDirectory"]["value"])

    def test_effective_data_directory_preserves_explicit_paths_and_hides_unsafe_root(self):
        catalog = {"definitions": {"kafka": {
            "x-dataDirectoryProjection": {
                "deploymentSetting": "dataDirectory",
                "memberSetting": "dataDirectory",
                "rootVariable": "platform_data_root_directory",
                "appendMemberIdWhenCoLocated": True,
            },
            "configuration": {"settings": {
                "dataDirectory": {"kind": "MANAGED", "type": "string", "validation": {"minLength": 1, "maxLength": 255}, "ui": {}},
            }},
        }}}
        configuration = {"services": {"kafka-main": {
            "serviceType": "kafka",
            "configuration": {"dataDirectory": {"state": "RESOLVED", "source": "DEPLOYMENT_OVERRIDE", "value": "/mnt/kafka"}},
            "members": {
                "broker-a": {"variableContext": {"hostId": "node1"}, "configuration": {"dataDirectory": {"state": "RESOLVED", "source": "DEPLOYMENT_OVERRIDE", "value": "/mnt/kafka"}}},
                "broker-b": {"variableContext": {"hostId": "node1"}, "configuration": {"dataDirectory": {"state": "RESOLVED", "source": "MEMBER_OVERRIDE", "value": "/srv/kafka-b"}}},
            },
        }}}
        result = _safe_configuration_preview(configuration, catalog, "sha256:" + "a" * 64, {"node1": {"platform_data_root_directory": "/data"}})["services"]["kafka-main"]
        self.assertEqual("/mnt/kafka", result["configuration"]["dataDirectory"]["value"])
        self.assertEqual("/mnt/kafka/broker-a", result["members"]["broker-a"]["dataDirectory"]["value"])
        self.assertEqual("/srv/kafka-b", result["members"]["broker-b"]["dataDirectory"]["value"])

        unsafe = {"services": {"qa-redis": {
            "serviceType": "redis",
            "configuration": {"dataRoot": {"state": "DEFERRED", "source": "RUNTIME_DEFERRED"}},
            "members": {"redis-a": {"variableContext": {"hostId": "node1"}, "configuration": {"dataDirectory": {"state": "DEFERRED", "source": "RUNTIME_DEFERRED"}}}},
        }}}
        redis_definition = {
            "x-dataDirectoryProjection": {
                "deploymentSetting": "dataRoot",
                "memberSetting": "dataDirectory",
                "rootVariable": "platform_data_root_directory",
                "appendMemberIdWhenCoLocated": True,
            },
            "configuration": {"settings": {
                "dataRoot": {"kind": "MANAGED", "type": "string", "validation": {"minLength": 1, "maxLength": 255}, "ui": {}},
                "dataDirectory": {"kind": "MANAGED", "type": "string", "validation": {"minLength": 1, "maxLength": 255}, "ui": {}},
            }},
        }
        for unsafe_root in ("{{ secret_path }}", "/data/../etc", "/data with spaces"):
            hidden = _safe_configuration_preview(
                unsafe, {"definitions": {"redis": redis_definition}}, "sha256:" + "b" * 64,
                {"node1": {"platform_data_root_directory": unsafe_root}},
            )
            self.assertNotIn("value", hidden["services"]["qa-redis"]["configuration"]["dataRoot"])
            self.assertNotIn(unsafe_root, json.dumps(hidden))

    def test_bundle_component_omits_secret_object_and_marks_expression_deferred(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "catalog").mkdir()
            (root / "catalog" / "service-catalog.yml").write_text(
                "definitions:\n  test:\n    roleEntrypoints: {apply: {fqcn: platform.test.service}}\n"
                "    configuration:\n      settings:\n"
                "        port: {kind: MANAGED, type: integer, roleVariable: platform_port, validation: {minimum: 1, maximum: 65535}, ui: {}}\n"
                "        accountName: {kind: MANAGED, type: string, roleVariable: platform_name, validation: {minLength: 1, maxLength: 64}, ui: {}}\n"
                "        dynamic: {kind: MANAGED, type: string, roleVariable: platform_dynamic, validation: {minLength: 1, maxLength: 64}, ui: {}}\n"
                "        freeform: {kind: MANAGED, type: string, roleVariable: platform_freeform, ui: {}}\n"
                "        invalidPort: {kind: MANAGED, type: integer, roleVariable: platform_invalid_port, validation: {minimum: 1, maximum: 65535}, ui: {}}\n"
                "        credential: {kind: MANAGED, type: object, roleVariable: platform_credential, schema: {type: object}, ui: {x-runtimeSecretRequirement: {requirementRef: secret}}}\n",
                encoding="utf-8",
            )
            path = root / "services" / "test" / "ansible_collections" / "platform" / "test" / "roles" / "service" / "defaults" / "main.yml"
            path.parent.mkdir(parents=True)
            path.write_text("platform_port: 8443\nplatform_name: service-user\nplatform_dynamic: '{{ inventory_hostname }}'\nplatform_freeform: unbounded-value\nplatform_invalid_port: 65536\nplatform_credential: {passwordSecretRef: 'runtime:secret'}\n", encoding="utf-8")
            write_ui_static_defaults(root)
            result = json.loads((root / "catalog" / "ui-static-defaults.json").read_text(encoding="utf-8"))
            settings = result["services"]["test"]
            self.assertEqual({"state": "LITERAL", "value": 8443}, settings["port"])
            self.assertEqual({"state": "LITERAL", "value": "service-user"}, settings["accountName"])
            self.assertEqual({"state": "DEFERRED"}, settings["dynamic"])
            self.assertEqual({"state": "UNAVAILABLE"}, settings["freeform"])
            self.assertEqual({"state": "UNAVAILABLE"}, settings["invalidPort"])
            self.assertNotIn("credential", settings)
            self.assertNotIn("runtime:secret", json.dumps(result))

    def test_core_producer_never_serializes_unbounded_or_out_of_range_values(self):
        settings = {
            "freeform": {"kind": "MANAGED", "type": "string", "ui": {}},
            "port": {"kind": "MANAGED", "type": "integer", "validation": {"minimum": 1, "maximum": 65535}, "ui": {}},
            "expression": {"kind": "MANAGED", "type": "string", "validation": {"minLength": 1, "maxLength": 64}, "ui": {}},
            "credential": {"kind": "MANAGED", "type": "object", "schema": {"type": "object"}, "ui": {"x-runtimeSecretRequirement": {"requirementRef": "secret"}}},
        }
        configuration = {"services": {"main": {"serviceType": "test", "members": {}, "configuration": {
            key: {"state": "RESOLVED", "source": "ROLE_DEFAULT", "value": value}
            for key, value in {"freeform": "unbounded-value", "port": 65536,
                               "expression": "{{ lookup('env', 'SECRET') }}",
                               "credential": {"passwordSecretRef": "runtime:secret"}}.items()
        }}}}
        result = _safe_configuration_preview(configuration, {"definitions": {"test": {"configuration": {"settings": settings}}}}, "sha256:" + "a" * 64)
        for entry in result["services"]["main"]["configuration"].values():
            self.assertNotIn("value", entry)
        self.assertNotIn("credential", result["services"]["main"]["configuration"])
        encoded = json.dumps(result)
        self.assertNotIn("unbounded-value", encoded)
        self.assertNotIn("runtime:secret", encoded)

    def test_closed_shapes_accept_ordinary_values_only(self):
        cases = (
            ({"kind": "MANAGED", "type": "boolean", "ui": {}}, True),
            ({"kind": "MANAGED", "type": "integer", "validation": {"minimum": 1, "maximum": 65535}, "ui": {}}, 8200),
            ({"kind": "MANAGED", "type": "number", "validation": {"minimum": 0, "maximum": 1}, "ui": {}}, 0.5),
            ({"kind": "MANAGED", "type": "string", "validation": {"enum": ["one", "two"]}, "ui": {}}, "two"),
            ({"kind": "MANAGED", "type": "string", "validation": {"minLength": 1, "maxLength": 64}, "ui": {}}, "service-user"),
            ({"kind": "MANAGED", "type": "string", "validation": {"minLength": 1}, "ui": {"x-referenceKind": "TLS_PROFILE"}}, "infrastructure-tls"),
            ({"kind": "MANAGED", "type": "string", "validation": {"minLength": 1}, "ui": {"x-referenceKind": "SERVICE_DEPLOYMENT"}}, "bind-main"),
        )
        for descriptor, value in cases:
            with self.subTest(descriptor=descriptor, value=value):
                self.assertTrue(ordinary_presentation_value(descriptor, value))
                self.assertFalse(ordinary_presentation_value(descriptor, {"raw": value}))


if __name__ == "__main__":
    unittest.main()

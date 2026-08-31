import importlib.util
import os
import sys
import unittest


ROOT = os.path.join(
    os.path.dirname(__file__), "..", "collections", "ansible_collections", "platform",
    "core", "plugins", "module_utils",
)


def load_module(name, filename):
    path = os.path.join(ROOT, filename)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


VALIDATION = load_module("project_validation", "project_validation.py")
RESOLUTION = load_module("topology_resolution_for_configuration", "topology_resolution.py")
CONTRACT = load_module("service_configuration_contract", "service_configuration_contract.py")
CONFIGURATION = load_module("service_configuration_resolution", "service_configuration_resolution.py")


def catalog(canonical=False):
    definition = {
        "metadata": {"id": "kafka", "version": "1"},
        "modes": {"kraft-standalone": {}},
        "configurationSchema": {"$ref": "configuration.schema.json"},
        "configurationMapping": {
            "clientPort": {"roleVariable": "platform_kafka_client_port", "scopes": ["deployment", "member"]},
            "dataDirectory": {"roleVariable": "platform_kafka_data_directory", "scopes": ["deployment", "member"]},
            "logRetentionHours": {"roleVariable": "platform_kafka_log_retention_hours", "scopes": ["deployment"]},
        },
    }
    if canonical:
        definition.pop("configurationMapping")
        definition["configuration"] = {
            "additionalProperties": True,
            "settings": {
                "clientPort": {"kind": "MANAGED", "roleVariable": "platform_kafka_client_port", "type": "integer", "scopes": ["deployment", "member"], "validation": {"minimum": 1, "maximum": 65535}},
                "dataDirectory": {"kind": "MANAGED", "roleVariable": "platform_kafka_data_directory", "type": "string", "scopes": ["deployment", "member"], "validation": {"minLength": 1}},
                "logRetentionHours": {"kind": "MANAGED", "roleVariable": "platform_kafka_log_retention_hours", "type": "integer", "scopes": ["deployment"], "validation": {"minimum": 1}},
                "advancedConfig": {"kind": "ADVANCED", "roleVariable": "platform_kafka_advanced_config", "type": "object", "scopes": ["deployment"], "validation": {"additionalProperties": True}},
            },
        }
    definition["x-definitionDigest"] = VALIDATION.canonical_digest(definition)
    unsigned = {
        "apiVersion": "platform.installer/catalog/v1alpha1",
        "kind": "ServiceCatalog",
        "definitions": {"kafka": definition},
    }
    return dict(unsigned, digest=VALIDATION.canonical_digest(unsigned))


def topology(configuration=None, member_configuration=None, host="node-a"):
    member = {"host": host, "roles": ["broker", "controller"]}
    if member_configuration is not None:
        member["configuration"] = member_configuration
    deployment = {
        "serviceType": "kafka",
        "definitionVersion": "1",
        "mode": "kraft-standalone",
        "members": {"member-a": member},
    }
    if configuration is not None:
        deployment["configuration"] = configuration
    return {"serviceDeployments": {"kafka-main": deployment}}


def resolved(topology_value):
    desired = topology_value["serviceDeployments"]
    resolved_deployments = {}
    for deployment_id, deployment in desired.items():
        resolved_deployments[deployment_id] = {
            "serviceType": deployment["serviceType"],
            "definitionVersion": deployment["definitionVersion"],
            "mode": deployment["mode"],
            "members": {
                member_id: {"host": member["host"], "roles": member["roles"]}
                for member_id, member in deployment["members"].items()
            },
        }
    return {
        "status": "PASS",
        "resolvedTopology": {"serviceDeployments": resolved_deployments},
        "topologyFingerprint": VALIDATION.canonical_digest(topology_value),
    }


class ServiceConfigurationResolutionTests(unittest.TestCase):
    def resolve(self, project_topology, defaults=None, topology_result=None, host_contexts=None, variable_documents=None, service_catalog=None):
        project_topology = project_topology or topology()
        selected_catalog = service_catalog or catalog()
        definition = selected_catalog["definitions"]["kafka"]
        selected_defaults = defaults if defaults is not None else {
            "platform_kafka_client_port": 9092,
            "platform_kafka_data_directory": "/var/lib/kafka",
            "platform_kafka_log_retention_hours": 168,
        }
        if "configuration" in definition and "platform_kafka_advanced_config" not in selected_defaults:
            selected_defaults = dict(selected_defaults, platform_kafka_advanced_config={})
        selected_schema = CONTRACT.generated_schema(definition) if "configuration" in definition and "configurationMapping" not in definition else {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "clientPort": {"type": "integer", "minimum": 1, "maximum": 65535},
                "dataDirectory": {"type": "string", "minLength": 1},
            },
        }
        return CONFIGURATION.resolve_service_configuration(
            topology_result or resolved(project_topology),
            project_topology,
            selected_catalog,
            {"kafka": selected_defaults},
            {"kafka": selected_schema},
            host_contexts=host_contexts,
            variable_documents=variable_documents,
        )

    def test_materializes_literal_role_defaults_and_override(self):
        result = self.resolve(topology({"clientPort": 19092}))
        config = result["services"]["kafka-main"]["configuration"]
        self.assertEqual({"state": "RESOLVED", "value": 19092, "source": "DEPLOYMENT_OVERRIDE"}, config["clientPort"])
        self.assertEqual({"state": "RESOLVED", "value": "/var/lib/kafka", "source": "ROLE_DEFAULT"}, config["dataDirectory"])
        self.assertEqual("PASS", result["status"])

    def test_non_literal_default_is_deferred(self):
        result = self.resolve(topology(), {
            "platform_kafka_client_port": "{{ platform_kafka_default_port | default(9092) }}",
            "platform_kafka_data_directory": "/var/lib/kafka",
            "platform_kafka_log_retention_hours": 168,
        })
        value = result["services"]["kafka-main"]["configuration"]["clientPort"]
        self.assertEqual({"state": "DEFERRED", "reason": "NON_LITERAL_ROLE_DEFAULT", "source": "RUNTIME_DEFERRED", "expression": "{{ platform_kafka_default_port | default(9092) }}"}, value)
        self.assertEqual("PASS", result["status"])

    def test_member_override_wins_and_keeps_member_identity(self):
        result = self.resolve(topology({"clientPort": 19092}, {"clientPort": 9192}))
        member = result["services"]["kafka-main"]["members"]["member-a"]
        self.assertEqual(9192, member["configuration"]["clientPort"]["value"])
        self.assertEqual("MEMBER_OVERRIDE", member["configuration"]["clientPort"]["source"])
        self.assertEqual("member-a", member["variableContext"]["memberId"])
        self.assertEqual("node-a", member["variableContext"]["hostId"])

    def test_member_configuration_scope_is_blocked(self):
        value = topology(member_configuration={"logRetentionHours": 1})
        result = self.resolve(value)
        self.assertEqual("BLOCKED", result["status"])
        finding = next(item for item in result["findings"] if item["code"] == "MEMBER_SETTING_SCOPE_UNSUPPORTED")
        self.assertEqual("serviceDeployments.kafka-main.members.member-a.configuration.logRetentionHours", finding["field"])

    def test_three_members_on_one_host_are_independent(self):
        project = topology({"clientPort": 9000})
        members = project["serviceDeployments"]["kafka-main"]["members"]
        members.clear()
        for member_id, port in (("member-a", 9092), ("member-b", 9192), ("member-c", 9292)):
            members[member_id] = {"host": "node-a", "roles": ["broker"], "configuration": {"clientPort": port}}
        result = self.resolve(project)
        self.assertEqual("PASS", result["status"])
        self.assertEqual([9092, 9192, 9292], [
            result["services"]["kafka-main"]["members"][member_id]["configuration"]["clientPort"]["value"]
            for member_id in ("member-a", "member-b", "member-c")
        ])

    def test_static_reference_resolves_and_tracks_reference(self):
        result = self.resolve(topology(), {
            "platform_kafka_client_port": "{{ platform_default_client_port }}",
            "platform_default_client_port": 9192,
            "platform_kafka_data_directory": "/var/lib/kafka",
        })
        value = result["services"]["kafka-main"]["configuration"]["clientPort"]
        self.assertEqual(9192, value["value"])
        self.assertEqual("STATIC_REFERENCE", value["source"])

    def test_static_reference_sees_same_scope_override(self):
        result = self.resolve(topology({"clientPort": 19092}), {
            "platform_kafka_client_port": 9092,
            "platform_kafka_data_directory": "{{ platform_kafka_client_port }}",
        })
        value = result["services"]["kafka-main"]["configuration"]["dataDirectory"]
        self.assertEqual(19092, value["value"])
        self.assertEqual("STATIC_REFERENCE", value["source"])

    def test_arbitrary_jinja_is_deferred_but_unknown_setting_is_blocked(self):
        result = self.resolve(topology({"clientPort": "{{ value | default(9092) }}"}))
        value = result["services"]["kafka-main"]["configuration"]["clientPort"]
        self.assertEqual("DEFERRED", value["state"])
        self.assertEqual("RUNTIME_DEFERRED", value["source"])
        unknown = self.resolve(topology({"unknown": "{{ value | default(1) }}"}))
        self.assertEqual("PASS", unknown["status"])
        self.assertEqual("unknown", unknown["services"]["kafka-main"]["opaqueVariables"][0]["name"])

    def test_static_reference_missing_and_cycle_are_diagnosed(self):
        missing = self.resolve(topology(), {"platform_kafka_client_port": "{{ missing_port }}", "platform_kafka_data_directory": "/var/lib/kafka"})
        self.assertIn("STATIC_REFERENCE_NOT_FOUND", [item["code"] for item in missing["findings"]])
        cyclic = self.resolve(topology(), {"platform_kafka_client_port": "{{ platform_kafka_data_directory }}", "platform_kafka_data_directory": "{{ platform_kafka_client_port }}"})
        self.assertIn("STATIC_REFERENCE_CYCLE", [item["code"] for item in cyclic["findings"]])

    def test_same_member_id_isolated_by_deployment(self):
        first = topology()
        second = topology()
        second_deployment = second["serviceDeployments"].pop("kafka-main")
        second["serviceDeployments"]["kafka-test"] = second_deployment
        second["serviceDeployments"]["kafka-test"]["configuration"] = {"clientPort": 29092}
        project = {"serviceDeployments": {
            "kafka-main": first["serviceDeployments"]["kafka-main"],
            "kafka-test": second["serviceDeployments"]["kafka-test"],
        }}
        project["serviceDeployments"]["kafka-test"]["members"]["member-a"]["configuration"] = {"clientPort": 29992}
        result = self.resolve(project)
        self.assertEqual(9092, result["services"]["kafka-main"]["members"]["member-a"]["configuration"]["clientPort"]["value"])
        self.assertEqual(29992, result["services"]["kafka-test"]["members"]["member-a"]["configuration"]["clientPort"]["value"])

    def test_placement_does_not_affect_configuration_fingerprint(self):
        first_topology = topology({"clientPort": 19092}, host="node-a")
        second_topology = topology({"clientPort": 19092}, host="node-b")
        first = self.resolve(first_topology)
        second_result = resolved(second_topology)
        second = self.resolve(second_topology, topology_result=second_result)
        self.assertNotEqual(first["services"]["kafka-main"]["inputs"]["topologyFingerprint"], second["services"]["kafka-main"]["inputs"]["topologyFingerprint"])
        self.assertEqual(first["configurationFingerprint"], second["configurationFingerprint"])

    def test_unknown_values_are_opaque_and_preserve_origin(self):
        result = self.resolve(topology({"unknown": 1}))
        self.assertEqual("PASS", result["status"])
        opaque = result["services"]["kafka-main"]["opaqueVariables"]
        self.assertEqual("unknown", opaque[0]["name"])
        self.assertEqual("DEPLOYMENT_CONFIGURATION", opaque[0]["origin"]["source"])
        self.assertEqual("serviceDeployments.kafka-main.configuration.unknown", opaque[0]["origin"]["path"])

    def test_unknown_member_and_role_values_are_opaque(self):
        project = topology(member_configuration={"customRoleVariable": "{{ runtime_value }}"})
        project["serviceDeployments"]["kafka-main"]["configuration"] = {"customDeployment": True}
        result = self.resolve(project, {
            "platform_kafka_client_port": 9092,
            "platform_kafka_data_directory": "/var/lib/kafka",
            "platform_kafka_log_retention_hours": 168,
            "platform_kafka_extra": "opaque",
        })
        self.assertEqual("PASS", result["status"])
        service = result["services"]["kafka-main"]
        sources = {item["origin"]["source"] for item in service["opaqueVariables"]}
        self.assertEqual({"ROLE_DEFAULT", "DEPLOYMENT_CONFIGURATION"}, sources)
        member_opaque = service["members"]["member-a"]["opaqueVariables"][0]
        self.assertEqual("MEMBER_CONFIGURATION", member_opaque["origin"]["source"])
        self.assertEqual("{{ runtime_value }}", member_opaque["expression"])

    def test_host_context_is_opaque_and_not_member_configuration(self):
        result = self.resolve(topology(), host_contexts={"node-a": {"platform_data_root": "/data"}})
        opaque = result["opaqueVariables"][0]
        self.assertEqual("platform_data_root", opaque["name"])
        self.assertEqual("HOST_CONTEXT", opaque["origin"]["source"])
        self.assertNotIn("platform_data_root", result["services"]["kafka-main"]["members"]["member-a"]["configuration"])

    def test_schema_type_and_range_findings_are_safe(self):
        result = self.resolve(topology({"clientPort": 0}))
        self.assertEqual("BLOCKED", result["status"])
        self.assertEqual("SERVICE_CONFIGURATION_MINIMUM_INVALID", result["findings"][0]["code"])

    def test_canonical_settings_and_advanced_container_resolve(self):
        project = topology({"advancedConfig": {"compression.type": "lz4"}})
        result = self.resolve(project, service_catalog=catalog(canonical=True))
        self.assertEqual("PASS", result["status"])
        self.assertEqual("MANAGED", catalog(canonical=True)["definitions"]["kafka"]["configuration"]["settings"]["clientPort"]["kind"])
        self.assertEqual({"compression.type": "lz4"}, result["services"]["kafka-main"]["configuration"]["advancedConfig"]["value"])

    def test_legacy_and_canonical_contract_conflict_is_blocked(self):
        conflicted = catalog(canonical=True)
        conflicted["definitions"]["kafka"]["configurationMapping"] = {"clientPort": {"roleVariable": "platform_kafka_client_port"}}
        result = self.resolve(topology(), service_catalog=conflicted)
        self.assertIn("SERVICE_CONFIGURATION_CONTRACT_CONFLICT", [item["code"] for item in result["findings"]])

    def test_bound_group_vars_manage_known_and_preserve_unknown(self):
        documents = [{
            "kind": "GROUP_VARS", "deploymentId": "kafka-main", "serviceType": "kafka",
            "groupId": "kafka-main", "logicalPath": "inventory/group_vars/kafka-main.yml",
            "variables": {"platform_kafka_client_port": 9192, "platform_kafka_heap_size": "4g", "company_custom_variable": "abc"},
        }]
        result = self.resolve(topology(), service_catalog=catalog(canonical=True), variable_documents=documents)
        service = result["services"]["kafka-main"]
        self.assertEqual(9192, service["configuration"]["clientPort"]["value"])
        self.assertEqual("GROUP_VARS", service["configuration"]["clientPort"]["physicalOrigin"]["kind"])
        self.assertEqual(["company_custom_variable", "platform_kafka_heap_size"], sorted(item["name"] for item in service["opaqueVariables"]))
        self.assertTrue(service["opaqueVariablesFingerprint"].startswith("sha256:"))

    def test_opaque_values_do_not_change_managed_configuration_fingerprint(self):
        first = [{"kind": "GROUP_VARS", "deploymentId": "kafka-main", "serviceType": "kafka", "groupId": "kafka-main", "logicalPath": "inventory/group_vars/kafka-main.yml", "variables": {"platform_kafka_heap_size": "4g"}}]
        second = [{"kind": "GROUP_VARS", "deploymentId": "kafka-main", "serviceType": "kafka", "groupId": "kafka-main", "logicalPath": "inventory/group_vars/kafka-main.yml", "variables": {"platform_kafka_heap_size": "8g"}}]
        one = self.resolve(topology(), service_catalog=catalog(canonical=True), variable_documents=first)
        two = self.resolve(topology(), service_catalog=catalog(canonical=True), variable_documents=second)
        self.assertEqual(one["configurationFingerprint"], two["configurationFingerprint"])
        self.assertNotEqual(one["opaqueVariablesFingerprint"], two["opaqueVariablesFingerprint"])

    def test_opaque_fingerprint_normalizes_logical_path_formatting(self):
        first = [{"kind": "GROUP_VARS", "deploymentId": "kafka-main", "serviceType": "kafka", "groupId": "kafka-main", "logicalPath": "inventory/group_vars/kafka-main.yml", "variables": {"platform_kafka_heap_size": "4g"}}]
        second = [{"kind": "GROUP_VARS", "deploymentId": "kafka-main", "serviceType": "kafka", "groupId": "kafka-main", "logicalPath": "inventory/group_vars/./kafka-main.yml", "variables": {"platform_kafka_heap_size": "4g"}}]
        one = self.resolve(topology(), service_catalog=catalog(canonical=True), variable_documents=first)
        two = self.resolve(topology(), service_catalog=catalog(canonical=True), variable_documents=second)
        self.assertEqual(one["opaqueVariablesFingerprint"], two["opaqueVariablesFingerprint"])

    def test_unknown_host_vars_are_opaque_without_semantic_scope(self):
        documents = [{"kind": "HOST_VARS", "hostId": "node-a", "logicalPath": "inventory/host_vars/node-a.yml", "variables": {"platform_kafka_heap_size": "4g"}}]
        result = self.resolve(topology(), variable_documents=documents)
        opaque = result["opaqueVariables"][0]
        self.assertEqual("HOST_VARS", opaque["origin"]["source"])
        self.assertNotIn("platform_kafka_heap_size", result["services"]["kafka-main"]["configuration"])

    def test_future_mapping_promotes_existing_group_variable(self):
        documents = [{"kind": "GROUP_VARS", "deploymentId": "kafka-main", "serviceType": "kafka", "groupId": "kafka-main", "logicalPath": "inventory/group_vars/kafka-main.yml", "variables": {"platform_kafka_heap_size": "4g"}}]
        before = self.resolve(topology(), service_catalog=catalog(canonical=True), variable_documents=documents)
        promoted = catalog(canonical=True)
        promoted["definitions"]["kafka"]["configuration"]["settings"]["heapSize"] = {"kind": "MANAGED", "roleVariable": "platform_kafka_heap_size", "type": "string", "scopes": ["deployment"], "validation": {}}
        after = self.resolve(topology(), defaults={"platform_kafka_client_port": 9092, "platform_kafka_data_directory": "/var/lib/kafka", "platform_kafka_log_retention_hours": 168, "platform_kafka_heap_size": "1g"}, service_catalog=promoted, variable_documents=documents)
        self.assertIn("platform_kafka_heap_size", [item["name"] for item in before["services"]["kafka-main"]["opaqueVariables"]])
        self.assertEqual("4g", after["services"]["kafka-main"]["configuration"]["heapSize"]["value"])

    def test_canonical_setting_without_default_is_not_blocked(self):
        selected = catalog(canonical=True)
        selected["definitions"]["kafka"]["configuration"]["settings"]["requiredInput"] = {"kind": "MANAGED", "roleVariable": "platform_kafka_required_input", "type": "string", "scopes": ["deployment"], "validation": {}}
        result = self.resolve(topology(), service_catalog=selected)
        self.assertEqual("PASS", result["status"])
        self.assertNotIn("requiredInput", result["services"]["kafka-main"]["configuration"])


if __name__ == "__main__":
    unittest.main()

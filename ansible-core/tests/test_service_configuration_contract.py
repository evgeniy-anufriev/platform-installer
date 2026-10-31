import importlib.util
import os
import unittest
from pathlib import Path
import yaml


ROOT = os.path.join(os.path.dirname(__file__), "..", "collections", "ansible_collections", "platform", "core", "plugins", "module_utils")
SPEC = importlib.util.spec_from_file_location("service_configuration_contract", os.path.join(ROOT, "service_configuration_contract.py"))
CONTRACT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTRACT)


def definition(settings):
    return {"metadata": {"id": "kafka", "displayName": "Kafka"}, "configuration": {"additionalProperties": True, "settings": settings}}


class ServiceConfigurationContractTests(unittest.TestCase):
    def test_tls_profile_unset_default_is_not_a_selected_profile(self):
        setting = {'kind': 'MANAGED', 'roleVariable': 'platform_tls_profile', 'type': 'string',
                   'scopes': ['deployment'], 'validation': {'minLength': 1},
                   'ui': {'x-referenceKind': 'TLS_PROFILE'}}
        self.assertEqual([], CONTRACT.validate_defaults(definition({'tlsProfile': setting}), {'platform_tls_profile': ''}, lambda value: True))
        setting['ui'] = {}
        self.assertIn('ROLE_DEFAULT_VALIDATION_INVALID', {item['code'] for item in
            CONTRACT.validate_defaults(definition({'name': setting}), {'platform_tls_profile': ''}, lambda value: True)})
        setting.update(type='number', validation={}, ui={'x-referenceKind': 'TLS_PROFILE'})
        self.assertIn('ROLE_DEFAULT_TYPE_INVALID', {item['code'] for item in
            CONTRACT.validate_defaults(definition({'tlsProfile': setting}), {'platform_tls_profile': ''}, lambda value: True)})

    def test_service_tls_defaults_are_unset_and_manual_tls_directories_still_work(self):
        from ansible.parsing.dataloader import DataLoader
        from ansible.template import Templar
        repository = Path(__file__).resolve().parents[2]
        for service in ('docker', 'clickhouse', 'kafka', 'postgresql', 'redis', 'vault', 'haproxy'):
            found = False
            for path in (repository / 'services' / service / 'ansible_collections' / 'platform' / service / 'roles').glob('*/defaults/main.yml'):
                defaults = yaml.safe_load(path.read_text())
                key = 'platform_%s_tls_profile' % service
                if key not in defaults:
                    continue
                found = True
                self.assertEqual('', defaults[key], path)
                if service in ('docker', 'clickhouse'):
                    defaults['platform_%s_tls_directory' % service] = '/existing/tls'
                    tasks = yaml.safe_load((path.parents[1] / 'tasks/validate.yml').read_text())
                    templar = Templar(loader=DataLoader(), variables=defaults)
                    for expression in tasks[0]['ansible.builtin.assert']['that']:
                        if key in expression:
                            self.assertTrue(templar.template('{{ ' + expression + ' }}'), expression)
            self.assertTrue(found, service)

    def test_generates_deterministic_schema_without_defaults(self):
        value = definition({"clientPort": {"kind": "MANAGED", "roleVariable": "platform_kafka_client_port", "type": "integer", "scopes": ["deployment"], "validation": {"minimum": 1}}})
        schema = CONTRACT.generated_schema(value)
        self.assertEqual({"type": "integer", "minimum": 1}, schema["properties"]["clientPort"])
        self.assertTrue(schema["additionalProperties"])
        self.assertNotIn("default", schema["properties"]["clientPort"])

    def test_rejects_duplicate_role_variable_and_invalid_advanced_type(self):
        settings = {
            "one": {"kind": "MANAGED", "roleVariable": "platform_value", "type": "integer", "scopes": ["deployment"], "validation": {}},
            "two": {"kind": "ADVANCED", "roleVariable": "platform_value", "type": "string", "scopes": ["host"], "validation": {"minimum": 1}},
        }
        codes = {issue["code"] for issue in CONTRACT.validate_settings(settings)}
        self.assertTrue({"SERVICE_CONFIGURATION_ROLE_VARIABLE_DUPLICATE", "SERVICE_CONFIGURATION_ADVANCED_TYPE_INVALID", "SERVICE_CONFIGURATION_SCOPES_INVALID", "SERVICE_CONFIGURATION_VALIDATION_TYPE_INVALID"}.issubset(codes))

    def test_rejects_invalid_role_variable_and_typed_enum(self):
        settings = {"port": {"kind": "MANAGED", "roleVariable": "Platform-Port", "type": "integer", "scopes": ["deployment"], "validation": {"enum": [9092, "bad"]}}}
        codes = {issue["code"] for issue in CONTRACT.validate_settings(settings)}
        self.assertIn("SERVICE_CONFIGURATION_ROLE_VARIABLE_INVALID", codes)
        self.assertIn("SERVICE_CONFIGURATION_VALIDATION_TYPE_INVALID", codes)

    def test_defaults_allow_jinja_and_absence_but_reject_invalid_literal(self):
        settings = {"clientPort": {"kind": "MANAGED", "roleVariable": "platform_client_port", "type": "integer", "scopes": ["deployment"], "validation": {"minimum": 1}}}
        value = definition(settings)
        self.assertEqual([], CONTRACT.validate_defaults(value, {}, lambda item: True))
        self.assertEqual([], CONTRACT.validate_defaults(value, {"platform_client_port": "{{ default_port }}"}, lambda item: False))
        codes = {issue["code"] for issue in CONTRACT.validate_defaults(value, {"platform_client_port": 0}, lambda item: True)}
        self.assertIn("ROLE_DEFAULT_VALIDATION_INVALID", codes)

    def test_managed_update_preserves_unknown_variable_values(self):
        settings = {"clientPort": {"kind": "MANAGED", "roleVariable": "platform_kafka_client_port", "type": "integer", "scopes": ["deployment"], "validation": {}}}
        updated, issues = CONTRACT.apply_managed_overrides(
            definition(settings),
            {"platform_kafka_client_port": 9192, "platform_kafka_heap_size": "4g", "company_custom_variable": "abc"},
            {"clientPort": 9292},
        )
        self.assertEqual([], issues)
        self.assertEqual(9292, updated["platform_kafka_client_port"])
        self.assertEqual("4g", updated["platform_kafka_heap_size"])
        self.assertEqual("abc", updated["company_custom_variable"])


if __name__ == "__main__":
    unittest.main()

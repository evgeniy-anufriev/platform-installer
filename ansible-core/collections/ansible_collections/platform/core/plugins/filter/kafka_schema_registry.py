from ansible_collections.platform.core.plugins.module_utils.kafka_schema_registry import registry_projection, properties_value


class FilterModule(object):
    def filters(self):
        return {"platform_kafka_schema_registry_projection": registry_projection,
                "platform_java_properties_value": properties_value}

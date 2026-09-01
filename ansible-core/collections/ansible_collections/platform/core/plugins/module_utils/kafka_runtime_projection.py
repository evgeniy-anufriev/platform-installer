from __future__ import absolute_import, division, print_function

__metaclass__ = type

try:
    from .project_validation import canonical_digest
    from .kafka_listener_resolution import listener_runtime_properties
except ImportError:
    from project_validation import canonical_digest
    from kafka_listener_resolution import listener_runtime_properties


def project_kafka_runtime(resolved_topology, resolved_configuration, host_addresses=None):
    """Build the public platform_kafka_instances input from final Core projections.

    This is deliberately a pure controller-side adapter. It neither reads
    Ansible precedence nor changes the standalone role contract.
    """
    topology = resolved_topology.get("resolvedTopology", {}) if isinstance(resolved_topology, dict) else {}
    services = resolved_configuration.get("services", {}) if isinstance(resolved_configuration, dict) else {}
    addresses = host_addresses if isinstance(host_addresses, dict) else {}
    output = {}
    for deployment_id, deployment in sorted(topology.get("serviceDeployments", {}).items()):
        if deployment.get("serviceType") != "kafka":
            continue
        service = services.get(deployment_id, {})
        instances = []
        for member_id, member in sorted(deployment.get("members", {}).items()):
            effective = service.get("members", {}).get(member_id, {}).get("configuration", {})
            host = member.get("host")
            address = effective.get("advertisedHost", addresses.get(host, host))
            deployment_config = service.get("configuration", {})
            namespace = deployment_config.get("runtimePathNamespace", deployment_id)
            data_root = deployment_config.get("dataDirectoryRoot", "/var/lib/kafka")
            log_root = deployment_config.get("logDirectoryRoot", "/var/log/kafka")
            config_root = deployment_config.get("configDirectoryRoot", "/etc/kafka")
            if deployment.get("mode") == "kraft-standalone":
                data_path = deployment_config.get("dataDirectory", data_root)
                log_path = deployment_config.get("logDirectory", log_root)
                config_path = deployment_config.get("configDirectory", config_root)
            else:
                data_path = "%s/%s/%s" % (data_root.rstrip("/"), namespace, member_id)
                log_path = "%s/%s/%s" % (log_root.rstrip("/"), namespace, member_id)
                config_path = "%s/%s/%s" % (config_root.rstrip("/"), deployment_config.get("configPathNamespace", "kafka"), member_id)
            instance = {
                "id": member_id, "host": host, "roles": sorted(member.get("roles", [])),
                "node_id": effective.get("nodeId"), "advertised_host": address,
                "data_directory": data_path,
                "log_directory": log_path,
                "config_directory": config_path,
            }
            member_identity = member.get("identity", {}) if isinstance(member.get("identity"), dict) else {}
            if "directoryId" in member_identity:
                instance["directory_id"] = member_identity["directoryId"]
            for logical, output_name in (("clientPort", "client_port"), ("controllerPort", "controller_port")):
                if logical in effective:
                    instance[output_name] = effective[logical]
            listener_projection = listener_runtime_properties(effective, instance)
            if listener_projection["status"] == "PASS":
                instance["listeners"] = listener_projection["listeners"]
                instance["listener_properties"] = listener_projection["properties"]
                instance["listener_fingerprint"] = listener_projection["listenerFingerprint"]
            else:
                instance["listener_findings"] = listener_projection["findings"]
            instances.append(instance)
        projection = {
            "clusterId": (deployment.get("identity", {}) if isinstance(deployment.get("identity"), dict) else {}).get("clusterId"),
            "quorumMode": service.get("configuration", {}).get("quorumMode", "dynamic"),
            "instances": instances,
        }
        projection["runtimeProjectionFingerprint"] = canonical_digest(projection)
        output[deployment_id] = projection
    return output

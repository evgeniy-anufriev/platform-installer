"""Pure Schema Registry projection shared by Core and ordinary Ansible roles."""
import re
from pathlib import PurePosixPath


def resolved_value(configuration, name, default=None):
    value = configuration.get(name, default)
    if isinstance(value, dict) and "state" in value:
        return value.get("value", default) if value.get("state") == "RESOLVED" else default
    return value


def properties_value(value):
    """Escape one Java properties value without interpreting its contents."""
    escaped = (str(value).replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n")
               .replace("\t", "\\t").replace(" ", "\\ ").replace("=", "\\=").replace(":", "\\:"))
    # Kafka Utils.loadProps uses Properties.load(InputStream), whose file
    # encoding is ISO-8859-1. Emit ASCII with Java UTF-16 escapes so credentials
    # retain their exact Unicode value, including supplementary characters.
    result = []
    for char in escaped:
        if ord(char) < 128:
            result.append(char)
        else:
            units = char.encode('utf-16-be')
            result.extend('\\u%04x' % int.from_bytes(units[i:i + 2], 'big') for i in range(0, len(units), 2))
    return ''.join(result)


def registry_projection(members, enabled=True, listener="SSL", http_port=8081,
                        https_port=8082, name="schema-registry", config_root="/etc/schema-registry",
                        log_root="/var/log/schema-registry"):
    """Consume final member values; never evaluate Ansible precedence or secrets."""
    findings, output, groups, occupied, units = [], [], {}, {}, set()

    def issue(code, member, message):
        findings.append({"code": code, "field": "members.%s.schemaRegistry" % member.get("id", "unknown"),
                         "message": message})

    if not isinstance(enabled, bool):
        return {"instances": [], "findings": [{"code": "SCHEMA_REGISTRY_ENABLED_INVALID",
                "field": "schemaRegistryEnabled", "message": "Expected a boolean"}]}
    for member in members:
        host = member.get("host")
        for entry in member.get("listeners", {}).values():
            purpose = entry.get("purpose")
            if ((purpose == "controller" and "controller" in member.get("roles", [])) or
                    (purpose != "controller" and "broker" in member.get("roles", []))):
                occupied.setdefault((host, entry.get("port")), "Kafka")
        if "broker" in member.get("roles", []):
            groups.setdefault(member.get("deployment_id", "kafka"), []).append(member)
    # Even disabled instances have deterministic resources, for ownership-safe removal guards.
    for deployment, brokers in sorted(groups.items()):
        endpoints, protocols = [], set()
        for member in sorted(brokers, key=lambda item: item.get("id", "")):
            entry = member.get("listeners", {}).get(listener)
            if not isinstance(entry, dict) or entry.get("purpose") not in ("client", "interBroker"):
                if enabled:
                    issue("SCHEMA_REGISTRY_LISTENER_INVALID", member, "Selected broker listener is missing or is a controller listener")
                continue
            protocol = entry.get("securityProtocol")
            if protocol not in ("PLAINTEXT", "SSL"):
                if enabled:
                    issue("SCHEMA_REGISTRY_PROTOCOL_UNSUPPORTED", member, "Only PLAINTEXT and SSL broker connections are supported")
                continue
            protocols.add(protocol)
            address = entry.get("advertisedAddress", member.get("advertised_host", member.get("host")))
            if not isinstance(address, str) or not address or re.search(r"[\s/,=]", address):
                issue("SCHEMA_REGISTRY_ADDRESS_INVALID", member, "Invalid advertised broker address")
                continue
            if ":" in address and not address.startswith("["):
                address = "[%s]" % address
            endpoints.append("%s://%s:%s" % (protocol, address, entry.get("port")))
        if enabled and len(protocols) != 1:
            issue("SCHEMA_REGISTRY_PROTOCOL_MISMATCH", brokers[0], "Selected broker listeners must use one security protocol")
        for member in sorted(brokers, key=lambda item: item.get("id", "")):
            settings = member.get("schema_registry", {})
            ports = [settings.get("http_port", http_port), settings.get("https_port", https_port)]
            if any(isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535 for port in ports):
                issue("SCHEMA_REGISTRY_PORT_INVALID", member, "REST ports must be integers from 1 to 65535")
                continue
            if enabled:
                for port in ports:
                    key = (member.get("host"), port)
                    if key in occupied:
                        issue("SCHEMA_REGISTRY_PORT_COLLISION", member, "REST port collides on this host; set member port overrides")
                    occupied[key] = member.get("id")
            address = member.get("advertised_host", member.get("host"))
            if not isinstance(address, str) or not address or re.search(r"[\s/,=]", address):
                issue("SCHEMA_REGISTRY_ADDRESS_INVALID", member, "Invalid Registry advertised address")
                continue
            suffix = str(member.get("id", "")).rsplit("-", 1)[-1]
            if not re.fullmatch(r"[1-9][0-9]*", suffix) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", deployment):
                issue("SCHEMA_REGISTRY_IDENTITY_INVALID", member, "Registry requires a deployment and numeric member identity")
                continue
            unit = "%s@%s-%s.service" % (name, deployment, suffix)
            if (member.get("host"), unit) in units:
                issue("SCHEMA_REGISTRY_UNIT_COLLISION", member, "Registry unit identity collides on this host")
            units.add((member.get("host"), unit))
            config = "%s/%s/%s/%s" % (config_root.rstrip("/"), name, deployment, member["id"])
            logs = "%s/%s/%s/%s" % (log_root.rstrip("/"), name, deployment, member["id"])
            if ".." in str(member["id"]) or not re.fullmatch(r"[A-Za-z0-9_.-]+", str(member["id"])):
                issue("SCHEMA_REGISTRY_IDENTITY_INVALID", member, "Unsafe member identity")
                continue
            # Kafka directories may be 0750 owned by kafka; Registry must not rely on traversing them.
            if any(not path.startswith("/") or ".." in path.split("/") or re.search(r"[\s\n]", path) for path in (config, logs)) or any(root in ('/', '/etc', '/var', '/var/log') for root in (config_root, log_root)):
                issue("SCHEMA_REGISTRY_PATH_INVALID", member, "Registry requires safe absolute member paths")
                continue
            url_host = "[%s]" % address if ":" in address and not address.startswith("[") else address
            output.append({"id": member["id"], "deployment_id": deployment, "host": member["host"],
                           "advertised_host": address, "http_port": ports[0], "https_port": ports[1],
                           "http_url": "http://%s:%s" % (url_host, ports[0]),
                           "https_url": "https://%s:%s" % (url_host, ports[1]),
                           "bootstrap_servers": ",".join(endpoints),
                           "broker_ids": sorted([broker["node_id"] for broker in brokers if isinstance(broker.get("node_id"), int)]),
                           "security_protocol": next(iter(protocols)) if len(protocols) == 1 else "SSL",
                           "config_directory": config, "log_directory": logs,
                           "managed_paths": [config, config + "/pki", logs],
                           "ownership_paths": [config, logs],
                           "guard_paths": sorted(set([config, config + "/pki", logs] +
                               [str(parent) for path in (config, logs) for parent in PurePosixPath(path).parents if str(parent) != "/"])),
                           "unit_name": unit, "unit_path": "/etc/systemd/system/" + unit,
                           "ownership_marker": "# platform-schema-registry-managed: " + unit,
                           "tls_profile": settings.get("tls_profile", member.get("tls_profile", "infrastructure-tls")),
                           "replication_factor": min(3, len(brokers)),
                           "min_insync_replicas": 1 if len(brokers) == 1 else 2})
    return {"instances": output, "findings": findings}


def configuration_registry_findings(services, resolved_topology):
    """Validate already resolved configuration; no target inspection."""
    members = []
    findings = []
    topology = resolved_topology.get("resolvedTopology", {}).get("serviceDeployments", {})
    for deployment, service in sorted(services.items()):
        if service.get("serviceType") != "kafka":
            continue
        config = service.get("configuration", {})
        enabled = resolved_value(config, "schemaRegistryEnabled", False)
        # Older service definitions without this setting retain their previous contract.
        if "schemaRegistryEnabled" not in config or enabled is False:
            continue
        local = []
        for member_id, member in sorted(topology.get(deployment, {}).get("members", {}).items()):
            effective = service.get("members", {}).get(member_id, {}).get("configuration", {})
            local.append({"id": member_id, "deployment_id": deployment, "host": member.get("host"),
                          "roles": member.get("roles", []), "advertised_host": member.get("host"),
                          "listeners": resolved_value(effective, "listeners", resolved_value(config, "listeners", {})),
                          "schema_registry": {"http_port": resolved_value(effective, "schemaRegistryHttpPort", 8081),
                                              "https_port": resolved_value(effective, "schemaRegistryHttpsPort", 8082)}})
        broker_count = sum("broker" in member.get("roles", []) for member in local)
        advanced = resolved_value(config, "advancedConfig", {})
        if isinstance(advanced, dict) and "offsets.topic.replication.factor" in advanced:
            factor = advanced["offsets.topic.replication.factor"]
            if isinstance(factor, bool) or not isinstance(factor, int) or not 1 <= factor <= broker_count:
                findings.append({"code": "SCHEMA_REGISTRY_OFFSETS_TOPIC_REPLICATION_UNSATISFIABLE",
                                 "field": "serviceDeployments.%s.configuration.advancedConfig" % deployment,
                                 "message": "Offsets topic replication factor exceeds the desired broker capacity"})
        projection = registry_projection(local, enabled, resolved_value(config, "schemaRegistryKafkaListener", "SSL"))
        for finding in projection["findings"]:
            finding["field"] = "serviceDeployments.%s.%s" % (deployment, finding["field"])
            findings.append(finding)
        members.extend(projection["instances"])
    seen = set()
    for instance in members:
        for port in (instance["http_port"], instance["https_port"]):
            key = (instance["host"], port)
            if key in seen:
                findings.append({"code": "SCHEMA_REGISTRY_PORT_COLLISION", "field": "serviceDeployments.%s" % instance["deployment_id"],
                                 "message": "Registry ports collide across deployments on this host"})
            seen.add(key)
    return findings

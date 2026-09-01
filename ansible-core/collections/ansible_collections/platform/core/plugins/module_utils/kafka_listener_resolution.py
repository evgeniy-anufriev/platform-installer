from __future__ import absolute_import, division, print_function

__metaclass__ = type

try:
    from .project_validation import canonical_digest
except ImportError:
    from project_validation import canonical_digest


SUPPORTED_PURPOSES = ("client", "interBroker", "controller")
SUPPORTED_PROTOCOLS = ("PLAINTEXT", "SSL")


def _finding(code, path, message, details=None):
    finding = {"code": code, "path": path, "message": message}
    if details:
        finding["safeDetails"] = details
    return finding


def _address(listener, member):
    bind = listener.get("bindAddress", "0.0.0.0")
    advertised = listener.get("advertisedAddress", member.get("advertised_host"))
    return bind, advertised


def _legacy_listeners(member):
    listeners = {}
    if "broker" in member.get("roles", []) and member.get("client_port") is not None:
        listeners["CLIENT"] = {
            "name": "CLIENT", "purpose": "client", "securityProtocol": "PLAINTEXT",
            "port": member["client_port"]
        }
    if "controller" in member.get("roles", []) and member.get("controller_port") is not None:
        listeners["CONTROLLER"] = {
            "name": "CONTROLLER", "purpose": "controller", "securityProtocol": "PLAINTEXT",
            "port": member["controller_port"]
        }
    return listeners


def normalize_listeners(configuration, member, path="configuration.listeners"):
    """Normalize named listeners without reading Ansible variables or precedence."""
    configuration = configuration if isinstance(configuration, dict) else {}
    named = configuration.get("listeners")
    legacy = _legacy_listeners(member)
    if named is None:
        return {"status": "PASS", "findings": [], "listeners": legacy, "source": "legacy"}
    if not isinstance(named, dict) or not named:
        return {"status": "BLOCKED", "findings": [_finding("LISTENERS_INVALID", path, "listeners must be a non-empty object")], "listeners": {}}

    listeners = {}
    findings = []
    for name, raw in sorted(named.items()):
        item_path = "%s.%s" % (path, name)
        if not isinstance(name, str) or not name or not name.replace("_", "").replace("-", "").isalnum() or name.upper() != name:
            findings.append(_finding("LISTENER_NAME_INVALID", item_path, "Listener names must be explicit uppercase identifiers"))
            continue
        if not isinstance(raw, dict):
            findings.append(_finding("LISTENER_INVALID", item_path, "Listener must be an object"))
            continue
        listener = dict(raw)
        listener["name"] = name
        purpose = listener.get("purpose")
        protocol = listener.get("securityProtocol")
        port = listener.get("port")
        if purpose not in SUPPORTED_PURPOSES:
            findings.append(_finding("LISTENER_PURPOSE_INVALID", item_path + ".purpose", "Unsupported listener purpose"))
        if protocol not in SUPPORTED_PROTOCOLS:
            findings.append(_finding("LISTENER_PROTOCOL_INVALID", item_path + ".securityProtocol", "Only PLAINTEXT and SSL are supported"))
        if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
            findings.append(_finding("LISTENER_PORT_INVALID", item_path + ".port", "Listener port must be an integer from 1 through 65535"))
        listeners[name] = listener

    if named and ("clientPort" in configuration or "controllerPort" in configuration):
        legacy_equivalent = legacy
        comparable = {key: {field: value for field, value in val.items() if field in ("name", "purpose", "securityProtocol", "port")} for key, val in listeners.items()}
        expected = {key: {field: value for field, value in val.items() if field in ("name", "purpose", "securityProtocol", "port")} for key, val in legacy_equivalent.items()}
        if comparable != expected:
            findings.append(_finding("LEGACY_NAMED_LISTENER_CONFLICT", path, "Legacy ports and named listeners are two conflicting desired-state sources"))
    if findings:
        return {"status": "BLOCKED", "findings": findings, "listeners": {}}
    ports = {}
    for name, listener in listeners.items():
        if isinstance(listener.get("port"), int) and not isinstance(listener.get("port"), bool):
            ports.setdefault(listener["port"], []).append(name)
    for port, names in sorted(ports.items()):
        if len(names) > 1:
            findings.append(_finding("LISTENER_PORT_COLLISION", "%s.%s.port" % (path, names[0]), "Listener ports must be unique within a logical member", {"port": port, "listeners": names}))
    if findings:
        return {"status": "BLOCKED", "findings": findings, "listeners": {}}
    return {"status": "PASS", "findings": [], "listeners": listeners, "source": "named"}


def project_member_listeners(configuration, member):
    normalized = normalize_listeners(configuration, member)
    if normalized["status"] != "PASS":
        return normalized
    projected = []
    for name, listener in normalized["listeners"].items():
        purpose = listener["purpose"]
        roles = member.get("roles", [])
        if purpose == "controller" and "controller" not in roles:
            continue
        if purpose in ("client", "interBroker") and "broker" not in roles:
            continue
        bind, advertised = _address(listener, member)
        item = dict(listener)
        item["bindAddress"] = bind
        item["advertisedAddress"] = advertised
        projected.append(item)
    projected.sort(key=lambda item: item["name"])
    return {"status": "PASS", "findings": [], "listeners": projected, "source": normalized["source"]}


def listener_runtime_properties(configuration, member):
    projected = project_member_listeners(configuration, member)
    if projected["status"] != "PASS":
        return projected
    listeners = projected["listeners"]
    if not listeners:
        return {"status": "BLOCKED", "findings": [_finding("LISTENER_ROLE_PROJECTION_EMPTY", "configuration.listeners", "No listener applies to this member role")], "properties": {}}
    properties = {
        "listeners": ",".join("%s://%s:%s" % (item["name"], item["bindAddress"], item["port"]) for item in listeners),
        "advertised.listeners": ",".join("%s://%s:%s" % (item["name"], item["advertisedAddress"], item["port"]) for item in listeners),
        "listener.security.protocol.map": ",".join("%s:%s" % (item["name"], item["securityProtocol"]) for item in listeners),
    }
    controller = [item["name"] for item in listeners if item["purpose"] == "controller"]
    inter_broker = [item["name"] for item in listeners if item["purpose"] == "interBroker"]
    if "controller" in member.get("roles", []) and not controller:
        return {"status": "BLOCKED", "findings": [_finding("CONTROLLER_LISTENER_REQUIRED", "configuration.listeners", "Controller member requires a controller listener")], "properties": {}}
    if "broker" in member.get("roles", []) and not inter_broker and projected["source"] == "legacy":
        inter_broker = [item["name"] for item in listeners if item["name"] == "CLIENT"]
    if "broker" in member.get("roles", []) and not inter_broker:
        return {"status": "BLOCKED", "findings": [_finding("INTER_BROKER_LISTENER_REQUIRED", "configuration.listeners", "Broker member requires an interBroker listener")], "properties": {}}
    if controller:
        properties["controller.listener.names"] = ",".join(controller)
    if inter_broker:
        properties["inter.broker.listener.name"] = inter_broker[0]
    return {"status": "PASS", "findings": [], "properties": properties, "listeners": listeners,
            "listenerFingerprint": canonical_digest(listeners)}

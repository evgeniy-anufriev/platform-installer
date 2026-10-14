"""Read-only application contract checks. Ansible owns composition and templating."""
import hashlib
import json
import os
import re

try:
    from .project_validation import canonical_digest
    from .schema_validation import SchemaValidator
    from .kafka_listener_resolution import project_member_listeners
except ImportError:
    from project_validation import canonical_digest
    from schema_validation import SchemaValidator
    from kafka_listener_resolution import project_member_listeners

CONTRACT = "platform.installer/project-desired-state/v3alpha1"
ID = re.compile(r"^[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*$")
COMPOSE_PROJECT = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
REF = re.compile(r"^([a-z][a-z0-9-]*)@([0-9]+\.[0-9]+\.[0-9]+)$")


def finding(code, field):
    return {"apiVersion": "platform.installer/finding/v1alpha1", "kind": "Finding",
            "code": code, "field": field, "category": "application-libraries",
            "status": "BLOCKED", "safeMessage": "Application library input violates the declared contract"}


def infrastructure_state(desired):
    return {key: value for key, value in desired.items() if key != "applicationLibraryDeployments"}


def schema_version(desired, contract):
    if "applicationLibraryDeployments" in desired:
        if contract != CONTRACT:
            raise ValueError("Application library contract must be selected explicitly")
        return "v3alpha1"
    if contract not in (None, "", "platform.installer/project-desired-state/v2alpha1", CONTRACT):
        raise ValueError("Unsupported desired state contract")
    return "v2alpha1"


def checked_file(root, relative):
    if not isinstance(relative, str) or not relative or "\\" in relative or relative.startswith("/"):
        raise ValueError("Invalid package path")
    parts = relative.split("/")
    if any(part in ("", ".", "..") or ":" in part for part in parts):
        raise ValueError("Invalid package component")
    current = os.path.abspath(root)
    for part in parts:
        current = os.path.join(current, part)
        if os.path.islink(current):
            raise ValueError("Package symlinks are forbidden")
    if os.path.commonpath((os.path.realpath(root), os.path.realpath(current))) != os.path.realpath(root):
        raise ValueError("Package path escapes project")
    if not os.path.isfile(current) or os.path.getsize(current) > 1024 * 1024:
        raise ValueError("Package file missing or oversized")
    return current


def nonsecret_values(value, field, findings):
    """User-defined names and assignments are unrestricted; private keys are runtime material."""
    if isinstance(value, dict):
        for key, item in value.items():
            path = field + "." + str(key)
            nonsecret_values(item, path, findings)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            nonsecret_values(item, field + ".%s" % index, findings)
    elif isinstance(value, str) and "PRIVATE KEY-----" in value:
        findings.append(finding("APPLICATION_PLAINTEXT_FORBIDDEN", field))


def package_inputs(root):
    """Include all package bytes (including library .env) in existing revision hashing."""
    paths = []
    for folder in ("application-packages", "library-packages"):
        directory = os.path.join(root, folder)
        if not os.path.exists(directory):
            continue
        if os.path.islink(directory):
            raise ValueError("Package root must not be a symlink")
        for current, dirs, files in os.walk(directory):
            if any(os.path.islink(os.path.join(current, name)) for name in dirs):
                raise ValueError("Package directory symlink")
            dirs.sort()
            for name in sorted(files):
                relative = os.path.relpath(os.path.join(current, name), root).replace("\\", "/")
                checked_file(root, relative)
                paths.append(relative)
                if len(paths) > 512:
                    raise ValueError("Package file limit exceeded")
    return paths


def load_package(root, reference, kind, loader, validator, inputs=None):
    match = REF.fullmatch(reference or "")
    if not match:
        raise ValueError("Invalid exact package reference")
    name, version = match.groups()
    folder = "%s-packages/%s/%s" % (kind, name, version)
    manifest_path = folder + "/" + kind + ".yml"
    manifest = loader(checked_file(root, manifest_path))
    schema = os.path.join(validator.schema_root, "application-libraries", "v1alpha1", "package.schema.json")
    if validator.validate(manifest, schema):
        raise ValueError("Package manifest shape invalid")
    if (manifest["name"], manifest["version"], manifest["kind"]) != (name, version, kind.title() + "Package"):
        raise ValueError("Package identity mismatch")
    defaults_path = "roles/%s_%s/defaults/main.yml" % (kind, name)
    if defaults_path not in manifest["files"]:
        raise ValueError("Defaults absent from allowlist")
    listed = set(manifest["files"]) | {kind + ".yml"}
    discovered = set()
    digest = []
    for relative in package_inputs(root) if inputs is None else inputs:
        if not relative.startswith(folder + "/"):
            continue
        short = relative[len(folder) + 1:]
        discovered.add(short)
        path = checked_file(root, relative)
        with open(path, "rb") as stream:
            content = stream.read()
        digest.append([short, hashlib.sha256(content).hexdigest()])
    if discovered != listed:
        raise ValueError("Package allowlist mismatch")
    defaults = loader(checked_file(root, folder + "/" + defaults_path))
    key = "platform_%s_definition" % kind
    if set(defaults) != {key}:
        raise ValueError("Package defaults namespace invalid")
    definition = defaults[key]
    if validator.validate(definition, os.path.join(validator.schema_root, "application-libraries", "v1alpha1", kind + ".schema.json")):
        raise ValueError("Package defaults shape invalid")
    if (definition["name"], definition["version"]) != (name, version):
        raise ValueError("Defaults identity mismatch")
    if kind == "library" and "files/.env" in discovered:
        with open(checked_file(root, folder + "/files/.env"), encoding="utf-8") as stream:
            env_keys = set()
            for line in stream:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                match_env = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", line)
                if not match_env or match_env[1] in env_keys or match_env[1] == "SERVER_ID":
                    raise ValueError("Library dotenv contract invalid")
                env_keys.add(match_env[1])
    return {"name": name, "version": version, "defaultsPath": os.path.join(root, folder, defaults_path),
            "definition": definition, "digest": canonical_digest(sorted(digest)), "logicalPath": folder,
            "render": manifest.get("render", {}), "files": manifest["files"]}


def invocation_package_loader(root, loader, validator):
    """Share checked inputs and read-only packages only within one preparation."""
    inputs = None
    packages = {}

    def load(reference, kind):
        nonlocal inputs
        key = (kind, reference)
        if key not in packages:
            if inputs is None:
                inputs = package_inputs(root)
            packages[key] = load_package(root, reference, kind, loader, validator, inputs)
        return packages[key]

    return load


def prepare(root, desired, memberships, contract, loader, contracts_root):
    schema_version(desired, contract)
    validator = SchemaValidator(contracts_root)
    # Kept here for callers/tests: no package/defaults is templated before validation.
    deployments = desired.get("applicationLibraryDeployments", {})
    findings = validator.validate(deployments, os.path.join(contracts_root, "application-libraries", "v1alpha1", "deployments.schema.json"))
    for host, membership in sorted(memberships.items()):
        findings.extend(validator.validate(membership, os.path.join(contracts_root, "application-libraries", "v1alpha1", "membership.schema.json")))
        for library in membership if isinstance(membership, dict) else []:
            if library not in deployments:
                findings.append(finding("APPLICATION_LIBRARY_UNKNOWN", "hosts.%s.%s" % (host, library)))
    if findings:
        return {"jobs": [], "findings": findings}
    jobs = []
    package = invocation_package_loader(root, loader, validator)
    for library_id, deployment in sorted(deployments.items()):
        field = "applicationLibraryDeployments." + library_id
        try:
            library = package(deployment["libraryRef"], "library")
            selected = deployment["applications"]
            slots = library["definition"]["slots"]
            if set(selected) - set(slots) or any(slot.get("required", False) and name not in selected for name, slot in slots.items()):
                raise ValueError("Recipe slots mismatch")
            placements = [host for host, membership in sorted(memberships.items()) if library_id in membership]
            if not placements:
                findings.append(finding("APPLICATION_LIBRARY_PLACEMENT_MISSING", field))
            app_names = set()
            for slot_id in sorted(selected):
                slot = slots[slot_id]
                application = package(slot["applicationRef"], "application")
                if application["name"] in app_names:
                    raise ValueError("Duplicate application definition")
                app_names.add(application["name"])
                for host in placements:
                    jobs.append({"libraryId": library_id, "slotId": slot_id, "hostId": host,
                                 "library": library, "application": application,
                                 "deployment": deployment, "instance": selected[slot_id],
                                 "slot": slot, "hostOverride": memberships[host][library_id].get("overrides", {})})
        except (ValueError, OSError, KeyError, TypeError):
            findings.append(finding("APPLICATION_PACKAGE_INVALID", field))
    return {"jobs": [] if findings else jobs, "findings": findings}


def _value(configuration, name):
    item = configuration.get(name, {})
    return item.get("value") if isinstance(item, dict) and item.get("state") == "RESOLVED" else None


def resolve_connection(deployment_id, declaration, selector, desired, configuration, catalog, hosts):
    """Use effective provider settings; never use a catalog port as effective config."""
    deployment = desired["serviceDeployments"][deployment_id]
    service_type = deployment["serviceType"]
    effective = configuration.get("services", {}).get(deployment_id, {})
    members = deployment.get("members", {})
    purpose = declaration.get("purpose", "client")
    targets = []
    if service_type == "kafka":
        if not selector:
            raise ValueError("Kafka selector required")
        listeners = _value(effective.get("configuration", {}), "listeners")
        for member_id, member in sorted(members.items()):
            member_settings = effective.get("members", {}).get(member_id, {}).get("configuration", {})
            member_listeners = _value(member_settings, "listeners") or listeners
            projected_member = dict(member)
            projected_member.setdefault("advertised_host", hosts[member["host"]]["ansibleHost"])
            projection = project_member_listeners({"listeners": member_listeners}, projected_member)
            if projection["status"] != "PASS":
                raise ValueError("Kafka listener unresolved")
            # An explicitly selected inter-broker listener serves the same broker
            # protocol; controller listeners are never application connections.
            selected = [item for item in projection["listeners"] if item["name"] == selector
                        and item["purpose"] in {"client", "interBroker"} and "broker" in member.get("roles", [])]
            if "broker" in member.get("roles", []) and not selected:
                raise ValueError("Kafka client listener missing")
            for item in selected:
                targets.append({"hostId": member["host"], "memberId": member_id, "address": item["advertisedAddress"],
                                "port": item["port"], "protocol": "tcp", "tls": item["securityProtocol"] == "SSL"})
    else:
        mapping = {"postgresql": {"client": ("port", "tcp")}, "redis": {"client": ("redisPort", "tcp"), "sentinel": ("sentinelPort", "tcp")},
                   "clickhouse": {"client": ("port", "https"), "native": ("nativePort", "tcp")}, "vault": {"client": ("port", "https")}}
        eligible = {key: value for key, value in mapping.get(service_type, {}).items()
                    if key == purpose and (not declaration.get("protocol") or value[1] == declaration["protocol"])}
        if selector:
            eligible = {key: value for key, value in eligible.items() if key == selector}
        if len(eligible) != 1:
            raise ValueError("Connection selector ambiguous or unsupported")
        selector, (setting, protocol) = next(iter(eligible.items()))
        allocated = {}
        if service_type in {'redis', 'clickhouse'}:
            # Import the provider's pure allocation function, also consumed by
            # its infrastructure role. Do not copy slot arithmetic here.
            if service_type == 'redis':
                from ansible_collections.platform.redis.plugins.module_utils.member_projection import project_members
                bases = {'port': 'redisPort', 'sentinel_port': 'sentinelPort'}
            else:
                from ansible_collections.platform.clickhouse.plugins.module_utils.member_projection import project_members
                bases = {'port': 'port', 'native_port': 'nativePort'}
            settings = {key: _value(effective.get('configuration', {}), value) for key, value in bases.items()
                        if _value(effective.get('configuration', {}), value) is not None}
            required = {'port', 'sentinel_port'} if service_type == 'redis' else {'port', 'native_port'} if purpose == 'native' else {'port'}
            if not required <= settings.keys() or any(not isinstance(port, int) or isinstance(port, bool) for port in settings.values()):
                raise ValueError('Effective connection port unavailable')
            inputs = [dict(value, id=key) for key, value in members.items()]
            if service_type == 'clickhouse':
                for item in inputs:
                    override = _value(effective.get('members', {}).get(item['id'], {}).get('configuration', {}), 'port')
                    if override is not None:
                        item['port'] = override
            allocated = {item['id']: item for item in project_members(inputs, deployment_id, settings)}
        for member_id, member in sorted(members.items()):
            if service_type == "postgresql" and "database" not in member.get("roles", []):
                continue
            if service_type == 'redis' and ('sentinel' if purpose == 'sentinel' else 'redis') not in member.get('roles', []):
                continue
            if service_type == 'clickhouse' and 'server' not in member.get('roles', []):
                continue
            member_effective = effective.get("members", {}).get(member_id, {}).get("configuration", {})
            # Multiple local instances require the provider's allocation projection,
            # not an invented copy of its slot/ordinal algorithm in this resolver.
            port = _value(member_effective, setting)
            if allocated:
                port = allocated[member_id]['sentinel_port' if purpose == 'sentinel' else 'redis_port' if service_type == 'redis' else 'native_port' if purpose == 'native' else 'https_port']
            if port is None:
                port = _value(effective.get("configuration", {}), setting)
            if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
                raise ValueError("Effective connection port unavailable")
            host = member["host"]
            targets.append({"hostId": host, "memberId": member_id, "address": hosts[host]["ansibleHost"],
                            "port": port, "protocol": protocol, "tlsProfileRef": _value(member_effective, "tlsProfile") or _value(effective.get("configuration", {}), "tlsProfile")})
    if not targets:
        raise ValueError("Connection targets unavailable")
    connection = {"deploymentRef": deployment_id, "serviceType": service_type, "connectionRef": selector, "targets": targets}
    if service_type == 'redis' and purpose == 'sentinel':
        connection['masterName'] = min(allocated.values(), key=lambda member: member['slot'])['id']
    return connection


def project(rows, desired, configuration, catalog, hosts, project_id="ansible-project"):
    findings, libraries, ports = [], {}, set()
    if not isinstance(project_id, str) or not ID.fullmatch(project_id):
        return {"apiVersion": "platform.installer/application-libraries/v1alpha1", "status": "BLOCKED", "libraries": {},
                "findings": [finding("APPLICATION_PROJECT_ID_INVALID", "project.id")]}
    for row in rows:
        library_id, app_id, host = row["libraryId"], row["instanceId"], row["hostId"]
        compose_project = "%s-%s-%s-%s" % (project_id, library_id, app_id, host)
        if not COMPOSE_PROJECT.fullmatch(compose_project):
            findings.append(finding("APPLICATION_COMPOSE_PROJECT_INVALID", "applicationLibraryDeployments." + library_id + ".placements." + host + ".composeProject"))
            continue
        field = "applicationLibraryDeployments.%s.applications.%s" % (library_id, row["slotId"])
        settings = row["settings"]
        if app_id != row["applicationName"] + "-" + library_id or host not in hosts or not ID.fullmatch(app_id) or len(app_id) > 128:
            findings.append(finding("APPLICATION_IDENTITY_INVALID", field))
        for section in ("parameters", "environment", "command"):
            nonsecret_values(settings.get(section, {}), field + "." + section, findings)
        nonsecret_values(settings.get("endpoint", {}), field + ".endpoint", findings)
        for resource_id, resource in row["resources"].items():
            nonsecret_values(resource.get("parameters", {}), field + ".resources." + resource_id + ".parameters", findings)
        declared_accounts = settings.get("accounts", {})
        accounts = declared_accounts
        secret_bindings = settings.get("provisioner", {}).get("secret_bindings", {})
        skipped = {name for name, declaration in row['connections'].items()
                   if not row['bindings'].get(declaration['library_binding'], {}).get('deploymentRef')}
        accounts = {name: account for name, account in accounts.items() if name not in skipped}
        secret_bindings = {name: binding for name, binding in secret_bindings.items()
                           if binding['source'].get('account') not in skipped}
        agent_required = bool(secret_bindings)
        if (accounts or agent_required) and settings.get("provisioner", {}).get("type") != "vault-agent":
            findings.append(finding("APPLICATION_PROVISIONER_REQUIRED", field))
        for name, account in declared_accounts.items():
            nonsecret_values(account.get("grants", []), field + ".accounts." + name + ".grants", findings)
            for credential, descriptor in account["credentials"].items():
                source = descriptor["source"]
                if credential == "password" and source["kind"] == "literal":
                    findings.append(finding("APPLICATION_PLAINTEXT_FORBIDDEN", field + ".accounts." + name))
                if source["kind"] == "runtime_secret_ref" and not ID.fullmatch(source["ref"]):
                    findings.append(finding("APPLICATION_SECRET_REF_INVALID", field + ".accounts." + name))
                if account["mode"] == "existing" and source["kind"] == "generated":
                    findings.append(finding("APPLICATION_EXISTING_CREDENTIAL_INVALID", field + ".accounts." + name))
        for name, descriptor in row["sharedSecrets"].items():
            if descriptor["source"]["kind"] == "literal":
                findings.append(finding("APPLICATION_PLAINTEXT_FORBIDDEN", field + ".shared_secrets." + name))
        declared_env = settings.get("environment", {})
        if set(secret_bindings).intersection(declared_env) or set(secret_bindings).intersection(row["identityNames"]):
            findings.append(finding("APPLICATION_ENVIRONMENT_CONFLICT", field))
        if any(name in declared_env for name in row["identityNames"]) or "SERVER_ID" in declared_env:
            findings.append(finding("APPLICATION_IDENTITY_OVERRIDE", field))
        connections = {}
        for name, declaration in row["connections"].items():
            binding = row["bindings"].get(declaration["library_binding"], {})
            reference = binding.get("deploymentRef")
            if not reference:
                if name in accounts:
                    findings.append(finding("APPLICATION_PROVIDER_REQUIRED", field + ".connections." + name))
                continue
            try:
                service_type = desired["serviceDeployments"][reference]["serviceType"]
                selector = row["connectionDefaults"].get(service_type, {}).get("connectionRef")
                connections[name] = resolve_connection(reference, declaration, selector, desired, configuration, catalog, hosts)
            except (ValueError, KeyError, TypeError):
                findings.append(finding("APPLICATION_CONNECTION_INVALID", field + ".connections." + name))
        for name in accounts:
            if name not in connections:
                findings.append(finding("APPLICATION_ACCOUNT_PROVIDER_MISSING", field + ".accounts." + name))
            if name in connections and connections[name]["serviceType"] == "kafka":
                findings.append(finding("APPLICATION_ACCOUNT_CAPABILITY_UNSUPPORTED", field + ".accounts." + name))
        if (accounts or agent_required) and "vault" not in connections:
            findings.append(finding("APPLICATION_VAULT_REQUIRED", field))
        for binding_id, binding in row["bindings"].items():
            if binding.get("deploymentRef") and binding["deploymentRef"] not in desired.get("serviceDeployments", {}):
                findings.append(finding("APPLICATION_BINDING_UNKNOWN", field + ".bindings." + binding_id))
            if binding.get("profileRef") and binding["profileRef"] not in desired.get("tlsProfiles", {}):
                findings.append(finding("APPLICATION_PKI_UNKNOWN", field + ".bindings." + binding_id))
        for resource_id, resource in row["resources"].items():
            binding = row["bindings"].get(resource["binding"], {})
            provider = desired.get("serviceDeployments", {}).get(binding.get("deploymentRef"), {})
            if provider.get("serviceType") != resource["kind"].split(".")[0]:
                findings.append(finding("APPLICATION_RESOURCE_PROVIDER_INVALID", field + ".resources." + resource_id))
        for variable, binding in secret_bindings.items():
            source = binding["source"]
            if source.get("account") and (source["account"] not in accounts or source.get("field") not in accounts[source["account"]]["credentials"]):
                findings.append(finding("APPLICATION_SECRET_BINDING_INVALID", field + ".secret_bindings." + variable))
            if source.get("library_secret") and source["library_secret"] not in row["sharedSecrets"]:
                findings.append(finding("APPLICATION_SECRET_BINDING_INVALID", field + ".secret_bindings." + variable))
        endpoint = settings.get("endpoint", {})
        if endpoint.get("enabled") and (endpoint.get("listener") not in settings.get("ports", {}) or endpoint.get("endpoint_group") not in desired.get("endpointGroups", {})):
            findings.append(finding("APPLICATION_ENDPOINT_INVALID", field + ".endpoint"))
        runtime_ref = row["runtimeRef"]
        runtime = desired.get("serviceDeployments", {}).get(runtime_ref, {})
        if runtime.get("serviceType") != "docker" or not (runtime_ref in hosts.get(host, {}).get("platformDeployments", {}) or any(member.get("host") == host for member in runtime.get("members", {}).values())):
            findings.append(finding("APPLICATION_DOCKER_PLACEMENT_INVALID", field + ".runtimeRef"))
        for listener, port in settings.get("ports", {}).items():
            key = (host, runtime_ref, port["published"])
            if key in ports:
                findings.append(finding("APPLICATION_PORT_COLLISION", field + ".ports." + listener))
            ports.add(key)
        library = libraries.setdefault(library_id, {"libraryRef": row["libraryRef"], "packages": {}, "instances": {}, "resources": row["resources"], "sharedSecretRequirements": row["sharedSecrets"]})
        library["packages"][row["applicationName"]] = row["packageIdentity"]
        instance = library["instances"].setdefault(app_id, {"applicationName": row["applicationName"], "slotId": row["slotId"], "placements": {},
                                                           "connections": connections, "credentialRequirements": accounts,
                                                           "identityEnvironment": {name: app_id for name in row["identityNames"]},
                                                           "agentRequired": agent_required, "executionPrerequisites": ["A2_IMAGE_DELIVERY", "A4_PROVIDER_PROVISIONING"] if accounts or agent_required else ["A2_IMAGE_DELIVERY"]})
        if library['resources'] != row['resources'] or library['sharedSecretRequirements'] != row['sharedSecrets']:
            findings.append(finding('APPLICATION_HOST_RESOURCE_CONFLICT', field))
        if instance['connections'] != connections:
            findings.append(finding('APPLICATION_HOST_CONNECTION_CONFLICT', field))
        if instance["credentialRequirements"] != accounts:
            findings.append(finding("APPLICATION_HOST_CREDENTIAL_CONFLICT", field))
        if instance['agentRequired'] != agent_required or ('secretBindings' in instance and instance['secretBindings'] != secret_bindings):
            findings.append(finding('APPLICATION_HOST_SECRET_BINDING_CONFLICT', field))
        instance["imageRequirement"] = {"image": settings.get("image"), "artifactType": "container-image",
                                        "sourcePolicy": "REPOSITORY_THEN_OFFLINE"}
        instance["secretBindings"] = secret_bindings
        instance["runtimeSecretRequirements"] = sorted({source["ref"] for account in accounts.values()
                                                        for credential in account["credentials"].values()
                                                        for source in [credential["source"]] if source["kind"] == "runtime_secret_ref"})
        instance["approle"] = {"bind_secret_id": False, "token_bound_cidrs": "RUNTIME_HOST_SUBNET_AND_LOOPBACK"} if agent_required else None
        # Settings safe projection is explicit: do not send raw defaults/hostvars to callers.
        instance["placements"][host] = {"SERVER_ID": host, "runtimeRef": runtime_ref, "command": settings.get("command", []),
                                          "imageRequirement": {"image": settings.get("image"), "artifactType": "container-image"},
                                          "origin": {"resolution": "ANSIBLE", "precision": "RESOLUTION_SCOPE",
                                                     "applicationPackage": row['applicationName'] + '@' + row['applicationVersion'],
                                                     "libraryPackage": row['libraryRef'], "host": host},
                                          "parameters": settings.get("parameters", {}), "environment": settings.get("environment", {}),
                                          "ports": settings.get("ports", {}), "endpoint": settings.get("endpoint", {}),
                                          "containerName": "%s-%s-%s" % (project_id, app_id, host),
                                          "composeProject": compose_project,
                                          "runtimePath": "applications/%s/%s/%s/%s" % (project_id, library_id, app_id, host),
                                          "libraryEnvPath": "applications/%s/%s/%s/.env" % (project_id, library_id, host)}
    for library in libraries.values():
        used = {binding["source"]["library_secret"] for instance in library["instances"].values()
                for binding in instance.get("secretBindings", {}).values() if "library_secret" in binding["source"]}
        library["sharedSecretRequirements"] = {key: value for key, value in library["sharedSecretRequirements"].items() if key in used}
    if findings:
        libraries = {}  # Never return potentially unsafe settings on invalid input.
    return {"apiVersion": "platform.installer/application-libraries/v1alpha1", "status": "BLOCKED" if findings else "PASS",
            "libraries": libraries, "findings": findings}


def validate_public_projection(projection):
    """Final boundary check of free fields; typed credential descriptors remain intact."""
    findings = []
    for library_id, library in projection.get("libraries", {}).items():
        field = "applicationLibraries." + library_id
        for resource_id, resource in library.get("resources", {}).items():
            nonsecret_values(resource.get("parameters", {}), field + ".resources." + resource_id + ".parameters", findings)
        for instance_id, instance in library.get("instances", {}).items():
            prefix = field + ".instances." + instance_id
            for account_id, account in instance.get("credentialRequirements", {}).items():
                nonsecret_values(account.get("grants", []), prefix + ".accounts." + account_id + ".grants", findings)
            for host_id, placement in instance.get("placements", {}).items():
                for section in ("parameters", "environment", "command", "endpoint"):
                    nonsecret_values(placement.get(section, {}), prefix + ".placements." + host_id + "." + section, findings)
    return findings

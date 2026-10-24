"""Read-only application contract checks. Ansible owns composition and templating."""
import hashlib
import json
import os
import re

try:
    from .project_validation import canonical_digest
    from .schema_validation import SchemaValidator
    from .kafka_listener_resolution import project_member_listeners
    from .kafka_schema_registry import registry_projection
    from .application_images import registry_request
    from .application_connections import provided_connections, application_connection, enabled, active_script, script_secret_source, connection_callback
except ImportError:
    from project_validation import canonical_digest
    from schema_validation import SchemaValidator
    from kafka_listener_resolution import project_member_listeners
    from kafka_schema_registry import registry_projection
    from application_images import registry_request
    from application_connections import provided_connections, application_connection, enabled, active_script, script_secret_source, connection_callback

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
    if not os.path.isfile(current):
        raise ValueError("Package file missing")
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
    input_paths = package_inputs(root) if inputs is None else inputs
    listed = {kind + ".yml"}
    for entry in manifest["files"]:
        if entry.endswith("/"):
            prefix = entry[:-1]
            if not prefix or not all(part not in ("", ".", "..") and ":" not in part for part in prefix.split("/")):
                raise ValueError("Invalid package directory")
            listed.update(relative[len(folder) + 1:] for relative in input_paths
                          if relative.startswith(folder + "/" + entry))
        else:
            listed.add(entry)
    discovered = set()
    digest = []
    for relative in input_paths:
        if not relative.startswith(folder + "/"):
            continue
        short = relative[len(folder) + 1:]
        discovered.add(short)
        path = checked_file(root, relative)
        checksum = hashlib.sha256()
        with open(path, "rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                checksum.update(chunk)
        digest.append([short, checksum.hexdigest()])
    if discovered != listed:
        raise ValueError("Package allowlist mismatch")
    scripts = manifest.get("scripts", [])
    if len({script["id"] for script in scripts}) != len(scripts):
        raise ValueError("Duplicate package script identity")
    for script in scripts:
        if script["source"] not in discovered or script["source"].endswith("/"):
            raise ValueError("Package script is not allowlisted")
        checked_file(root, folder + "/" + script["source"])
        for argument in script.get("argv", []):
            if not isinstance(argument, dict):
                continue
            source = argument["valueFrom"]
            expected = ({"valueFrom", "name"} if source in ("parameter", "endpoint", "connection", "library_secret", "provided_connection") else
                        {"valueFrom", "application"} if source == "placement_https" else {"valueFrom"})
            if source == 'endpoint' and script['phase'] == 'connection_apply' and set(argument) == {'valueFrom'}:
                expected = {'valueFrom'}
            if set(argument) - {'field'} != expected or ('field' in argument and source not in ('connection', 'provided_connection')):
                raise ValueError("Package script reference invalid")
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
            "render": manifest.get("render", {}), "scripts": scripts, "files": sorted(listed - {kind + ".yml"}),
            "directoryEntries": [entry for entry in manifest["files"] if entry.endswith("/")]}


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
            if set(deployment.get('provided_connections', {})) - set(library['definition'].get('provided_connections', {})):
                raise ValueError('Unknown provided connection override')
            for resource in deployment.get("resources", {}).values():
                restore = resource.get("parameters", {}).get("restore_on_create")
                if restore is None:
                    continue
                if (resource["kind"] != "postgresql.database" or resource.get("mode", "managed") != "managed"
                        or restore["source"] not in library["files"]):
                    raise ValueError("Package database restore invalid")
                checksum = hashlib.sha256()
                with open(checked_file(root, library["logicalPath"] + "/" + restore["source"]), "rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        checksum.update(chunk)
                if checksum.hexdigest() != restore["sha256"]:
                    raise ValueError("Package database restore digest mismatch")
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
                    if 'connections' in memberships[host][library_id].get('overrides', {}):
                        raise ValueError('Host connection override is not supported')
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
    if service_type == 'redis' and selector in ('client', 'sentinel'):
        purpose = selector
    targets = []
    if service_type == 'kafka' and purpose == 'schema-registry':
        if _value(effective.get('configuration', {}), 'schemaRegistryEnabled') is not True:
            raise ValueError('Schema Registry disabled')
        inputs = []
        for member_id, member in sorted(members.items()):
            config = effective.get('members', {}).get(member_id, {}).get('configuration', {})
            inputs.append(dict(member, id=member_id, deployment_id=deployment_id,
                advertised_host=hosts[member['host']]['ansibleHost'],
                listeners=_value(config, 'listeners') or _value(effective.get('configuration', {}), 'listeners'),
                schema_registry={'http_port': _value(config, 'schemaRegistryHttpPort') or _value(effective.get('configuration', {}), 'schemaRegistryHttpPort'),
                                 'https_port': _value(config, 'schemaRegistryHttpsPort') or _value(effective.get('configuration', {}), 'schemaRegistryHttpsPort'),
                                 'tls_profile': _value(config, 'tlsProfile') or _value(effective.get('configuration', {}), 'tlsProfile')}))
        projection = registry_projection(inputs, listener=_value(effective.get('configuration', {}), 'schemaRegistryKafkaListener'))
        if projection['findings']:
            raise ValueError('Schema Registry unresolved')
        targets = [{'hostId': item['host'], 'memberId': item['id'], 'address': item['advertised_host'],
                    'port': item['https_port'], 'protocol': 'https', 'tlsProfileRef': item['tls_profile']}
                   for item in projection['instances']]
        selector = 'schema-registry'
    elif service_type == "kafka":
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
                                "port": item["port"], "protocol": "tcp", "tls": item["securityProtocol"] in {"SSL", "SASL_SSL"},
                                "securityProtocol": item["securityProtocol"],
                                "saslMechanism": "SCRAM-SHA-512" if item["securityProtocol"] == "SASL_SSL" else None})
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


def account_policies(settings, layers):
    """Keep typed source and policy alternatives atomic after Ansible combine.

    The resolving task supplies layers in its existing order. Credential
    inheritance remains field-level; an explicit source replaces its descriptor.
    """
    import copy
    result = copy.deepcopy(settings)
    policies = {}
    for layer in layers:
        for name, declaration in layer.get('accounts', {}).items():
            for field, credential in declaration.get('credentials', {}).items():
                if isinstance(credential, dict) and 'source' in credential:
                    result['accounts'][name]['credentials'][field]['source'] = copy.deepcopy(credential['source'])
            if 'databaseAccess' in declaration:
                if 'databaseRef' in declaration or 'grants' in declaration:
                    raise ValueError('APPLICATION_PROVIDER_GRANTS_INVALID')
                policies[name] = 'databaseAccess'
            elif 'databaseRef' in declaration or 'grants' in declaration:
                policies[name] = 'legacy'
    for name, policy in policies.items():
        for key in (('databaseRef', 'grants') if policy == 'databaseAccess' else ('databaseAccess',)):
            result['accounts'][name].pop(key, None)
    return result


def resolve_topics(resources, bindings, desired):
    """Pure projection; Ansible already resolved resource parameters and topology."""
    topics = {}
    for key, resource in resources.items():
        if resource['kind'] != 'kafka.topic':
            continue
        ref = bindings[resource['binding']]['deploymentRef']
        deployment = desired['serviceDeployments'][ref]
        if deployment['serviceType'] != 'kafka' or deployment['mode'] not in ('kraft-standalone', 'kraft-distributed'):
            raise ValueError('APPLICATION_TOPIC_PROVIDER_INVALID')
        count = sum('broker' in m.get('roles', []) for m in deployment.get('members', {}).values())
        p = resource['parameters']
        name = p['name']
        if (set(p) - {'name', 'partitions', 'replication_factor', 'config'} or
                not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,249}', name) or name in ('.', '..')):
            raise ValueError('APPLICATION_TOPIC_SETTINGS_INVALID')
        partitions = p.get('partitions', 1)
        rf = p.get('replication_factor', 1 if deployment['mode'] == 'kraft-standalone' else min(3, count))
        config = dict(p.get('config', {}))
        minimum = config.get('min.insync.replicas', min(2, rf) if type(rf) is int else 0)
        if isinstance(minimum, str) and minimum.isdecimal():
            minimum = int(minimum)
        if (any(type(v) is not int or v < 1 for v in (partitions, rf, minimum)) or rf > count or
                any(not isinstance(k, str) or not isinstance(v, (str, int, float, bool)) for k, v in config.items())):
            raise ValueError('APPLICATION_TOPIC_SETTINGS_INVALID')
        config = {k: str(v).lower() if type(v) is bool else str(v) for k, v in config.items()}
        config['min.insync.replicas'] = str(minimum)
        topics[key] = dict(resourceId=key, deploymentRef=ref, name=name,
                           mode=resource.get('mode', 'managed'), partitions=partitions,
                           replicationFactor=rf, config=config,
                           minISRWarning=minimum > rf)
    return topics


def resolve_tables(resources, bindings, desired, defaults, catalog, project_id):
    result = {}
    for resource_id, resource in resources.items():
        if resource['kind'] != 'clickhouse.database':
            continue
        ref = bindings[resource['binding']]['deploymentRef']
        deployment = desired['serviceDeployments'][ref]
        if deployment['serviceType'] != 'clickhouse' or deployment['mode'] not in ('standalone', 'raft-ha'):
            raise ValueError('APPLICATION_TABLE_PROVIDER_INVALID')
        specs = defaults.get('clickhouse', {}).get('tables', {})
        if specs and 'service.clickhouse.table' not in catalog['definitions']['clickhouse'].get('capabilities', []):
            raise ValueError('APPLICATION_TABLE_CAPABILITY_UNSUPPORTED')
        result[resource_id] = [dict(spec, name=name,
            engine=('Replicated' if deployment['mode'] == 'raft-ha' else '') + spec['engine'],
            replicationPath='/clickhouse/tables/%s/%s/{shard}/%s/%s' % (project_id, ref, resource['parameters']['name'], name))
            for name, spec in sorted(specs.items())]
    return result


def project(rows, desired, configuration, catalog, hosts, project_id="ansible-project"):
    findings, libraries, ports = [], {}, set()
    try:
        exports = provided_connections(rows, desired, hosts)
    except (ValueError, KeyError, TypeError):
        exports = {}
        findings.append(finding('APPLICATION_PROVIDED_CONNECTION_INVALID', 'applicationLibraryDeployments'))
    instance_owners = {}
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
        owner = (library_id, row["slotId"])
        if app_id in instance_owners and instance_owners[app_id] != owner:
            findings.append(finding("APPLICATION_IDENTITY_DUPLICATE", field))
        instance_owners[app_id] = owner
        settings = row["settings"]
        strategy = row.get("instanceIdStrategy", "qualified")
        expected_id = row["applicationName"] if strategy == "application-name" else row["applicationName"] + "-" + library_id
        if strategy not in ("qualified", "application-name") or app_id != expected_id or host not in hosts or not ID.fullmatch(app_id) or len(app_id) > 128:
            findings.append(finding("APPLICATION_IDENTITY_INVALID", field))
        for section in ("parameters", "environment", "command"):
            nonsecret_values(settings.get(section, {}), field + "." + section, findings)
        for key in ('commonDefaults', 'inherited'):
            nonsecret_values(row.get(key, {}), field + '.' + key, findings)
        nonsecret_values(settings.get("endpoint", {}), field + ".endpoint", findings)
        for resource_id, resource in row["resources"].items():
            nonsecret_values(resource.get("parameters", {}), field + ".resources." + resource_id + ".parameters", findings)
        declared_accounts = settings.get("accounts", {})
        accounts = {name: value for name, value in declared_accounts.items() if enabled(settings, name)}
        secret_bindings = settings.get("provisioner", {}).get("secret_bindings", {})
        secret_bindings = {name: value for name, value in secret_bindings.items()
                           if all(enabled(settings, alias) for alias in value.get('requires_connections', []))
                           and enabled(settings, value['source'].get('account', ''))}
        skipped = {name for name, declaration in row['connections'].items()
                   if not (row['bindings'].get(declaration['library_binding'], {}).get('deploymentRef')
                           or row['bindings'].get(declaration['library_binding'], {}).get('providedConnectionRef'))}
        accounts = {name: account for name, account in accounts.items() if name not in skipped}
        secret_bindings = {name: binding for name, binding in secret_bindings.items()
                           if binding['source'].get('account') not in skipped}
        agent_required = bool(secret_bindings)
        if (accounts or agent_required) and settings.get("provisioner", {}).get("type") != "vault-agent":
            findings.append(finding("APPLICATION_PROVISIONER_REQUIRED", field))
        for name, account in declared_accounts.items():
            nonsecret_values(account.get("databaseAccess", []), field + ".accounts." + name + ".databaseAccess", findings)
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
            if not enabled(settings, name):
                continue
            binding = row["bindings"].get(declaration["library_binding"], {})
            if not binding and settings.get('connections', {}).get(name, {}).get('enabled') is True:
                findings.append(finding('APPLICATION_BINDING_REQUIRED', field + '.bindings.' + declaration['library_binding']))
                continue
            if 'providedConnectionRef' in binding:
                try:
                    connections[name] = application_connection(binding, declaration, exports)
                    if name in accounts and not connections[name].get('accountProvisioner'):
                        raise ValueError('APPLICATION_ACCOUNT_CAPABILITY_UNSUPPORTED')
                except (ValueError, KeyError, TypeError):
                    findings.append(finding('APPLICATION_PROVIDED_CONNECTION_INVALID', field + '.connections.' + name))
                continue
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
                if ('service.kafka.account' not in catalog['definitions']['kafka'].get('capabilities', [])
                        or any(t.get('securityProtocol') != 'SASL_SSL' for t in connections[name]['targets'])):
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
            if binding.get('format') == 'kafka_scram_jaas':
                connection = connections.get(source.get('account'), {})
                if (connection.get('serviceType') != 'kafka' or source.get('field') != 'password'
                        or source.get('account') not in accounts):
                    findings.append(finding("APPLICATION_SECRET_BINDING_INVALID", field + ".secret_bindings." + variable))
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
        shared_connections = {}
        for name, declaration in row.get('libraryConnections', {}).items():
            if 'providedConnectionRef' in row['bindings'].get(declaration['library_binding'], {}):
                try:
                    shared_connections[name] = application_connection(row['bindings'][declaration['library_binding']], declaration, exports)
                except (ValueError, KeyError, TypeError):
                    pass  # A disabled optional consumer need not resolve this connection.
                continue
            reference = row['bindings'].get(declaration['library_binding'], {}).get('deploymentRef')
            if not reference:
                continue
            try:
                service_type = desired['serviceDeployments'][reference]['serviceType']
                selector = row['connectionDefaults'].get(service_type, {}).get('connectionRef')
                shared_connections[name] = resolve_connection(reference, declaration, selector, desired, configuration, catalog, hosts)
            except (ValueError, KeyError, TypeError):
                findings.append(finding('APPLICATION_CONNECTION_INVALID', field + '.libraryConnections.' + name))
        try:
            topics = resolve_topics(row['resources'], row['bindings'], desired)
            topic_bindings = {}
            for alias, refs in settings.get('topicBindings', {}).items():
                connection = connections[alias]
                selected = {role: topics[ref] for role, ref in refs.items()} if isinstance(refs, dict) else [topics[ref] for ref in refs]
                values = selected.values() if isinstance(selected, dict) else selected
                if connection['serviceType'] != 'kafka' or any(t['deploymentRef'] != connection['deploymentRef'] for t in values):
                    raise ValueError('APPLICATION_TOPIC_BINDING_INVALID')
                topic_bindings[alias] = selected
        except (KeyError, TypeError, ValueError):
            topics, topic_bindings = {}, {}
            findings.append(finding('APPLICATION_TOPIC_BINDING_INVALID', field + '.topicBindings'))
        library = libraries.setdefault(library_id, {"libraryRef": row["libraryRef"], "packages": {}, "instances": {}, "resources": row["resources"], 'topics': topics, "sharedSecretRequirements": row["sharedSecrets"], 'connections': shared_connections, 'runtimeDirectory': row.get('runtimeDirectory', '~/' + library_id), 'scripts': row.get('libraryScripts', [])})
        library['providedConnections'] = exports.get(library_id, {})
        if library.setdefault('registryCredentials', row.get('registryCredentials', {})) != row.get('registryCredentials', {}):
            findings.append(finding('APPLICATION_HOST_RESOURCE_CONFLICT', field))
        registries = library.setdefault('registries', [])
        if row['settings'].get('image'):
            registry = registry_request(row['settings']['image'])['registry']
            if registry not in registries:
                registries.append(registry)
                registries.sort()
        if (library['connections'] != shared_connections or library['runtimeDirectory'] != row.get('runtimeDirectory', '~/' + library_id)
                or library['scripts'] != row.get('libraryScripts', [])):
            findings.append(finding('APPLICATION_HOST_RESOURCE_CONFLICT', field))
        library["packages"][row["applicationName"]] = row["packageIdentity"]
        try:
            tables = resolve_tables(row['resources'], row['bindings'], desired, row.get('resourceDefaults', {}), catalog, project_id)
            if library.setdefault('tables', tables) != tables:
                findings.append(finding('APPLICATION_HOST_RESOURCE_CONFLICT', field))
        except (KeyError, ValueError, TypeError):
            findings.append(finding('APPLICATION_TABLE_RESOURCE_INVALID', field))
        if library.setdefault('resourceDefaults', row.get('resourceDefaults', {})) != row.get('resourceDefaults', {}):
            findings.append(finding('APPLICATION_HOST_RESOURCE_CONFLICT', field))
        instance = library["instances"].setdefault(app_id, {"applicationName": row["applicationName"], "slotId": row["slotId"],
                                                            "startupPriority": row.get("startupPriority", 100), "placements": {},
                                                            "scripts": row.get('applicationScripts', []),
                                                           "connections": connections, 'topics': topic_bindings, "credentialRequirements": accounts,
                                                           "identityEnvironment": {name: app_id for name in row["identityNames"]},
                                                           "agentRequired": agent_required, "executionPrerequisites": ["A2_IMAGE_DELIVERY", "A4_PROVIDER_PROVISIONING"] if accounts or agent_required else ["A2_IMAGE_DELIVERY"]})
        if library['resources'] != row['resources'] or library['sharedSecretRequirements'] != row['sharedSecrets']:
            findings.append(finding('APPLICATION_HOST_RESOURCE_CONFLICT', field))
        if instance['connections'] != connections:
            findings.append(finding('APPLICATION_HOST_CONNECTION_CONFLICT', field))
        if instance['scripts'] != row.get('applicationScripts', []):
            findings.append(finding('APPLICATION_HOST_RESOURCE_CONFLICT', field))
        if instance['startupPriority'] != row.get('startupPriority', 100):
            findings.append(finding('APPLICATION_HOST_RESOURCE_CONFLICT', field))
        if instance['topics'] != topic_bindings:
            findings.append(finding('APPLICATION_HOST_RESOURCE_CONFLICT', field))
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
                                          "commonDefaults": row.get('commonDefaults', {}), "inherited": row.get('inherited', {}),
                                          "imageRequirement": {"image": settings.get("image"), "artifactType": "container-image"},
                                          "origin": {"resolution": "ANSIBLE", "precision": "RESOLUTION_SCOPE",
                                                     "applicationPackage": row['applicationName'] + '@' + row['applicationVersion'],
                                                     "libraryPackage": row['libraryRef'], "host": host},
                                          "connectionSettings": settings.get('connections', {}),
                                          "parameters": settings.get("parameters", {}), "environment": settings.get("environment", {}),
                                          "topicBindings": settings.get('topicBindings', {}),
                                          "ports": settings.get("ports", {}), "endpoint": settings.get("endpoint", {}),
                                          "containerName": "%s-%s" % (app_id, host),
                                          "composeProject": compose_project,
                                          "runtimeDirectory": library['runtimeDirectory'],
                                          "runtimePath": app_id, "libraryEnvPath": '.env'}
    for library in libraries.values():
        used = {binding["source"]["library_secret"] for instance in library["instances"].values()
                for binding in instance.get("secretBindings", {}).values() if "library_secret" in binding["source"]}
        used.update(source['name'] for instance in library['instances'].values()
                    for script in library.get('scripts', []) + instance.get('scripts', []) if active_script(script, instance)
                    for source in script.get('secretInputs', {}).values() if source.get('valueFrom') == 'library_secret')
        library["sharedSecretRequirements"] = {key: value for key, value in library["sharedSecretRequirements"].items() if key in used}
    for library_id, library in libraries.items():
        for export_name, export in library.get('providedConnections', {}).items():
            callback = export.get('accountProvisioner', {}).get('apply_script')
            if callback and len([script for script in library['instances'][export['applicationId']].get('scripts', [])
                                 if script['id'] == callback and script['phase'] == 'account_apply']) != 1:
                findings.append(finding('APPLICATION_ACCOUNT_CALLBACK_INVALID',
                                        'applicationLibraryDeployments.' + library_id + '.provided_connections.' + export_name))
            if export.get('connectionProvisioner'):
                try:
                    connection_callback(libraries, export)
                except (ValueError, KeyError, TypeError):
                    findings.append(finding('APPLICATION_CONNECTION_CALLBACK_INVALID',
                                            'applicationLibraryDeployments.' + library_id + '.provided_connections.' + export_name))
        named = {instance['applicationName']: instance for instance in library['instances'].values()}
        for consumer in library['instances'].values():
            for alias, connection in consumer.get('connections', {}).items():
                if not connection.get('connectionProvisioner'):
                    continue
                try:
                    provider, _, callback = connection_callback(libraries, connection)
                    for source in callback.get('secretInputs', {}).values():
                        value = script_secret_source(source, library, consumer, provider)
                        if value is None and not source.get('optional', False):
                            raise ValueError('APPLICATION_SCRIPT_REFERENCE_INVALID')
                    for argument in callback.get('argv', []):
                        if not isinstance(argument, dict):
                            continue
                        if argument['valueFrom'] == 'parameter' and any(
                                argument['name'] not in placement.get('parameters', {}) for placement in consumer['placements'].values()):
                            raise ValueError('APPLICATION_SCRIPT_REFERENCE_INVALID')
                        if argument['valueFrom'] == 'endpoint' and 'name' not in argument and any(
                                not placement.get('endpoint', {}).get('enabled') for placement in consumer['placements'].values()):
                            raise ValueError('APPLICATION_SCRIPT_REFERENCE_INVALID')
                except (ValueError, KeyError, TypeError):
                    findings.append(finding('APPLICATION_CONNECTION_CALLBACK_INVALID',
                                            'applicationLibraryDeployments.' + library_id + '.connections.' + alias))

        for instance_id, instance in library['instances'].items():
            scripts = library.get('scripts', []) + instance.get('scripts', [])
            if len({script['id'] for script in scripts}) != len(scripts):
                findings.append(finding('APPLICATION_SCRIPT_ID_CONFLICT', 'applicationLibraryDeployments.' + library_id))
            for script in scripts:
                if script['phase'] == 'connection_apply':
                    continue
                if script['phase'] != 'account_apply' and not active_script(script, instance):
                    continue
                for source in script.get('secretInputs', {}).values():
                    try:
                        value = script_secret_source(source, library, instance)
                        if value is None and script['phase'] != 'account_apply' and not source.get('optional', False):
                            raise ValueError('APPLICATION_SCRIPT_REFERENCE_INVALID')
                    except (ValueError, KeyError, TypeError):
                        findings.append(finding('APPLICATION_SCRIPT_REFERENCE_INVALID',
                                                'applicationLibraryDeployments.' + library_id + '.scripts.' + script['id']))
                for argument in script.get('argv', []):
                    if not isinstance(argument, dict):
                        continue
                    source = argument['valueFrom']
                    name = argument.get('name')
                    if source == 'parameter':
                        valid = all(name in p.get('parameters', {}) and isinstance(p['parameters'][name], (str, int, float, bool, dict, list))
                                    for p in instance['placements'].values())
                    elif source in ('placement_https', 'endpoint'):
                        target = named.get(argument.get('application', name), {})
                        valid = bool(target) and all(
                            host in target.get('placements', {}) and
                            (target['placements'][host].get('endpoint', {}).get('protocol') == 'https'
                             if source == 'placement_https' else target['placements'][host].get('endpoint', {}).get('enabled')) and
                            target['placements'][host].get('endpoint', {}).get('listener') in target['placements'][host].get('ports', {})
                            for host in instance['placements'])
                    elif source == 'connection':
                        valid = name in instance.get('connections', {}) and bool(instance['connections'][name].get('targets'))
                    elif source == 'provided_connection':
                        valid = name in library.get('providedConnections', {})
                    elif source == 'account_batch':
                        valid = script['phase'] == 'account_apply'
                    else:
                        valid = source in ('applicationId', 'projectId', 'libraryId', 'targetHostId')
                    if not valid:
                        findings.append(finding('APPLICATION_SCRIPT_REFERENCE_INVALID',
                                                'applicationLibraryDeployments.' + library_id + '.scripts.' + script['id']))
    if findings:
        libraries = {}  # Never return potentially unsafe settings on invalid input.
    return {"apiVersion": "platform.installer/application-libraries/v1alpha1", "status": "BLOCKED" if findings else "PASS",
            "libraries": libraries, "findings": findings}


def validate_public_projection(projection):
    """Final boundary check of free fields; typed credential descriptors remain intact."""
    findings = []
    for library_id, library in projection.get("libraries", {}).items():
        field = "applicationLibraries." + library_id
        nonsecret_values(library.get('resourceDefaults', {}), field + '.resourceDefaults', findings)
        for resource_id, resource in library.get("resources", {}).items():
            nonsecret_values(resource.get("parameters", {}), field + ".resources." + resource_id + ".parameters", findings)
        for instance_id, instance in library.get("instances", {}).items():
            prefix = field + ".instances." + instance_id
            for account_id, account in instance.get("credentialRequirements", {}).items():
                nonsecret_values(account.get("grants", []), prefix + ".accounts." + account_id + ".grants", findings)
            for host_id, placement in instance.get("placements", {}).items():
                for section in ("parameters", "environment", "command", "endpoint", "commonDefaults", "inherited"):
                    nonsecret_values(placement.get(section, {}), prefix + ".placements." + host_id + "." + section, findings)
    return findings

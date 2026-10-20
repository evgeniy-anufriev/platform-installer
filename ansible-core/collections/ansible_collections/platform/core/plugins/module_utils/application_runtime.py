"""Typed A2 preflight. Ansible owns precedence, templates and target execution."""
import base64
import hashlib
import os
import re

try:
    from .application_libraries import checked_file, invocation_package_loader, nonsecret_values
    from .artifact_authority import assemble_authority
    from .application_images import selected_image, registry_request
except ImportError:
    from application_libraries import checked_file, invocation_package_loader, nonsecret_values
    from artifact_authority import assemble_authority
    from application_images import selected_image, registry_request

DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
REFERENCE = re.compile(r"^[a-z0-9][a-z0-9._:/-]*(?::[A-Za-z0-9_][A-Za-z0-9_.-]*)?(?:@sha256:[0-9a-f]{64})?$")
LABEL = "platform.installer.config-digest"


def runtime_reference(image_id):
    if not isinstance(image_id, str) or not DIGEST.fullmatch(image_id):
        raise ValueError("APPLICATION_IMAGE_ID_INVALID")
    return "platform-application:sha256-" + image_id.split(":", 1)[1]


def pinned_registry_reference(reference, digest):
    if not isinstance(reference, str) or not REFERENCE.fullmatch(reference) or "@" in reference or not DIGEST.fullmatch(digest):
        raise ValueError("APPLICATION_REGISTRY_REFERENCE_INVALID")
    prefix, slash, name = reference.rpartition("/")
    name = name.split(":", 1)[0]
    return (prefix + slash + name) + "@" + digest


def safe_relative(value):
    return (isinstance(value, str) and bool(value) and not value.startswith("/") and
            "\\" not in value and not any(x in ("", ".", "..") for x in value.split("/")))


def image_requirement(instance_id, image_name, image):
    """One locked image identity for standalone execution and target-free planning."""
    if not isinstance(image_name, str) or not REFERENCE.fullmatch(image_name) or not isinstance(image, dict):
        raise ValueError('APPLICATION_IMAGE_NOT_LOCKED')
    reference = runtime_reference(image['imageId'])
    platform = image.get('platform')
    if (not isinstance(platform, dict) or set(platform) - {'os', 'architecture', 'variant'} or
            platform.get('os') != 'linux' or platform.get('architecture') not in ('amd64', 'arm64') or
            ('variant' in platform and (not isinstance(platform['variant'], str) or
             re.fullmatch(r'[a-z0-9]+', platform['variant']) is None))):
        raise ValueError('APPLICATION_IMAGE_PLATFORM_INVALID')
    if image.get('localReference', reference) != reference:
        raise ValueError('APPLICATION_IMAGE_REFERENCE_NOT_BOUND')
    return dict(id=instance_id + ':image', name=image_name, artifactType='container-image',
                imageId=image['imageId'], platform=image['platform'], localReference=reference)


def resolve_image_lock(native_lock, manifest_lock, prepared=None):
    """Existing standalone lock conflict rule, shared by snapshot and runtime."""
    if native_lock is not None and manifest_lock is not None and native_lock != manifest_lock:
        raise ValueError('APPLICATION_ARTIFACT_LOCK_CONFLICT')
    legacy = (native_lock or manifest_lock or {}).get('x-container-images', {})
    if prepared is not None:
        for entry in prepared.get('placements', {}).values():
            original = selected_image(legacy, entry['reference'], '', '', '')
            if original is not None and original != entry['image']:
                raise ValueError('APPLICATION_ARTIFACT_LOCK_CONFLICT')
        return prepared
    return legacy


def bundle_archive(root, digest, record, loader):
    """Verify the locked manifest and selected component; no bundle mutation."""
    manifest_path = checked_file(root, "manifest.yaml")
    with open(manifest_path, "rb") as stream:
        if "sha256:" + hashlib.sha256(stream.read()).hexdigest() != digest:
            raise ValueError("APPLICATION_BUNDLE_DIGEST_INVALID")
    manifest = loader(manifest_path)
    if manifest.get("apiVersion") != "platform.installer/execution-bundle/v1alpha1" or manifest.get("kind") != "ExecutionRuntimeBundle":
        raise ValueError("APPLICATION_BUNDLE_MANIFEST_INVALID")
    matches = [x for x in manifest.get("components", []) if x.get("path") == record["ref"]]
    if len(matches) != 1 or matches[0].get("sha256") != record["sha256"] or matches[0].get("size") != record["size"]:
        raise ValueError("APPLICATION_IMAGE_ARCHIVE_NOT_LOCKED")
    if not safe_relative(record["ref"]) or not record["ref"].startswith("runtime/artifacts/"):
        raise ValueError("APPLICATION_IMAGE_ARCHIVE_PATH_INVALID")
    path = os.path.abspath(root)
    for part in record["ref"].split("/"):
        path = os.path.join(path, part)
        if os.path.islink(path):
            raise ValueError("APPLICATION_IMAGE_ARCHIVE_PATH_INVALID")
    if not os.path.isfile(path):
        raise ValueError("APPLICATION_IMAGE_ARCHIVE_MISSING")
    sha = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
    if "sha256:" + sha.hexdigest() != record["sha256"] or os.path.getsize(path) != record["size"]:
        raise ValueError("APPLICATION_IMAGE_ARCHIVE_INVALID")
    return path


def selected_archive(root, source, offline, loader):
    """Validate fallback bytes only after the target selected the fallback."""
    if source == "REPOSITORY":
        return None
    if source != "OFFLINE_BUNDLE" or not offline:
        raise ValueError("APPLICATION_IMAGE_SOURCE_INVALID")
    if not root:
        raise ValueError("APPLICATION_BUNDLE_REQUIRED")
    return bundle_archive(root, offline["bundleDigest"], offline, loader)


def validate_compose(config, job, instance_path, digest):
    """Check only values projected by Core; leave package-authored Compose fields alone."""
    services = config.get("services", {})
    if config.get("name") != job["placement"]["composeProject"] or set(services) != {job["instanceId"]}:
        raise ValueError("APPLICATION_COMPOSE_IDENTITY_INVALID")
    service = services[job["instanceId"]]
    reference = job['settings']['image']
    if '@' in reference:
        reference = job['authority']['requirement']['localReference']
    if (service.get("image") != reference or
            service.get("container_name") != job["placement"]["containerName"]):
        raise ValueError("APPLICATION_COMPOSE_IDENTITY_INVALID")
    launch = service.get("entrypoint") or service.get("command")
    expected_launch = ['/usr/bin/vault', 'agent', '-config=/opt/vault/agent.hcl'] if job.get('agentTemplate') else job['settings']['command']
    if launch != expected_launch or (service.get("entrypoint") and service.get("command")):
        raise ValueError("APPLICATION_COMPOSE_COMMAND_INVALID")
    for key in ("user", "restart"):
        if key in job["settings"] and service.get(key) != job["settings"][key]:
            raise ValueError("APPLICATION_COMPOSE_CONFIGURATION_INVALID")
    if job["settings"].get("readiness", {}).get("mode") == "healthcheck" and not service.get("healthcheck"):
        raise ValueError("APPLICATION_HEALTHCHECK_REQUIRED")
    expected_labels = {"platform.installer.project": job["projectId"], "platform.installer.library": job["libraryId"],
                       "platform.installer.instance": job["instanceId"], "platform.installer.host": job["hostId"], LABEL: digest}
    labels = service.get("labels", {})
    if any(labels.get(name) != value for name, value in expected_labels.items()):
        raise ValueError("APPLICATION_COMPOSE_LABEL_INVALID")
    expected_env = dict(job["settings"].get("environment", {}), **{key: job["instanceId"] for key in job["identityNames"]})
    environment = service.get("environment", {})
    if any(environment.get(key) != str(value) for key, value in expected_env.items()):
        raise ValueError("APPLICATION_COMPOSE_ENVIRONMENT_INVALID")
    findings = []
    nonsecret_values(environment, "environment", findings)
    if findings:
        raise ValueError("APPLICATION_COMPOSE_SECRET_INVALID")
    expected_ports = sorted((str(x["published"]), x["container"]) for x in job["settings"].get("ports", {}).values())
    ports = service.get("ports", [])
    if sorted((str(x["published"]), x["target"]) for x in ports) != expected_ports:
        raise ValueError("APPLICATION_COMPOSE_PORT_INVALID")
    expected_mounts = {os.path.join(instance_path, "config", x["destination"]): None for x in job["configs"]}
    core_mounts = {os.path.join(instance_path, 'vault'): '/opt/vault'} if job.get('agentTemplate') else {}
    if job.get('vault', {}).get('pkiPlans'):
        core_mounts[os.path.join(instance_path, 'pki')] = '/opt/application/pki'
    expected_mounts.update(core_mounts)
    for source, target in expected_mounts.items():
        matches = [x for x in service.get("volumes", []) if x.get("source") == source]
        if len(matches) != 1 or matches[0].get("type") != "bind" or not matches[0].get("read_only"):
            raise ValueError("APPLICATION_COMPOSE_MOUNT_INVALID")
        if (target is not None and matches[0].get("target") != target) or not matches[0].get("target", "").startswith("/"):
            raise ValueError("APPLICATION_COMPOSE_MOUNT_INVALID")
    return True


def prepare_runtime(root, snapshot, rows, desired, lock, validator, loader):
    libraries = snapshot.get("applicationLibraries", {})
    if snapshot.get("validation", {}).get("status") != "PASS" or libraries.get("status") != "PASS":
        raise ValueError("APPLICATION_RUNTIME_PROJECT_BLOCKED")
    image_lock = lock.get("x-container-images", {}) if isinstance(lock, dict) else {}
    schema = os.path.join(validator.schema_root, 'artifact-source/v1alpha2/' +
                          ('prepared-images.schema.json' if image_lock.get('apiVersion') == 'platform.installer/container-images/v1alpha2' else 'image-lock.schema.json'))
    if validator.validate(image_lock, schema) or not DIGEST.fullmatch(lock.get("digest", "")):
        raise ValueError("APPLICATION_IMAGE_LOCK_INVALID")
    jobs = []
    package_loader = invocation_package_loader(root, loader, validator)
    for row in rows:
        lib_id, app_id, host = row["libraryId"], row["instanceId"], row["hostId"]
        library = libraries["libraries"][lib_id]
        instance = library["instances"][app_id]
        placement = instance["placements"][host]
        settings = row["settings"]
        if (any(r['kind'] not in {'postgresql.database', 'postgresql.schema', 'clickhouse.database', 'kafka.topic', 'redis.key'} for r in row['resources'].values()) or
                any(instance['connections'].get(k, {}).get('serviceType') not in {'postgresql', 'redis', 'clickhouse'} for k in instance['credentialRequirements']) or
                any(x.get("tls") for x in instance["connections"].values())):
            raise ValueError("APPLICATION_RUNTIME_DEFERRED_FEATURE")
        # Recheck packages after native variable composition, before any rendering.
        app_ref = row["applicationName"] + "@" + row["applicationVersion"]
        app = package_loader(app_ref, "application")
        lib = package_loader(row["libraryRef"], "library")
        if row["packageIdentity"] != {"application": app["digest"], "library": lib["digest"]}:
            raise ValueError("APPLICATION_PACKAGE_CHANGED")
        app_render, lib_render = app.get("render", {}), lib.get("render", {})
        agent_template = app_render.get('agent_template') if instance['agentRequired'] else None
        if instance['agentRequired'] and (not agent_template or agent_template not in app['files']):
            raise ValueError('APPLICATION_AGENT_TEMPLATE_REQUIRED')
        if not app_render.get("compose_template") or not lib_render.get("base_compose_template"):
            raise ValueError("APPLICATION_RENDER_REQUIRED")
        for package, key in ((app, "compose_template"), (lib, "base_compose_template")):
            if package["render"][key] not in package["files"]:
                raise ValueError("APPLICATION_RENDER_NOT_ALLOWLISTED")
        configs = []
        for config in settings.get("config_files", []):
            name = config.get("template", config.get("source"))
            if name not in app["files"] or not safe_relative(config["destination"]):
                raise ValueError("APPLICATION_CONFIG_NOT_ALLOWLISTED")
            configs.append(dict(config, path=checked_file(root, app["logicalPath"] + "/" + name)))
        if len({x["destination"] for x in configs}) != len(configs):
            raise ValueError("APPLICATION_CONFIG_DESTINATION_COLLISION")
        image = selected_image(image_lock, settings['image'], lib_id, app_id, host)
        if not image:
            raise ValueError("APPLICATION_IMAGE_NOT_LOCKED")
        reference = runtime_reference(image["imageId"])
        if not REFERENCE.fullmatch(settings["image"]):
            raise ValueError("APPLICATION_IMAGE_REFERENCE_INVALID")
        if image.get("localReference", reference) != reference:
            raise ValueError("APPLICATION_IMAGE_REFERENCE_NOT_BOUND")
        registry = image.get("registry")
        if registry and (not REFERENCE.fullmatch(registry["reference"]) or "@" in registry["reference"]):
            raise ValueError("APPLICATION_REGISTRY_REFERENCE_INVALID")
        # Registry allowlist is node scoped, independent of package defaults.
        configuration = snapshot["effectiveConfiguration"]["services"][row["runtimeRef"]]["configuration"]
        account_setting = configuration.get("accountName", {})
        account = account_setting.get("value") if account_setting.get("state") == "RESOLVED" else None
        if not isinstance(account, str) or not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", account):
            raise ValueError("APPLICATION_DOCKER_ACCOUNT_REQUIRED")
        offline = image.get("archive")
        archive_path = None
        if offline:
            if not safe_relative(offline["ref"]) or not offline["ref"].startswith("runtime/artifacts/"):
                raise ValueError("APPLICATION_IMAGE_ARCHIVE_PATH_INVALID")
            offline = dict(offline, kind="OFFLINE_BUNDLE", type="archive", bundleDigest=lock["digest"])
        requirement = image_requirement(app_id, settings['image'], image)
        authority = assemble_authority(requirement, offline, dict(registry or {}, kind="REPOSITORY"), image=True)
        registry_credentials = row.get('registryCredentials', {}).get(registry_request(registry['reference'])['registry'], {}) if registry else {}
        jobs.append(dict(row, placement=placement, account=account, configs=configs, registryCredentials=registry_credentials,
                         agentTemplate=checked_file(root, app['logicalPath']+'/'+agent_template) if agent_template else None,
                         appTemplate=checked_file(root, app["logicalPath"] + "/" + app_render["compose_template"]),
                         baseTemplate=checked_file(root, lib["logicalPath"] + "/" + lib_render["base_compose_template"]),
                         baseFilename=lib_render["base_compose_filename"], baseService=lib_render["base_service"],
                         envSource=checked_file(root, lib["logicalPath"] + "/files/.env") if "files/.env" in lib["files"] else None,
                         archivePath=archive_path, authority=authority))
    return jobs


def validate_config_contents(configs):
    for item in configs:
        content = item["content"]
        if not isinstance(content, str):
            raise ValueError("APPLICATION_CONFIG_CONTENT_INVALID")
        if item.get("encoding") == "base64":
            raw = base64.b64decode(content, validate=True)
            if len(raw) > 8 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != item['sha256']:
                raise ValueError("APPLICATION_CONFIG_CONTENT_INVALID")
            content = raw.decode("utf-8", errors="replace")
        elif len(content.encode("utf-8")) > 1024 * 1024:
            raise ValueError("APPLICATION_CONFIG_CONTENT_INVALID")
        findings = []
        nonsecret_values(content, "config", findings)
        if findings or re.search(r"(?:password|passphrase|token|secret|role.?id)\s*[:=]", content, re.I):
            raise ValueError("APPLICATION_CONFIG_SECRET_FORBIDDEN")
    return True


def agent_config(runtime):
    """Closed supervisor profile: no arbitrary exec, template files or token sinks."""
    import json
    vault = runtime['vault']
    q = json.dumps
    lines = ['exit_after_auth = false', 'vault {', '  address = '+q(vault['endpoint_url']),
             '  ca_cert = '+q(vault['ca_container_path']), '}', 'auto_auth {', '  method "approle" {',
             '    mount_path = '+q(vault['auth_mount']), '    config = {',
             '      role_id_file_path = '+q(vault['role_id_container_path']), '    }', '  }', '}']
    lines += ['template_config {', '  exit_on_retry_failure = true', '}']
    for binding in vault['env_templates']:
        lines += ['env_template '+q(binding['name'])+' {', '  contents = '+q(binding['contents']),
                  '  error_on_missing_key = true', '}']
    lines += ['exec {', '  command = '+q(runtime['application_command']),
              '  restart_on_secret_changes = "always"', '}']
    return '\n'.join(lines)+'\n'


def validate_agent(content, runtime):
    if content.replace('\r\n', '\n').strip() != agent_config(runtime).strip():
        raise ValueError('APPLICATION_AGENT_PROFILE_INVALID')
    return True

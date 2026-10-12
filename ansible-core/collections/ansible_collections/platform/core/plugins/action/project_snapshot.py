from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
import os
import posixpath
import re
from collections.abc import Mapping

from ansible.errors import AnsibleError
from ansible.plugins.action import ActionBase

from ansible_collections.platform.core.plugins.module_utils.dns_resolution import resolve_dns_zones
from ansible_collections.platform.core.plugins.module_utils.deployment_plan import _service_runtime_secret_requirements
from ansible_collections.platform.core.plugins.module_utils.haproxy_resolution import resolve_haproxy_backends
from ansible_collections.platform.core.plugins.module_utils.pki_resolution import resolve_certificate_requests
from ansible_collections.platform.core.plugins.module_utils.project_snapshot import build_project_snapshot, project_documents
from ansible_collections.platform.core.plugins.module_utils.project_state import canonical_inventory_members
from ansible_collections.platform.core.plugins.module_utils.service_configuration_resolution import resolve_service_configuration
from ansible_collections.platform.core.plugins.module_utils.service_configuration_preview import ordinary_presentation_value
from ansible_collections.platform.core.plugins.module_utils.service_endpoint_resolution import resolve_service_endpoints
from ansible_collections.platform.core.plugins.module_utils.schema_validation import SchemaValidationError, SchemaValidator
from ansible_collections.platform.core.plugins.module_utils.topology_resolution import resolve_topology
from ansible_collections.platform.core.plugins.module_utils.application_libraries import (
    infrastructure_state, schema_version, prepare, validate_public_projection, project as project_application_libraries,
)
from ansible_collections.platform.core.plugins.module_utils.project_validation import canonical_digest
from ansible_collections.platform.core.plugins.module_utils.application_runtime import resolve_image_lock
from ansible_collections.platform.core.plugins.module_utils.application_plan import application_execution_model


_CANONICAL_PORT = re.compile(r"^(0|[1-9][0-9]*)$")
_SAFE_DATA_ROOT = re.compile(r"^/(?:[A-Za-z0-9][A-Za-z0-9_.-]{0,95}/)*[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")


def _materialize_resolved_members(desired_state, topology, inventory_deployments, target_ids):
    """Keep topology identity and inventory-owned member settings together."""
    materialized = copy.deepcopy(desired_state)
    if topology.get("status") != "PASS":
        return materialized
    inventory_members, findings = canonical_inventory_members(inventory_deployments, target_ids)
    if findings:
        raise ValueError("validated inventory members could not be materialized")
    for deployment_id, resolved in topology["resolvedTopology"].get("serviceDeployments", {}).items():
        deployment = materialized.get("serviceDeployments", {}).get(deployment_id)
        if not isinstance(deployment, dict) or not resolved.get("members"):
            continue
        members = copy.deepcopy(resolved["members"])
        for member_id, member in members.items():
            source = inventory_members.get((deployment_id, member_id))
            if source is not None:
                member["configuration"] = copy.deepcopy(source["configuration"])
        deployment["members"] = members
    return materialized


def _safe_data_root(value):
    if not isinstance(value, str) or len(value) > 240 or not _SAFE_DATA_ROOT.fullmatch(value):
        return None
    return posixpath.normpath(value)


def _project_effective_data_directories(configuration, catalog, hostvars):
    """Resolve declared service data paths for presentation only.

    Apply/Verify continue to use role defaults and ordinary Ansible precedence.
    This projection fills deferred path defaults only in the target-free UI
    preview, from the same resolved deployment/member placement and host vars.
    """
    configuration = copy.deepcopy(configuration)
    services = configuration.get("services", {}) if isinstance(configuration, dict) else {}
    definitions = catalog.get("definitions", {}) if isinstance(catalog, dict) else {}
    # Ansible exposes ``hostvars`` as its HostVars mapping proxy, not always a
    # built-in dict. Accept the mapping contract or project-global inventory
    # values silently disappear from this presentation-only calculation.
    hostvars = hostvars if isinstance(hostvars, Mapping) else {}
    if not isinstance(services, dict) or not isinstance(definitions, dict):
        return configuration

    for deployment_id, service in services.items():
        if not isinstance(deployment_id, str) or not isinstance(service, dict):
            continue
        definition = definitions.get(service.get("serviceType"), {})
        projection = definition.get("x-dataDirectoryProjection") if isinstance(definition, dict) else None
        if not isinstance(projection, dict) or set(projection) - {
            "deploymentSetting", "memberSetting", "rootVariable", "deploymentPathSuffix", "appendMemberIdWhenCoLocated"
        }:
            continue
        deployment_setting = projection.get("deploymentSetting")
        member_setting = projection.get("memberSetting")
        root_variable = projection.get("rootVariable")
        deployment_path_suffix = projection.get("deploymentPathSuffix", "")
        append_member = projection.get("appendMemberIdWhenCoLocated")
        if (not isinstance(deployment_setting, str) or
                (member_setting is not None and not isinstance(member_setting, str)) or
                not isinstance(root_variable, str) or
                not root_variable.startswith("platform_") or
                not isinstance(deployment_path_suffix, str) or
                (deployment_path_suffix and (deployment_path_suffix.startswith("/") or ".." in deployment_path_suffix.split("/"))) or
                type(append_member) is not bool):
            continue

        deployment_values = service.get("configuration", {})
        members = service.get("members", {})
        if not isinstance(deployment_values, dict) or not isinstance(members, dict):
            continue
        deployment_value = deployment_values.get(deployment_setting)
        if isinstance(deployment_value, dict) and deployment_value.get("state") == "RESOLVED":
            base_path = _safe_data_root(deployment_value.get("value"))
            explicit_deployment = deployment_value.get("source") not in ("ROLE_DEFAULT", "STATIC_REFERENCE")
        else:
            base_path = None
            explicit_deployment = False

        member_hosts = {
            member.get("variableContext", {}).get("hostId")
            for member in members.values()
            if isinstance(member, dict) and isinstance(member.get("variableContext"), dict)
        }
        member_hosts.discard(None)
        root_hosts = member_hosts or set(hostvars)
        default_roots = {}
        for host_id in root_hosts:
            values = hostvars.get(host_id)
            raw_root = values.get(root_variable, "/var/lib") if isinstance(values, Mapping) else None
            root = _safe_data_root(raw_root)
            if root is not None:
                default_roots[host_id] = root

        def default_path(host_id, member_id=None):
            root = default_roots.get(host_id)
            if root is None:
                return None
            parts = [root, deployment_id]
            if deployment_path_suffix:
                parts.extend(deployment_path_suffix.split("/"))
            if member_id is not None:
                parts.append(member_id)
            path = posixpath.normpath(posixpath.join(*parts))
            return path if len(path) <= 255 else None

        if not explicit_deployment:
            unique_roots = set(default_roots.values())
            if len(unique_roots) == 1:
                base_path = default_path(next(iter(default_roots))) if default_roots else None
            else:
                base_path = None
            if base_path is not None:
                deployment_values[deployment_setting] = {
                    "state": "RESOLVED", "source": "ROLE_DEFAULT", "value": base_path,
                }

        host_counts = {}
        for host_id in member_hosts:
            host_counts[host_id] = sum(
                1 for member in members.values()
                if isinstance(member, dict) and
                isinstance(member.get("variableContext"), dict) and
                member["variableContext"].get("hostId") == host_id
            )

        if member_setting is None:
            continue
        for member_id, member in members.items():
            if not isinstance(member_id, str) or not isinstance(member, dict):
                continue
            values = member.get("configuration", {})
            context = member.get("variableContext", {})
            host_id = context.get("hostId") if isinstance(context, dict) else None
            if not isinstance(values, dict) or not isinstance(host_id, str):
                continue
            current = values.get(member_setting)
            if isinstance(current, dict) and current.get("state") == "RESOLVED" and current.get("source") == "MEMBER_OVERRIDE":
                continue
            if explicit_deployment and base_path is not None:
                path = base_path
                if append_member and host_counts.get(host_id, 0) > 1:
                    path = posixpath.normpath(posixpath.join(base_path, member_id))
            else:
                path = default_path(
                    host_id,
                    member_id if append_member and host_counts.get(host_id, 0) > 1 else None,
                )
            if path is not None and len(path) <= 255:
                values[member_setting] = {
                    "state": "RESOLVED",
                    "source": "MEMBER_OVERRIDE" if current and current.get("source") == "MEMBER_OVERRIDE" else (
                        "DEPLOYMENT_OVERRIDE" if explicit_deployment else "ROLE_DEFAULT"
                    ),
                    "value": path,
                }
    return configuration


def _safe_configuration_preview(configuration, catalog, revision, hostvars=None):
    """Project only bounded, manifest-mapped ordinary values for the UI."""
    configuration = _project_effective_data_directories(configuration, catalog, hostvars)
    definitions = catalog.get("definitions", {}) if isinstance(catalog, dict) else {}
    services = configuration.get("services", {}) if isinstance(configuration, dict) else {}
    if not isinstance(services, dict) or len(services) > 512:
        raise ValueError("configuration preview exceeds deployment limit")

    def scoped(values, settings):
        result = {}
        if not isinstance(values, dict) or len(values) > 256:
            raise ValueError("configuration preview exceeds setting limit")
        for name, item in sorted(values.items()):
            descriptor = settings.get(name)
            if not isinstance(descriptor, dict) or descriptor.get("kind") != "MANAGED" or isinstance(descriptor.get("schema"), dict):
                continue
            ui = descriptor.get("ui", {})
            if not isinstance(ui, dict) or "x-runtimeSecretRequirement" in ui or not isinstance(item, dict):
                continue
            state, source = item.get("state"), item.get("source")
            if state not in ("RESOLVED", "DEFERRED", "UNRESOLVED", "CYCLIC") or source not in ("ROLE_DEFAULT", "DEPLOYMENT_OVERRIDE", "MEMBER_OVERRIDE", "STATIC_REFERENCE", "RUNTIME_DEFERRED"):
                continue
            entry = {"state": state, "source": source}
            value = item.get("value")
            if state == "RESOLVED" and ordinary_presentation_value(descriptor, value):
                entry["value"] = value
            result[name] = entry
        return result

    projected = {}
    for deployment_id, service in sorted(services.items()):
        if not isinstance(service, dict):
            continue
        definition = definitions.get(service.get("serviceType"), {})
        settings = definition.get("configuration", {}).get("settings", {}) if isinstance(definition, dict) else {}
        if not isinstance(settings, dict):
            continue
        members = service.get("members", {})
        if not isinstance(members, dict) or len(members) > 512:
            raise ValueError("configuration preview exceeds member limit")
        projected[deployment_id] = {
            "configuration": scoped(service.get("configuration", {}), settings),
            "members": {member_id: scoped(member.get("configuration", {}), settings)
                        for member_id, member in sorted(members.items()) if isinstance(member, dict)},
        }
    result = {"apiVersion": "platform.installer/service-configuration-preview/v1alpha1", "kind": "ServiceConfigurationPreview", "projectRevision": revision, "services": projected}
    if len(json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")) > 1024 * 1024:
        raise ValueError("configuration preview exceeds response limit")
    return result


def snapshot_host(values, host_id):
    result = {"ansibleHost": values.get("ansible_host", host_id)}
    platform_host = values.get("platform_host", {})
    if isinstance(platform_host, dict) and isinstance(platform_host.get("type"), str):
        result["type"] = platform_host["type"]
    if isinstance(platform_host, dict) and isinstance(platform_host.get("desiredHostname"), str):
        result["desiredHostname"] = platform_host["desiredHostname"]
    raw_port = values.get("ansible_port", 22)
    if isinstance(raw_port, bool):
        return result, {"apiVersion": "platform.installer/finding/v1alpha1", "kind": "Finding",
                        "code": "HOST_TRANSPORT_PORT_INVALID", "status": "BLOCKED",
                        "category": "project-state", "field": "/hosts/%s/ansible_port" % host_id,
                        "safeMessage": "Host SSH port must be an integer between 1 and 65535"}
    if isinstance(raw_port, int):
        port = raw_port
    elif isinstance(raw_port, str) and _CANONICAL_PORT.match(raw_port):
        port = int(raw_port)
    else:
        return result, {"apiVersion": "platform.installer/finding/v1alpha1", "kind": "Finding",
                        "code": "HOST_TRANSPORT_PORT_INVALID", "status": "BLOCKED",
                        "category": "project-state", "field": "/hosts/%s/ansible_port" % host_id,
                        "safeMessage": "Host SSH port must be an integer between 1 and 65535"}
    if port < 1 or port > 65535:
        return result, {"apiVersion": "platform.installer/finding/v1alpha1", "kind": "Finding",
                        "code": "HOST_TRANSPORT_PORT_INVALID", "status": "BLOCKED",
                        "category": "project-state", "field": "/hosts/%s/ansible_port" % host_id,
                        "safeMessage": "Host SSH port must be an integer between 1 and 65535"}
    result["ansiblePort"] = port
    return result, None


def snapshot_execution_connection(values, host):
    """Return private connection input and fail closed on SSH endpoint aliases."""
    ssh_override_keys = (
        "ansible_ssh_args", "ansible_ssh_common_args", "ansible_ssh_extra_args",
        "ansible_ssh_executable", "ansible_ssh_host_key_checking",
        "ansible_host_key_checking", "ansible_ssh_user_known_hosts_file",
        # The SSH plugin accepts these aliases as effective destination and
        # port inputs too. They cannot be proven equal from ansible_host/port.
        "ansible_ssh_host", "ansible_ssh_port",
    )
    return {
        "address": host.get("ansibleHost"),
        "port": host.get("ansiblePort"),
        "mode": values.get("ansible_connection", "ssh"),
        "unsupportedOptions": any(key in values for key in ssh_override_keys),
    }


def validate_host_desired_values(validator, schema_path, hostvars, host_ids):
    findings = []
    for host_id in sorted(host_ids):
        values = hostvars.get(host_id, {})
        platform_host = values.get("platform_host", {}) if isinstance(values, dict) else {}
        prefix = "/hosts/%s/platform_host" % str(host_id).replace("~", "~0").replace("/", "~1")
        for finding in validator.validate(platform_host, schema_path):
            contextual = copy.deepcopy(finding)
            contextual["field"] = prefix + contextual.get("field", "")
            findings.append(contextual)
    return findings


class ActionModule(ActionBase):
    """Build a target-free read-only projection from the loaded Ansible project."""

    TRANSFERS_FILES = False

    def _load(self, path, required=True):
        if not os.path.isfile(path):
            if required:
                raise AnsibleError("Required snapshot input is missing: %s" % os.path.basename(path))
            return {}
        value = self._loader.load_from_file(path)
        return value if isinstance(value, dict) else {}

    def _catalog_reference(self, root, catalog_path, reference):
        """Resolve catalog references in both source and published layouts.

        The catalog digest is layout-independent. Published bundles place the
        generated catalog under ``catalog/`` while service inputs remain under
        ``services/``; legacy generated refs therefore need the bundle root as
        their repository anchor rather than the catalog directory.
        """
        candidates = [os.path.realpath(os.path.join(os.path.dirname(catalog_path), reference))]
        if reference.startswith("../../services/"):
            candidates.append(os.path.realpath(os.path.join(root, reference[6:])))
        if reference.startswith("../fixtures/"):
            candidates.append(os.path.realpath(os.path.join(root, "catalog", reference[3:])))
        for candidate in candidates:
            if os.path.commonpath((root, candidate)) == root and os.path.isfile(candidate):
                return candidate
        raise AnsibleError("Published catalog reference cannot be resolved")

    def _repo_root(self, catalog_path, catalog):
        sources = [item.get("x-sourceManifest") for item in catalog.get("definitions", {}).values() if isinstance(item, dict)]
        current = os.path.dirname(os.path.realpath(catalog_path))
        while True:
            def source_exists(source):
                if not source:
                    return True
                candidates = [os.path.join(current, source)]
                if source.startswith("examples/catalog/"):
                    candidates.append(os.path.join(current, "catalog", source[len("examples/catalog/"):]))
                return any(os.path.isfile(candidate) for candidate in candidates)
            if all(source_exists(source) for source in sources):
                return current
            parent = os.path.dirname(current)
            if parent == current:
                raise AnsibleError("Published catalog source manifests cannot be resolved locally")
            current = parent

    def _service_inputs(self, root, catalog_path, catalog, service_types):
        defaults, schemas, paths = {}, {}, {}
        for service_type, definition in sorted(catalog.get("definitions", {}).items()):
            if service_type not in service_types:
                continue
            entrypoint = (definition.get("roleEntrypoints", {}).get("apply", {}) if isinstance(definition, dict) else {})
            fqcn = entrypoint.get("fqcn")
            if isinstance(fqcn, str) and len(fqcn.split(".")) == 3:
                namespace, collection, role = fqcn.split(".")
                path = os.path.join(root, "services", service_type, "ansible_collections", namespace, collection, "roles", role, "defaults", "main.yml")
                defaults[service_type] = self._load(path)
                paths[service_type] = os.path.relpath(path, root).replace("\\", "/")
            schema_ref = (definition.get("configurationSchema", {}) or {}).get("$ref")
            if isinstance(schema_ref, str):
                schema_path = self._catalog_reference(root, catalog_path, schema_ref)
                schemas[service_type] = self._load(schema_path)
        return defaults, schemas, paths

    def _provenance_sources(self, project_root, documents, host_ids):
        desired_candidates = []
        placement_candidates = {host_id: [] for host_id in host_ids}

        def inspect_inventory(node, logical_path):
            if not isinstance(node, dict):
                return
            for host_id, values in (node.get("hosts", {}) or {}).items():
                if host_id in placement_candidates and isinstance(values, dict) and "platform_deployments" in values:
                    placement_candidates[host_id].append(logical_path)
            for child in (node.get("children", {}) or {}).values():
                inspect_inventory(child, logical_path)

        for document in documents:
            logical_path = document["logicalPath"]
            if not document["revisionIncluded"]:
                continue
            if os.path.splitext(logical_path)[1].lower() not in (".yml", ".yaml", ".json"):
                continue
            parsed = self._load(os.path.join(project_root, *logical_path.split("/")), required=False)
            if "platform_desired_state" in parsed:
                desired_candidates.append(logical_path)
            if logical_path == "inventory/hosts.yml":
                inspect_inventory(parsed.get("all", parsed), logical_path)
            elif logical_path.startswith("inventory/host_vars/") and "platform_deployments" in parsed:
                parts = logical_path.split("/")
                host_id = (parts[2] if len(parts) > 3 else os.path.splitext(os.path.basename(logical_path))[0])
                if host_id in placement_candidates:
                    placement_candidates[host_id].append(logical_path)
            elif logical_path.startswith("inventory/group_vars/") and "platform_deployments" in parsed:
                for host_id in host_ids:
                    placement_candidates[host_id].append(logical_path)
        desired_path = desired_candidates[0] if len(desired_candidates) == 1 else None
        placement_paths = {
            host_id: paths[0] if len(paths) == 1 else None
            for host_id, paths in placement_candidates.items()
        }
        return desired_path, placement_paths

    def _generic_host_references(self, project_root):
        """Return safe host-reference records without service-specific policy."""
        result = {}
        root = os.path.join(project_root, "inventory", "host_vars")
        if not os.path.isdir(root):
            return result
        for host_id in sorted(os.listdir(root)):
            path = os.path.join(root, host_id, "platform-installer.yml")
            document = self._load(path, required=False)
            deployments = document.get("platform_deployments", {}) if isinstance(document, dict) else {}
            if not isinstance(deployments, dict):
                continue
            for deployment_id in sorted(deployments):
                result.setdefault(host_id, []).append({
                    "kind": "placement", "sourceId": str(deployment_id),
                    "field": "inventory/host_vars/%s/platform-installer.yml#platform_deployments.%s" % (host_id, deployment_id),
                })
        return result

    def run(self, tmp=None, task_vars=None):
        del tmp
        task_vars = task_vars or {}
        try:
            requested_root = self._task.args.get("project_root")
            if requested_root and not os.path.isdir(os.path.realpath(requested_root)):
                raise AnsibleError("Selected project directory does not exist")
            inventory_dir = os.path.realpath(task_vars.get("inventory_dir") or os.path.join(requested_root, "inventory"))
            project_root = os.path.realpath(requested_root or os.path.dirname(inventory_dir))
            if os.path.commonpath((project_root, inventory_dir)) != project_root:
                raise AnsibleError("Inventory is outside the selected project root")
            inventory_path = os.path.join(project_root, "inventory", "hosts.yml")
            self._load(inventory_path)
            if os.path.realpath(os.path.dirname(inventory_path)) != inventory_dir:
                raise AnsibleError("Selected project inventory is not the inventory loaded by Ansible")
            catalog_path = os.path.realpath(self._task.args.get("service_catalog_path") or task_vars.get("platform_service_catalog_path", ""))
            catalog_file = self._load(catalog_path)
            catalog = catalog_file.get("platform_service_catalog", catalog_file)
            repo_root = self._repo_root(catalog_path, catalog)
            desired_state = task_vars.get("platform_desired_state", {})
            application_desired_state = desired_state
            desired_schema_version = schema_version(desired_state, task_vars.get("platform_desired_state_contract"))
            applications_enabled = bool(desired_state.get('applicationLibraryDeployments'))
            if task_vars.get('platform_application_expected_fingerprint') and not applications_enabled:
                raise ValueError('APPLICATION_EXECUTION_MODEL_MISMATCH')
            if applications_enabled and "platform_application_rows" not in task_vars:
                raise ValueError("Application resolve role must run before snapshot")
            desired_state = infrastructure_state(desired_state)
            service_types = set(
                item.get("serviceType")
                for item in desired_state.get("serviceDeployments", {}).values()
                if isinstance(item, dict)
            )
            role_defaults, schemas, role_paths = self._service_inputs(
                repo_root, catalog_path, catalog, service_types
            )

            manifest = self._load(os.path.join(project_root, "project.yml"), required=False)
            groups = task_vars.get("groups", {})
            hostvars = task_vars.get("hostvars", {})
            target_ids = sorted(groups.get("platform_targets", []))
            hosts, inventory_deployments, transport_findings = {}, {}, []
            for host_id in target_ids:
                values = hostvars[host_id]
                hosts[host_id], finding = snapshot_host(values, host_id)
                if finding:
                    transport_findings.append(finding)
                inventory_deployments[host_id] = values.get("platform_deployments", {})

            # Core-owned, private execution input.  Do not expose raw hostvars
            # or connection overrides in the public ProjectSnapshot.
            execution_connections = {}
            for host_id in target_ids:
                values = hostvars[host_id]
                execution_connections[host_id] = snapshot_execution_connection(values, hosts[host_id])

            host_addresses = {host_id: {"ansible_host": hosts[host_id]["ansibleHost"]} for host_id in target_ids}
            topology = resolve_topology(
                manifest, {}, target_ids, catalog,
                inventory_deployments_by_host=inventory_deployments,
                ansible_desired_state=desired_state,
                inventory_host_addresses=host_addresses,
            )
            try:
                validator = SchemaValidator(os.path.join(repo_root, "contracts"))
                schema_specs = [
                    ("project/%s/desired-state.schema.json" % desired_schema_version, application_desired_state),
                    ("service-catalog/v1alpha1/schema.json", catalog),
                ]
                if manifest:
                    schema_specs.append(("project/v2alpha1/project-manifest.schema.json", manifest))
                schema_findings = []
                schema_findings.extend(validate_host_desired_values(
                    validator,
                    os.path.join(repo_root, "contracts", "project", "v2alpha1", "host-desired-vars.schema.json"),
                    hostvars,
                    target_ids,
                ))
                for relative, document in schema_specs:
                    schema_findings.extend(validator.validate(document, os.path.join(repo_root, "contracts", *relative.split("/"))))
                if schema_findings or transport_findings:
                    topology["findings"] = sorted(topology.get("findings", []) + schema_findings + transport_findings,
                                                   key=lambda item: (item.get("field", ""), item.get("code", "")))
                    topology["status"] = "BLOCKED"
            except SchemaValidationError:
                topology["findings"] = topology.get("findings", []) + [{
                    "apiVersion": "platform.installer/finding/v1alpha1", "kind": "Finding",
                    "code": "SCHEMA_VALIDATION_ENGINE_ERROR", "status": "BLOCKED",
                    "category": "schema-validation", "field": "schema",
                    "safeMessage": "Published project schemas could not be evaluated",
                }]
                topology["status"] = "BLOCKED"
            materialized = _materialize_resolved_members(
                desired_state, topology, inventory_deployments, target_ids,
            )
            configuration = resolve_service_configuration(
                topology, materialized, catalog, role_defaults, schemas,
            )
            if self._task.args.get("configuration_only") is True:
                _, revision = project_documents(project_root, [])
                return {"changed": False, "snapshot": _safe_configuration_preview(configuration, catalog, revision, hostvars)}
            deployments = materialized.get("serviceDeployments", {}) if isinstance(materialized, dict) else {}
            definitions = catalog.get("definitions", {}) if isinstance(catalog, dict) else {}
            _, _, secret_findings = _service_runtime_secret_requirements(
                deployments, definitions, sorted(hosts),
            )
            if secret_findings:
                configuration["findings"] = sorted(
                    list(configuration.get("findings", [])) + secret_findings,
                    key=lambda item: (item.get("field", ""), item.get("code", ""), item.get("safeMessage", "")),
                )
                configuration["status"] = "BLOCKED"
            endpoints = resolve_service_endpoints(materialized, catalog, configuration, inventory_deployments)
            dns = resolve_dns_zones(materialized, catalog, host_addresses, inventory_deployments)
            pki_defaults_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "roles", "pki_materialize", "defaults", "main.yml"
            )
            pki_defaults = self._load(pki_defaults_path).get("platform_pki_policy_defaults", {})
            pki = resolve_certificate_requests(
                manifest.get("metadata", {}).get("id", os.path.basename(project_root)),
                materialized, host_addresses, pki_defaults, endpoints, inventory_deployments,
            )
            haproxy = resolve_haproxy_backends(
                materialized, catalog, host_addresses, inventory_deployments, endpoints, {}, configuration,
                pki.get("requests", []) if pki.get("status") == "PASS" else [],
            )
            owned = self._task.args.get("installer_owned_paths", [])
            documents, revision = project_documents(project_root, owned)
            document_ownership = {item["logicalPath"]: item["ownership"] for item in documents}
            desired_path, placement_paths = self._provenance_sources(project_root, documents, target_ids)
            for host_id in target_ids:
                placement_path = placement_paths[host_id]
                hosts[host_id]["platformDeployments"] = inventory_deployments[host_id]
                hosts[host_id]["provenance"] = {
                    "semanticSource": "INVENTORY",
                    "physicalOrigin": ({"kind": "INVENTORY", "logicalPath": placement_path}
                                       if placement_path else {"kind": "UNKNOWN"}),
                    "editPolicy": ("FUTURE_EDITABLE" if placement_path and document_ownership.get(placement_path) == "INSTALLER_OWNED"
                                   else "READ_ONLY_UNRESOLVED" if not placement_path else "READ_ONLY"),
                }
            metadata = manifest.get("metadata", {})
            snapshot = build_project_snapshot(
                metadata.get("id", os.path.basename(project_root)),
                metadata.get("name", metadata.get("id", os.path.basename(project_root))),
                documents, revision, catalog, hosts, desired_state, topology,
                configuration, endpoints, pki, haproxy, dns, desired_path, role_paths,
                references={"hosts": self._generic_host_references(project_root)},
                identity_source="PROJECT_MANIFEST" if metadata.get("id") else "PATH_FALLBACK",
            )
            if applications_enabled:
                rechecked = prepare(project_root, application_desired_state,
                                    {host: hostvars[host].get("platform_application_libraries", {}) for host in target_ids},
                                    task_vars.get("platform_desired_state_contract"), self._load, os.path.join(repo_root, "contracts"))
                expected = {(job["libraryId"], job["slotId"], job["hostId"]): job for job in rechecked["jobs"]}
                rows = task_vars["platform_application_rows"]
                actual = {(row["libraryId"], row["slotId"], row["hostId"]) for row in rows}
                if not rechecked["findings"] and (actual != set(expected) or len(rows) != len(expected)):
                    raise ValueError("Application projection placement identity mismatch")
                resolved_findings = []
                for row in rows:
                    job = expected.get((row["libraryId"], row["slotId"], row["hostId"]))
                    if job is None or row["packageIdentity"] != {"application": job["application"]["digest"], "library": job["library"]["digest"]}:
                        raise ValueError("Application package inputs changed during resolution")
                    definition = {"name": row["applicationName"], "version": "1.0.0", "defaults": row["settings"],
                                  "connections": row["connections"], "identity_environment": row["identityNames"]}
                    resolved_findings.extend(validator.validate(definition, os.path.join(repo_root, "contracts", "application-libraries", "v1alpha1", "application.schema.json")))
                applications = project_application_libraries(
                    task_vars["platform_application_rows"], materialized, configuration, catalog, hosts,
                    metadata.get("id", os.path.basename(project_root)),
                )
                applications["findings"].extend(task_vars.get("platform_application_findings", []))
                applications["findings"].extend(rechecked["findings"])
                applications["findings"].extend(resolved_findings)
                applications["findings"].extend(validate_public_projection(applications))
                if applications["findings"]:
                    applications.update(status="BLOCKED", libraries={})
                    snapshot.update(status="PARTIAL", partial=True)
                    snapshot["findings"].extend(applications["findings"])
                    snapshot["validation"]["status"] = "BLOCKED"
                    snapshot["readiness"]["status"] = "BLOCKED"
                snapshot["apiVersion"] = "platform.installer/project-snapshot/v2alpha1"
                snapshot["applicationLibraries"] = applications
                private_image_lock = resolve_image_lock(task_vars.get('platform_artifact_lock'),
                                                        (manifest or {}).get('artifactLock'))
                if task_vars.get('platform_application_expected_fingerprint'):
                    model = application_execution_model(snapshot, private_image_lock)
                    if (model['semanticFingerprint'] != task_vars['platform_application_expected_fingerprint'] or
                            model['libraryIds'] != task_vars.get('platform_application_expected_library_ids')):
                        raise ValueError('APPLICATION_EXECUTION_MODEL_MISMATCH')
                snapshot.pop("snapshotFingerprint", None)
                snapshot["snapshotFingerprint"] = canonical_digest(snapshot)
            # This is controller-private Core plumbing for the immediately
            # following plan action.  `snapshot` remains the redacted public
            # read-only projection returned to Go/Wails.
            # This is private Core-to-plan plumbing.  The public snapshot
            # remains redacted; the immediately following planner receives
            # the resolved configuration needed to build a digest-bound
            # execution manifest.
            return {"changed": False, "snapshot": snapshot, "pki_materialization": pki,
                    "application_image_lock": private_image_lock if applications_enabled else {},
                    "execution_configuration": configuration,
                    "execution_connections": execution_connections}
        except (AnsibleError, KeyError, OSError, TypeError, ValueError):
            return {
                "failed": True,
                "changed": False,
                "error_code": "PROJECT_SNAPSHOT_INPUT_INVALID",
                "msg": "Project snapshot inputs could not be loaded; inspect the structured finding",
                "finding": {
                    "apiVersion": "platform.installer/finding/v1alpha1",
                    "kind": "Finding", "code": "PROJECT_SNAPSHOT_INPUT_INVALID",
                    "status": "BLOCKED", "category": "project-snapshot",
                    "field": "project", "safeMessage": "Project snapshot inputs could not be loaded",
                },
            }

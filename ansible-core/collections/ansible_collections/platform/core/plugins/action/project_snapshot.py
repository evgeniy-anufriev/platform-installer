from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import os
import re

from ansible.errors import AnsibleError
from ansible.plugins.action import ActionBase

from ansible_collections.platform.core.plugins.module_utils.dns_resolution import resolve_dns_zones
from ansible_collections.platform.core.plugins.module_utils.deployment_plan import _service_runtime_secret_requirements
from ansible_collections.platform.core.plugins.module_utils.haproxy_resolution import resolve_haproxy_backends
from ansible_collections.platform.core.plugins.module_utils.pki_resolution import resolve_certificate_requests
from ansible_collections.platform.core.plugins.module_utils.project_snapshot import build_project_snapshot, project_documents
from ansible_collections.platform.core.plugins.module_utils.service_configuration_resolution import resolve_service_configuration
from ansible_collections.platform.core.plugins.module_utils.service_endpoint_resolution import resolve_service_endpoints
from ansible_collections.platform.core.plugins.module_utils.schema_validation import SchemaValidationError, SchemaValidator
from ansible_collections.platform.core.plugins.module_utils.topology_resolution import resolve_topology


_CANONICAL_PORT = re.compile(r"^(0|[1-9][0-9]*)$")


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
                    ("project/v2alpha1/desired-state.schema.json", desired_state),
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
            materialized = copy.deepcopy(desired_state)
            if topology.get("status") == "PASS":
                for deployment_id, resolved in topology["resolvedTopology"].get("serviceDeployments", {}).items():
                    deployment = materialized.get("serviceDeployments", {}).get(deployment_id)
                    if isinstance(deployment, dict) and resolved.get("members"):
                        deployment["members"] = resolved["members"]
            configuration = resolve_service_configuration(
                topology, materialized, catalog, role_defaults, schemas,
            )
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
            # This is controller-private Core plumbing for the immediately
            # following plan action.  `snapshot` remains the redacted public
            # read-only projection returned to Go/Wails.
            # This is private Core-to-plan plumbing.  The public snapshot
            # remains redacted; the immediately following planner receives
            # the resolved configuration needed to build a digest-bound
            # execution manifest.
            return {"changed": False, "snapshot": snapshot, "pki_materialization": pki,
                    "execution_configuration": configuration}
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

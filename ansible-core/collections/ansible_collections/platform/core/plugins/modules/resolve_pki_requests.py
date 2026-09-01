#!/usr/bin/python
from __future__ import absolute_import, division, print_function

import yaml
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.platform.core.plugins.module_utils.pki_resolution import resolve_certificate_requests
from ansible_collections.platform.core.plugins.module_utils.project_state import canonical_inventory_members, topology_with_inventory_members


def _load_yaml(path):
    with open(path, "r") as handle:
        value = yaml.safe_load(handle) or {}
    return value if isinstance(value, dict) else {}


def _inventory_hosts(inventory):
    all_group = inventory.get("all", {}) if isinstance(inventory, dict) else {}
    hosts = all_group.get("hosts", {}) if isinstance(all_group, dict) else {}
    return hosts if isinstance(hosts, dict) else {}


def main():
    module = AnsibleModule(argument_spec={
        "project_path": {"type": "path", "required": True},
        "inventory_path": {"type": "path", "required": True},
        "pki_defaults": {"type": "dict", "required": True},
    }, supports_check_mode=True)
    try:
        project = _load_yaml(module.params["project_path"])
        inventory = _load_yaml(module.params["inventory_path"])
        desired = project.get("desiredState", {}) if isinstance(project.get("desiredState"), dict) else {}
        hosts = _inventory_hosts(inventory)
        by_host = {host_id: values.get("platform_deployments", {}) for host_id, values in hosts.items() if isinstance(values, dict)}
        members, findings = canonical_inventory_members(by_host, hosts.keys())
        if findings:
            result = {"status": "BLOCKED", "findings": findings}
        else:
            result = resolve_certificate_requests(project.get("metadata", {}).get("id", "project"), topology_with_inventory_members(desired, members), hosts, module.params["pki_defaults"])
    except Exception as error:
        module.fail_json(msg="PKI request resolution failed", error_code="PKI_RESOLUTION_FAILED", safe_details=str(error))
    if result.get("status") != "PASS":
        module.fail_json(msg="PKI request resolution is blocked", error_code="PKI_RESOLUTION_BLOCKED", findings=result.get("findings", []))
    module.exit_json(changed=False, pki=result)


if __name__ == "__main__":
    main()

#!/usr/bin/python
from ansible.module_utils.basic import AnsibleModule
from ansible_collections.platform.core.plugins.module_utils.haproxy_resolution import resolve_haproxy_backends

def main():
    module = AnsibleModule(argument_spec={
        "desired_state": {"type": "dict", "required": True}, "service_catalog": {"type": "dict", "required": True},
        "inventory_hosts": {"type": "dict", "required": True}, "inventory_deployments": {"type": "dict", "required": True},
        "resolved_service_endpoints": {"type": "dict", "required": True}, "backend_defaults": {"type": "dict", "default": {}},
    }, supports_check_mode=True)
    result = resolve_haproxy_backends(module.params["desired_state"], module.params["service_catalog"], module.params["inventory_hosts"], module.params["inventory_deployments"], module.params["resolved_service_endpoints"], module.params["backend_defaults"])
    if result["status"] != "PASS":
        module.fail_json(msg="HAProxy backend resolution is blocked", error_code="HAPROXY_BACKEND_RESOLUTION_BLOCKED", findings=result["findings"])
    module.exit_json(changed=False, resolved_haproxy_backends=result)

if __name__ == "__main__":
    main()

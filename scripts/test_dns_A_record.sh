sudo python3 - <<'PY'
import json, os, subprocess, sys
from pathlib import Path
import yaml

run = Path("/var/lib/platform-installer/execution/runs/installer-fdae863d27dee46cd8689e27fff2ce54")
project = run / "project"
runtime = Path("/var/lib/platform-installer/runtime/current").resolve()
collections = runtime / "ansible-core/collections"
sys.path.insert(0, str(collections))

from ansible_collections.platform.core.plugins.module_utils.dns_resolution import resolve_dns_zones

env = os.environ.copy()
env["ANSIBLE_CONFIG"] = str(runtime / "ansible-core/ansible.cfg")
env["ANSIBLE_COLLECTIONS_PATH"] = str(collections)
result = subprocess.run(
    ["ansible-inventory", "-i", str(project / "inventory/hosts.yml"), "--list"],
    env=env, capture_output=True, text=True, check=True)
inventory = json.loads(result.stdout)
hosts = inventory["_meta"]["hostvars"]
desired = yaml.safe_load(
    (project / "inventory/group_vars/all/platform-installer.yml").read_text()
)["platform_desired_state"]
catalog = yaml.safe_load(
    (runtime / "catalog/service-catalog.yml").read_text()
)
catalog = catalog.get("platform_service_catalog", catalog)

resolved = resolve_dns_zones(
    desired, catalog,
    {name: {"ansible_host": value.get("ansible_host", name)}
     for name, value in hosts.items() if name != "localhost"},
    {name: value.get("platform_deployments", {})
     for name, value in hosts.items() if name != "localhost"},
    include_service_endpoints=False,
    include_group_wildcards=True)

print("Статус:", resolved["status"])
for finding in resolved.get("findings", []):
    print(finding.get("code"), finding.get("field"))
for name, zone in resolved.get("zones", {}).items():
    print("DNS:", name, "зона:", zone["zone"],
          "TTL:", repr(zone["defaultTtl"]))
    for record in zone.get("records", []):
        if record.get("type") == "A":
            print(json.dumps(record, ensure_ascii=False))
PY

sudo sh -c '
set -eu
runtime=$(readlink -f /var/lib/platform-installer/runtime/current)
project=/var/tmp/servers5

export ANSIBLE_CONFIG="$runtime/ansible-core/ansible.cfg"
export ANSIBLE_COLLECTIONS_PATH="$runtime/ansible-core/collections"

ansible-playbook \
  -i "$project/inventory/hosts.yml" \
  "$runtime/ansible-core/playbooks/service-configuration-preview.yml" \
  -e "platform_project_root=$project" \
  -e "platform_service_catalog_path=$runtime/catalog/service-catalog.yml"
'
sudo sh -c '
r=$(readlink -f /var/lib/platform-installer/runtime/current)
p="$r/ansible-core/collections/ansible_collections/platform/core/plugins"

sha256sum "$p/action/project_snapshot.py" "$p/module_utils/project_snapshot.py"
sed -n "1,28p" "$p/module_utils/project_snapshot.py"
'


sudo python3 - <<'PY'
import os, json, subprocess
from pathlib import Path
import yaml

base = Path("/var/lib/platform-installer/execution/runs")
projects = []
for manifest in base.glob("*/project/project.yml"):
    doc = yaml.safe_load(manifest.read_text()) or {}
    if doc.get("metadata", {}).get("name") == "installer-5s":
        projects.append(manifest)

if not projects:
    raise SystemExit("Копия installer-5s на узле не найдена.")

project = max(projects, key=lambda p: p.stat().st_mtime).parent
runtime = Path("/var/lib/platform-installer/runtime/current").resolve()
print("Проверяется копия:", project, flush=True)

env = os.environ.copy()
env["ANSIBLE_CONFIG"] = str(runtime / "ansible-core/ansible.cfg")
env["ANSIBLE_COLLECTIONS_PATH"] = ":".join(
    [str(runtime / "ansible-core/collections")] +
    [str(p) for p in sorted(runtime.glob("services/*/ansible_collections"))]
)
variables = {
    "platform_project_root": str(project),
    "platform_service_catalog_path": str(runtime / "catalog/service-catalog.yml"),
}
subprocess.run([
    "ansible-playbook", "-i", str(project / "inventory/hosts.yml"),
    str(runtime / "ansible-core/playbooks/project-snapshot-machine.yml"),
    "-e", json.dumps(variables),
], env=env)
PY

sudo python3 <<'PY'
import json
import subprocess
from pathlib import Path

base = Path("/var/lib/platform-installer/execution/runs")
statuses = list(base.glob("*/status.json"))
if not statuses:
    raise SystemExit("Запуски не найдены")

run = max(statuses, key=lambda p: p.stat().st_mtime).parent
print("Запуск:", run.name)

result = subprocess.run(
    ["ansible-inventory", "-i",
     str(run / "project/inventory/hosts.yml"), "--list"],
    capture_output=True, text=True
)
if result.returncode:
    raise SystemExit("Не удалось прочитать inventory через ansible-inventory")

hosts = json.loads(result.stdout).get("_meta", {}).get("hostvars", {})
for host, variables in sorted(hosts.items()):
    for deployment, settings in variables.get("platform_deployments", {}).items():
        for member, data in settings.get("members", {}).items():
            if not set(data.get("roles", [])) & {"broker", "controller"}:
                continue
            node_id = data.get("configuration", {}).get("nodeId", "НЕ ЗАДАН")
            print(f"{host}: {deployment}/{member}, nodeId={node_id}")
PY

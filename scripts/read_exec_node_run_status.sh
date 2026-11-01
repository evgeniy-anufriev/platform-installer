sudo python3 - <<'PY'
import json
import subprocess
from pathlib import Path

root = Path("/var/lib/platform-installer/execution/runs")
files = sorted(root.glob("*/status.json"),
               key=lambda p: p.stat().st_mtime, reverse=True)

for path in files[:5]:
    status = json.loads(path.read_text())
    run_id = path.parent.name
    unit = f"platform-installer-run-{run_id}.service"
    process = subprocess.run(
        ["systemctl", "is-active", unit],
        capture_output=True, text=True
    )
    print("Run:", run_id)
    print("Статус:", status.get("state"))
    print("Обновлён:", status.get("updatedAt"))
    print("Процесс:", process.stdout.strip())
    print("Каталог:", path.parent)
    print()
PY

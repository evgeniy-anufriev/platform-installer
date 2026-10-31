sudo find /var/lib/platform-installer/execution \
  -type f -path '*/raw-ansible-diagnostics/ansible-output-*.log' \
  -printf '%T@ %p\n' | sort -nr | head -5


sudo python3 - <<'PY'
import json
from pathlib import Path

base = Path("/var/lib/platform-installer/execution/runs")
runs = sorted(base.glob("*/status.json"),
              key=lambda p: p.stat().st_mtime, reverse=True)

for path in runs:
    status = json.loads(path.read_text())
    if "FAILED" not in json.dumps(status).upper():
        continue
    run = path.parent
    print("Запуск:", run.name)
    print("Копия проекта:", run / "project")
    print("Состояние:", json.dumps(status, ensure_ascii=False))
    print("Файлы inventory:")
    for item in sorted((run / "project" / "inventory").rglob("*.yml")):
        print(item)
    break
else:
    print("Завершившийся ошибкой запуск не найден.")
PY

sudo sh <<'SH'
set -eu

run=$(find /var/lib/platform-installer/execution/runs \
  -mindepth 2 -maxdepth 2 -type f -name status.json \
  -printf '%T@ %h\n' | sort -nr | head -n 1 | cut -d ' ' -f 2-)

test -n "$run" || {
  echo "Запуски не найдены"
  exit 1
}

echo "Проверяется запуск: $run"

ansible-inventory \
  -i "$run/project/inventory/hosts.yml" \
  --graph platform_targets
SH

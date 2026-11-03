#!/usr/bin/env bash
# Run on installer-04: sudo bash diagnose_vault_ca.sh
# Read-only CA probe for the owner's isolated installer-5 project.
# Uses the failed run's inventory/trust; does not replay installation or log passwords.
set -euo pipefail

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
  printf '%s\n' 'На installer-04: sudo bash diagnose_vault_ca.sh' \
    'Автоматически выбирает последний FAILED-запуск project-bc8d04c2dcc8c9e4.' \
    'Запрашивает SSH- и sudo-пароли; выполняет только чтение CA на node1.'
  exit 0
fi
if (( $# != 0 )); then
  printf '%s\n' 'Аргументы не требуются. Используйте --help.' >&2
  exit 2
fi
if (( EUID != 0 )); then
  exec sudo -- bash "$(readlink -f -- "$0")"
fi

for tool in python3 ansible-playbook mktemp; do
  command -v "$tool" >/dev/null || {
    printf 'Не найдена команда: %s\n' "$tool" >&2
    exit 1
  }
done

readonly PROJECT_ID=project-bc8d04c2dcc8c9e4
readonly CA_SOURCE=/etc/platform-installer/pki/project-bc8d04c2dcc8c9e4/installer-tls--node1/ca-chain.pem
readonly RUNTIME=/var/lib/platform-installer/runtime/current

RUN=$(python3 - "$PROJECT_ID" <<'PY'
import json
import sys
from pathlib import Path

root = Path('/var/lib/platform-installer/execution/runs')
matches = []
for metadata_path in root.glob('*/metadata.json'):
    try:
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
        if metadata.get('projectIdentity') != sys.argv[1]:
            continue
        run = metadata_path.parent
        if run.is_symlink() or run.resolve().parent != root.resolve():
            raise SystemExit('Небезопасный путь рабочего каталога запуска.')
        status_path = run / 'status.json'
        status = json.loads(status_path.read_text(encoding='utf-8'))
        if status.get('state') in ('PENDING', 'STARTING', 'RUNNING'):
            raise SystemExit('У проекта есть активный запуск. Дождитесь его завершения.')
        if status.get('state') == 'FAILED':
            matches.append((status_path.stat().st_mtime_ns, str(run)))
    except (OSError, ValueError, AttributeError):
        continue
if not matches:
    raise SystemExit('FAILED-запуск project-bc8d04c2dcc8c9e4 не найден. Другой проект не выбран.')
print(max(matches)[1])
PY
)
readonly RUN

for required in "$RUN/project/inventory/hosts.yml" "$RUN/known_hosts" "$RUNTIME/ansible-core/ansible.cfg"; do
  if [[ ! -f "$required" || ! -r "$required" ]]; then
    printf 'Нет доступного файла: %s\n' "$required" >&2
    exit 1
  fi
done

printf 'Execution Node: %s\nЗапуск: %s\nCA на node1: %s\n' "$(hostname)" "$RUN" "$CA_SOURCE"
printf '%s\n' 'Проверяется только чтение CA. Пароли вводите в запросах Ansible.'

umask 077
WORK=$(mktemp -d /var/tmp/platform-installer-ca-probe.XXXXXXXX)
cleanup() { rm -rf -- "$WORK"; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
cat > "$WORK/probe.yml" <<'YAML'
---
- name: Диагностика чтения CA без установки
  hosts: localhost
  connection: local
  gather_facts: false
  tasks:
    - name: Чтение CA выбранного провайдера из подготовленных PKI-файлов
      ansible.builtin.slurp:
        src: "{{ lookup('ansible.builtin.env', 'PLATFORM_CA_PROBE_SOURCE') }}"
      delegate_to: node1
      become: true
      no_log: false
YAML

# Ordinary console output, without Installer event callbacks or persistent logs.
# As in the controller, use only this run's approved host keys; never TOFU here.
unset ANSIBLE_CALLBACK_PLUGINS ANSIBLE_CALLBACK_WHITELIST ANSIBLE_SKIP_TAGS ANSIBLE_RUN_TAGS
unset ANSIBLE_SSH_COMMON_ARGS ANSIBLE_SSH_EXTRA_ARGS ANSIBLE_SSH_EXECUTABLE ANSIBLE_PRIVATE_KEY_FILE
export ANSIBLE_CONFIG="$RUNTIME/ansible-core/ansible.cfg"
export ANSIBLE_COLLECTIONS_PATH="$RUNTIME/ansible-core/collections"
export ANSIBLE_STDOUT_CALLBACK=default ANSIBLE_CALLBACKS_ENABLED='' ANSIBLE_LOAD_CALLBACK_PLUGINS=0
export ANSIBLE_HOST_KEY_CHECKING=True ANSIBLE_SSH_HOST_KEY_CHECKING=True
export ANSIBLE_SSH_ARGS="-F none -o UserKnownHostsFile=$RUN/known_hosts -o GlobalKnownHostsFile=none -o KnownHostsCommand=none -o UpdateHostKeys=no -o StrictHostKeyChecking=yes -o IdentitiesOnly=yes"
export ANSIBLE_LOCAL_TEMP="$WORK/local"
export PLATFORM_CA_PROBE_SOURCE="$CA_SOURCE"

if ansible-playbook -i "$RUN/project/inventory/hosts.yml" -u scada-docker \
    --ask-pass --ask-become-pass "$WORK/probe.yml"; then
  printf '%s\n' 'PASS: CA прочитан с inventory и SSH-доверием выбранного запуска.' \
    'Это проверка чтения CA с повторно введёнными паролями, а не всего запуска установщика.'
else
  result=$?
  printf '%s\n' 'FAIL: исходная ошибка Ansible показана выше. Передавайте только сообщение ошибки, без паролей.' >&2
  exit "$result"
fi

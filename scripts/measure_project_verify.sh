#!/bin/sh
# Run on the Execution Node: sudo sh scripts/measure_project_verify.sh /absolute/project/path
set -eu

if [ "$#" -ne 1 ]; then
    echo "Использование: sudo sh $0 /абсолютный/путь/к/проекту" >&2
    exit 2
fi
project=$1
case "$project" in
    /*) ;;
    *) echo "Укажите абсолютный путь к проекту на узле исполнения." >&2; exit 2 ;;
esac
test -f "$project/inventory/hosts.yml" || {
    echo "Не найден inventory/hosts.yml в указанном проекте." >&2
    exit 2
}

runtime=$(readlink -f /var/lib/platform-installer/runtime/current)
playbook="$runtime/ansible-core/playbooks/project-snapshot-machine.yml"
test -f "$playbook" || {
    echo "В активном runtime отсутствует project-snapshot-machine.yml." >&2
    exit 2
}
export ANSIBLE_CONFIG="$runtime/ansible-core/ansible.cfg"
collections="$runtime/ansible-core/collections"
for p in "$runtime"/services/*/ansible_collections; do
    [ ! -d "$p" ] || collections="$collections:$p"
done
export ANSIBLE_COLLECTIONS_PATH="$collections"

# JSON preserves paths containing spaces or quote characters.
variables=$(python3 -c 'import json, sys; print(json.dumps({"platform_project_root": sys.argv[1], "platform_service_catalog_path": sys.argv[2]}))' \
    "$project" "$runtime/catalog/service-catalog.yml")

echo "Проверяемый проект: $project"
echo "Runtime: $runtime"
started=$(date +%s)
rc=0
ansible-playbook \
    -i "$project/inventory/hosts.yml" \
    "$playbook" \
    -e "$variables" || rc=$?
finished=$(date +%s)
printf '\nВремя проверки Core: %s сек. Код завершения: %s\n' "$((finished - started))" "$rc"
exit "$rc"

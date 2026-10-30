read -r -p "Путь к проекту на Linux: " project

sudo sh -s -- "$project" <<'SH'
set -eu
project=$1
test -f "$project/inventory/hosts.yml" || {
    echo "Не найден inventory/hosts.yml в указанной папке"
    exit 1
}
runtime=$(readlink -f /var/lib/platform-installer/runtime/current)
export ANSIBLE_CONFIG="$runtime/ansible-core/ansible.cfg"
collections="$runtime/ansible-core/collections"
for p in "$runtime"/services/*/ansible_collections; do
    if [ -d "$p" ]; then collections="$collections:$p"; fi
done
export ANSIBLE_COLLECTIONS_PATH="$collections"

ansible-playbook \
  -i "$project/inventory/hosts.yml" \
  "$runtime/ansible-core/playbooks/project-snapshot.yml" \
  -e "platform_project_root=$project" \
  -e "platform_service_catalog_path=$runtime/catalog/service-catalog.yml"
SH

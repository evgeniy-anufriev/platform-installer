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

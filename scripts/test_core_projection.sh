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

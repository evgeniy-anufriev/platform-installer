# A1 target-free application library fixture

No project.yml required. Inventory addresses are documentation-only TEST-NET.
The package closure is trusted operator input: defaults/templates are executable
Ansible/Jinja and must be reviewed before use. A1 does not render templates or
connect to hosts, registry, Vault or Docker. The image tag is a QA requirement,
not evidence of immutable delivery; image locking/loading belongs to A2.1.

Use ansible-core/playbooks/project-snapshot.yml or validate.yml on an Execution
Node with inventory/hosts.yml, platform_project_root and a published catalog.
Select desired-state v3alpha1 explicitly; library output uses snapshot v2alpha1.
Provider allocation uses the Redis and ClickHouse collections as well as Core.
From the repository root on the Execution Node:

```bash
export ANSIBLE_COLLECTIONS_PATH="$PWD/ansible-core/collections:$PWD/services/redis/ansible_collections:$PWD/services/clickhouse/ansible_collections"
ansible-playbook -i examples/valid/application-libraries/inventory/hosts.yml \
  ansible-core/playbooks/validate.yml \
  -e platform_project_root="$PWD/examples/valid/application-libraries" \
  -e platform_service_catalog_path="$PWD/examples/catalog/service-catalog.yml"
```

This target-free fixture has no immutable application image lock; successful
validation does not authorize installation.

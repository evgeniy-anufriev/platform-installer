# Application playbooks

Paths below are relative to `ansible-core/playbooks/applications/`.

| Entrypoint | Purpose |
| --- | --- |
| `apply.yml` | Prepare selected libraries, then apply and verify each library in order |
| `verify.yml` | Verify selected application placements and endpoints |
| `post-install.yml` | Run declared terminal package scripts after successful installation |
| `images/inputs.yml` | Resolve image-preparation inputs without contacting target nodes |
| `images/prepare.yml` | Prepare image metadata through selected target nodes |
| `images/plan.yml` | Compose image preparation with the existing machine planner |

`stages/` contains imported playbooks with their own host scope. The
`providers-*.yml` playbooks also support standalone provider operations.
`tasks/` contains task lists for `include_tasks`/`import_tasks`; these files
are not independent playbooks.

From a configured Ansible environment with the Core and required service
collections available, ordinary inventory remains the input:

```sh
ansible-playbook -i /project/inventory/hosts.yml \
  /bundle/ansible-core/playbooks/applications/verify.yml \
  -e platform_project_root=/project \
  -e platform_service_catalog_path=/bundle/catalog/service-catalog.yml
```

Use the same inventory and documented runtime inputs for Apply, provider and
image operations. Runtime secrets belong in protected runtime files, never in
inventory or project files. Go and the Installer UI are not required.

The relocated entrypoints replace the former root-level
`application-libraries-*.yml` and `application-images-*.yml` paths. Runtime
controllers and their playbooks must come from the same verified bundle.
`platform_contracts_root` remains an explicit override; native resolution also
works when the playbook is imported from another directory.

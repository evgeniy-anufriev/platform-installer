# Standalone PostgreSQL application providers

Two application packages, `apigateway` and `datamanager`, use one PostgreSQL hook.
Both logical instances belong to `sdku`; its membership includes node1/node2.
One library database/schema and two login accounts are provisioned, regardless
of Docker placement count. This fixture contains references only, no passwords.

Use `ansible-core/playbooks/applications/stages/providers-{preflight,apply,verify}.yml`
with this inventory, `platform_project_root` and `platform_service_catalog_path`.
Collection paths include `ansible-core/collections` and `services/postgresql`.
Supply `platform_postgresql_secret_files` and a private
`platform_postgresql_application_secret_root` using protected runtime variables
on the Execution Node. Each file and directory under that root is owned by the
controller identity and private (files 0600, directories 0700), without symlinks.
Never store runtime credential paths or values in this fixture.

The provider must already be installed, with its local administrative socket,
password HBA and PKI materialization available. These hooks do not install
PostgreSQL, change HBA, issue certificates or run Docker/Vault. A2 still blocks
container startup with accounts until A4 delivers secrets through Vault Agent.

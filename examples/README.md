# CORE-01 project fixtures

These directories are ordinary Ansible projects. Each fixture keeps
`group_vars` and `host_vars` next to `inventory/hosts.yml` under the inventory
directory, so standard `ansible-playbook -i <fixture>/inventory/hosts.yml`
variable auto-loading works without extra options. None requires the future
Installer, Go code, or a proprietary launcher.

`valid/` contains portable desired-state examples that CORE-01 validation must
accept. `invalid/` contains one deliberately isolated contract error per
fixture and an `expected.yml` file describing the structured finding expected
from validation.

`catalog/service-catalog.yml` is a schema-conformant derived fixture catalog.
Its complete ServiceManifest-shaped definitions preserve the same semantics as
the authored Kafka package and explicitly mark PostgreSQL/etcd as
conformance-only. Fixture
`inventory/group_vars` reference this artifact and their adjacent `project.yml` manifest;
they do not embed a second copy of catalog or project metadata.

The catalog is generated offline from `services/kafka/service.yml` and the two
authored manifests under `catalog/manifests/`:

```bash
python ansible-core/tools/build_fixture_catalog.py
python ansible-core/tools/build_fixture_catalog.py --check
```

`x-definitionDigest` is SHA256 of canonical JSON for the embedded definition
after relative schema/compatibility references are relocated, but before the
generated `x-definitionDigest` and `x-sourceManifest` fields are added. A
consumer can therefore recompute it directly from the catalog by removing those
two generated fields. The catalog digest is SHA256 of canonical JSON for
`apiVersion`, `kind`, and the assembled definitions; the self-referential
top-level `digest` field is excluded. Canonical JSON uses UTF-8, recursively
sorted object keys, original array order, and compact separators. The generator
also synchronizes/checks all fixture project catalog locks.

Host-specific desired inputs are stored under the `platform_host` variable in
`inventory/host_vars/<inventory-host>.yml`. The value of `platform_host` conforms to the
published `host-desired-vars.schema.json`; the wrapper itself is the normal
Ansible variable name and is not part of that value schema.

The PostgreSQL fixtures are contract-conformance inputs only. They do not imply
that a PostgreSQL production role is implemented or scheduled before Kafka.

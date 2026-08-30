# Platform Ansible Core

This directory contains the standalone Ansible Core. It has no dependency on
the Installer backend or frontend.

## Validate a project

From this directory, run:

```bash
ansible-playbook -i examples/valid/inventory/hosts.yml playbooks/validate.yml
```

Ansible loads `project.yml` as the portable metadata/catalog-lock manifest and
the example's normal `inventory/group_vars/all/platform.yml` as desired
topology. Keeping both variable directories beside the selected inventory
allows standard Ansible auto-loading with only `-i inventory/hosts.yml`. The
default manifest location is one directory above `inventory/`; an explicit
`platform_project_manifest_path` can select another file. The group variables
reference a separately published service catalog artifact through
`platform_service_catalog_path`; service definitions are not copied into the
project variables. Validation runs once on the controller, does not gather
target facts, and does not connect to or modify target hosts. Its
machine-readable result is written to `.runtime/validation-result.json` by
default. Inventories declare `localhost` with `ansible_connection: local` as
the controller and put desired hosts in `platform_targets`; this keeps
controller execution independent from target cardinality. The same playbook
also runs when `platform_targets` is empty:

```bash
ansible-playbook -i examples/empty/inventory/hosts.yml playbooks/validate.yml
```

Use another output location with a non-secret extra variable:

```bash
ansible-playbook -i inventory/hosts.yml playbooks/validate.yml \
  -e platform_validation_artifact=/tmp/platform-validation.json
```

For a root fixture, the equivalent command from `ansible-core/` is:

```bash
ansible-playbook -i ../examples/valid/kafka-single/inventory/hosts.yml playbooks/validate.yml
```

Contract or reference errors still produce the JSON artifact and then fail the
play. Ansible therefore exits non-zero without requiring an operator to parse a
Python traceback. The artifact contains no inventory connection variables and
must never be given secret values.

The `projectFingerprint` covers the manifest and topology together. Inventory
connection variables, runtime credentials, and external catalog contents are
deliberately excluded; later plan fingerprints pin their own catalog and
artifact evidence.

### Current schema boundary

CORE-01 currently enforces the documented manifest identity, catalog locks,
service references, modes, explicit hosts, supported member roles, and
`distinctHosts` constraints with its dependency-free validator. Full JSON
Schema Draft 2020-12 enforcement is **not implemented yet**. The baseline RED
OS Ansible controller does not provide the Python `jsonschema` package, and
Core must not download it from the Internet. A later contract-conformance slice
must supply an offline-pinned validator before the complete published schemas
can be claimed as enforced.

## Development tests

The validator logic uses only the Python standard library:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

The shared fixture catalog has one authored Kafka source plus explicitly
conformance-only PostgreSQL/etcd sources. Rebuild or check it offline with the
PyYAML already supplied by the Ansible controller environment:

```bash
python tools/build_fixture_catalog.py
python tools/build_fixture_catalog.py --check
```

This is a development artifact generator, not a launcher or runtime dependency
for normal `ansible-playbook` operation.

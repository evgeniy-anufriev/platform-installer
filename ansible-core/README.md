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

### Draft 2020-12 schema engine

CORE-01 uses `jsonschema` 4.17.3, vendored behind
`platform.core`'s `SchemaValidator` interface together with its pinned pure-
Python dependencies (`attrs` 23.2.0 and `pyrsistent` 0.19.3). The engine is
selected explicitly as `Draft202012Validator` and uses a `FormatChecker`.
The vendored source licenses are retained beside the packages.

The validator builds a registry from the local `contracts/` directory by
schema `$id`. Only registered local IDs and fragments are resolvable; HTTP(S)
and file handlers fail with `SCHEMA_EXTERNAL_REF_FORBIDDEN`, so schema
validation cannot make a network request. Engine exceptions and validation
errors are converted to safe `Finding` records without copying instance
values or raw exception text into diagnostics.
The published `validate_project` action plugin executes this boundary on the
controller; it is intentionally not transferred to managed hosts, which also
keeps the vendored JSON schema resources available offline.

The playbook passes the contracts root explicitly or defaults to the sibling
`contracts/` directory:

```bash
ansible-playbook -i ../examples/valid/kafka-single/inventory/hosts.yml \
  playbooks/validate.yml \
  -e platform_contracts_root=../contracts
```

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

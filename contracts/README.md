# Published contracts

This directory contains the machine-readable contracts shared by standalone
Ansible Core, service packages and future Installer adapters. The contracts do
not depend on Go, Wails, SQLite or a proprietary launcher.

## Published versions

| Contract | Version | Schema |
| --- | --- | --- |
| Project manifest (`project.yml`) | `v2alpha1` | `project/v2alpha1/project-manifest.schema.json` |
| Project desired topology (`platform_project`) | `v2alpha1` | `project/v2alpha1/desired-state.schema.json` |
| Host desired variables (`platform_host`) | `v2alpha1` | `project/v2alpha1/host-desired-vars.schema.json` |
| Assembled project validation input | `v2alpha1` | `project/v2alpha1/assembled-project.schema.json` |
| Installer application configuration | `v1alpha1` | `application-config/v1alpha1/schema.json` |
| Project edit command (compatibility) | `v1alpha2` | `project-edit/v1alpha2/schema.json` |
| CreateServer command with required type | `v1alpha3` | `project-edit/v1alpha3/schema.json` |
| Server CRUD command with required desired hostname | `v1alpha4` | `project-edit/v1alpha4/schema.json` |
| Server and topology edit commands | `v1alpha5` | `project-edit/v1alpha5/schema.json` |
| Server, topology and provider edit commands | `v1alpha6` | `project-edit/v1alpha6/schema.json` |
| Local structural Save plan/result | `v1alpha1` | `project-save/v1alpha1/schema.json` |
| Derived saved-revision verification | `v1alpha1` | `project-verification/v1alpha1/schema.json` |
| Service package manifest | `v1alpha1` | `service-manifest/v1alpha1/schema.json` |
| Derived service catalog | `v1alpha1` | `service-catalog/v1alpha1/schema.json` |
| Finding | `v1alpha1` | `finding/v1alpha1/schema.json` |
| Project validation result | `v1alpha1` | `validation-result/v1alpha1/schema.json` |
| Resolved service configuration | `v1alpha1` | `resolved-service-configuration/v1alpha1/schema.json` |
| Resolved plan | `v1alpha1` | `plan/v1alpha1/schema.json` |
| Target-free deployment plan | `v1alpha2` | `plan/v1alpha2/schema.json` |
| Normalized execution event | `v1alpha1` | `event/v1alpha1/schema.json` |
| Execution result | `v1alpha1` | `result/v1alpha1/schema.json` |
| Execution node selection | `v1alpha1` | `execution/v1alpha1/schema.json` |

Execution selection is project/execution state, not service topology. Candidate
eligibility is evaluated before preparation; `EXECUTION_READY` is reported only
after Python, Ansible, workspace, offline payload and execution identity are
prepared. Target bootstrap is a separate phase and may skip a self-target when
the selected Execution Node uses explicit `ansible_connection: local`.

All schemas use JSON Schema 2020-12 and validate YAML after YAML-to-JSON data
model conversion.

Application configuration is local Installer product behavior, not portable
infrastructure desired state. The project persists only the selected stable
server type ID under `platform_host.type`; its schema validates ID grammar and
does not copy or enumerate the local configured list.

The structural Save contract reports only typed local changes and guarded
filesystem persistence; it contains no Core validation claim. Project
verification is derived runtime evidence for one exact saved revision and is
not portable desired state or execution authorization.

## Versioning

- `apiVersion` selects a contract version; readers reject unsupported versions.
- Alpha versions may change incompatibly, but never silently during `apply`.
- A migration is an explicit, deterministic operation that retains an original
  backup and reports its source and destination versions.
- A stable contract adds compatible optional fields within a major version and
  uses a new major version for incompatible semantic changes.
- Plans and results record the exact project, catalog, artifact and Core
  fingerprints used to create them.

## Extension preservation

Objects intended as extension boundaries accept properties named `x-*`.
Readers and writers must preserve their parsed YAML values semantically even
when the extension is unknown. Field ordering, comments, anchors, scalar style
and byte-identical formatting are not contractual. Unknown properties without
the `x-` prefix are rejected so that misspellings do not silently become
desired state.

## Project directory boundary

The portable contract is intentionally split across ordinary Ansible project
files:

```text
project/
  project.yml
  inventory/
    hosts.yml
    group_vars/all/platform.yml
    group_vars/<group>.yml
    host_vars/<host>.yml
  ansible.cfg
```

Inventory, `group_vars` and `host_vars` remain ordinary Ansible inputs. Host
keys referenced by explicit member placements must exist in the supplied
inventory; that cross-file invariant is checked by Core validation rather than
JSON Schema.

`project.yml` is the only owner of project identity and contract/lock versions.
The value of `platform_project` in `inventory/group_vars/all/platform.yml` contains only
desired topology and policy; it does not repeat project identity or
`apiVersion`. Each `inventory/host_vars/<host>.yml` may expose desired host data under
`platform_host`. The assembled-project schema describes the normalized input
to validation and fingerprinting; it is derived and is not a fourth persisted
project representation. `project/v2alpha1/schema.json` is a convenience alias
for that assembled schema.

## Catalog ownership

Service package manifests are the only authored source of service modes,
roles, placement constraints, listeners and configuration schemas. A CORE-01
service catalog is a derived, fingerprinted artifact whose definitions embed
complete conforming manifests. Projects pin catalog and per-service manifest
digests; projects do not copy catalog definitions into group vars. A referenced
manifest representation is deferred until Core has a defined, tested resolver
for it.

## Runtime schema enforcement status

The schemas are the published contract, but CORE-01 has not yet selected or
bundled a Draft 2020-12 runtime validation dependency. The current dependency-
free manual validator enforces only its documented CORE-01 semantic subset; it
must not be described as full JSON Schema enforcement. The current contract
check is limited to dependency-free JSON syntax and local-reference existence
checks. Semantic tests cover only the explicitly implemented subset until an
offline-safe runtime dependency is approved and bundled.

## Secret boundary

Published desired-state schemas contain only secret requirements and provider
references. Secret values belong to the runtime provider and must never be
written into project files, plans, events or results. JSON Schema establishes
the data shape; Core also performs semantic redaction and forbidden-value
checks.

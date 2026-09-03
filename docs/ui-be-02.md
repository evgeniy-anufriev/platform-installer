# UI-BE-02 — Read-only ProjectSnapshot

Status: **DONE**. This milestone implements the first real Installer read path.
It adds no writer, Wails/React application, SQLite desired-state copy, runtime
observation, apply, or verify behavior.

## Query boundary

`platform.core.project_snapshot` is the transport-neutral query facade. The
controller-only action reads the inventory already loaded by Ansible and
therefore uses Ansible's real inventory, `group_vars`, and `host_vars`
precedence. `ansible-core/playbooks/project-snapshot.yml` is the standalone
adapter entrypoint. It runs only on `localhost`, returns `changed: false`, and
does not write an artifact.

The external contract is
`platform.installer/project-snapshot/v1alpha1`, published at
`contracts/project-snapshot/v1alpha1/schema.json`. Its sections contain:

- project identity, revisions, and project-relative document metadata;
- canonical hosts, inventory participation, deployments, and endpoint groups;
- one normalized catalog entry per production service type;
- Core-resolved topology, effective configuration, endpoints, DNS zones,
  address providers, HAProxy backends, and integration relations;
- deduplicated PKI certificate identities and their consumers;
- structured validation findings and static readiness.

The snapshot is derived output and is never accepted as a write payload.

## Revisions and ownership

`projectRevision` is SHA-256 over the sorted normalized relative path and the
SHA-256 digest of each canonical document's exact bytes. The implementation
does not parse and reserialize bytes before hashing. Current revision inputs
are optional `project.yml`, optional `ansible.cfg`, `inventory/hosts.yml`, and
YAML/JSON files below `inventory/group_vars` and `inventory/host_vars`.

`inventory/group_vars/all/platform-state.yml` is reported as
`GENERATED_READ_ONLY` but excluded from `projectRevision`. `.runtime`, logs,
temporary files, service data, catalogs, and role defaults are also excluded.
Catalog semantics are tracked separately by `catalogRevision`; the Core
collection version is exposed as `coreVersion`.

Documents are `USER_OWNED_READ_ONLY` unless the caller explicitly identifies a
supported Installer-owned path for this read session. That classification is
read-model metadata only and changes no filesystem ownership.

## Provenance

Effective configuration reuses `ResolvedServiceConfiguration/v1alpha1`.
Semantic sources remain Core sources such as `ROLE_DEFAULT`,
`DEPLOYMENT_OVERRIDE`, and `MEMBER_OVERRIDE`. The snapshot adds a physical
origin only where this milestone can prove one:

- role defaults point to the package role defaults and offer a future
  `overrideTarget` in the Installer-owned project variables document;
- explicit deployment values point to the selected project variables document;
- inventory participation points to `inventory/hosts.yml`;
- unresolved origins use `UNKNOWN` and `READ_ONLY_UNRESOLVED`.

No helper merges variables or simulates Ansible precedence. An explicit value
is marked `FUTURE_EDITABLE` only when its actual document is classified as
Installer-owned. UI-BE-02 does not perform the future edit.

## Partial and fatal results

Schema, topology, configuration, endpoint, DNS, HAProxy, or PKI findings yield
`status: PARTIAL`, `partial: true`, and retain readable canonical sections.
Unavailable projections are represented explicitly and the findings explain
the block. Runtime health remains `NOT_CHECKED`; static success is
`REQUIRES_PREPARATION`, not a claim that a service is currently healthy.

A missing project root/inventory, unreadable input, unsupported inventory
selection, invalid project document, or symlinked canonical document is a
fatal open error with `PROJECT_SNAPSHOT_INPUT_INVALID`. The action returns a
safe structured finding rather than exposing parser content as its primary
API.

## Security and runtime boundary

Only the canonical connection address and `platform_deployments` subset cross
the host boundary; arbitrary `hostvars`, environment variables, facts, and
credentials do not. A final recursive guard redacts secret-like values while
allowing safe `SecretRef`/`CredentialRef` identifiers. PKI materialization
plans, private keys, store passwords, PGPASS content, generated configs, logs,
and raw inventory dumps are absent.

The query never discovers hosts, contacts services, resolves current VRRP
ownership, reads current PostgreSQL roles, or materializes PKI. Those are lazy
runtime observations deferred to UI-BE-04.

## Acceptance evidence

The representative `examples/valid/ui-project-snapshot` project has three
unreachable-by-design inventory hosts and exercises Kafka, PostgreSQL HA,
Keepalived, BIND, dns-client, HAProxy, endpoint publication, provider
relations, and shared host-scoped PKI identities.

On RED OS:

- 168 Core unit tests passed;
- catalog and configuration-schema reproducibility checks passed;
- two repeated queries were logically identical and all snapshot assertions
  passed with `changed=0` and only `localhost` in the play recap;
- the same acceptance play passed under `sudo -n unshare -n`;
- one standalone query, including Ansible startup and serialization, took
  0.87 seconds and produced a 70,853-byte JSON snapshot.

No service runtime acceptance is required by this milestone.

## UI-BE-03 handoff

UI-BE-03 may consume `projectRevision`, per-document digests and ownership,
effective-value logical paths, `editPolicy`, and `overrideTarget` to implement
`EditCommand -> EditPlan -> review -> guarded write`. It must recheck aggregate
and per-document revisions and preserve the Ansible-native writer boundary.
No part of that writer is implemented here.

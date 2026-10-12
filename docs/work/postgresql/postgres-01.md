# POSTGRES-01 — PostgreSQL standalone and pg_auto_failover

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

## Status

See [historical checkpoint](evidence/documentation-checkpoints-20261012.md#postgres-01-checkpoint-001). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).

## Contract

The service package is Ansible-native. Desired service configuration is owned
by ordinary group/member variables; generated state may contain only stable
machine identities and reconcile metadata. The initial modes are:

- `standalone`: exactly one `database` member;
- `pg_auto_failover`: exactly one `monitor` and exactly two `database` members
  on distinct hosts.

Every deployment requires a configurable `adminSuperuser` with a username and
runtime `passwordSecretRef`. Only the SecretRef is authored or persisted. The
password is resolved immediately at runtime, never placed in argv, generated
state, events or evidence.

## Ownership

| Area | Platform role | PostgreSQL | pg_auto_failover |
| --- | --- | --- | --- |
| Packages, paths, config and HBA | owns desired projection | consumes files | observes managed node |
| initdb and system lifecycle | performs state-aware orchestration | owns data files | supervises HA node when enabled |
| Monitor formation and node registration | invokes declared CLI | hosts extension | owns formation/state transitions |
| TLS material | consumes PKI-01 PEM projection | owns SSL runtime use | receives verified connection policy |
| Failover/rejoin | verifies outcome | exposes runtime state | owns promotion and rejoin decisions |

The role must not repeatedly rewrite files or settings owned by pg_autoctl.
Expected configuration is kept separate from observed configuration during
verify. Verify never initializes data, changes roles/passwords, registers
nodes, changes HBA, restarts services or writes generated state.

## TLS and security

PostgreSQL consumes PKI-01 PEM material directly. It does not create a second
PKI lifecycle and does not convert the material to JKS/PKCS12. HA internal
connections use `hostssl` HBA rules only; plaintext fallback is not permitted.
The selected pg_auto_failover 2.2 CLI supports `--ssl-mode verify-full`,
`--ssl-ca-file`, `--server-key` and `--server-cert`. Acceptance must prove
actual TLS through PostgreSQL runtime views, not only configuration text.

## Lifecycle and state

Managed paths are deployment/member scoped. Data state is classified as
uninitialized, initialized or partial/unknown using `PG_VERSION` and
`pg_controldata`; partial or conflicting initialized state blocks apply.
PostgreSQL `system_identifier` is the stable storage identity for reconcile.
The monitor formation/node identity is retained only when needed to prevent
unsafe re-registration.

The file created by `initdb` at `data/postgresql.conf` is never replaced.
Platform renders `postgresql-platform.conf` as a separate, Jinja-generated
fragment and adds one idempotent `include` line to the initdb-owned file.
Managed settings are emitted from dynamic dictionaries, including
`advancedConfig`; the systemd unit starts PostgreSQL with its normal data
directory and therefore keeps the PostgreSQL default configuration chain
intact.

## Deferred

Patroni, multi-monitor HA, more than two data members, backup/PITR, upgrades,
certificate rotation, imported external CA, generic database provisioning and
production UI remain outside POSTGRES-01.
